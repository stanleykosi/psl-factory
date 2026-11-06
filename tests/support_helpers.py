import json,copy
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.support_drafts import draft_support_policy
from apps.policy.support_validators import INTAKE,FLOW,AUTH,METRICS
from apps.baas import support as d
from .helpers import setup_case,activate,rev

def evidence(f,kind,body='Explicit synthetic support evidence; not actual owner acceptance'):
 return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(body) if isinstance(body,dict) else body,'synthetic:support')
def policy(f,key,value):
 p=draft_support_policy(f['actor'],f['case'].pk,key,value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

def fixture(prefix='support',people=None,configured=True):
 if people:
  a,b,s=people;c=Case.objects.create(tenant='test-tenant',title='Synthetic support flow',kind='support',synthetic=True)
 else:
  a,c=setup_case(kind='support',username=prefix+'-preparer');b=get_user_model().objects.create_user(username=prefix+'-reviewer');s=get_user_model().objects.create_user(username=prefix+'-specialist')
 for p in [a,b,s]:
  Grant.objects.bulk_create([Grant(case=c,user=p,action=action) for action in ACTIONS],ignore_conflicts=True)
 f={'actor':a,'case':c,'reviewer':b,'specialist':s,'e':{},'t':timezone.now()-timedelta(hours=1)}
 for kind in ['policy_decision','support_review','support_triage','support_start','support_transition','support_response','support_report','support_merge','support_migration']:f['e'][kind]=evidence(f,kind)
 refs=[]
 for p,role in [(a,'Support'),(b,'Support'),(s,'Engineering')]:refs.append(register_reference(a,c.pk,'support-role:'+str(p.pk),'schema:psl/role-assignment/v1',{'role':role,'user_id':p.pk},f['e']['policy_decision'].pk).ref)
 activate(a,c,'D05.role_principal_assignments',refs,f['e']['policy_decision'])
 v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/support-flow.json').read_text(encoding='utf-8'));v['flow']['specification_evidence_id']=f['e']['policy_decision'].pk
 for row,p in zip(v['authority']['assignments'],[a,b,s]):row['user_id']=p.pk
 v['message'].update(message_ref=prefix+'-MSG-1',received_at=f['t'].isoformat());f['v']=v;f['policies']={}
 if configured:
  for k,key in [(INTAKE,'intake'),(FLOW,'flow'),(AUTH,'authority'),(METRICS,'metrics')]:f['policies'][k]=policy(f,k,v[key])
 return f

def capture(f,changes=None):
 body=copy.deepcopy(f['v']['message']);body.update(changes or {});e=evidence(f,'support_intake',body);return d.capture(f['actor'],f['case'].pk,e.pk,rev(f['case']))
def ready(f):
 i=capture(f);d.link(f['actor'],f['case'].pk,i.pk,f['e']['support_triage'].pk,rev(f['case']));d.review_flow(f['reviewer'],f['case'].pk,f['e']['support_review'].pk,'approve',rev(f['case']));return d.start(f['actor'],f['case'].pk,f['actor'].pk,f['e']['support_start'].pk,f['t'].isoformat(),rev(f['case']))
def act(f,action,at=None):
 return d.transition(f['actor'],f['case'].pk,action,f['actor'].pk,f['e']['support_response' if action=='respond' else 'support_transition'].pk,(at or timezone.now()).isoformat(),rev(f['case']))
def result(f,pending,status='resolved',kind='backend_reference',request_id=None,verification_id=None):
 e=evidence(f,'support_specialist_result',{'status':status,'kind':kind,'reference':'SPECIALIST-1','corrective_request_id':request_id,'verification_id':verification_id});return d.specialist_result(f['specialist'],f['case'].pk,pending.pk,e.pk,rev(f['case']))
def report(f,reviewed=True):
 r=d.prepare_report(f['actor'],f['case'].pk,f['e']['support_report'].pk,rev(f['case']))
 if reviewed:d.review_report(f['reviewer'],f['case'].pk,r.pk,f['e']['support_review'].pk,'approve',rev(f['case']))
 return r

def owner_package(f):
 from apps.documents import validation as av
 from apps.policy.validation_drafts import draft_validation_policy
 from apps.policy.validation_validators import OWNER,ACCEPTANCE
 a,c=f['actor'],f['case'];spec=f['e']['policy_decision']
 def activate_validation(key,value):
  p=draft_validation_policy(a,c.pk,key,value,spec.pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active');return p
 activate_validation(OWNER,{'human_only':True,'assignments':[{'user_id':a.pk,'role':'Support','process_ids':['B14'],'purposes':['meaning','expectations']},{'user_id':f['reviewer'].pk,'role':'Support','process_ids':['B14'],'purposes':['acceptance']}],'allow_preparer_review':True})
 activate_validation(ACCEPTANCE,{'allowed_levels':['definition'],'independent_tester':True,'independent_acceptor':True})
 metadata={'document_kind':'other','source_version':'synthetic-v1','source_date':None,'owner_label':'Synthetic Support','classification':'proposed_design','process_ids':['B14'],'clauses':[]}
 src=av.capture_source(a,c.pk,'support-flow-spec',spec.pk,metadata,rev(c));examples=[]
 for kind in ['normal','exception']:
  e=evidence(f,'validation_example','Synthetic B14 '+kind);examples.append(av.capture_example(a,c.pk,'b14-'+kind,['B14'],kind,{'held':kind=='exception'},e.pk,rev(c)))
 payload={'process_ids':['B14'],'source_ids':[src.pk],'example_ids':[e.pk for e in examples],'policy_components':[],'level':'definition','purpose':'P15','gaps':[],'build_ref':'','role_list':[],'manual_fallback':'','rollout_plan':'','migration_plan':'','support_owner_id':a.pk}
 package=av.prepare_package(a,c.pk,'B14-owner-flow',payload,spec.pk,rev(c))
 for kind,person in [('meaning',a),('expectations',a),('acceptance',f['reviewer'])]:av.review(person,c.pk,package.pk,kind,'approve','support-'+kind,spec.pk,'Explicit synthetic owner definition review',rev(c))
 flow=copy.deepcopy(f['v']['flow']);flow.update(validation_mode='af13_required',validation_package_id=package.pk);policy(f,FLOW,flow);return package
