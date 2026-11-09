import json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.policy.services import register_reference,transition
from apps.policy.recognition_drafts import draft_recognition_policy
from apps.policy.recognition_validators import AUTHORITY,REVIEW
from apps.pmo.services import complete_milestone
from apps.finance import recognition as domain
from .helpers import setup_case,signed,activate,rev
from .signature_helpers import reaffirm_for

def policy(a,c,key,value,e):
 r=draft_recognition_policy(a,c.pk,key,value,e.pk,timezone.now()-timedelta(seconds=1));transition(a,r.pk,'validated');transition(a,r.pk,'active');return r

def fixture():
 a,c=setup_case();e=signed(a,c)
 f=get_user_model().objects.create_user(username='finance-reviewer',password='test-only')
 for action in ['case.read','recognition.read','recognition.receive','recognition.review','recognition.export']:Grant.objects.create(user=f,case=c,action=action)
 refs=[]
 for person,role in [(a,'PM'),(f,'Finance')]:
  r=register_reference(a,c.pk,'f33-role:'+role,'schema:psl/role-assignment/v1',{'user_id':person.pk,'role':role},e['policy_decision'].pk);refs.append(r.ref)
 activate(a,c,'D05.role_principal_assignments',refs,e['policy_decision'])
 reaffirm_for(a,c)
 pe=add_evidence(a,c.pk,'recognition_policy','Synthetic Finance review criteria; no revenue formula','synthetic:f33')
 de=add_evidence(a,c.pk,'recognition_decision','Synthetic external human review memo; no journal','synthetic:f33')
 price=add_evidence(a,c.pk,'progress_price','Signed price evidence; exact amount remains in source','synthetic:f33')
 milestone=complete_milestone(a,c.pk,'M1',e['completion'].pk,rev(c))
 cfg=json.loads((Path(__file__).resolve().parent.parent/'fixtures/recognition-review.json').read_text())
 cfg['authority']['assignments'][0]['user_id']=a.pk;cfg['authority']['assignments'][1]['user_id']=f.pk
 ac=policy(a,c,AUTHORITY,cfg['authority'],e['policy_decision'])
 cfg['review']['policy_evidence_id']=pe.pk;rc=policy(a,c,REVIEW,cfg['review'],e['policy_decision'])
 p=cfg['packet'];p.update(as_of=timezone.localdate().isoformat(),statement='Dated PM completion with independent acceptance unresolved',gaps=[],facts=[{'category':'price','evidence_id':price.pk,'description':'Commercial price source'},{'category':'completion','evidence_id':e['completion'].pk,'description':'PM milestone completed'}],milestone_ids=[milestone.pk])
 packet=domain.prepare(a,c.pk,'monthly-review',p,e['completion'].pk,rev(c))
 return {'actor':a,'finance':f,'case':c,'evidence':e,'policy':pe,'decision':de,'packet':packet,'config':cfg,'authority':ac,'review_policy':rc}

def record(f,kind,key=None,**kwargs):
 a=f['finance'] if kind in ['receive','review'] else f['actor']
 return domain.record(a,f['case'].pk,f['packet'].pk,kind,key or kind,f['evidence']['completion'].pk,'Explicit synthetic human statement',rev(f['case']),**kwargs)

def received(f):
 for k in ['attest','request','receive']:record(f,k)
def reviewed(f):
 received(f);return record(f,'review',verdict='reviewed',decision_evidence_id=f['decision'].pk)
