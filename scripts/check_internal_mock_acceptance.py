"""Validate evidence-backed internal mock acceptance; no Django or database needed."""
import argparse
import hashlib
import json
from pathlib import Path
import re

STATUSES = {'NOT_EVALUATED', 'BLOCKED', 'FAIL', 'PASS'}
DEFERRALS = {'owner_policy', 'provider_setup', 'external_connection', 'independent_uat',
             'production_authorization'}


class AcceptanceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


class Evidence:
    def __init__(self, root, packet):
        self.root = Path(root).resolve()
        self.packet = packet
        self.runtime = packet.get('runtime_files', [])
        require(isinstance(self.runtime, list) and self.runtime and
                len(set(self.runtime)) == len(self.runtime), 'Declare unique runtime_files')
        require(bool(packet.get('runtime_scope_review')), 'Missing runtime scope review')
        for name in self.runtime:
            require(name.startswith(('apps/', 'adapters/', 'config/', 'templates/', 'contracts/', 'static/'))
                    or name in ('requirements.lock', 'requirements.in'), 'Not a runtime file: ' + name)
            self.path(name)

    def path(self, name):
        require(isinstance(name, str) and bool(name), 'Missing evidence path')
        path = (self.root / name).resolve()
        require(not Path(name).is_absolute() and path.is_relative_to(self.root), 'Unsafe evidence path')
        require(path.is_file() and path.stat().st_size > 0, 'Missing or empty evidence: ' + name)
        return path

    def read(self, name):
        try:
            value = json.loads(self.path(name).read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc:
            raise AcceptanceError('Unreadable evidence: ' + str(name)) from exc
        require(isinstance(value, dict), 'Evidence must be an object')
        return value

    def source(self, manifest):
        files = self.read(manifest).get('files', {})
        changes = {}
        for name in self.runtime:
            before = files.get(name)
            require(isinstance(before, str) and re.fullmatch('[0-9a-f]{64}', before),
                    'Runtime file absent from source manifest: ' + name)
            after = hashlib.sha256(self.path(name).read_bytes()).hexdigest()
            if before != after:
                changes[name] = {'before': before, 'after': after}
        if changes:
            refs = self.packet.get('composition_reviews', [])
            reviews = [self.read(ref) for ref in refs]
            require(any(r.get('status') == 'PASS' and r.get('source_manifest') == manifest
                        and r.get('changes') == changes and r.get('reviewer')
                        and r.get('rationale') and r.get('unchanged_runtime_behavior') is True
                        for r in reviews), 'Changed runtime requires exact reviewed composition: ' + manifest)

    def run(self, item):
        record = self.read(item['record'])
        require(record.get('status') == 'finished' and type(record.get('returncode')) is int
                and record['returncode'] == 0, 'Run is not finished successfully')
        require('postgresql' in record.get('database', '').lower(), 'Native run must use PostgreSQL')
        require(record.get('command') and record.get('started_at'), 'Run lacks command/time')
        expected_manifest = record.get('source_manifest', item['record'].removesuffix('.json') + '-source.json')
        require(item['source_manifest'] == expected_manifest, 'Run source manifest is not bound to record')
        self.source(item['source_manifest'])
        log = self.path(record.get('log')).read_text(encoding='utf-8')
        require(re.search(r'^OK\s*$', log, re.M), 'Run log has no clean OK result')
        tests = item.get('tests', [])
        require(isinstance(tests, list) and tests, 'Run has no mapped passing tests')
        passed = set(re.findall(r'^test_\S+ \(([^)]+)\) \.\.\. ok\s*$', log, re.M))
        require(set(tests) <= passed, 'Mapped test did not pass in run log')
        return set(tests)

    def proof(self, name, kind):
        proof = self.read(name)
        require(proof.get('status') == 'PASS' and proof.get('kind') == kind,
                'Missing passing ' + kind + ' proof')
        self.source(proof.get('source_manifest'))
        require(proof.get('command') and proof.get('observed_at'), 'Proof lacks command/time')
        self.path(proof.get('log'))
        return proof


def validate_packet(root, row):
    packet = row['factory_consolidation']['mock_acceptance']
    require(packet.get('scope') == 'whole_process_internal_mock', 'PASS requires whole-process internal scope')
    require(packet.get('remaining_internal_engineering') == [], 'Internal engineering gaps remain')
    deferrals = packet.get('deferrals')
    require(isinstance(deferrals, list), 'Declare typed deferrals separately')
    for item in deferrals:
        require(isinstance(item, dict) and item.get('kind') in DEFERRALS and item.get('description'),
                'Invalid deferred dependency')
    evidence = Evidence(root, packet)
    runs = packet.get('runs', [])
    require(isinstance(runs, list) and runs, 'Missing runs')
    require({'native', 'connected', 'recovery'} <= {r.get('kind') for r in runs},
            'Require native, connected and recovery runs')
    passed = set()
    for run in runs:
        passed.update(evidence.run(run))
    assertions = packet.get('assertions', {})
    expected = row['factory_consolidation']['source_assertion_ids']
    require(bool(expected) and set(assertions) == set(expected), 'Source assertion mapping is incomplete')
    for assertion in assertions.values():
        require(assertion.get('status') == 'PASS' and assertion.get('tests')
                and set(assertion['tests']) <= passed, 'Source assertion lacks passing mapped tests')
    browser = evidence.proof(packet.get('browser'), 'browser')
    require(browser.get('browser') and browser.get('environment') and browser.get('role')
            and browser.get('fixture') and browser.get('viewport'), 'Browser context incomplete')
    journeys = browser.get('journeys', {})
    require({'queue_to_case', 'agent_work', 'evidence_review', 'exact_version_approval',
             'exception_recovery', 'verified_outcome', 'keyboard', 'narrow_screen'} <= set(journeys),
            'Browser journeys incomplete')
    for journey in journeys.values():
        require(journey.get('status') == 'PASS' and journey.get('observation')
                and journey.get('screenshots'), 'Browser journey lacks observed proof')
        for screenshot in journey['screenshots']:
            evidence.path(screenshot)
    for kind in ('fresh_schema', 'preservation'):
        proof = evidence.proof(packet.get(kind), kind)
        require(proof.get('checks') and all(v == 'PASS' for v in proof['checks'].values()),
                'Schema/preservation checks incomplete')


def validate(root, coverage=None, source=None):
    root = Path(root)
    if coverage is None:
        coverage = json.loads((root / 'contracts/implementation-coverage.json').read_text())
    if source is None:
        source = json.loads((root / 'contracts/process-map.json').read_text())
    original = source['rows']
    require(len(original) == 122 and len({r['id'] for r in original}) == 122, 'Source IDs must be unique')
    release = {r['id'] for r in original if r['department'] in ('PMO', 'Finance')}
    deferred = {r['id'] for r in original if r['department'] == 'BaaS'}
    require(len(release) == 108 and len(deferred) == 14, 'Release scope must remain 108/14')
    rows = coverage['rows']
    require(len(rows) == 122 and {r['id'] for r in rows} == release | deferred, 'Coverage IDs differ from source')
    summary = coverage['factory_consolidation']
    require(set(summary['release_ids']) == release and len(summary['release_ids']) == 108
            and set(summary['deferred_baas_ids']) == deferred and len(summary['deferred_baas_ids']) == 14,
            'Declared release/deferred IDs differ')
    source_by_id = {r['id']: r for r in original}
    accepted = []
    for row in rows:
        state = row['factory_consolidation']
        require(state['source_assertion_ids'] == source_by_id[row['id']]['source_test_ids'],
                'Source assertion IDs differ from canonical process map')
        require(state['release_scope'] == ('first_release' if row['id'] in release else 'deferred_baas'),
                'Incorrect release scope')
        require(state['mock_acceptance']['status'] in STATUSES and
                state['connected_process_acceptance'] in STATUSES, 'Invalid acceptance status')
        if (state['mock_acceptance']['status'] == 'PASS' and
                state['mock_acceptance'].get('scope') == 'whole_process_internal_mock'):
            require(row['id'] in release, 'Deferred process cannot count as release acceptance')
            validate_packet(root, row)
            accepted.append(row['id'])
        if state['connected_process_acceptance'] == 'PASS':
            require(row['id'] in accepted and
                    state.get('connected_acceptance_scope') == 'whole_process_internal_mock',
                    'Connected PASS requires explicit scope and validated connected evidence')
    result = {'accepted_ids': sorted(accepted), 'accepted_count': len(accepted),
              'release_count': len(release), 'deferred_count': len(deferred),
              'full108_internal_handoff_gate': 'MET' if set(accepted) == release else 'NOT_MET'}
    declared = summary.get('internal_mock_acceptance')
    require(declared == result if declared is not None else not accepted,
            'Missing or inflated internal mock summary')
    if 'full108_internal_handoff_gate' in summary:
        require(summary['full108_internal_handoff_gate'] == result['full108_internal_handoff_gate'],
                'Full108 gate does not match validated acceptance')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root), indent=2))
    except (AcceptanceError, KeyError, TypeError, OSError, ValueError) as exc:
        parser.exit(1, 'Internal mock acceptance invalid: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
