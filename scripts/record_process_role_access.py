"""Generate the 108-process role evidence only from completed Railway role suites."""
import argparse
from collections import defaultdict
from pathlib import Path
import re
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.workflows.factory_processes import PROCESS_IDS
from apps.workflows.native_station_contracts import DEFINITION


ROLES = {'pmo_head': 'PMO lead', 'pmo_member': 'PMO member', 'finance_head': 'Finance lead',
         'finance_member': 'Finance member', 'hr': 'HR', 'ceo': 'CEO', 'cto': 'CTO', 'admin': 'Admin'}


def render(runs):
    expected = {pid for values in PROCESS_IDS.values() for pid in values}
    processes = set(PROCESS_IDS[DEFINITION])
    groups = {'original': expected - processes, 'pmo': {pid for pid in processes if pid.startswith('P')},
              'accounts': set('F02 F04 F05 F06 F08 F10 F11 F14 F15 F19 F20 F24 F25 F26 F27'.split())}
    groups['operations'] = processes - groups['pmo'] - groups['accounts']
    groups['surface'] = set()
    sources, evidence = {}, defaultdict(set)
    for group, ids in groups.items():
        for run, contents in reversed(runs):
            text = '\n'.join(line.partition('] ')[2] for line in contents.splitlines() if line.startswith(f'[{group}] '))
            if not re.search(r'^OK\s*$', text, re.M) or re.search(r'^FAILED\b', text, re.M):
                continue
            if group == 'surface':
                personas = set(re.findall(r'ROLE_DIRECTORY (\w+) 108 processes;', text))
                if personas != set(ROLES):
                    continue
            else:
                rows = re.findall(r'ROLE_ACCESS ([PF]\d{2}) ([^\n]+)', text)
                if {pid for pid, _ in rows} != ids or f'Role reads checked for {len(ids)} processes; missing [].' not in text:
                    continue
                receivers = dict(re.findall(r'Native station verified ([PF]\d{2}) -> ([\w.]+)', text))
                if group != 'original' and set(receivers) != ids:
                    continue
                for pid, result in rows:
                    fields = dict(entry.split('=', 1) for entry in result.split() if '=' in entry)
                    states = tuple(fields[k] for k in ROLES)
                    if any(v not in ('read', 'restricted') for v in states):
                        raise ValueError(f'Unrecognised role outcome for {pid}')
                    record = fields['line'] if group == 'original' else receivers[pid]
                    evidence[pid].add((fields.get('level', 'verified-receipt'), record, states))
            sources[group] = run
            break
        else:
            raise ValueError(f'Missing a complete passing Railway suite for {group}')
    if set(evidence) != expected or len(expected) != 108:
        raise ValueError('The release register and role evidence disagree.')
    lines = ['# Role access on Railway', '',
             'Every row comes from an authenticated request to the Django page and its JSON API on an isolated Railway PostgreSQL database. Each account was admitted to a synthetic project. The two department member accounts test the difference between project access and team oversight. The Admin account has no business appointment.', '',
             'Read means both surfaces returned the tested record. A dash means access to that record was restricted on both. A read gives no approval or publication authority. Private records and appointments are checked independently. The evidence column identifies the stage tested. For source-triggered processes it is the completed receiving record. Multiple outcomes for an ID retain separate rows.', '',
             'All eight accounts could discover all 108 processes. Starting work separately required the intake permissions for a project. For P34, for example, the row checks the Finance record receiving the completed PMO milestone. A PMO member can still consult the milestone in PMO. [Release routes](specialist-process-routes.md) · [Approval and provider tests](../../BUILD-TESTS.md)', '',
             '| Suite | Railway checks deployment |', '| --- | --- |']
    lines.extend(f'| {group} | `{run}` |' for group, run in sources.items())
    lines += ['', '| Process | Evidence | Record checked | ' + ' | '.join(ROLES.values()) + ' |', '| --- ' * (len(ROLES)+3) + '|']
    for pid in sorted(expected, key=lambda key: (key.startswith('F'), key)):
        for level, record, states in sorted(evidence[pid]):
            cells = [pid, level.replace('_', ' ').replace('-', ' '), f'`{record}`'] + ['Read' if v == 'read' else '—' for v in states]
            lines.append('| ' + ' | '.join(cells) + ' |')
    restricted = sorted(pid for pid, observations in evidence.items()
                        if all('read' not in states for _, _, states in observations))
    lines.extend(['', '## Reading the restricted rows', '',
                  f'On the sampled records, {len(restricted)} processes required authority beyond the eight unappointed accounts: '
                  + ', '.join(restricted) + '.', '',
                  '- For controlled documents, the source version, audience and distribution evidence have their own access checks. Department approval records check access to each contributing department’s evidence.',
                  '- Work crossing from PMO into Finance can require the original milestone or signature recorder, a Finance reader or a commercial reviewer. The receiving record can have a different audience from its source.',
                  '- Private payroll, business-unit costs and contract coverage check the original source permissions. For an HR disclosure, only the Finance recipient named on the approved snapshot can acknowledge it.',
                  '- The independent decision tests also exercise named PMO and Finance reviewers and the appointed HR handoff recipient. [Decision tests and live specialist receipts](../../BUILD-TESTS.md)'])
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--run', action='append', nargs=2, metavar=('DEPLOYMENT', 'LOG'), required=True)
    args = parser.parse_args()
    runs = [(UUID(run), Path(path).read_text(encoding='utf-8-sig')) for run, path in args.run]
    args.output.write_text(render(runs), encoding='utf-8', newline='\n')
