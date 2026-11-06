from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.baas import support as d
from apps.baas.models import SupportIntake,SupportLink,SupportResult,SupportMerge
from apps.policy.services import resolve
from apps.policy.support_validators import SCHEMAS
from .models import AgentRun
@transaction.atomic
def investigate(actor,case_id,expected=None):
 c=d.locked(actor,case_id,'agent.support',expected);h=d.head(c)
 linked=set(SupportLink.objects.filter(case=c).values_list('intake_id',flat=True));rows=list(SupportIntake.objects.filter(case=c).order_by('-pk').values('id','channel','message_ref')[:40]);findings=[]
 for r in rows:
  r['linked']=r['id'] in linked
  if not r['linked']:findings.append({'intake_id':r['id'],'question':'Confirm exact customer, transaction and issue before a human links this message; preserve distinct complaints.'})
 pending=d.SupportEvent.objects.filter(case=c,action='await_specialist').order_by('-pk').first()
 if pending:
  result=SupportResult.objects.filter(pending=pending).order_by('-pk').first();findings.append({'pending_event_id':pending.pk,'result_id':result.pk if result else None,'status':result.payload['status'] if result else 'missing','question':'Obtain an authorised specialist result tied to this exact wait. Financial correction remains with the Engineering-mediated process.'})
 if h:findings.append({'event_id':h.pk,'owner_id':h.owner_id,'state':h.state,'question':'Confirm accountable next action and evidence; preserve unresolved/reopened history.'})
 e=add_evidence(actor,c.pk,'agent_support','Bounded reference/ownership investigation; no customer text read or closure/financial authority','local:deterministic-support-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='B14',provider='deterministic-support-v1',result={'sources':rows,'findings':findings,'policy_readiness':{k:resolve(k,c).status for k in SCHEMAS},'coverage':'selected case; at most40 intake references','customer_text_read':False,'closure_authorized':False,'financial_execution_authorized':False,'native_channel_verified':False})
 event(actor,c,'agent.support',run=r.pk);bump(c);return r
