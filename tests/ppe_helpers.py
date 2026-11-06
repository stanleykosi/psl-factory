import copy,json
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from apps.policy.ppe_drafts import draft_ppe_policy
from apps.policy.services import transition
from apps.policy.ppe_validators import SOURCE,CALC,AUTH
from apps.finance import ppe
from .schedule_helpers import fixture as schedule_fixture,evidence
from .helpers import rev
def values():return json.loads((Path(__file__).resolve().parent.parent/'fixtures/ppe.json').read_text(encoding='utf-8'))
def policy(f,key,value):
 p=draft_ppe_policy(f['actor'],f['case'].pk,key,value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p
def fixture(username='human',reviewer_username='schedule-reviewer',recipient_username='finance-reader'):
 f=schedule_fixture(username,reviewer_username,recipient_username);v=values();f['ppe']=v
 for kind in ['ppe_opening','ppe_classification','ppe_event','ppe_policy','ppe_basis_explanation']:f['e'][kind]=evidence(f,kind,'Explicit synthetic '+kind+' evidence; not native or actual owner acceptance')
 v['body']['opening_evidence_id']=f['e']['ppe_opening'].pk;v['body']['assets'][0]['classification_evidence_id']=f['e']['ppe_classification'].pk;v['body']['extracted_at']=(timezone.now()-timedelta(minutes=1)).isoformat();v['calculation']['rules'][0]['method_evidence_id']=f['e']['ppe_policy'].pk;v['authority']['assignments'][0]['user_id']=f['reviewer'].pk
 for key,value in [(SOURCE,v['source']),(CALC,v['calculation']),(AUTH,v['authority'])]:policy(f,key,value)
 f['register']=capture(f);review(f,f['register'],'register');return f
def capture(f,body=None,reference='asset-register-oct'):
 body=copy.deepcopy(body if body is not None else f['ppe']['body']);e=evidence(f,'ppe_register',json.dumps(body));return ppe.capture(f['actor'],f['case'].pk,reference,e.pk,rev(f['case']))
def prepare(f,register=None,reference='ppe-oct',prior=None,ledger=True):return ppe.prepare(f['actor'],f['case'].pk,reference,(register or f['register']).pk,prior.pk if prior else None,f['parent'].pk if ledger else None,rev(f['case']))
def review(f,w,purpose='schedule',verdict='approve'):
 return ppe.review(f['reviewer'],f['case'].pk,w.pk,purpose,verdict,f['e']['ppe_basis_explanation' if purpose=='basis' else 'finance_review'].pk,'Explicit synthetic Finance '+purpose+' decision',rev(f['case']))
def owner_package(f):
 from apps.documents import validation as av
 from apps.policy.validation_drafts import draft_validation_policy
 from apps.policy.validation_validators import OWNER,ACCEPTANCE
 a,c=f['actor'],f['case'];e=f['e']['policy_decision'];b=f['reviewer']
 for key,value in [(OWNER,{'human_only':True,'allow_preparer_review':True,'assignments':[{'user_id':a.pk,'role':'Finance','process_ids':['F07'],'purposes':['meaning','expectations']},{'user_id':b.pk,'role':'Finance','process_ids':['F07'],'purposes':['acceptance']}]}),(ACCEPTANCE,{'allowed_levels':['definition'],'independent_tester':True,'independent_acceptor':True})]:
  p=draft_validation_policy(a,c.pk,key,value,e.pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active')
 s=av.capture_source(a,c.pk,'ppe-method',f['e']['ppe_policy'].pk,{'document_kind':'other','source_version':'synthetic-1','source_date':None,'owner_label':'Synthetic Finance','classification':'proposed_design','process_ids':['F07'],'clauses':[]},rev(c));examples=[]
 for scenario,output in [('normal',{'charge':'100.00','book_value':'500.00'}),('exception',{'life':None,'charge':None,'state':'held'})]:
  ex=evidence(f,'validation_example','Explicit synthetic '+scenario);examples.append(av.capture_example(a,c.pk,'ppe-'+scenario,['F07'],scenario,output,ex.pk,rev(c)))
 payload={'process_ids':['F07'],'source_ids':[s.pk],'example_ids':[x.pk for x in examples],'policy_components':[CALC],'level':'definition','purpose':'P15','gaps':[],'build_ref':'','role_list':[],'manual_fallback':'','rollout_plan':'','migration_plan':'','support_owner_id':None}
 p=av.prepare_package(a,c.pk,'ppe-policy',payload,e.pk,rev(c))
 for kind,actor in [('meaning',a),('expectations',a),('acceptance',b)]:av.review(actor,c.pk,p.pk,kind,'approve','ppe-'+kind,e.pk,'Explicit synthetic method definition review',rev(c))
 source=copy.deepcopy(f['ppe']['source']);source.update(validation_requirement='af13_required',validation_package_id=p.pk);policy(f,SOURCE,source);return p
