from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.workflows.operator_recovery import locked
from apps.workflows.operator_inventory import jobs
from apps.workflows.operator_models import RecoveryAssessment
from apps.policy.services import resolve
from apps.policy.operator_validators import SCHEMAS
from .models import AgentRun
@transaction.atomic
def investigate(a,case_id,expected=None):
    c=locked(a,case_id,'agent.operations',expected);rows,omitted,_=jobs(a,c,500,include_private=False);questions=[]
    for row in rows:
        if row['status'] in ['unknown','held'] or row['lease_expired']:
            questions.append({'status':row['status'],'lease_expired':row['lease_expired'],'question':'Run source receipt lookup before any retry/cancellation; inspect scoped authority/intent and use its explicit recovery interface.'})
    assessments=[{'assessment':r.pk,'recorded_complete':r.result['documentary_complete'],'question':'Distinguish supplied reports from actual metadata drill receipts; unknown objectives and full-database acceptance remain separate.'} for r in (RecoveryAssessment.objects.none() if c.kind=='support' or c.ledgerprojection_set.exists() else RecoveryAssessment.objects.filter(plan__case=c).exclude(plan__payload__has_key='private_readiness_packet_ids').exclude(plan__payload__has_key='private_protection_packet_ids')).order_by('-pk')[:20]]
    e=add_evidence(a,c.pk,'agent_operations','Bounded cross-family metadata diagnostics; no raw errors, payloads, proof body or recovery effects','local:deterministic-operations-v1')
    r=AgentRun.objects.create(case=c,actor=a,evidence=e,process_id='P13',provider='deterministic-operations-v1',result={'job_findings':questions,'assessments':assessments,'omitted_family_count':len(omitted),'policy_status':{k:resolve(k,c).status for k in SCHEMAS},'source_body_read':False,'recovery_executed':False,'full_database_restore_verified':False,'deployment_authorized':False});event(a,c,'agent.operations',run=r.pk);bump(c);return r
