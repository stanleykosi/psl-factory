import copy,json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.costing_drafts import draft_costing_policy
from apps.policy.costing_validators import COMPONENT
from apps.pmo import costing as d
from apps.documents.contracts import digest
from .helpers import setup_case,project_evidence,activate,rev

def evidence(f,kind,body='EXPLICIT SYNTHETIC costing evidence'):
    return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(body) if isinstance(body,(dict,list)) else body,'synthetic:p14')

def policy(f,value=None):
    p=draft_costing_policy(f['actor'],f['case'].pk,value or f['policy_value'],f['sources']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

def review(f,oracle=None,verdict='confirm',key=None,actor=None):
    return d.review(actor or (f['tester'] if oracle else f['owner']),f['case'].pk,f['rule'].pk,oracle.pk if oracle else None,verdict,key or verdict+'-'+str(oracle.pk if oracle else 'rule'),f['review_evidence'].pk)

def fixture(configured=True):
    a,c=setup_case();sources=project_evidence(a,c);people={}
    for key in ['owner','tester']:
        u=get_user_model().objects.create_user(username='costing-'+key);Grant.objects.bulk_create([Grant(case=c,user=u,action=x) for x in ACTIONS]);people[key]=u
    f={'actor':a,'case':c,'sources':sources,**people};refs=[]
    for u,role in [(a,'PM'),(a,'Head of PMO'),(a,'CEO'),(a,'PMO Lead'),(people['owner'],'PMO'),(people['tester'],'Finance')]:refs.append(register_reference(a,c.pk,'cost-role:'+str(u.pk)+':'+role.replace(' ','-'),'schema:psl/role-assignment/v1',{'role':role,'user_id':u.pk},sources['policy_decision'].pk).ref)
    activate(a,c,'D05.role_principal_assignments',refs,sources['policy_decision'])
    v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/commercial-costing.json').read_text(encoding='utf-8'));f['values']=v
    r=copy.deepcopy(v['rule']);r.update(owner_id=f['owner'].pk,oracle_owner_id=f['tester'].pk);r['parameters'][0]['evidence_id']=evidence(f,'p14_parameter').pk
    f['rule']=d.capture_rule(a,c.pk,'calculator',evidence(f,'p14_rule',r).pk);f['review_evidence']=evidence(f,'p14_review');rr=review(f)
    o={'rule_sha256':f['rule'].sha256,'calculator_ref':r['calculator_ref'],'calculator_version':r['calculator_version'],'source_class':'synthetic_fixture','source_locator':'independently-entered-example-fixture','scenarios':copy.deepcopy(v['scenarios'])}
    f['oracle']=d.capture_oracle(f['tester'],c.pk,f['rule'].pk,'independent',evidence(f,'p14_oracle',o).pk);orr=review(f,f['oracle']);f['policy_value']={'rule_id':f['rule'].pk,'rule_sha256':f['rule'].sha256,'rule_review_id':rr.pk,'oracle_id':f['oracle'].pk,'oracle_sha256':f['oracle'].sha256,'oracle_review_id':orr.pk}
    if configured:f['policy']=policy(f)
    f['inputs']=evidence(f,'p14_inputs',v['scenarios'][0]['inputs']);return f

def run(f,inputs=None,key='calculation'):
    s=f['sources'];return d.run(f['actor'],f['case'].pk,s['plan'].pk,s['engineering_estimate'].pk,s['security_estimate'].pk,(inputs or f['inputs']).pk,key)

def package(f):
    from apps.documents import validation as af
    from apps.policy.validation_validators import OWNER
    from .validation_helpers import values,policy as af_policy
    c=f['case'];a=f['actor'];v=values();e=f['sources']['policy_decision']
    auth={'human_only':True,'allow_preparer_review':False,'assignments':[{'user_id':f['owner'].pk,'role':'PMO','process_ids':['P14'],'purposes':['meaning','expectations']}]};af_policy(a,c,OWNER,auth,e)
    metadata=copy.deepcopy(v['metadata']);metadata.update(process_ids=['P14'],clauses=[],classification='proposed_design',document_kind='walkthrough')
    source=af.capture_source(a,c.pk,'p14-summary',evidence(f,'procedure_source','Explicit synthetic calculator evidence discovery, not native workbook verification').pk,metadata,rev(c));examples=[]
    for index,x in enumerate(f['oracle'].payload['scenarios'],1):
        expected={'oracle_sha256':f['oracle'].sha256,'scenario_sha256':digest(x)}
        examples.append(af.capture_example(a,c.pk,'example-'+str(index),['P14'],x['scenario'],expected,evidence(f,'validation_example').pk,rev(c)))
    payload=dict(v['package'],process_ids=['P14'],source_ids=[source.pk],example_ids=[x.pk for x in examples],policy_components=[COMPONENT],support_owner_id=a.pk)
    p=af.prepare_package(a,c.pk,'p14-package',payload,e.pk,rev(c))
    for kind in ['meaning','expectations']:af.review(f['owner'],c.pk,p.pk,kind,'approve',kind,e.pk,'Exact synthetic P14 scope',rev(c))
    return p
