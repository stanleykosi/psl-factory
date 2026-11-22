"""Run the three real workflow suites on separate synthetic PostgreSQL databases."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.workflows.native_station_contracts import PROCESSES

SUITES = {
    "pmo": ("tests.test_pmo_coordinator_stations", {p for p in PROCESSES if p.startswith("P")}),
    "accounts": ("tests.test_finance_coordinator_accounts", set("F02 F04 F05 F06 F08 F10 F11 F14 F15 F19 F20 F24 F25 F26 F27".split())),
    "operations": ("tests.test_finance_coordinator_operations", set("F28 F31 F32 F33 F34 F35 F36 F37 F38 F40 F41 F42 F43 F45".split())),
}
LIVE_CASES = {
    "P02": "test_department_routing_from_source_to_receipt",
    "F35": "test_restricted_hr_handoff_to_named_finance_recipient",
}
PLANNING_API_TESTS = (
    'tests.test_planning_department_inputs.PlanningDepartmentInputTests.test_five_departments_reach_native_handoff_and_changed_effort_requires_exact_human_review',
    'tests.test_factory_planning.FactoryPlanningTests.test_exact_department_panel_records_only_native_owner_observation',
)
API_GROUPS = ('directory', 'cutover', 'project-api', 'delivery-api', 'planning-api', 'payroll-api', 'setup-api', 'hr-api',
              'recover-api', 'go-live-api', 'staff-api', 'money-api', 'decide-api', 'report-api', 'cost-api', 'scope-api', 'close-api', 'cash-api', 'change-api', 'bid-api', 'private-api')


def run(group, token, role_access):
    environment = dict(os.environ, DJANGO_SETTINGS_MODULE="config.native_station_acceptance", PSL_STATION_SUITE=group, PSL_STATION_RUN=token, PYTHONUNBUFFERED="1")
    if group == 'original':
        from apps.workflows.factory_processes import PROCESS_IDS
        from apps.workflows.native_station_contracts import DEFINITION
        required = {pid for line, processes in PROCESS_IDS.items() if line != DEFINITION for pid in processes}
        modules = ['tests.test_original_process_role_access']
    elif group == 'directory':
        modules = ['tests.test_process_trigger_navigation', 'tests.test_process_role_directory',
                   'tests.test_native_station_role_access', 'tests.test_factory_api',
                   'tests.test_rfp_fresh_intake.FreshBidIntakeTests.test_api_and_form_share_the_original_file_receipt_and_delegation',
                   'tests.test_role_scoped_work.RoleScopedWorkTests.test_role_accounts_keep_the_full_factory_shell_and_scoped_destinations']
    elif group == 'cutover':
        modules = [
            'tests.test_factory_api', 'tests.test_railway_worker',
            'tests.test_bank_receipt_capture.BankReceiptCaptureTests.test_api_report_verify_allocate_and_private_readback',
            'tests.test_rfp_assignment_queue.RFPAssignmentQueueTests.test_api_assigns_current_bid_to_named_manager_and_prevents_repeat',
            'tests.test_design_consolidation.DesignConsolidationTests.test_api_project_action_assignment_completion_and_history',
            'tests.test_design_consolidation.DesignConsolidationTests.test_template_catalog_reads_controlled_versions_and_revokes_access',
            'tests.test_change_milestone_link.ChangeMilestoneLinkTests.test_api_links_signed_stage_and_retains_native_evidence',
            'tests.test_design_client_documents.ClientAndTemplateDesignTests.test_api_first_template_catalogue_and_download',
            'tests.test_client_directory.ClientDirectoryTests.test_api_directory_contact_proof_and_versioned_readback',
            'tests.test_design_delegation.DesignDelegationTests.test_api_readback_and_idempotent_delegation_draft',
            'tests.test_month_end_overview.MonthEndOverviewTests.test_api_capture_current_as_of_and_read_company_close',
            'tests.test_design_reminders_staff.PaymentReminderTests.test_api_schedules_checked_attachment_and_reads_verified_mailbox_receipt',
            'tests.test_rfp_messages.BidMessageTests.test_api_bid_followup_review_release_and_verified_receipt',
            'tests.test_rfp_pdf_portal.RFPReviewedPDFPortalTests.test_manual_pdf_receipt_binds_exact_approved_artifact_through_verified_outcome',
            'tests.test_factory_closure.FactoryClosureTests.test_corrected_report_requires_new_head_decision_and_preserves_native_history_and_budget',
            'tests.test_factory_human_independence.IndependentInvoiceReviewTests.test_reading_finance_user_can_comment_on_exact_other_review_without_any_decision',
            'tests.test_cash_reported_amount.CashReportedAmountBrowserTests',
            'tests.test_payments_overview.PaymentsOverviewTests.test_trial_reads_exact_part_payment_and_only_current_reviewed_ageing',
            'tests.test_client_workspace_link.ClientWorkspaceLinkTests.test_current_groups_use_only_reviewed_same_tenant_visible_projects',
            'tests.test_factory_delivery.FactoryDeliveryTests.test_native_planning_decision_is_available_in_primary_ui_without_finance',
            'tests.test_factory_go_live.FactoryGoLiveTests.test_agent_drafts_reviews_and_publishes_but_only_human_attestation_establishes_native_acceptance',
            'tests.test_factory_handover.FactoryHandoverTests.test_distinct_actual_recipient_uses_exact_http_receipt_and_has_no_execution_or_private_run_access',
        ]
    elif group == 'project-api':
        modules = [
            'tests.test_factory_api.ContractTests',
            'tests.test_factory_api_project_records', 'tests.test_work_access_requests',
            'tests.test_factory_minutes.FactoryMinutesTests.test_start_upload_connects_exact_notes_and_original_source_authority',
            'tests.test_factory_minutes.FactoryMinutesTests.test_external_exact_quality_review_all_recipients_and_receipts',
            'tests.test_controlled_documents.ControlledDocumentTests.test_focused_status_report_returns_revises_and_shows_original_receipt',
            'tests.test_invoice_milestone_proof.InvoiceMilestoneProofTests.test_private_pdf_and_successor_unlock_only_exact_draft_and_finance_review',
            'tests.test_factory_invoice_draft_cancellation.InvoiceDraftCancellationTests.test_same_obligation_issued_invoice_is_linked_with_exact_cancellation_history',
        ]
    elif group == 'delivery-api':
        modules = [
            'tests.test_factory_api.ContractTests',
            'tests.test_factory_closure.FactoryClosureTests.test_corrected_report_requires_new_head_decision_and_preserves_native_history_and_budget',
            'tests.test_factory_hypercare.FactoryHypercareTests.test_typed_observation_uses_current_rule_unknown_metrics_and_source_permissions',
            'tests.test_factory_delivery.FactoryDeliveryTests.test_agent_waits_for_native_gates_then_prepares_and_verifies_readiness',
            'tests.test_factory_delivery.FactoryDeliveryTests.test_native_planning_decision_is_available_in_primary_ui_without_finance',
            'tests.test_project_archive_files.ArchiveFileTests.test_selected_files_through_worker_byte_receipts_native_handover_and_factory_verification',
            'tests.test_project_archive_files.ArchiveFileTests.test_only_confirmed_missing_file_can_be_retried_and_other_files_keep_their_state',
            'tests.test_project_archive_files.ArchiveFileTests.test_store_rules_save_as_draft_and_bad_sources_do_not_reserve_effects',
            'tests.test_factory_minutes.FactoryMinutesTests.test_external_exact_quality_review_all_recipients_and_receipts',
            'tests.test_factory_minutes.FactoryMinutesTests.test_cited_extraction_human_confirmation_internal_minutes_and_action_owner',
            *PLANNING_API_TESTS,
            'tests.test_planning_workaround_walkthrough',
            'tests.test_go_live_replies.GoLiveReplyTests.test_client_changes_prepare_version_two_with_fresh_review_receipt_and_actual_signatures',
            'tests.test_go_live_milestone_walkthrough',
            'tests.test_handover_replies.HandoverReplyTests.test_configured_recorder_can_record_distinct_recipient_and_native_downstream_verifies',
        ]
    elif group == 'planning-api':
        modules = list(PLANNING_API_TESTS)
    elif group == 'payroll-api':
        modules = [
            'tests.test_factory_api.ContractTests', 'tests.test_payroll_api_cutover',
            'tests.test_factory_payroll.FactoryPayrollTests.test_missing_hr_receipt_requires_exact_matcher_and_new_match',
            'tests.test_factory_payroll.FactoryPayrollTests.test_withdrawal_preserves_original_receipt_and_requires_new_reviewed_sources',
        ]
    elif group == 'setup-api':
        modules = ['tests.test_factory_api.ContractTests', 'tests.test_policy_reviews_api',
                   'tests.test_rfp_fresh_intake.FreshBidIntakeTests.test_api_retains_the_original_private_receipt_and_rechecks_download_authority']
    elif group == 'hr-api':
        modules = ['tests.test_factory_api.ContractTests', 'tests.test_hr_handoff_api',
                   'tests.test_payroll_questions.PayrollQuestionTests.test_api_question_review_send_answer_and_exact_recipient_receipt',
                   'tests.test_payroll_questions.PayrollQuestionTests.test_original_source_owner_revocation_holds_before_private_loading',
                   'tests.test_payroll_question_reads']
    elif group == 'recover-api':
        modules = [
            'tests.test_factory_api.ContractTests',
            'tests.test_payroll_api_cutover.PayrollApiCutoverTests.test_multipart_sources_are_nominee_scoped_and_held_rows_stay_private',
            'tests.test_payroll_identity.PayrollIdentityTests.test_api_compares_original_owner_attestations_and_routes_private_hr_correction',
            'tests.test_factory_payroll_restart.PayrollRestartTests.test_api_restarts_the_exact_unpublished_work_with_its_current_profile',
            'tests.test_factory_payroll.FactoryPayrollTests.test_withdrawal_preserves_original_receipt_and_requires_new_reviewed_sources',
            'tests.test_design_reminders_staff.PaymentReminderTests.test_api_schedules_checked_attachment_and_reads_verified_mailbox_receipt',
        ]
    elif group == 'go-live-api':
        modules = [
            'tests.test_factory_hypercare.FactoryHypercareTests.test_api_records_observed_release_and_acceptance_before_stability_work_runs',
            'tests.test_factory_hypercare.FactoryHypercareTests.test_actual_release_ui_remains_available_before_execution_and_stability_configuration',
            'tests.test_go_live_replies.GoLiveReplyTests.test_decline_moves_through_an_owned_issue_fix_fresh_candidate_gates_and_new_acceptance',
            'tests.test_go_live_replies.GoLiveReplyTests.test_http_roles_exact_receipts_draft_rules_and_unavailable_actions',
        ]
    elif group == 'staff-api':
        modules = ['tests.test_factory_api.ContractTests', 'tests.test_account_delivery', 'tests.test_staff_access_api',
                   'tests.test_role_scoped_work.RoleScopedWorkTests.test_api_team_invitation_renewal_admits_only_the_reviewed_role_and_team',
                   'tests.test_role_scoped_work.RoleScopedWorkTests.test_18_pmo_finance_and_hr_leads_invite_only_their_team_members']
    elif group == 'money-api':
        modules = ['tests.test_factory_api.ContractTests', 'tests.test_invoice_short_payments',
                   'tests.test_admitted_cash_successor_walkthrough',
                   'tests.test_financial_corrections.FinancialCorrectionTests.test_api_exact_credit_receipt_and_reversed_cash_successor',
                   'tests.test_financial_corrections.FinancialCorrectionTests.test_full_correction_staff_ui_calls_real_services_and_preserves_one_debt']
    elif group == 'decide-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_payments.PaymentTests.test_api_payment_exception_and_release_keep_independent_authorities',
                   'tests.test_factory_emergency.FactoryEmergencyTests.test_current_cto_refusal_holds_preauthorization_and_preserves_actual_outcome_capture',
                   'tests.test_factory_emergency.FactoryEmergencyTests.test_full_human_preauthorization_actual_capture_review_retrospective_and_report',
                   'tests.test_emergency_incident_intake',
                   'tests.test_authority_recovery.AuthorityRecoveryTests.test_api_records_fresh_authority_without_moving_historical_times',
                   'tests.test_authority_recovery.EmergencyFollowupTests.test_api_links_exact_ordinary_revision_without_inheriting_emergency_authority',
                   'tests.test_role_scoped_work.RoleScopedWorkTests.test_16_my_work_links_only_current_specialist_desks_in_that_workspace']
    elif group == 'report-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_factory_reporting.FactoryReportingTests.test_api_weekly_save_start_return_correct_and_confirm_original_receipt',
                   'tests.test_factory_reporting.FactoryReportingTests.test_returned_report_requires_explicit_rework_and_new_exact_version_review',
                   'tests.test_factory_leadership.FactoryLeadershipTests.test_api_cited_monthly_report_returns_for_fresh_review_and_records_receipt',
                   'tests.test_factory_leadership.FactoryLeadershipTests.test_tuesday_no_extra_approval_and_exact_receipts',
                   'tests.test_factory_escalation.FactoryEscalationTests.test_api_client_escalation_requires_authority_and_returns_exact_communication_receipt',
                   'tests.test_factory_escalation.FactoryEscalationTests.test_primary_http_intake_decisions_review_and_get_preserves_rows']
    elif group == 'cost-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_factory_engagement.FactoryEngagementTests.test_api_engagement_assignment_details_and_registered_planning_handoff',
                   'tests.test_factory_engagement.FactoryEngagementTests.test_route_b_human_assignment_planning_before_registration_exact_final_handoff',
                   'tests.test_costing.CostingTests.test_api_rule_oracle_reviews_bind_supported_calculation_and_preserve_source_scope',
                   'tests.test_costing.CostingTests.test_connected_calculation_cost_approvals_signature_and_af13',
                   'tests.test_costing_proposals.CostingProposalTests.test_api_comparison_and_independent_proposal_review_preserve_source_checks']
    elif group == 'scope-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_policy_scopes.PolicyScopeTests.test_api_scope_requires_explicit_application_and_current_source_reader',
                   'tests.test_policy_scopes.PolicyScopeTests.test_four_scope_identities_and_no_cross_case_precedence',
                   'tests.test_policy_impact.PolicyImpactTests.test_api_observes_affected_records_and_requires_second_current_reviewer',
                   'tests.test_policy_impact.PolicyImpactTests.test_paged_projection_is_actor_configuration_bound_and_cannot_hide_truncation',
                   'tests.test_factory_forecast.ForecastFactoryTests.test_api_intake_picker_requires_current_scenario_source_grant',
                   'tests.test_emergency_incident_intake.EmergencyIncidentIntakeTests.test_api_incident_and_classification_pin_the_original_request']
    elif group == 'close-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_factory_schedules.FactorySchedulesTests.test_api_schedule_duplicate_correction_review_and_adjustment_handoff',
                   'tests.test_factory_schedules.FactorySchedulesTests.test_api_schedule_return_preparer_correction_and_inventory_selection',
                   'tests.test_ppe_date_proof.PPEAssetDateProofTests.test_api_register_capture_date_proof_and_independent_basis_review',
                   'tests.test_ppe_opening_proof.PPEOpeningProofTests.test_api_opening_proof_successor_and_current_approved_readback',
                   'tests.test_factory_accounting_intake.AccountingSuppliedIntakeTests.test_api_supplied_import_unit_confirmation_preserves_original_and_queues_work',
                   'tests.test_factory_accounting_intake.AccountingSuppliedIntakeTests.test_http_supplied_intake_to_reviewed_accounts_and_recipient_receipt']
    elif group == 'cash-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_factory_forecast.ForecastFactoryTests.test_api_forecast_approval_actual_match_and_original_receipt',
                   'tests.test_factory_group_forecast.GroupForecastFactoryTests.test_api_group_disclosure_draft_requires_oracle_then_exact_group_approval',
                   'tests.test_forecast_receipt_recovery.ForecastReceiptRecoveryTests.test_api_observation_stays_private_and_lookup_reconciles_only_original',
                   'tests.test_accounting_source_return.AccountingSourceReturnTests.test_api_source_return_upload_and_exact_unit_successor',
                   'tests.test_factory_accounting_intake.AccountingSuppliedIntakeTests.test_http_supplied_intake_to_reviewed_accounts_and_recipient_receipt']
    elif group == 'change-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_factory_issues.FactoryIssueTests.test_api_issue_register_capture_and_exact_owner_acknowledgement',
                   'tests.test_issue_teams.IssueTeamTests.test_api_issue_owner_assignment_exact_response_and_verified_investigation',
                   'tests.test_issue_messages.IssueMessageTests.test_api_message_review_release_and_original_receipt_leave_issue_open',
                   'tests.test_factory_change.FactoryChangeTests.test_api_normal_change_review_execution_and_signed_receipts',
                   'tests.test_factory_change.FactoryChangeTests.test_api_standard_intake_only_catalogue_binding_waits_for_owner_configuration',
                   'tests.test_factory_change.FactoryChangeTests.test_complete_native_flow_requires_human_assessment_review_execution_signatures_and_receipts']
    elif group == 'bid-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_rfp_estimate_requests.RFPEstimateRequestTests.test_api_missing_estimate_review_and_synthetic_delivery_receipt',
                   'tests.test_factory_rfp_pricing.FactoryBidAdjustmentTests.test_api_adjustment_recalculates_current_bid_without_reusing_old_human_decisions',
                   'tests.test_rfp_answers.RFPAnswerTests.test_api_answer_review_and_verified_winning_handoff',
                   'tests.test_rfp_submission_pack.RFPSubmissionPackTests.test_pack_draft_return_and_exact_review_preserve_legacy_snapshot']
    elif group == 'private-api':
        modules = ['tests.test_factory_api.ContractTests',
                   'tests.test_factory_bu.FactoryBUTests.test_api_private_event_through_reviewed_aggregate_and_original_recipient',
                   'tests.test_factory_bu.FactoryBUTests.test_focused_staff_reviews_publication_and_private_recipient_receipt',
                   'tests.test_factory_ledger.FactoryLedgerTests.test_api_incumbent_observation_independent_review_and_private_readback',
                   'tests.test_factory_ledger_observation_proof.LedgerObservationProofTests.test_api_private_proof_round_trip_remains_unverified',
                   'tests.test_ledger_resolution.LedgerResolutionTests.test_api_duplicate_resolution_requires_independent_review_and_fresh_original_check']
    elif group == 'surface':
        required = set()
        modules = ['tests.test_process_role_directory', 'tests.test_native_station_role_access', 'tests.test_factory_api',
                   'tests.test_role_scoped_work', 'tests.test_role_guard', 'tests.test_primary_roles',
                   'tests.test_role_eligibility', 'tests.test_finance_document_review',
                   'tests.test_factory_change.FactoryChangeTests.test_withdrawn_decision_authority_invalidates_selected_authorization',
                   'tests.test_factory_payroll.FactoryPayrollTests.test_complete_native_path_requires_reviews_human_publication_and_actual_recipient_receipt',
                   'tests.test_factory_payroll.FactoryPayrollTests.test_current_review_revocation_invalidates_verification',
                   'tests.test_payroll.PayrollTests.test_recipient_grant_revocation_and_HR_approval_revocation_hold_use',
                   'tests.test_payroll.PayrollTests.test_policy_and_retention_revocation_hold_current_read_and_report',
                   'tests.test_payroll.PayrollTests.test_raw_rows_and_salary_values_are_private_to_named_readers',
                   'tests.test_rfp_fresh_intake.FreshBidIntakeTests.test_api_and_form_share_the_original_file_receipt_and_delegation']
    else:
        module, required = SUITES[group]
        modules = [module]
        if role_access:
            environment['PSL_VERIFY_NATIVE_ROLES'] = '1'
    if group == "pmo":
        modules += ["tests.test_native_station_controls", "tests.test_specialist_loop.SpecialistLoopTests"]
    if group == "accounts":
        modules.append("tests.test_finance_import_projection")
    cmd = [sys.executable, "manage.py", "test", *modules, "--keepdb", "--noinput", "--verbosity", "1"]
    if group in API_GROUPS:
        cmd += ["--testrunner", "tests.api_contract_runner.ContractRunner"]
    observed = set()
    role_observed = set()
    with subprocess.Popen(cmd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
        for line in process.stdout:
            print(f"[{group}] {line}", end="", flush=True)
            if "Native station verified " in line and " -> " in line:
                observed.add(line.split("Native station verified ", 1)[1].split(" -> ", 1)[0])
            if 'ROLE_ACCESS ' in line:
                role_observed.add(line.split('ROLE_ACCESS ', 1)[1].split()[0])
        status = process.wait()
    if group in SUITES:
        print(f"[{group}] Passed receiver checks {sorted(observed)}. Missing {sorted(required - observed)}.", flush=True)
        if observed != required:
            return False
    if role_access and group not in ('surface', *API_GROUPS):
        print(f"[{group}] Role reads checked for {len(role_observed)} processes; missing {sorted(required - role_observed)}.", flush=True)
        if role_observed != required:
            return False
    return status == 0


def live(params, database, processes):
    """Reserve any paid run once per deployment, even if the container is restarted."""
    if not all(os.environ.get(k) for k in ("PSL_ACCEPTANCE_SOURCE_MODEL", "PSL_ACCEPTANCE_SOURCE_KEY")):
        raise RuntimeError("The checks service has no temporary provider binding.")
    params = {**params, "dbname": database}
    with psycopg.connect(**params, autocommit=True) as state:
        state.execute("CREATE SCHEMA IF NOT EXISTS specialist_acceptance")
        state.execute("CREATE TABLE IF NOT EXISTS specialist_acceptance.station_live(deployment text PRIMARY KEY, result int)")
        deployment = os.environ["RAILWAY_DEPLOYMENT_ID"]
        new = state.execute("INSERT INTO specialist_acceptance.station_live(deployment) VALUES (%s) ON CONFLICT DO NOTHING RETURNING deployment", (deployment,)).fetchone()
        if not new:
            row = state.execute("SELECT result FROM specialist_acceptance.station_live WHERE deployment=%s", (deployment,)).fetchone()
            return row == (0,)
        names = ["tests.test_native_station_live.NativeProviderAcceptance." + LIVE_CASES[pid] for pid in processes]
        result = subprocess.run([sys.executable, "manage.py", "test", *names, "--keepdb", "--noinput", "--verbosity", "2"],
                                env={**os.environ, "PSL_STATION_LIVE": "1"}).returncode
        state.execute("UPDATE specialist_acceptance.station_live SET result=%s WHERE deployment=%s", (result, deployment))
        return result == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*")
    parser.add_argument('--role-access', action='store_true', help='Check admitted staff on the HTML and API for each process.')
    provider = parser.add_mutually_exclusive_group()
    provider.add_argument("--live", action="store_true", help="Also run both synthetic provider and storage checks.")
    provider.add_argument("--live-case", choices=LIVE_CASES, help="Run one fresh synthetic provider case before the department suites.")
    options = parser.parse_args()
    default_groups = (*SUITES, 'original', 'surface', 'directory') if options.role_access else tuple(SUITES)
    available = (*default_groups, *API_GROUPS[1:]) if options.role_access else default_groups
    groups = options.groups or default_groups
    if set(groups) - set(available) or len(set(groups)) != len(groups):
        parser.error("Choose distinct department suites.")
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.specialist_acceptance"
    import django
    django.setup()
    from django.db import connections
    if os.environ.get("RAILWAY_SERVICE_NAME") != "psl-design-checks":
        raise RuntimeError("The isolated Railway checks service is required.")
    settings = connections["default"].settings_dict
    template = settings["TEST"]["NAME"]
    if template != "test_psl_specialist_loop" or settings["NAME"].startswith("test_"):
        raise RuntimeError("Unexpected test database environment.")
    params = connections["default"].get_connection_params()
    params.pop("cursor_factory", None)
    params.pop("context", None)
    params["dbname"] = "postgres"
    selected_passed = live(params, template, [options.live_case]) if options.live_case else True
    # A previous container may have stopped in the middle of a transactional
    # fixture. Never reuse its data, even when Railway restarts a deployment.
    with psycopg.connect(**{**params, "dbname": template}) as check:
        if check.execute("SELECT EXISTS(SELECT 1 FROM auth_user)").fetchone()[0]:
            raise RuntimeError("The synthetic template contains accounts. A clean migrated template is required.")
    token = uuid4().hex
    owned = []
    with psycopg.connect(**params, autocommit=True) as admin:
        try:
            for group in groups:
                name = f"test_psl_stations_{group}_{token}"
                admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(name), sql.Identifier(template)))
                owned.append(name)
            with ThreadPoolExecutor(max_workers=len(groups)) as pool:
                results = [pool.submit(run, group, token, options.role_access) for group in groups]
                passed = all([result.result() for result in results])
        finally:
            for name in owned:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    if passed and options.live:
        passed = live(params, template, LIVE_CASES)
    return passed and selected_passed


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
