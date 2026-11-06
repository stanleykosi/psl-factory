"""Evidence body boundaries shared by generic readers; domain readers enforce their own grants."""
from django.db.models import Q
PLANNING_PRIVATE=['planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness']
PRIVATE=['ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source']+PLANNING_PRIVATE
def restricted(e):return getattr(e,'source','')=='psl:p56-confirmed-request/v1' or e.kind in PRIVATE or e.kind.startswith(('d03_control_','p14_','ops_','integration_','agent_private_'))
def public_evidence(queryset):return queryset.exclude(Q(source='psl:p56-confirmed-request/v1')|Q(kind__in=PRIVATE)|Q(kind__startswith='d03_control_')|Q(kind__startswith='p14_')|Q(kind__startswith='ops_')|Q(kind__startswith='integration_')|Q(kind__startswith='agent_private_'))

def public_agent_runs(queryset):
 # A public workspace/agent.extract grant does not authorise a private domain result.
 from apps.core.models import Evidence
 return queryset.filter(evidence_id__in=public_evidence(Evidence.objects.all()).values('pk'))

def public_timeline(case):
 private_ids=list(case.evidence.filter(Q(source='psl:p56-confirmed-request/v1')|Q(kind__startswith='agent_private_')|Q(kind__in=['ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review']+PLANNING_PRIVATE)).values_list('pk',flat=True))
 from apps.workflows.readiness_models import IntegrationContract,IntegrationObservation,IntegrationReview,IntegrationSelection
 private_contracts=IntegrationContract.objects.filter(case=case).filter(Q(payload__family__in=['supportresponse','supportchannel','ledgerdata'])|Q(finance_publication_readiness__isnull=False)|Q(private_protection_readiness__isnull=False)|Q(private_file_readiness__isnull=False))
 private_ids+=list(private_contracts.values_list('evidence_id',flat=True))
 private_ids+=list(IntegrationObservation.objects.filter(contract__in=private_contracts).values_list('evidence_id',flat=True))
 private_ids+=list(IntegrationReview.objects.filter(assessment__contract__in=private_contracts).values_list('evidence_id',flat=True))
 private_ids+=list(IntegrationSelection.objects.filter(contract__in=private_contracts).values_list('evidence_id',flat=True))
 private_ids=[pk for pk in private_ids if pk is not None]
 # JSON missing keys must retain unrelated public activity; NOT(NULL) alone would drop it.
 return case.audit.exclude(action__startswith='agent.data.').exclude(action__startswith='planning.').exclude(action__startswith='factory.').exclude(Q(data__has_key='evidence')&Q(data__evidence__in=private_ids))
