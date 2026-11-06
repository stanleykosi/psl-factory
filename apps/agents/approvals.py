from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.pmo import approvals as d
from apps.pmo.models import ApprovalRequest,ApprovalRouteJob
from apps.policy.services import resolve
from apps.policy.approval_validators import SCHEMAS
from .models import AgentRun
@transaction.atomic
def investigate(a,case_id,expected=None):
 c=d.locked(a,case_id,'agent.approvals',expected);rows=[];findings=[]
 for r in ApprovalRequest.objects.filter(case=c).select_related('case','candidate__requirements').order_by('-pk')[:40]:
  v=d.visibility(a,r);rows.append({k:v[k] for k in ['request_id','reference','version','kind']})
  findings.append({'request_id':r.pk,'status':'current_owner_followup_required','next_action':'Confirm the exact department owner, current candidate/build/release, source access and decision version. An unavailable observation requires fresh owner evidence, never a PMO substitute decision.'})
 jobs=list(ApprovalRouteJob.objects.filter(request__case=c,status__in=['unknown','held']).values('id','status')[:40])
 e=add_evidence(a,c.pk,'agent_approvals','Bounded prerequisite metadata investigation; no source body read or approval authority','local:deterministic-approvals-v1')
 run=AgentRun.objects.create(case=c,actor=a,evidence=e,process_id='P02',provider='deterministic-approvals-v1',result={'requests':rows,'findings':findings,'routing_recovery':jobs,'policy_readiness':{k:resolve(k,c).status for k in SCHEMAS},'coverage':'At most 40 requests and 40 recovery jobs in the granted case','source_body_read':False,'approval_granted':False,'native_verified':False})
 event(a,c,'agent.approvals',run=run.pk);bump(c);return run
