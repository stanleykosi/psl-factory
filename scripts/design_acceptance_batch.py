"""Audit the design ledger and run workflow suites on Railway test databases."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
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
        'factory_rfp_console_flow', 'factory_rfp_outcome_console', 'factory_rfp_pricing',
    ),
    'project_delivery': (
        'factory_change', 'factory_change_branches', 'standard_changes', 'factory_emergency',
        'factory_escalation', 'factory_go_live', 'factory_hypercare', 'factory_archive',
        'factory_closure_recovery', 'client_uat', 'project_archive_files',
    ),
    'finance_reporting': (
        'factory_leadership', 'factory_accounting', 'factory_accounting_provenance', 'factory_accounting_intake',
        'factory_ppe', 'factory_schedules', 'factory_forecast', 'factory_group_forecast',
        'factory_invoice_recovery_priority', 'factory_payroll_restart',
    ),
    'shared': (
        'factory_console', 'factory_human_independence', 'factory_review_authority',
        'factory_progress', 'design_delegation', 'staff_accounts', 'staff_profiles',
        'staff_reactivation', 'ui_layout', 'design_batch_walkthrough',
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
    parser.add_argument('--parallel-groups', type=int, choices=(2, 3, 4),
                        help='Run acceptance groups on separate PostgreSQL test databases on Railway.')
    args = parser.parse_args()
    if args.audit:
        audit()
        return 0
    suites = list(dict.fromkeys(args.suite or SUITES))
    labels = list(dict.fromkeys(f'tests.test_{name}' for suite in suites for name in SUITES[suite]))
    missing = [label for label in labels if not (ROOT / (label.replace('.', '/') + '.py')).is_file()]
    if missing:
        parser.error(f'Missing suites: {", ".join(missing)}')
    if args.list:
        print('\n'.join(labels))
        return 0
    if args.parallel_groups:
        if args.settings:
            parser.error('Parallel groups use their own guarded Railway test settings.')
        if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
            parser.error('Parallel groups require the Railway design-acceptance environment.')
        with ThreadPoolExecutor(max_workers=args.parallel_groups) as pool:
            results = list(pool.map(run_group, suites))
        print('PSL_GROUPED_TEST_RESULTS=' + json.dumps(dict(zip(suites, results))), flush=True)
        return int(any(results))
    return run_tests(labels, settings=args.settings)


def run_tests(labels, *, settings=None, env=None):
    command = [sys.executable, 'manage.py', 'test', *labels, '--keepdb', '--noinput', '--verbosity', '2']
    if settings:
        command.extend(['--settings', settings])
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def run_group(name):
    env = {**os.environ, 'PSL_DESIGN_TEST_GROUP': name}
    print(f'PSL_GROUP_STARTED={name}', flush=True)
    status = run_tests([f'tests.test_{module}' for module in SUITES[name]],
                       settings='config.design_batch_settings', env=env)
    print(f'PSL_GROUP_EXIT={name}:{status}', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
