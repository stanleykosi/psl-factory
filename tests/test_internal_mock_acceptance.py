"""Acceptance metadata is not evidence unless its referenced proof validates."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.test import SimpleTestCase
from scripts.check_internal_mock_acceptance import AcceptanceError, validate


class InternalMockAcceptanceTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.coverage = json.loads((settings.BASE_DIR / 'contracts/implementation-coverage.json').read_text())
        self.source = json.loads((settings.BASE_DIR / 'contracts/process-map.json').read_text())
        self.row = next(r for r in self.coverage['rows'] if r['id'] == 'P45')
        self.runtime = 'apps/example.py'
        self.write(self.runtime, 'original runtime')
        self.files = {self.runtime: hashlib.sha256(b'original runtime').hexdigest()}
        self.save('run-source.json', {'files': self.files})
        self.test_id = 'tests.test_example.ExampleTests.test_connected'
        self.write('run.txt', f'test_connected ({self.test_id}) ... ok\n\nRan 1 test in 1s\n\nOK\n')
        self.save('run.json', {'status': 'finished', 'returncode': 0, 'database': 'PostgreSQL test',
                              'command': ['python', 'manage.py', 'test'], 'started_at': '2026-11-06', 'log': 'run.txt'})
        self.write('proof.txt', 'Observed synthetic evidence for validator unit tests only')
        self.write('screen.png', b'\x89PNG\r\n\x1a\nsynthetic validator fixture')
        for kind in ('browser', 'fresh_schema', 'preservation'):
            record = {'status': 'PASS', 'kind': kind, 'source_manifest': 'run-source.json',
                      'command': ['synthetic'], 'observed_at': '2026-11-06', 'log': 'proof.txt',
                      'checks': {'expected': 'PASS'}}
            if kind == 'browser':
                record.update(browser='Chromium', environment='cloud', role='synthetic PM',
                              fixture='synthetic only', viewport=[1280, 720],
                              journeys={name: {'status': 'PASS', 'observation': 'Synthetic unit fixture',
                                               'screenshots': ['screen.png']} for name in
                                        ('queue_to_case', 'agent_work', 'evidence_review', 'exact_version_approval',
                                         'exception_recovery', 'verified_outcome', 'keyboard', 'narrow_screen')})
            self.save(kind + '.json', record)
        self.packet = {'status': 'PASS', 'scope': 'whole_process_internal_mock',
                       'runtime_files': [self.runtime], 'runtime_scope_review': 'Synthetic unit fixture',
                       'remaining_internal_engineering': [], 'deferrals': [],
                       'runs': [{'kind': kind, 'record': 'run.json', 'source_manifest': 'run-source.json',
                                 'tests': [self.test_id]} for kind in ('native', 'connected', 'recovery')],
                       'assertions': {name: {'status': 'PASS', 'tests': [self.test_id]}
                                      for name in self.row['factory_consolidation']['source_assertion_ids']},
                       **{kind: kind + '.json' for kind in ('browser', 'fresh_schema', 'preservation')}}
        self.row['factory_consolidation']['mock_acceptance'] = self.packet
        self.coverage['factory_consolidation']['internal_mock_acceptance'] = {
            'accepted_ids': ['P45'], 'accepted_count': 1, 'release_count': 108,
            'deferred_count': 14, 'full108_internal_handoff_gate': 'NOT_MET'}

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())

    def save(self, name, value):
        self.write(name, json.dumps(value))

    def check(self):
        return validate(self.root, self.coverage, self.source)

    def reject(self):
        with self.assertRaises((AcceptanceError, KeyError, TypeError, ValueError)):
            self.check()

    def test_current_unaccepted_dataset_still_validates(self):
        result = validate(settings.BASE_DIR)
        self.assertEqual(result['release_count'], 108)
        self.assertEqual(result['deferred_count'], 14)

    def test_complete_synthetic_packet_derives_count_without_promoting_connected_or_production(self):
        self.assertEqual(self.check()['accepted_ids'], ['P45'])
        self.assertEqual(self.row['factory_consolidation']['connected_process_acceptance'], 'NOT_EVALUATED')
        self.assertFalse(self.coverage['factory_consolidation']['full_product_complete'])

    def test_missing_assertion_rejected(self):
        self.packet['assertions'].pop(next(iter(self.packet['assertions'])))
        self.reject()

    def test_missing_evidence_rejected(self):
        (self.root / 'screen.png').unlink()
        self.reject()

    def test_failed_or_incomplete_run_rejected(self):
        original = json.loads((self.root / 'run.json').read_text())
        for update in ({'status': 'running'}, {'returncode': 1}, {'returncode': False}):
            with self.subTest(update=update):
                self.save('run.json', dict(original, **update))
                self.reject()

    def test_selected_but_not_passing_test_rejected(self):
        self.packet['runs'][0]['tests'] = ['tests.test_example.ExampleTests.test_not_run']
        self.reject()

    def test_skipped_test_cannot_count(self):
        self.write('run.txt', f'test_connected ({self.test_id}) ... skipped "unavailable"\nOK\n')
        self.reject()

    def test_sqlite_run_rejected(self):
        record = json.loads((self.root / 'run.json').read_text())
        record['database'] = 'sqlite'
        self.save('run.json', record)
        self.reject()

    def test_changed_runtime_requires_exact_composition(self):
        self.write(self.runtime, 'changed runtime')
        self.reject()
        review = {'status': 'PASS', 'source_manifest': 'run-source.json', 'reviewer': 'Synthetic reviewer',
                  'rationale': 'Synthetic unchanged behavior review', 'unchanged_runtime_behavior': True,
                  'changes': {self.runtime: {'before': self.files[self.runtime],
                                             'after': hashlib.sha256(b'changed runtime').hexdigest()}}}
        self.save('composition.json', review)
        self.packet['composition_reviews'] = ['composition.json']
        self.assertEqual(self.check()['accepted_count'], 1)
        self.write(self.runtime, 'another change')
        self.reject()

    def test_unrelated_runtime_change_does_not_invalidate_scoped_acceptance(self):
        self.write('apps/unrelated.py', 'new unrelated component')
        self.assertEqual(self.check()['accepted_count'], 1)

    def test_manifest_must_contain_runtime_and_be_bound_to_run(self):
        self.save('run-source.json', {'files': {}})
        self.reject()
        self.save('run-source.json', {'files': self.files})
        self.save('unbound.json', {'files': self.files})
        self.packet['runs'][0]['source_manifest'] = 'unbound.json'
        self.reject()

    def test_browser_keyboard_narrow_or_observation_missing_rejected(self):
        original = json.loads((self.root / 'browser.json').read_text())
        for name in ('keyboard', 'narrow_screen', 'verified_outcome'):
            with self.subTest(name=name):
                changed = deepcopy(original)
                del changed['journeys'][name]
                self.save('browser.json', changed)
                self.reject()

    def test_schema_and_preservation_failure_rejected(self):
        for kind in ('fresh_schema', 'preservation'):
            original = json.loads((self.root / (kind + '.json')).read_text())
            changed = deepcopy(original)
            changed['checks']['expected'] = 'FAIL'
            self.save(kind + '.json', changed)
            self.reject()
            self.save(kind + '.json', original)

    def test_internal_gap_cannot_be_deferred_as_owner_setup(self):
        self.packet['remaining_internal_engineering'] = ['Missing native disposition']
        self.reject()
        self.packet['remaining_internal_engineering'] = []
        self.packet['deferrals'] = [{'kind': 'implementation', 'description': 'Unbuilt feature'}]
        self.reject()

    def test_deferred_baas_and_duplicate_ids_rejected(self):
        self.row['id'] = next(r['id'] for r in self.source['rows'] if r['department'] == 'BaaS')
        self.reject()

    def test_inflated_summary_and_gate_rejected(self):
        summary = self.coverage['factory_consolidation']['internal_mock_acceptance']
        summary['accepted_count'] = 5
        self.reject()
        summary['accepted_count'] = 1
        summary['full108_internal_handoff_gate'] = 'MET'
        self.reject()

    def test_connected_pass_requires_explicit_evidence_scope(self):
        self.row['factory_consolidation']['connected_process_acceptance'] = 'PASS'
        self.reject()
        self.row['factory_consolidation']['connected_acceptance_scope'] = 'whole_process_internal_mock'
        self.assertEqual(self.check()['accepted_count'], 1)

    def test_paths_cannot_escape_repository(self):
        self.packet['browser'] = '../outside.json'
        self.reject()

    def test_all_release_ids_are_needed_for_met_gate(self):
        release = set(self.coverage['factory_consolidation']['release_ids'])
        for row in self.coverage['rows']:
            if row['id'] in release:
                packet = deepcopy(self.packet)
                packet['assertions'] = {name: {'status': 'PASS', 'tests': [self.test_id]}
                                        for name in row['factory_consolidation']['source_assertion_ids']}
                row['factory_consolidation']['mock_acceptance'] = packet
        self.coverage['factory_consolidation']['internal_mock_acceptance'] = {
            'accepted_ids': sorted(release), 'accepted_count': 108, 'release_count': 108,
            'deferred_count': 14, 'full108_internal_handoff_gate': 'MET'}
        self.assertEqual(self.check()['full108_internal_handoff_gate'], 'MET')

    def test_deferred_baas_cannot_be_promoted_even_with_packet(self):
        row = next(r for r in self.coverage['rows'] if r['id'].startswith('B'))
        row['factory_consolidation']['mock_acceptance'] = deepcopy(self.packet)
        self.reject()

    def test_legacy_bounded_pass_does_not_count(self):
        self.row['factory_consolidation']['mock_acceptance']['scope'] = 'Bounded source branches only'
        del self.coverage['factory_consolidation']['internal_mock_acceptance']
        self.assertEqual(self.check()['accepted_count'], 0)

    def test_cannot_drop_canonical_source_assertion(self):
        self.row['factory_consolidation']['source_assertion_ids'].pop()
        self.reject()

    def test_empty_package_marker_is_valid_when_present_and_hash_matches(self):
        marker = 'apps/example/__init__.py'
        self.write(marker, b'')
        self.packet['runtime_files'].append(marker)
        self.files[marker] = hashlib.sha256(b'').hexdigest()
        self.save('run-source.json', {'files': self.files})
        self.assertEqual(self.check()['accepted_count'], 1)
        self.write(marker, 'changed package initializer')
        self.reject()

    def test_missing_runtime_file_is_rejected(self):
        (self.root / self.runtime).unlink()
        self.reject()

    def test_empty_evidence_artifact_still_rejected(self):
        self.write('screen.png', b'')
        self.reject()
