from apps.finance import usage_intake_views
from apps.documents import template_views
from apps.pmo import leadership_report_views
from apps.pmo import planning_views
from apps.pmo import project_view_views
from apps.finance import receipt_followup_views
from apps.finance.followup_intake import endpoint as finance_followup_inbox
from apps.documents import protection_acceptance_views
from apps.finance import readiness_acceptance_views
from apps.finance import accepted_document_views
from apps.finance import acceptance_views
from apps.workflows import readiness_views
from apps.workflows import operator_views
from apps.pmo import costing_views
from apps.finance import d03_views
from apps.documents import migration_views
from apps.pmo import approval_views
from apps.baas import support_views
from apps.finance import ledger_views,ledger_agent_views
from apps.finance import ppe_views
from apps.finance import schedule_views
from apps.finance import bu_views
from django.urls import path, include
finance_intake_patterns=[path('finance/followup-inbox/<uuid:case_id>/<str:operation_key>/',finance_followup_inbox,name='finance_followup_inbox')]
from apps.documents import validation_views
from apps.finance import payroll_views
from apps.finance import hrfinance_views
from apps.finance import recognition_views
from apps.finance import payment_views
from apps.core import views
from apps.baas import views as baas_views, partner_views
from apps.documents import views as document_views
from apps.pmo import views as pmo_views
from apps.pmo import commercial_views
from apps.pmo import issue_views
from apps.pmo import escalation_views
from apps.pmo import emergency_views, recovery_views, delivery_views
from apps.pmo import rfp_views
from apps.finance import views as finance_views
from apps.finance import performance_views,billing_views,settlement_views,correction_views,forecast_views
from apps.baas import support_agent_views,support_release_views,support_channel_views
from apps.agents import boundary_views
from apps.workflows import application_recovery_views
from apps.policy import pilot_views
from apps.policy import pilot_binding_views
pilot_patterns=[path('cases/<uuid:case_id>/pilot/',pilot_views.workbench,name='pilot_preflight'),
    path('cases/<uuid:case_id>/pilot/contracts/<int:pk>/',pilot_views.contract,name='pilot_contract'),
    path('cases/<uuid:case_id>/pilot/observations/<int:pk>/',pilot_views.report,name='pilot_observation')]
urlpatterns = [
    path('cases/<uuid:case_id>/documents/templates/current/', template_views.workbench, name='template_current'),
    path('cases/<uuid:case_id>/leadership-reports/<str:kind>/', leadership_report_views.prepare, name='leadership_report'),path('cases/<uuid:case_id>/planning/',planning_views.workbench,name='planning'),path('project-views/',project_view_views.index,name='project_views'),path('cases/<uuid:case_id>/project-view/<slug:key>/',project_view_views.audience,name='project_audience'),path('cases/<uuid:case_id>/project-sharing/configuration/',project_view_views.configuration,name='project_view_configuration'),path('cases/<uuid:case_id>/finance/receipt-followup/',receipt_followup_views.workbench,name='finance_receipt_followup'),path('cases/<uuid:case_id>/application-recovery/',application_recovery_views.workbench,name='application_recovery'),path('cases/<uuid:case_id>/application-recovery/<int:plan_id>/',application_recovery_views.report,name='application_recovery_report'),path('cases/<uuid:case_id>/validation/protection/',protection_acceptance_views.workbench,name='protection_acceptance'),path('cases/<uuid:case_id>/validation/protection/<int:pk>/',protection_acceptance_views.report,name='protection_acceptance_report'),path('cases/<uuid:case_id>/validation/protection/<int:pk>/export/',protection_acceptance_views.export,name='protection_acceptance_export'),path('cases/<uuid:case_id>/finance/readiness-acceptance/',readiness_acceptance_views.workbench,name='private_readiness_acceptance'),path('cases/<uuid:case_id>/finance/readiness-acceptance/<int:pk>/',readiness_acceptance_views.report,name='private_readiness_report'),path('cases/<uuid:case_id>/finance/readiness-acceptance/<int:pk>/export/',readiness_acceptance_views.export,name='private_readiness_export'),path('cases/<uuid:case_id>/finance/accepted-documents/',accepted_document_views.workbench,name='accepted_finance'),path('cases/<uuid:case_id>/finance/accepted-documents/<int:pk>/',accepted_document_views.report,name='accepted_finance_report'),path('cases/<uuid:case_id>/finance/acceptance/',acceptance_views.workbench,name='finance_acceptance'),path('cases/<uuid:case_id>/finance/acceptance/<int:pk>/',acceptance_views.report,name='finance_acceptance_report'),path('cases/<uuid:case_id>/finance/ledger/agents/drafts/<int:pk>/approved-evidence/',ledger_agent_views.approved,name='ledger_approved_evidence'),path('cases/<uuid:case_id>/finance/ledger/agents/',ledger_agent_views.workbench,name='ledger_agents'),path('cases/<uuid:case_id>/finance/ledger/agents/drafts/<int:pk>/',ledger_agent_views.report,name='ledger_agent_report'),path('cases/<uuid:case_id>/support/channels/',support_channel_views.workbench,name='support_channels'),path('cases/<uuid:case_id>/support/channels/guidance/',support_channel_views.guidance,name='support_channel_guidance'),path('cases/<uuid:case_id>/support/channels/<int:pk>/',support_channel_views.report,name='support_channel_report'),path('cases/<uuid:case_id>/support/responses/operations/',support_release_views.diagnostics,name='support_response_operations'),path('cases/<uuid:case_id>/support/responses/',support_release_views.workbench,name='support_responses'),path('cases/<uuid:case_id>/support/responses/<int:pk>/',support_release_views.report,name='support_response_report'),path('cases/<uuid:case_id>/support/response-receipts/<int:pk>/',support_release_views.receipt,name='support_response_receipt'),path('cases/<uuid:case_id>/support/agents/',support_agent_views.workbench,name='support_agents'),path('cases/<uuid:case_id>/support/agents/drafts/<int:pk>/',support_agent_views.report,name='support_agent_report'),path('cases/<uuid:case_id>/private-evidence/',boundary_views.workbench,name='private_evidence'),path('cases/<uuid:case_id>/private-evidence/results/<int:pk>/',boundary_views.result,name='private_result'),path('cases/<uuid:case_id>/private-evidence/projections/<int:pk>/',boundary_views.projection,name='private_projection'),path('cases/<uuid:case_id>/integrations/',readiness_views.workbench,name='integration_readiness'),path('cases/<uuid:case_id>/integrations/source/<str:kind>/<int:pk>/',readiness_views.source,name='integration_source'),path('cases/<uuid:case_id>/integrations/report/<int:pk>/',readiness_views.report,name='integration_report'),path('cases/<uuid:case_id>/operations/',operator_views.workbench,name='operations'),path('cases/<uuid:case_id>/operations/artifact/<int:pk>/',operator_views.artifact,name='operator_artifact'),path('cases/<uuid:case_id>/operations/source/<str:kind>/<int:pk>/',operator_views.proof,name='operator_proof'),path('cases/<uuid:case_id>/operations/report/<int:pk>/',operator_views.report,name='operator_report'),path('cases/<uuid:case_id>/costing/',costing_views.workbench,name='costing'),path('cases/<uuid:case_id>/costing/report/<int:pk>/',costing_views.report,name='costing_report'),path('cases/<uuid:case_id>/costing/source/<str:kind>/<int:pk>/',costing_views.source,name='costing_source'),path('cases/<uuid:case_id>/finance/billing-evidence/controls/<int:pk>/',d03_views.controls,name='billing_control_history'),path('cases/<uuid:case_id>/finance/billing-evidence/',d03_views.workbench,name='billing_evidence'),path('cases/<uuid:case_id>/finance/billing-evidence/report/<int:pk>/',d03_views.report,name='billing_evidence_report'),path('cases/<uuid:case_id>/finance/billing-evidence/source/<int:pk>/',d03_views.source,name='billing_evidence_source'),path('cases/<uuid:case_id>/migration/',migration_views.workbench,name='migration_readiness'),path('cases/<uuid:case_id>/migration/report/<int:pk>/',migration_views.report,name='migration_report'),path('cases/<uuid:case_id>/migration/evidence/<int:pk>/',migration_views.evidence,name='migration_evidence'),path('approvals/inbox/',approval_views.inbox,name='approval_inbox'),path('cases/<uuid:case_id>/approvals/',approval_views.workbench,name='approvals'),path('cases/<uuid:case_id>/approvals/report/',approval_views.report,name='approval_report'),path('cases/<uuid:case_id>/approvals/source/<int:pk>/',approval_views.source,name='approval_source'),path('support/inbox/',support_views.inbox,name='support_inbox'),path('cases/<uuid:case_id>/support/',support_views.workbench,name='support_flow'),path('cases/<uuid:case_id>/support/reports/<int:pk>/',support_views.report,name='support_report'),path('cases/<uuid:case_id>/finance/ledger/',ledger_views.workbench,name='ledger'),path('cases/<uuid:case_id>/finance/ledger/<int:pk>/report/',ledger_views.report,name='ledger_report'),path('cases/<uuid:case_id>/finance/assets/',ppe_views.workbench,name='ppe'),path('cases/<uuid:case_id>/finance/assets/<int:pk>/report/',ppe_views.report,name='ppe_report'),path('cases/<uuid:case_id>/finance/schedules/',schedule_views.workbench,name='finance_schedules'),path('cases/<uuid:case_id>/finance/schedules/<int:pk>/report/',schedule_views.report,name='schedule_report'),path('cases/<uuid:case_id>/finance/bu-attribution/',bu_views.workbench,name='bu'),path('cases/<uuid:case_id>/finance/bu-attribution/<str:kind>/<int:pk>/',bu_views.inspect,name='bu_inspect'),path('cases/<uuid:case_id>/finance/payroll/inspect/<str:kind>/<int:pk>/',payroll_views.inspect,name='payroll_inspect'),path('cases/<uuid:case_id>/finance/payroll/',payroll_views.workbench,name='payroll'),path('cases/<uuid:case_id>/finance/payroll/data/<str:kind>/<int:pk>/',payroll_views.data,name='payroll_data'),path('cases/<uuid:case_id>/finance/hr-handoff/',hrfinance_views.workbench,name='hrfinance'),path('cases/<uuid:case_id>/finance/hr-handoff/snapshots/<int:snapshot_id>/',hrfinance_views.snapshot,name='hrfinance_snapshot'),path('cases/<uuid:case_id>/finance/recognition/',recognition_views.workbench,name='recognition'),path('cases/<uuid:case_id>/finance/recognition/report/<int:packet_id>/',recognition_views.export,name='recognition_export'),path('cases/<uuid:case_id>/validation/',validation_views.workbench,name='validation'),path('cases/<uuid:case_id>/validation/report/<int:review_id>/',validation_views.export,name='validation_export'),path('cases/<uuid:case_id>/payment-controls/',payment_views.workbench,name='payment_controls'),path('cases/<uuid:case_id>/partners/',partner_views.workbench,name='partner_operations'),path('finance/partner-activity/inbox/',partner_views.inbox,name='partner_finance_inbox'),path('cases/<uuid:case_id>/baas/reconciliation/',baas_views.workbench,name='baas_reconciliation'),path('baas/engineering/inbox/',baas_views.inbox,name='engineering_inbox'),path('cases/<uuid:case_id>/finance/forecast/',forecast_views.workbench,name='finance_forecast'),path('cases/<uuid:case_id>/finance/corrections/',correction_views.workbench,name='finance_corrections'),path('finance/invoices/inbox/',settlement_views.inbox,name='invoice_inbox'),path('cases/<uuid:case_id>/finance/settlement/',settlement_views.workbench,name='finance_settlement'),path('cases/<uuid:case_id>/finance/usage-intake/',usage_intake_views.workbench,name='finance_usage_intake'),path('cases/<uuid:case_id>/finance/billing/',billing_views.workbench,name='finance_billing'),path('cases/<uuid:case_id>/finance/performance/',performance_views.workbench,name='finance_performance'),path('cases/<uuid:case_id>/finance/',finance_views.workbench,name='finance_analysis'),path("cases/<uuid:case_id>/rfp/",rfp_views.workbench,name="rfp"),path("cases/<uuid:case_id>/delivery/",delivery_views.workbench,name="delivery"),path("cases/<uuid:case_id>/authority/",recovery_views.workbench,name="authority_recovery"),path('cases/<uuid:case_id>/meetings/',pmo_views.workbench,name='meetings'),path('documents/inbox/',document_views.inbox,name='document_inbox'),
    path('cases/<uuid:case_id>/commercial/',commercial_views.workbench,name='commercial'),
    path('cases/<uuid:case_id>/changes/',commercial_views.changes,name='changes'),
    path('cases/<uuid:case_id>/emergencies/',emergency_views.workbench,name='emergencies'),
    path('cases/<uuid:case_id>/issues/',issue_views.workbench,name='issues'),
    path('cases/<uuid:case_id>/escalations/',escalation_views.workbench,name='escalations'),
    path('cases/<uuid:case_id>/documents/',document_views.workbench,name='documents'),path('accounts/', include('django.contrib.auth.urls')),
    path('', views.home, name='home'), path('coverage/', views.coverage, name='coverage'),
    path('cases/<uuid:case_id>/', views.case_detail, name='case'),
    path('cases/<uuid:case_id>/policy/', views.policy_workbench, name='policy')]
urlpatterns += finance_intake_patterns
from apps.policy import scope_views
from apps.policy import impact_views
urlpatterns += [path('cases/<uuid:case_id>/policy/impact/',impact_views.workbench,name='policy_impact'),
    path('cases/<uuid:case_id>/policy/impact/<int:pk>/',impact_views.assessment,name='policy_impact_assessment'),
    path('cases/<uuid:case_id>/policy/impact/<int:pk>/agent/',impact_views.investigation,name='policy_impact_agent'),
    path('cases/<uuid:case_id>/policy/impact/records/<int:configuration_id>/<str:key>/',impact_views.records,name='policy_impact_records')]
urlpatterns += [path('cases/<uuid:case_id>/policy/scopes/',scope_views.workbench,name='policy_scopes'),
    path('cases/<uuid:case_id>/policy/scopes/investigate/',scope_views.investigate,name='policy_scope_investigation')]

from apps.identity import intake_views
urlpatterns += [path('intake/',intake_views.create,name='case_create'),path('cases/<uuid:case_id>/access/',intake_views.access,name='case_access')]
urlpatterns += [path('tenant-access/',intake_views.provision,name='tenant_access'),path('cases/<uuid:case_id>/intake-investigation/',intake_views.investigate,name='intake_investigate')]
from apps.pmo import engagement_views
urlpatterns += [path('cases/<uuid:case_id>/engagement/',engagement_views.workbench,name='engagement')]
from apps.pmo import identity_resolution_views
urlpatterns += [path('cases/<uuid:case_id>/identity-resolution/',identity_resolution_views.workbench,name='identity_resolution')]
from apps.baas import summary_views
urlpatterns += [path('cases/<uuid:case_id>/support/summaries/',summary_views.workbench,name='complaint_summaries'),path('cases/<uuid:case_id>/support/summaries/<int:pk>/',summary_views.view,name='complaint_summary_draft'),path('cases/<uuid:case_id>/support/summaries/<int:pk>/export/',summary_views.view,{'reviewed':True},name='complaint_summary_export')]
from apps.core import workbench_views
urlpatterns += [path('work/',workbench_views.inbox,name='work_inbox')]
urlpatterns += pilot_patterns
urlpatterns += [path('cases/<uuid:case_id>/pilot/contracts/<int:contract_id>/bindings/',pilot_binding_views.workbench,name='pilot_bindings'),
    path('cases/<uuid:case_id>/pilot/bindings/<int:pk>/',pilot_binding_views.detail,name='pilot_binding')]
from apps.policy import role_views
urlpatterns += [path('cases/<uuid:case_id>/policy/role-eligibility/',role_views.guidance,name='role_eligibility_guidance')]
from apps.workflows import factory_views
from apps.workflows import factory_coordinator_views
from apps.workflows import factory_execution_views
from apps.pmo import closure_views
urlpatterns += [path('cases/<uuid:case_id>/delivery/<int:dossier_id>/closure/',closure_views.preparation,name='closure_preparation')]
from apps.core import workbench_views
urlpatterns += [path('workspaces/',workbench_views.home,name='workspace_overview'),
    path('factory/new/',factory_views.create,name='factory_create'),
    path('factory/start/',factory_views.intake,name='factory_intake'),
    path('work/<int:work_id>/',factory_views.detail,name='factory_detail'),
    path('work/<int:work_id>/worker-recovery/',factory_execution_views.review,name='factory_execution_review'),
    path('cases/<uuid:case_id>/factory/worker-recovery/',factory_execution_views.configuration,name='factory_execution_configuration'),
    path('work/<int:work_id>/coordinator/reconcile/',factory_coordinator_views.reconcile,name='factory_coordinator_reconcile'),
    path('cases/<uuid:case_id>/factory/responsibility/',factory_views.responsibility_configuration,name='factory_responsibility'),
    path('cases/<uuid:case_id>/factory/configuration/',factory_views.configuration,name='factory_configuration'),
    path('cases/<uuid:case_id>/factory/coordinator/',factory_coordinator_views.configuration,name='factory_coordinator_configuration')]

from apps.workflows import factory_receipt_recovery_views
urlpatterns += [path('work/<int:work_id>/response-recovery/',factory_receipt_recovery_views.review,name='factory_receipt_recovery_review'),
    path('cases/<uuid:case_id>/factory/response-recovery/',factory_receipt_recovery_views.configuration,name='factory_receipt_recovery_configuration')]

from apps.workflows import factory_change_intake_views
urlpatterns += [path('cases/<uuid:case_id>/factory/change-intake/',factory_change_intake_views.create,name='p56_intake'),
    path('cases/<uuid:case_id>/factory/change-intake/<int:receipt_id>/',factory_change_intake_views.detail,name='p56_intake_detail')]

from apps.workflows import factory_intake_views
urlpatterns += [path('work/<int:work_id>/project-instruction/',factory_intake_views.review,name='factory_intake_reaffirm')]
from apps.workflows import factory_rfp_views
urlpatterns += [path('cases/<uuid:case_id>/factory/rfp-outcome-settings/',factory_rfp_views.outcome_configuration,name='factory_rfp_outcome_configuration')]

from apps.finance import coverage_views
urlpatterns += [path('cases/<uuid:case_id>/finance/contract-coverage/', coverage_views.workbench, name='finance_contract_coverage')]

from apps.pmo import progress_views
urlpatterns += [path('cases/<uuid:case_id>/delivery/<int:dossier_id>/progress/',progress_views.workbench,name='delivery_progress')]
