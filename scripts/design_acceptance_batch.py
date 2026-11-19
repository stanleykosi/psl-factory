"""Audit the design ledger and run selected workflow suites against one test database."""

import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs' / 'design'
SUITES = {
    'commercial': (
        'commercial_client_response', 'commercial_rework', 'commercial_changes',
        'commercial_signatures', 'factory_commercial', 'costing_design',
        'factory_rfp_console_flow', 'factory_rfp_outcome_console',
    ),
    'project_delivery': (
        'factory_change', 'factory_change_branches', 'standard_changes', 'factory_emergency',
        'factory_escalation', 'factory_go_live', 'factory_hypercare', 'factory_archive',
        'factory_closure_recovery', 'client_uat',
    ),
    'finance_reporting': (
        'factory_leadership', 'factory_accounting', 'factory_accounting_provenance',
        'factory_ppe', 'factory_schedules', 'factory_forecast', 'factory_group_forecast',
        'factory_invoice_recovery_priority', 'factory_payroll_restart',
    ),
    'shared': (
        'factory_console', 'factory_human_independence', 'factory_review_authority',
        'factory_progress', 'design_delegation', 'staff_accounts', 'staff_profiles',
        'staff_reactivation', 'ui_layout',
    ),
}
LEDGER_ROW = re.compile(r'^\| `(SCR-[^\x60]+)` \| [^\n]+ \| (.+) \|$', re.MULTILINE)


def audit():
    with (DESIGN / 'screen-state-inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
        inventory = list(csv.DictReader(stream))
    state_ids = [row['state_id'] for row in inventory]
    missing_boards = [
        path for row in inventory for path in row['board_paths'].split('|')
        if not (ROOT / path).is_file()
    ]
    if len(state_ids) != len(set(state_ids)) or missing_boards:
        raise ValueError(f'Inventory has duplicate IDs or missing boards: {missing_boards}')
    rows = LEDGER_ROW.findall((DESIGN / 'screen-state-acceptance.md').read_text(encoding='utf-8'))
    observed = {state for state, _ in rows}
    if len(rows) != len(observed) or observed - set(state_ids):
        raise ValueError('Acceptance ledger has duplicate states or states outside the design inventory.')
    complete = {state for state, status in rows if status.startswith('Complete for ')}
    unseen = set(state_ids) - observed
    backlog = json.loads((ROOT / 'BUILD-BACKLOG.json').read_text(encoding='utf-8'))['design_consolidation_20261116']
    direct = backlog['pending_direct_browser_groups_20261119']
    grouped = [state for states in direct['groups'].values() for state in states]
    if set(grouped) != unseen or len(grouped) != len(unseen) or direct['unseen_count'] != len(unseen):
        raise ValueError('The direct-browser groups do not match the states missing from the ledger.')
    counts = {'observed': len(observed), 'observed_with_open_checks': len(observed - complete),
              'unseen': len(unseen), 'completed_scoped_journeys': len(complete)}
    current = backlog['current_acceptance_20261119']
    if any(current[key] != count for key, count in counts.items()):
        raise ValueError(f'The backlog totals do not match the ledger: {counts}')
    print(json.dumps({'inventory': len(inventory), **counts, 'open_states': sorted(observed - complete),
                      'unseen_states': sorted(unseen)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', action='store_true', help='Check design and browser evidence records without a database.')
    parser.add_argument('--suite', action='append', choices=SUITES, help='Include a workflow suite. Defaults to all.')
    parser.add_argument('--settings', help='Django settings module for the isolated test database.')
    parser.add_argument('--list', action='store_true', help='Print the selected test labels without running them.')
    args = parser.parse_args()
    if args.audit:
        audit()
        return 0
    labels = list(dict.fromkeys(f'tests.test_{name}' for suite in args.suite or SUITES for name in SUITES[suite]))
    missing = [label for label in labels if not (ROOT / (label.replace('.', '/') + '.py')).is_file()]
    if missing:
        parser.error(f'Missing suites: {", ".join(missing)}')
    if args.list:
        print('\n'.join(labels))
        return 0
    command = [sys.executable, 'manage.py', 'test', *labels, '--keepdb', '--noinput', '--verbosity', '2']
    if args.settings:
        command.extend(['--settings', args.settings])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
