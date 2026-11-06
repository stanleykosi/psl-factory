import json
from copy import deepcopy
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from apps.core.services import add_evidence
from apps.policy.services import transition,register_reference
from apps.policy.bu_drafts import draft_bu_policy
from apps.policy.bu_validators import STAFF,SOURCE,MAPPING,AUTH,DISCLOSE
from apps.finance import bu as domain,payroll
from .payroll_helpers import fixture as payroll_fixture,combined,approve
from .helpers import rev,activate
from .finance_analysis_helpers import policy as finance_policy

def policy(f,key,value):
 p=draft_bu_policy(f['preparer'],f['case'].pk,key,value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['preparer'],p.pk,'validated');transition(f['preparer'],p.pk,'active');return p

def configure(f,catalogue=True):
 c=f['case'];a=f['preparer'];e=f['e']
 from apps.identity.models import Grant
 for action in ['bu.read','bu.report.read','bu.receive']:Grant.objects.get_or_create(case=c,user=f['manager'],action=action)
 for kind in ['bu_review','bu_pool_contract','bu_source_contract','bu_design_decision']:e[kind]=add_evidence(a,c.pk,kind,'EXPLICIT SYNTHETIC '+kind+' safe metadata only','synthetic:bu')
 v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/bu.json').read_text(encoding='utf-8'))
 v['staff']['pool_contract_evidence_id']=e['bu_pool_contract'].pk;v['source'].update(owner_id=a.pk,reader_ids=sorted({a.pk,f['reviewer'].pk}),source_contract_evidence_id=e['bu_source_contract'].pk,design_decision_evidence_id=e['bu_design_decision'].pk)
 v['authority']['assignments'][0]['user_id']=f['reviewer'].pk;v['authority']['assignments'][1]['user_id']=a.pk;v['disclosure']['recipient_ids']=[f['manager'].pk];v['exception']['rationale_evidence_id']=e['bu_review'].pk
 f['bu_config']=v;f['bu_policies']={k:policy(f,k,v[n]) for k,n in [(STAFF,'staff'),(SOURCE,'source'),(MAPPING,'mapping'),(AUTH,'authority'),(DISCLOSE,'disclosure')]}
 if catalogue:finance_policy(a,c,'D10.report_category_effective_dates',[{'key':b,'name':b,'entity':'synthetic-company','from_period':'2026-09','to_period':'2026-10'} for b in ['BU-A','BU-B']],e['policy_decision'])
 return f

def fixture():
 f=payroll_fixture(employee_ids=['E900','E002']);configure(f);c=combined(f);approve(f,c)
 m=payroll.match(f['preparer'],f['case'].pk,c.pk,f['hr'].pk,'BU-match',rev(f['case']));approve(f,m);f['match']=m;return f

def review(f,w,verdict='approve',purpose=None,key=None):
 return domain.review(f['reviewer'],f['case'].pk,w.pk,purpose or w.kind,verdict,key or str(w.pk)+'-'+(purpose or w.kind)+'-'+verdict,f['e']['bu_review'].pk,rev(f['case']))

def rule(f,key='exception',**updates):
 value=deepcopy(f['bu_config']['exception']);value.update(updates)
 return domain.rule(f['preparer'],f['case'].pk,f['match'].pk,'E900-BASIC',key,value,rev(f['case']))

def staff(f,key='staff',rules=None,declared=None):
 if rules is None:r=rule(f);review(f,r);rules=[r.pk]
 return domain.staff(f['preparer'],f['case'].pk,f['match'].pk,'staff-report',key,[['E900','BASIC']] if declared is None else declared,rules,rev(f['case']))

def body(f,**updates):
 v=deepcopy(f['bu_config']['export']);v['extracted_at']=(timezone.now()-timedelta(seconds=1)).isoformat();v.update(updates);return json.dumps(v)

def source(f,key='events',reference='events',**updates):
 scope={k:f['bu_config']['export'][k] for k in ['entity','period','currency']}
 return domain.capture(f['preparer'],f['case'].pk,reference,key,scope,body(f,**updates),rev(f['case']))

def event(f,key='event',s=None,comparison=None):
 s=s or source(f);review(f,s)
 return domain.attribute(f['preparer'],f['case'].pk,s.pk,'event-report',key,rev(f['case']),comparison)

def publish(f,w):
 review(f,w)
 if w.metadata.get('historical'):review(f,w,purpose='historical')
 return domain.publish(f['preparer'],f['case'].pk,w.pk,'publish-'+str(w.pk),rev(f['case']))
