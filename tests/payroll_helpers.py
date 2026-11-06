import json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.policy.payroll_validators import ACCESS,MERGE,MATCH,REPORT,AUTH
from apps.policy.hrfinance_validators import AUTHORITY as HR_AUTH,DISCLOSURE as HR_DATA
from apps.finance import hrfinance as hr,payroll as domain
from .helpers import setup_case,activate,rev
from .hrfinance_helpers import policy as hr_policy

def policy(f,key,value):
 r=draft_payroll_policy(f['owner'],f['case'].pk,key,value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['owner'],r.pk,'validated');transition(f['owner'],r.pk,'active');return r

def fixture(employee_ids=None):
 owner,c=setup_case(username='payroll-owner');people={}
 for name in ['preparer','reviewer','manager']:
  u=get_user_model().objects.create_user(username='payroll-'+name,password='test-only')
  actions=ACTIONS if name!='manager' else ['case.read','payroll.read','payroll.report.read','payroll.report.receive']
  for action in actions:Grant.objects.create(user=u,case=c,action=action)
  people[name]=u
 e={}
 for k in ['policy_decision','payroll_need','payroll_source_contract','payroll_review','hr_finance_need','hr_contract_source','hr_disclosure_decision','hr_correction_request']:
  e[k]=add_evidence(owner,c.pk,k,'Synthetic '+k+' metadata only; no payroll/staff source rows','synthetic:payroll')
 refs=[]
 for u,role in [(owner,'HR'),(people['preparer'],'Finance'),(people['reviewer'],'Finance')]:refs.append(register_reference(owner,c.pk,'payroll-role:'+str(u.pk),'schema:psl/role-assignment/v1',{'user_id':u.pk,'role':role},e['policy_decision'].pk).ref)
 activate(owner,c,'D05.role_principal_assignments',refs,e['policy_decision'])
 cfg=json.loads((Path(__file__).resolve().parent.parent/'fixtures/payroll.json').read_text(encoding='utf-8'))
 if employee_ids:
  for export,emp in zip(cfg['exports'],employee_ids):export['rows'][0]['employee_id']=emp
 cfg['access']['providers'][0]['owner_id']=owner.pk;cfg['access']['providers'][1]['owner_id']=owner.pk;cfg['access']['reader_ids']=[people['preparer'].pk,people['reviewer'].pk];cfg['access']['source_contract_evidence_id']=e['payroll_source_contract'].pk
 cfg['authority']['assignments'][0]['user_id']=people['reviewer'].pk;cfg['authority']['assignments'][1]['user_id']=people['preparer'].pk;cfg['report']['recipient_ids']=[people['manager'].pk]
 f={'owner':owner,'case':c,'e':e,**people,'config':cfg}
 f['policies']={key:policy(f,key,cfg[name]) for key,name in [(ACCESS,'access'),(MERGE,'merge'),(MATCH,'match'),(REPORT,'report'),(AUTH,'authority')]}
 h=json.loads((Path(__file__).resolve().parent.parent/'fixtures/hr-finance.json').read_text(encoding='utf-8'));recipients=cfg['access']['reader_ids']
 h['authority']['assignments']=[{'user_id':owner.pk,'role':'HR','purpose':'authorize'},{'user_id':owner.pk,'role':'HR','purpose':'respond'}]+[{'user_id':uid,'role':'Finance','purpose':'receive'} for uid in recipients]
 h['disclosure'].update(recipient_ids=recipients,purposes=['payroll_matching'],from_period='2026-09',to_period='2026-09',source_evidence_id=e['hr_contract_source'].pk)
 h['need'].update(recipient_ids=recipients,purpose='payroll_matching',period='2026-09',as_of='2026-09-30')
 hr_policy(owner,c,HR_AUTH,h['authority'],e['policy_decision']);hr_policy(owner,c,HR_DATA,h['disclosure'],e['policy_decision'])
 n=hr.need(people['preparer'],c.pk,'payroll-hr-view',h['need'],e['hr_finance_need'].pk,rev(c));d=hr.contract(people['preparer'],c.pk,n.pk,'hr-contract',e['hr_contract_source'].pk,rev(c));hr.decide(owner,c.pk,d.pk,'approve','hr-approve',e['hr_disclosure_decision'].pk,rev(c))
 h['export'].update(period='2026-09',as_of='2026-09-30',extracted_at=(timezone.now()-timedelta(seconds=1)).isoformat(),rows=[{'employee_id':emp,'bu':'BU-A','effective_from':'2026-01-01','effective_until':None} for emp in (employee_ids or ['E001','E002'])])
 s=hr.capture(owner,c.pk,d.pk,'hr-source',json.dumps(h['export']),rev(c))
 for u in [people['preparer'],people['reviewer']]:hr.receive(u,c.pk,s.pk,'hr-receipt:'+str(u.pk),e['hr_disclosure_decision'].pk,rev(c))
 f.update(hr=s,hr_config=h,hr_contract=d)
 f['request']=domain.request(people['preparer'],c.pk,'staff-costs',cfg['request'],e['payroll_need'].pk,rev(c))
 f['inputs']=[capture(f,idx) for idx in [0,1]];return f

def body(f,index,**updates):
 v=json.loads(json.dumps(f['config']['exports'][index]));v['extracted_at']=(timezone.now()-timedelta(seconds=1)).isoformat();v.update(updates);return json.dumps(v)
def capture(f,index,key=None,**updates):return domain.capture(f['owner'],f['case'].pk,f['request'].pk,f['config']['exports'][index]['provider'],key or 'input-'+str(index),body(f,index,**updates),rev(f['case']))
def approve(f,item,key=None,verdict='approve'):
 from apps.finance.models import PayrollInput
 kind='input' if isinstance(item,PayrollInput) else 'run'
 return domain.review(f['reviewer'],f['case'].pk,kind,item.pk,verdict,key or kind+'-'+str(item.pk)+'-'+verdict,f['e']['payroll_review'].pk,rev(f['case']))
def combined(f,key='combine'):
 for i in f['inputs']:approve(f,i,key='source-'+str(i.pk)+'-'+key)
 r=domain.combine(f['preparer'],f['case'].pk,f['request'].pk,[i.pk for i in f['inputs']],key,rev(f['case']));return r
def pipeline(f,prefix='normal'):
 c=combined(f,prefix+'-combine');approve(f,c)
 m=domain.match(f['preparer'],f['case'].pk,c.pk,f['hr'].pk,prefix+'-match',rev(f['case']));approve(f,m)
 a=domain.aggregate(f['preparer'],f['case'].pk,m.pk,prefix+'-aggregate',rev(f['case']));approve(f,a)
 p=domain.publish(f['preparer'],f['case'].pk,a.pk,prefix+'-publish',rev(f['case']));return c,m,a,p
