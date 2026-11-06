import json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.policy.services import register_reference,transition
from apps.policy.validation_drafts import draft_validation_policy
from apps.policy.validation_validators import OWNER,ACCEPTANCE
from apps.documents import validation as domain
from .helpers import setup_case,rev,activate

FIXTURE=Path(__file__).resolve().parent.parent/'fixtures/evidence-validation.json'
def values():return json.loads(FIXTURE.read_text(encoding='utf-8'))
def evidence(a,c,kind='owner_validation',body='Synthetic owner evidence'):return add_evidence(a,c.pk,kind,body,'synthetic:validation-tests')
def policy(a,c,key,value,e):
    r=draft_validation_policy(a,c.pk,key,value,e.pk,timezone.now()-timedelta(seconds=1));transition(a,r.pk,'validated');transition(a,r.pk,'active');return r

def fixture(kind='project',synthetic=True):
    a,c=setup_case(kind=kind,synthetic=synthetic);e=evidence(a,c,'policy_decision','Synthetic owner nomination only')
    people={}
    for name,actions in [('owner',['validation.review']),('tester',['validation.replay.record']),('acceptor',['validation.accept','validation.export'])]:
        p=get_user_model().objects.create_user(username='validation-'+name,password='test-only')
        for action in ['case.read','validation.read']+actions:Grant.objects.create(user=p,case=c,action=action)
        people[name]=p
    refs=[]
    for name,role in [('owner','PMO'),('acceptor','Head of PMO')]:
        r=register_reference(a,c.pk,'validation-role:'+name,'schema:psl/role-assignment/v1',{'user_id':people[name].pk,'role':role},e.pk);refs.append(r.ref)
    activate(a,c,'D05.role_principal_assignments',refs,e)
    f=values();f['authority']['assignments'][0]['user_id']=people['owner'].pk;f['authority']['assignments'][1]['user_id']=people['acceptor'].pk
    policy(a,c,OWNER,f['authority'],e);policy(a,c,ACCEPTANCE,f['acceptance'],e)
    src_e=evidence(a,c,'procedure_source','A payment exception does not waive debt.\nSource receipt is not implementation acceptance.')
    source=domain.capture_source(a,c.pk,'SOP',src_e.pk,f['metadata'],rev(c))
    examples=[]
    for kind,expected in [('normal',{'permitted':True}),('exception',{'permitted':False})]:
        ex=evidence(a,c,'validation_example','Independent synthetic '+kind+' example')
        examples.append(domain.capture_example(a,c.pk,kind,f['package']['process_ids'],kind,expected,ex.pk,rev(c)))
    payload=dict(f['package'],source_ids=[source.pk],example_ids=[r.pk for r in examples],support_owner_id=a.pk)
    p=domain.prepare_package(a,c.pk,'review-scope',payload,e.pk,rev(c))
    return {'actor':a,'case':c,**people,'decision_evidence':e,'source':source,'examples':examples,'package':p,'config':f}

def review(f,kind='meaning',verdict='approve',key=None):
    actor=f['acceptor'] if kind=='acceptance' else f['owner']
    return domain.review(actor,f['case'].pk,f['package'].pk,kind,verdict,key or kind+'-'+verdict,f['decision_evidence'].pk,'Exact synthetic owner review',rev(f['case']))
def replays(f,wrong=False):
    result=[]
    for ex in f['examples']:
        value=dict(f['config']['replay'],example_id=ex.pk,actual={'permitted':'wrong'} if wrong else ex.expected)
        e=evidence(f['actor'],f['case'],'validation_result',json.dumps(value));result.append(domain.record_replay(f['tester'],f['case'].pk,f['package'].pk,e.pk,'result-'+str(e.pk),rev(f['case'])))
    return result
def ready(f):review(f);review(f,'expectations');return replays(f)
