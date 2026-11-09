"""Evidence body boundaries shared by generic readers; domain readers enforce their own grants."""
from django.db.models import Exists, OuterRef, Q
from django.db.models.expressions import RawSQL
PLANNING_PRIVATE=['planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness']
PRIVATE=['qbo_native_intent','qbo_native_observation','template_current_source','ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source']+PLANNING_PRIVATE
def forecast_private(e):
 if e.kind.startswith('forecast_') or e.kind=='finance_group_snapshot' or e.kind=='finance_report_snapshot' and getattr(e,'source','').startswith('derived:forecast:'):return True
 if not getattr(e,'pk',None) or not getattr(e,'case_id',None):return False
 from apps.finance.models import ForecastEvidenceReference,ForecastScenario,ForecastItemSupport
 if ForecastItemSupport.objects.filter(case_id=e.case_id,evidence_id=e.pk).exists():return True
 if ForecastScenario.objects.filter(case_id=e.case_id,evidence_id=e.pk).exists():return True
 return ForecastEvidenceReference.objects.filter(scenario__case_id=e.case_id,evidence_id=e.pk,numeric_reference=True).exists()

def forecast_private_query():
 # The generic boundary has always excluded references from any scenario case,
 # including historical string IDs accepted by the previous PostgreSQL cast.
 from apps.finance.models import ForecastEvidenceReference,ForecastScenario,ForecastItemSupport
 reference = {'evidence_id': OuterRef('pk')}
 return (Q(Exists(ForecastEvidenceReference.objects.filter(**reference))) |
         Q(Exists(ForecastScenario.objects.filter(**reference))) |
         Q(Exists(ForecastItemSupport.objects.filter(**reference))) |
         Q(kind__startswith='forecast_') | Q(kind='finance_group_snapshot') |
         Q(kind='finance_report_snapshot',source__startswith='derived:forecast:'))

def ppe_statement_private(e):
 if e.kind=='finance_report_snapshot' and getattr(e,'source','').startswith('derived:ppe-statement:'):return True
 from apps.finance.models import FinanceStatementPPEProjection
 return bool(getattr(e,'pk',None) and FinanceStatementPPEProjection.objects.filter(evidence_id=e.pk).exists())

def ppe_statement_private_query():
 from apps.finance.models import FinanceStatementPPEProjection
 return Q(Exists(FinanceStatementPPEProjection.objects.filter(evidence_id=OuterRef('pk'))))|Q(kind='finance_report_snapshot',source__startswith='derived:ppe-statement:')

def restricted(e):return ppe_statement_private(e) or getattr(e,'source','')=='psl:p56-confirmed-request/v1' or forecast_private(e) or e.kind in PRIVATE or e.kind.startswith(('d03_control_','p14_','ops_','integration_','agent_private_','coverage_','usage_intake_'))
def public_evidence(queryset):return queryset.exclude(ppe_statement_private_query()|forecast_private_query()|Q(source='psl:p56-confirmed-request/v1')|Q(kind__in=PRIVATE)|Q(kind__startswith='d03_control_')|Q(kind__startswith='p14_')|Q(kind__startswith='ops_')|Q(kind__startswith='integration_')|Q(kind__startswith='agent_private_')|Q(kind__startswith='coverage_')|Q(kind__startswith='usage_intake_'))

def public_agent_runs(queryset):
 # A public workspace/agent.extract grant does not authorise a private domain result.
 from apps.core.models import Evidence
 sources = public_evidence(Evidence.objects.filter(pk=OuterRef('evidence_id')))
 return queryset.filter(Exists(sources)).exclude(provider='deterministic-finance-lineage-v1',result__has_key='statement_inputs',result__statement_inputs__contains=[{'source_type':'ppe_schedule'}]).exclude(provider='deterministic-finance-lineage-v1',result__has_key='run',result__run__in=RawSQL('SELECT to_jsonb(statement_id) FROM finance_financestatementppeinput',[]))

def public_timeline(case):
 private_ids=list(case.evidence.filter(ppe_statement_private_query()|forecast_private_query()|Q(source='psl:p56-confirmed-request/v1')|Q(kind__startswith='agent_private_')|Q(kind__startswith='coverage_')|Q(kind__startswith='usage_intake_')|Q(kind__in=['qbo_native_intent','qbo_native_observation','ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review']+PLANNING_PRIVATE)).values_list('pk',flat=True))
 from apps.workflows.readiness_models import IntegrationContract,IntegrationObservation,IntegrationReview,IntegrationSelection
 private_contracts=IntegrationContract.objects.filter(case=case).filter(Q(payload__family__in=['supportresponse','supportchannel','ledgerdata'])|Q(finance_publication_readiness__isnull=False)|Q(private_protection_readiness__isnull=False)|Q(private_file_readiness__isnull=False))
 private_ids+=list(private_contracts.values_list('evidence_id',flat=True))
 private_ids+=list(IntegrationObservation.objects.filter(contract__in=private_contracts).values_list('evidence_id',flat=True))
 private_ids+=list(IntegrationReview.objects.filter(assessment__contract__in=private_contracts).values_list('evidence_id',flat=True))
 private_ids+=list(IntegrationSelection.objects.filter(contract__in=private_contracts).values_list('evidence_id',flat=True))
 private_ids=[pk for pk in private_ids if pk is not None]
 # JSON missing keys must retain unrelated public activity; NOT(NULL) alone would drop it.
 return case.audit.exclude(action__startswith='ledger.qbo.').exclude(action__startswith='delivery.progress.').exclude(action__startswith='document.template_current.').exclude(action__startswith='coverage.').exclude(action__startswith='usage_intake.').exclude(action__startswith='agent.coverage').exclude(action__startswith='agent.contract_coverage').exclude(action__startswith='forecast.').exclude(action__startswith='agent.forecast_').exclude(action__startswith='agent.data.').exclude(action__startswith='planning.').exclude(action__startswith='factory.').exclude(Q(data__has_key='evidence')&Q(data__evidence__in=private_ids))
