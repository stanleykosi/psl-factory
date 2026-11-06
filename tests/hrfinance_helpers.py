import json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.hrfinance_drafts import draft_hrfinance_policy
from apps.policy.hrfinance_validators import AUTHORITY,DISCLOSURE
from apps.finance import hrfinance as domain
from .helpers import setup_case,activate,rev

def policy(actor,case,key,value,e):
 r=draft_hrfinance_policy(actor,case.pk,key,value,e.pk,timezone.now()-timedelta(seconds=1));transition(actor,r.pk,'validated');transition(actor,r.pk,'active');return r

def fixture(configure=True,base=None):
 if base:
  finance,c,owner=base;hr=get_user_model().objects.create_user(username='hr-owner',password='test-only')
  for action in ACTIONS:Grant.objects.create(user=hr,case=c,action=action)
 else:
  hr,c=setup_case(username='hr-owner');finance=get_user_model().objects.create_user(username='finance-recipient',password='test-only')
  for action in ['case.read','hrfinance.read','hrfinance.need','hrfinance.contract','hrfinance.snapshot.read','hrfinance.receive','hrfinance.correction','hrfinance.bind','policy.configure','policy.validate','policy.activate','policy.revoke']:Grant.objects.create(user=finance,case=c,action=action)
  owner=add_evidence(hr,c.pk,'policy_decision','Synthetic actual HR/Finance nominations','synthetic:f35')
 e={'owner':owner}
 for k in ['hr_finance_need','hr_contract_source','hr_disclosure_decision','hr_correction_request','hr_correction_response']:
  e[k]=add_evidence(hr,c.pk,k,'Synthetic '+k+' metadata only; no staff/payroll rows','synthetic:f35')
 cfg=json.loads((Path(__file__).resolve().parent.parent/'fixtures/hr-finance.json').read_text(encoding='utf-8'))
 cfg['authority']['assignments'][0]['user_id']=hr.pk;cfg['authority']['assignments'][1]['user_id']=hr.pk;cfg['authority']['assignments'][2]['user_id']=finance.pk
 cfg['disclosure']['recipient_ids']=[finance.pk];cfg['disclosure']['source_evidence_id']=e['hr_contract_source'].pk;cfg['need']['recipient_ids']=[finance.pk]
 refs=[]
 for person,role in [(hr,'HR'),(finance,'Finance')]:refs.append(register_reference(hr,c.pk,'hrf-role:'+role,'schema:psl/role-assignment/v1',{'user_id':person.pk,'role':role},owner.pk).ref)
 activate(hr,c,'D05.role_principal_assignments',refs,owner)
 n=domain.need(finance,c.pk,'staff-attribution',cfg['need'],e['hr_finance_need'].pk,rev(c))
 f={'hr':hr,'finance':finance,'case':c,'e':e,'config':cfg,'need':n}
 if configure:
  f['authority_policy']=policy(hr,c,AUTHORITY,cfg['authority'],owner);f['disclosure_policy']=policy(hr,c,DISCLOSURE,cfg['disclosure'],owner)
  f['contract']=domain.contract(finance,c.pk,n.pk,'prepare',e['hr_contract_source'].pk,rev(c))
  f['approval']=domain.decide(hr,c.pk,f['contract'].pk,'approve','approve',e['hr_disclosure_decision'].pk,rev(c))
 return f

def body(f,**updates):
 v=json.loads(json.dumps(f['config']['export']));v['extracted_at']=(timezone.now()-timedelta(seconds=1)).isoformat();v.update(updates);return json.dumps(v)

def capture(f,key='snapshot',**updates):return domain.capture(f['hr'],f['case'].pk,f['contract'].pk,key,body(f,**updates),rev(f['case']))
def receive(f,s,key='receipt'):return domain.receive(f['finance'],f['case'].pk,s.pk,key,f['e']['hr_disclosure_decision'].pk,rev(f['case']))
