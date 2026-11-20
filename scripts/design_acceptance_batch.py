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
        'factory_rfp_console_flow', 'factory_rfp_outcome_console', 'factory_rfp_pricing', 'rfp_estimate_requests',
    ),
    'project_delivery': (
        'factory_change', 'factory_change_branches', 'standard_changes', 'factory_emergency',
        'factory_escalation', 'factory_go_live', 'factory_hypercare', 'factory_archive',
        'factory_closure_recovery', 'client_uat', 'client_testing_pack', 'project_archive_files', 'factory_minutes', 'factory_minutes_console',
    ),
    'finance_reporting': (
        'factory_leadership', 'factory_accounting', 'factory_accounting_provenance', 'factory_accounting_intake',
        'factory_ppe', 'factory_schedules', 'factory_forecast', 'factory_group_forecast',
        'factory_invoice_recovery_priority', 'factory_payroll_restart', 'factory_bu', 'invoice_short_payments',
    ),
    'shared': (
        'factory_console', 'factory_human_independence', 'factory_review_authority',
        'factory_progress', 'design_delegation', 'staff_accounts', 'staff_profiles',
        'staff_reactivation', 'ui_layout', 'design_batch_walkthrough', 'work_access_requests', 'product_intake',
        'department_assistant', 'design_consolidation',
    ),
}
LEDGER_ROW = re.compile(r'^\| `(SCR-[^\x60]+)` \| [^\n]+ \| (.+) \|$', re.MULTILINE)
PARALLEL_ORDER = ('project_delivery', 'finance_reporting', 'commercial', 'shared')
CANDIDATE_GATE = (
    'factory_rfp_outcome_console.FactoryRFPOutcomeConsoleTests.test_outcome_form_explicitly_targets_each_actual_submission_without_a_method',
    'factory_rfp_pricing',
    'standard_changes.StandardChangeTests.test_new_preapproval_or_pm_match_invalidates_authorization_snapshot',
    'standard_changes.StandardChangeTests.test_revoked_preapprover_grant_holds_queued_publication',
    'factory_invoice_recovery_priority.InvoiceRecoveryRealClockTests.test_process_exit_after_acceptance_and_actual_native_lease_expiry_recover_original_job',
    'factory_review_authority.FactoryReviewAuthorityTests.test_pending_original_reservation_precedes_review_update_and_get_does_not_dispatch',
    'factory_review_authority.FactoryReviewAuthorityTests.test_restored_approval_does_not_override_current_original_pending_job',
    'project_archive_files.ArchiveFileTests.test_interrupted_copy_recovers_original_receipt_without_another_copy',
    'factory_hypercare.FactoryHypercareTests.test_release_stability_progress_follows_an_actual_claim_and_stops_at_observed_result',
    'factory_escalation.FactoryEscalationTests.test_decline_requires_its_own_role_and_records_no_communication',
    'factory_emergency.FactoryEmergencyTests.test_current_cto_refusal_holds_preauthorization_and_preserves_actual_outcome_capture',
    'factory_leadership.FactoryLeadershipTests.test_live_drafting_uses_the_current_claim_and_stops_at_review',
    'commercial_rework.CommercialReworkTests.test_rework_browser_fixture_is_additive_and_does_not_create_responses_or_model_jobs',
    'design_batch_walkthrough',
    'factory_accounting.FactoryAccountingTests.test_controlled_trial_balance_reaches_reviewed_report_and_native_recipient_receipt',
    'factory_accounting.AccountingOperatorTests.test_continue_queues_accounting_on_the_worker_and_preserves_native_review',
    'factory_accounting.AccountingRecoveryTests.test_missing_receipt_remains_uncertain_without_a_second_delivery',
    'factory_accounting_intake.AccountingSuppliedIntakeTests.test_http_confirm_units_starts_successor_from_the_same_unchanged_file',
    'factory_accounting_intake.AccountingSuppliedIntakeTests.test_confirming_thousands_records_evidence_but_keeps_calculation_on_hold',
    'factory_schedules.FactorySchedulesTests.test_income_native_chain_and_read_only_metadata',
    'factory_ppe.FactoryPPETests.test_native_chain_exact_reviews_note_and_read_only_console',
    'factory_ppe.FactoryPPETests.test_unused_linked_note_role_assignee_inactivity_invalidates_policy_gate',
    'factory_forecast.ForecastFactoryTests.test_complete_native_review_and_aggregate_receipt_chain',
    'factory_group_forecast.GroupForecastFactoryTests.test_returned_group_disclosure_requires_source_owned_rework_and_fresh_review',
)


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
    parser.add_argument('--candidate-gate', action='store_true', help='Check the staged corrections and browser fixtures before deployment.')
    parser.add_argument('--parallel-groups', type=int, choices=(2, 3, 4),
                        help='Run acceptance groups on separate PostgreSQL test databases on Railway.')
    args = parser.parse_args()
    if args.audit:
        audit()
        return 0
    if args.candidate_gate:
        if args.suite or args.settings or args.parallel_groups:
            parser.error('The candidate gate has a fixed test selection and Railway database settings.')
        labels = [f'tests.test_{name}' for name in CANDIDATE_GATE]
        if args.list:
            print('\n'.join(labels))
            return 0
        if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
            parser.error('The candidate gate requires the Railway design-acceptance environment.')
        env = {**os.environ, 'PSL_DESIGN_TEST_GROUP': 'finance_reporting'}
        return run_tests(labels, settings='config.design_batch_settings', env=env)
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
        scheduled = [name for name in PARALLEL_ORDER if name in suites]
        with ThreadPoolExecutor(max_workers=args.parallel_groups) as pool:
            results = list(pool.map(run_group, scheduled))
        print('PSL_GROUPED_TEST_RESULTS=' + json.dumps(dict(zip(scheduled, results))), flush=True)
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
