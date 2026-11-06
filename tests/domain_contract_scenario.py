"""Actual PostgreSQL/control services and HTTP; provider responses are synthetic."""
import os,sys,json,copy
from datetime import timedelta
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread,Barrier
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import django
django.setup()
from django.conf import settings
from django.utils import timezone
from django.db import transaction,DatabaseError,connection,close_old_connections
from django.test import Client
from django.urls import reverse
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import add_evidence
from apps.core.models import Case
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.domain_contract_validators import COMPONENT,SCHEMA,validate_reference
from apps.workflows import domain_contracts as d
from apps.agents import domain_contracts as agent
from apps.agents.models import AgentRun
from apps.documents.contracts import digest
from adapters import domain_contracts as adapter
from tests import reconstitution_scenario as prior

v={};stage=None;check=prior.check

class Provider(BaseHTTPRequestHandler):
    calls=0;mode='present';last_request=None
    def log_message(self,*args):pass
    def do_POST(self):
        if self.headers.get('Authorization')!='Bearer synthetic-domain-secret':
            self.send_response(403);self.end_headers();return
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        Provider.calls+=1;Provider.last_request=request;now=timezone.now()
        result={'request_sha256':digest(request),'provider_ref':'fixture-provider','principal_ref':'principal:fixture-domain',
            'contract_version':request['format'],'observed_at':(now-timedelta(seconds=1)).isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat()}
        if self.path=='/domain-receipts/verify':
            outcome=Provider.mode if Provider.mode in ['present','unknown','conflict'] else 'present'
            result.update(outcome=outcome,receipt_ref='fixture-receipt' if outcome=='present' else None,
                receipt_sha256=digest({'fixture':'receipt'}) if outcome=='present' else None)
        elif self.path=='/destinations/preflight':
            result.update(prerequisites={k:'verified' if value else 'missing' for k,value in request['prerequisites'].items()},activation_enabled=False,provisioning_executed=False)
        else:self.send_response(404);self.end_headers();return
        if Provider.mode=='wrong-request':result['request_sha256']='0'*64
        if Provider.mode=='expired':result['expires_at']=(now-timedelta(seconds=1)).isoformat()
        data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)

def registry(server):
    settings.READINESS_ENDPOINTS={'endpoint:fixture-domain':{'url':f'http://127.0.0.1:{server.server_port}','classification':'synthetic'}}
    settings.READINESS_SECRET_REFS={'secret:fixture-domain':{'env':'PSL_TEST_DOMAIN_SECRET','revision':'fixture-v1'}}
    os.environ['PSL_TEST_DOMAIN_SECRET']='synthetic-domain-secret'

def fixture():
    a,b,c,p,_=prior.fixture()
    for actor in [a,b]:
        for action in ['reconstitution.domain.handoff.verify','reconstitution.domain.handoff.review','reconstitution.destination.verify','reconstitution.destination.review']:
            Grant.objects.get_or_create(user=actor,case=c,action=action)
    client=Client();client.force_login(a)
    response=client.post(reverse('domain_contracts',args=[c.pk]),{'action':'evidence',
        'body':'Synthetic owned metadata protocol and intended destination; no vendor contract','source':'synthetic:domain-contract'})
    check.assertEqual(response.status_code,302)
    evidence=c.evidence.filter(kind='integration_contract').latest('pk')
    common={'implementation':'authenticated_json_v1','target_key':'endpoint:fixture-domain','credential_ref':'secret:fixture-domain',
        'credential_revision':'fixture-v1','principal_ref':'principal:fixture-domain','provider_ref':'fixture-provider'}
    provider={**common,'contract_version':'psl.domain-receipt/v1','family':'handoff','source_payload_version':'psl.milestone-handoff/v1',
        'operation_mapping':'sha256_original_operation_key_v1','intent_mapping':'postgres_jsonb_archived_job_row_sha256_v1',
        'evidence_semantics':'authenticated_remote_receipt_claim','source_owner_ref':'fixture-finance-owner'}
    destination={**common,'contract_version':'psl.destination-preflight/v1','destination_ref':p.payload['destination_ref'],
        **{k+'_ref':'fixture:'+k for k in adapter.PREREQUISITES},'activation_enabled':False,'archived_authority_accepted':False}
    destination['outbound_ref']=None
    criteria={'operator_id':a.pk,'operator_role':'PM','reviewer_id':b.pk,'reviewer_role':'PMO','allowed_provider_refs':['fixture-provider'],
        'destination_ref':p.payload['destination_ref'],'review_valid_seconds':3600,'observation_valid_seconds':3600,'allow_synthetic':True,'activation_mode':'reviewed_preflight_only'}
    return a,b,c,p,evidence,provider,destination,criteria

def configure(a,c,criteria):
    cfg=draft_operator_policy(a,c.pk,COMPONENT,criteria,v['evidence'],timezone.now()-timedelta(seconds=1))
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active');return cfg

def connected():
    a,b,c,p,e,provider,destination,criteria=fixture()
    r=agent.prepare(a,c.pk,p.pk,'provider','provider',provider,e.pk)
    with check.assertRaises(ValidationError):d.probe(a,c.pk,r.pk,'missing-policy',p.payload['inventory']['effects'][0]['effect_key'])
    client=Client();client.force_login(a);url=reverse('domain_contracts',args=[c.pk])
    response=client.get(url);check.assertContains(response,'MISSING');check.assertEqual(response['Cache-Control'],'no-store')
    configure(a,c,criteria)
    with check.assertRaises(PermissionDenied):d.review(a,c.pk,r.pk,'approve','Self review rejected','self')
    with check.assertRaises(ValidationError):d.probe(a,c.pk,r.pk,'unreviewed',p.payload['inventory']['effects'][0]['effect_key'])
    d.review(b,c.pk,r.pk,'approve','Synthetic source-owner receipt protocol review','contract-review')
    row=next(x for x in p.payload['inventory']['effects'] if x['family']=='handoff' and x['status']=='unknown')
    Provider.mode='unknown';o=d.probe(a,c.pk,r.pk,'unknown',row['effect_key'])
    check.assertEqual(o.result['outcome'],'unknown');check.assertFalse(o.result['direct_vendor_verification'])
    check.assertEqual(o.request['effect']['intent_sha256'],row['intent_sha256'])
    Provider.mode='conflict';conflict=d.probe(a,c.pk,r.pk,'conflict',row['effect_key'])
    check.assertEqual(conflict.result['outcome'],'conflict');check.assertIsNone(conflict.result['receipt_sha256'])
    Provider.mode='present';barrier=Barrier(2);calls=Provider.calls
    def concurrent_probe(_):
        close_old_connections()
        try:
            barrier.wait(timeout=30)
            return d.probe(a,c.pk,r.pk,'present',row['effect_key']).pk
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(concurrent_probe,range(2)))
    check.assertEqual(ids[0],ids[1]);check.assertEqual(Provider.calls,calls+1)
    present=d.probe(a,c.pk,r.pk,'present',row['effect_key'])
    calls=Provider.calls;check.assertEqual(d.probe(a,c.pk,r.pk,'present',row['effect_key']).pk,present.pk);check.assertEqual(Provider.calls,calls)
    d.review(b,c.pk,r.pk,'approve','Synthetic source-owned reviewed receipt claim, no retry authorization','observation-review',present.pk)
    result=d.report(a,c.pk,r.pk);check.assertTrue(result['observations'][-1]['human_review_current'])
    with transaction.atomic(),patch('apps.workflows.domain_contracts.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
        with check.assertRaises(ValidationError):d.reviewed(a,r,present.pin,criteria,present)
    dest=d.capture(a,c.pk,p.pk,'destination','destination',destination,e.pk)
    d.review(b,c.pk,dest.pk,'approve','Synthetic intended destination with missing outbound contract','dest-review')
    preflight=d.probe(a,c.pk,dest.pk,'preflight');check.assertEqual(preflight.result['prerequisites']['outbound'],'missing')
    d.review(b,c.pk,dest.pk,'approve','Reviewed missing outbound prerequisite; dependent activation held','preflight-review',preflight.pk)
    count=AgentRun.objects.count();analysis=agent.investigate(a,c.pk,dest.pk)
    check.assertEqual(analysis['effect_tools'],[]);check.assertTrue(any('outbound: missing' in x for x in analysis['next_steps']));check.assertEqual(AgentRun.objects.count(),count)
    response=client.post(url,{'action':'investigate','contract':dest.pk});check.assertEqual(response.status_code,200)
    check.assertNotIn('CONFIDENTIAL RESTORED SOURCE BODY',response.content.decode());check.assertNotIn('synthetic-domain-secret',response.content.decode())
    with transaction.atomic():
        for table,pk in [('workflows_domaincontract',r.pk),('workflows_domainobservation',o.pk),('workflows_domaincontractreview',d.Review.objects.filter(contract=r).first().pk)]:
            with check.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(f'DELETE FROM {table} WHERE id=%s',[pk])
    with check.assertRaises(DatabaseError),transaction.atomic():
        d.Observation.objects.create(contract=r,operation_key='forged',effect_key=present.effect_key,request=present.request,
            result={**present.result,'activation_enabled':True},pin=present.pin,actor=a)
    return {'unknown_preserved':True,'destination_reviewed':True,'activation_enabled':False,'contract':r.pk,'observations':4,'plan':p.pk}

def negatives():
    a,b,c,p,e,provider,destination,criteria=fixture();cfg=configure(a,c,criteria)
    for change in [{'reviewer_id':a.pk},{'observation_valid_seconds':0},{'activation_mode':'enable'},{'allow_synthetic':False}]:
        with check.assertRaises(ValidationError):validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content={**criteria,**change}),c)
    validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content=criteria),c)
    r=d.capture(a,c.pk,p.pk,'provider','provider',provider,e.pk);d.review(b,c.pk,r.pk,'approve','Synthetic source-owner approval','approve')
    row=next(x for x in p.payload['inventory']['effects'] if x['family']=='handoff')
    # Closed malformed/binding-invalid results cannot become observations.
    for mode in ['wrong-request','expired']:
        Provider.mode=mode
        with check.assertRaises(ValidationError):d.probe(a,c.pk,r.pk,mode,row['effect_key'])
    Provider.mode='present'
    foreign=Case.objects.create(tenant=c.tenant,title='Other control case',kind='project',synthetic=True)
    client=Client();client.force_login(a)
    check.assertEqual(client.get(reverse('domain_contract_report',args=[foreign.pk,r.pk])).status_code,404)
    with check.assertRaises(d.Contract.DoesNotExist):d.probe(a,foreign.pk,r.pk,'foreign',row['effect_key'])
    os.environ['PSL_TEST_DOMAIN_SECRET']='rotated-fixture-secret'
    with check.assertRaises(ValidationError):d.probe(a,c.pk,r.pk,'rotated',row['effect_key'])
    # Rotation remains; a successor must be explicitly reviewed. No old review is renewed.
    successor=d.capture(a,c.pk,p.pk,'provider','provider',{**provider,'source_payload_version':'psl.milestone-handoff/v2'},e.pk,r.pk)
    with check.assertRaises(ValidationError):d.probe(a,c.pk,r.pk,'superseded',row['effect_key'])
    with check.assertRaises(ValidationError):d.capture(a,c.pk,p.pk,'provider','provider',provider,e.pk,r.pk)
    with check.assertRaises(DatabaseError),transaction.atomic():
        with connection.cursor() as cursor:cursor.execute('UPDATE workflows_domaincontract SET payload=%s WHERE id=%s',[json.dumps(provider),successor.pk])
    Grant.objects.filter(user=b,case=c,action='reconstitution.domain.handoff.review').update(active=False)
    with check.assertRaises(PermissionDenied):d.review(b,c.pk,successor.pk,'approve','Revoked owner','revoked')
    transition(a,cfg.pk,'revoked')
    check.assertEqual(d.report(a,c.pk,successor.pk)['policy_status'],'REVOKED')
    return {'sql_guards':True,'rotation_held':True,'foreign_scope_held':True}

@transaction.atomic
def restart():
    from django.contrib.auth import get_user_model
    a=get_user_model().objects.get(pk=v['operator']);r=d.get(a,v['case'],v['contract'])
    return {'persisted':r.plan_id==v['plan'],'observations':d.Observation.objects.filter(contract__plan=r.plan).count()}

if __name__=='__main__':
    v=json.load(sys.stdin);stage=sys.argv[1];prior.v=v;prior.old.v=v;settings.COLD_RECOVERY=prior.old.runtime()
    server=ThreadingHTTPServer(('127.0.0.1',0),Provider);thread=Thread(target=server.serve_forever,daemon=True);thread.start();registry(server)
    try:result=globals()[stage]()
    finally:server.shutdown();server.server_close();thread.join()
    print(json.dumps(result))
