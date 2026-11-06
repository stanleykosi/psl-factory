"""Bounded, cited investigation and question drafting; no amounts or source bodies read."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import add_evidence,event,bump
from apps.finance.schedules import locked
from apps.finance.schedule_models import ScheduleWork
from apps.policy.schedule_validators import SCHEMAS
from apps.policy.services import resolve
from .models import AgentRun

@transaction.atomic
def investigate(actor,case_id,expected=None):
 c=locked(actor,case_id,'agent.schedules',expected);findings=[]
 # Only ID/status/gap projections are selected; income/adjustment values stay out of agent context.
 for w in ScheduleWork.objects.filter(case=c,kind__in=['income','inventory']).order_by('-pk').values('id','kind','version','sha256','parent_id','result__status','result__findings','result__schedules')[:40]:
  gaps=w.get('result__findings') or []
  questions=[]
  if w['kind']=='income':questions.append('Ask Finance to confirm disaggregation, zero-sum reclassification or separately justified addition; reconcile duplicated source accounts and the single unit conversion against the exact note version.')
  else:
   questions.append('Ask each configured owner for native workbook/tab links, formulas/manual cells, consumers, a normal and an exception oracle; obtain current AF13 meaning, expectations and acceptance before inclusion.')
   questions.append('Resolve whether monthly performance is a separate output; retain named-only schedules as explicit exclusions.')
  findings.append({'work_id':w['id'],'kind':w['kind'],'version':w['version'],'sha256':w['sha256'],'parent_run_id':w['parent_id'],'recorded_status':w['result__status'],'findings':gaps,'schedule_gaps':w.get('result__schedules') or [],'owner_questions':questions,'current_use':'Current source/authority must be rechecked by human report/review services'})
 e=add_evidence(actor,c.pk,'agent_schedules','Bounded reference/status investigation and owner questions; no financial amounts, source bodies or authority inferred','local:deterministic-schedules-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='F12',provider='deterministic-schedules-v1',result={'process_ids':['F12','F13'],'findings':findings,'policy_readiness':{k:resolve(k,c).status for k in SCHEMAS},'work_budget':40,'financial_values_read':False,'approval_granted':False,'ledger_posted':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.schedules',run=r.pk);bump(c);return r
