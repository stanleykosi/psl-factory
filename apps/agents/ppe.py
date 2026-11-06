from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.finance.ppe import locked
from apps.finance.models import ScheduleWork
from apps.policy.ppe_validators import SCHEMAS
from apps.policy.services import resolve
from .models import AgentRun
@transaction.atomic
def investigate(actor,case_id,expected=None):
 c=locked(actor,case_id,'agent.ppe',expected);findings=[]
 for w in ScheduleWork.objects.filter(case=c,kind__startswith='ppe_').order_by('-pk').values('id','kind','sha256','result__status','result__findings','result__date_basis_ambiguous')[:40]:
  findings.append({'work_id':w['id'],'kind':w['kind'],'sha256':w['sha256'],'recorded_status':w['result__status'],'recorded_findings':w['result__findings'],'date_basis_ambiguous':w['result__date_basis_ambiguous'],'owner_questions':['Confirm source completeness, prior approved opening and evidence/approval for each addition, disposal and reclassification.','Supply actual method, capitalization, useful-life, residual, period fraction and numerical oracle; never infer rates or calendar proration.','Explain any label/reporting-date discrepancy with an actual Finance basis decision; preserve both dates.','Reconcile closing balances to the exact reviewed Finance note and review a successor when source, policy or authority changes.']})
 e=add_evidence(actor,c.pk,'agent_ppe','Bounded reference and gap investigation; no asset amounts read; no accounting decisions','local:deterministic-ppe-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='F07',provider='deterministic-ppe-v1',result={'findings':findings,'policy_readiness':{k:resolve(k,c).status for k in SCHEMAS},'work_budget':40,'financial_values_read':False,'approval_granted':False,'ledger_posted':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.ppe',run=r.pk);bump(c);return r
