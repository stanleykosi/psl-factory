from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.finance.recognition import locked,position
from apps.pmo.services import subject
from apps.policy.services import resolve
from apps.policy.recognition_validators import AUTHORITY,REVIEW
from apps.finance.recognition_models import ProgressPacket
from .models import AgentRun
@transaction.atomic
def investigate(actor,case_id,expected):
 c=locked(actor,case_id,'agent.recognition',expected)
 packets=list(ProgressPacket.objects.filter(case=c).order_by('-pk')[:20]);findings=[]
 for p in packets:
  s=position(p);questions=list(s['holds']);categories={f['category'] for f in p.payload['facts']}
  if 'estimate' in categories and 'acceptance' not in categories:questions.append('An estimate is supplied without acceptance; ask Finance whether its configured review criteria require acceptance.')
  if not p.payload['source_ids']:questions.append('Manual evidence has no AF13 provenance record; confirm the source and owner through the authorised manual route.')
  if not p.payload['gaps'] and any(word in p.payload['statement'].lower() for word in ['unresolved','conflict','disagree']):questions.append('The supplied narrative signals unresolved evidence but the declared gap list is empty; reconcile the discrepancy with the PM.')
  readiness={k:resolve(k,c).status for k in [AUTHORITY,REVIEW]}
  for k,status in readiness.items():
   if status!='ACTIVE':questions.append(k+': '+status+'; configure only the dependent human review action.')
  findings.append({'packet_id':p.pk,'sha256':p.sha256,'citations':[{'evidence_id':f['evidence_id'],'category':f['category'],'description':f['description'][:500],'sha256':p.manifest['evidence'][str(f['evidence_id'])],'source_quote':subject(c,f['evidence_id']).body[:300]} for f in p.payload['facts'][:20]],'omitted_citations':max(0,len(p.payload['facts'])-20),'questions':questions,'policy_readiness':readiness,'distinctions':['PM estimate is not acceptance','cash is not progress or recognised revenue','Finance receipt is not approval'],'draft_followup':'Ask the attesting PM for missing or conflicting evidence; Finance owns the accounting disposition.'})
 e=add_evidence(actor,c.pk,'agent_recognition','Bounded F33 evidence comparison','local:deterministic-recognition-v1')
 c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,provider='deterministic-recognition-v1',process_id='F33',result={'findings':findings,'packet_limit':20,'recognised_amount':None,'accounting_posted':False,'authority_granted':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.recognition',run=r.pk);bump(c);return r
