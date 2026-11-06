import copy,json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import connection
from django.conf import settings
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.operator_validators import OPERATOR,PROTECTION
from apps.workflows import protection as d,operator_delivery as worker
from apps.workflows.operator_inventory import bundle
from apps.workflows.operator_models import RecoveryArtifact
from adapters.operator_protection import provision_target
from .helpers import setup_case,project_evidence,activate

def provision_test_database():
    import psycopg
    from psycopg import sql
    name=settings.OPERATOR_DRILL_DATABASE
    assert name=='test_psl_drill_operators' and name!=connection.settings_dict['NAME']
    args=connection.get_connection_params()
    with psycopg.connect(**args,autocommit=True) as conn:
        if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',[name]).fetchone():conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    provision_target() # Never deletes an existing database or reinitialises operational data.

def evidence(f,kind,body='EXPLICIT SYNTHETIC operator evidence'):
    return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(body) if isinstance(body,(dict,list)) else body,'synthetic:operator-tests')
def policy(f,key,value):
    p=draft_operator_policy(f['actor'],f['case'].pk,key,value,f['sources']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p
def fixture(configured=True,known=True,prefix=None):
    a,c=setup_case(username=(prefix+'-actor') if prefix else 'human');b=get_user_model().objects.create_user(username=(prefix+'-reviewer') if prefix else 'operator-reviewer');Grant.objects.bulk_create([Grant(case=c,user=b,action=x) for x in ACTIONS]);s=project_evidence(a,c);refs=[]
    for u,role in [(a,'PM'),(b,'PMO')]:refs.append(register_reference(a,c.pk,'ops-role:'+str(u.pk),'schema:psl/role-assignment/v1',{'role':role,'user_id':u.pk},s['policy_decision'].pk).ref)
    activate(a,c,'D05.role_principal_assignments',refs,s['policy_decision']);f={'actor':a,'reviewer':b,'case':c,'sources':s};v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/operator-recovery.json').read_text(encoding='utf-8'));v['operator'].update(operators=[{'user_id':a.pk,'role':'PM','purposes':['recover','export','backup','restore','review']},{'user_id':b.pk,'role':'PMO','purposes':['review']}],reviewer_id=b.pk);f['values']=v
    if configured:f['policies']=[policy(f,k,value) for k,value in [(OPERATOR,v['operator']),(PROTECTION,v['protection'])]]
    manifest=bundle(a,c,200);from apps.documents.contracts import digest
    payload={'scope':'portable_case_metadata_v1','process_ids':['P13','P14'],'build_ref':'synthetic-ops-v1','source_ref':'case:'+str(c.pk),'source_version':'explicit-fixture-v1','target_ref':'isolated_metadata_db_v1','expected_record_count':len(manifest['evidence'])+len(manifest['jobs']) if known else None,'expected_manifest_sha256':digest(manifest) if known else None}
    f['plan']=d.capture_plan(a,c.pk,'recovery',payload,evidence(f,'ops_plan').pk);f['review_evidence']=evidence(f,'ops_review');return f
def effect(f,kind,input_id=None):
    j=worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,kind,input_id);worker.run_once();j.refresh_from_db()
    if j.status!='confirmed':raise AssertionError('Metadata effect failed: '+j.kind+'/'+j.status+'/'+j.error)
    return j,RecoveryArtifact.objects.get(job=j)
def connected(f):
    j,e=effect(f,'export');j,b=effect(f,'backup',e.pk);j,r=effect(f,'restore',b.pk);return e,b,r
def proof(f,kind='restore',changes=None,actor=None):
    p=f['plan'];v={'plan_id':p.pk,'plan_sha256':p.sha256,'kind':kind,'scope':p.payload['scope'],'system':'synthetic-ops','external_ref':str(f['case'].pk)+':'+kind,'receipt_version':'v1','source_ref':p.payload['source_ref'],'source_version':p.payload['source_version'],'target_ref':p.payload['target_ref'],'recorded_at':timezone.now().isoformat(),'outcome':'passed','evidence_class':'synthetic_report','record_count':p.payload['expected_record_count'],'manifest_sha256':p.payload['expected_manifest_sha256'],'elapsed_seconds':None,'source_lag_seconds':None};v.update(changes or {})
    return d.capture_proof(actor or f['actor'],f['case'].pk,p.pk,evidence(f,'ops_proof',v).pk)
