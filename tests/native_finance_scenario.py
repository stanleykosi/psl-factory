"""Real independent current Finance/PostgreSQL provider and control services; inputs synthetic."""
import os,sys,json,copy,base64
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from threading import Thread,Barrier
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import django
django.setup()
import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction,connection,DatabaseError,close_old_connections
from django.core.management import call_command
from django.core.exceptions import ValidationError,PermissionDenied
from django.test import Client,override_settings
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.native_finance_validators import COMPONENT,SCHEMA,validate_reference
from apps.workflows import native_finance as d
from apps.agents import native_finance as agent
from apps.agents.models import AgentRun
from adapters import native_finance as adapter,native_application_archive as n
from tests import domain_contract_scenario as domain

v=json.load(sys.stdin);stage=sys.argv[1];domain.v=v;domain.prior.v=v;domain.prior.old.v=v;check=domain.check
if stage!='provider_seed':settings.COLD_RECOVERY=domain.prior.old.runtime()

def provider_registry():
    os.environ['PSL_NATIVE_FINANCE_PASSWORD_FIXTURE']=connection.settings_dict.get('PASSWORD','')
    os.environ['PSL_NATIVE_FINANCE_IDENTITY_FIXTURE']=v['provider_identity']
    return {'database':v['provider_database'],'host':connection.settings_dict['HOST'],'port':int(connection.settings_dict['PORT']),
        'user':connection.settings_dict['USER'],'password_env':'PSL_NATIVE_FINANCE_PASSWORD_FIXTURE','credential_revision':'fixture-v1',
        'identity_ref':'fixture-current-finance','identity_secret_env':'PSL_NATIVE_FINANCE_IDENTITY_FIXTURE','classification':'synthetic',
        'sslmode':'disable','revision':'fixture-v1','case_ids':v.get('provider_case_ids',[])}

def provider_seed():
    from apps.core.management.commands.seed_demo import ACTIONS
    from apps.pmo.services import complete_milestone
    from apps.workflows.models import Outbox
    from adapters.finance import InternalFinanceAdapter
    from tests.helpers import signed,rev
    with n.connect(v['target']) as db:source_case=db.execute('SELECT case_id::text FROM workflows_outbox ORDER BY id LIMIT 1').fetchone()[0]
    a=get_user_model().objects.create_user(username='independent-current-finance-operator')
    c=Case.objects.create(id=source_case,tenant='test-tenant',title='Independent synthetic current provider',kind='project',synthetic=True)
    for action in ACTIONS:Grant.objects.create(user=a,case=c,action=action)
    ev=signed(a,c)
    names=['Confirmed source milestone','Uncertain source milestone','Pending source milestone']
    for i,name in enumerate(names):
        # Native fixture intentionally supplies a different second completion payload.
        evidence=add_evidence(a,c.pk,'completion','Different current-provider evidence','synthetic:provider-conflict') if i==1 else ev['completion']
        m=complete_milestone(a,c.pk,name,evidence.pk,rev(c));job=Outbox.objects.get(milestone=m)
        if i<2:InternalFinanceAdapter().deliver(job)
    cases=[source_case]
    if v.get('with_invoice_variants'):
        # Fresh current service graph with explicit incumbent fixture IDs, never restored rows/authority.
        get_user_model().objects.create_user(username='independent-second-human')
        get_user_model().objects.create_user(username='independent-private-human')
        from tests.invoice_variant_helpers import documents
        _,finance_case,_,_,_=documents(v['archive']['invoice_case_id']);cases.append(str(finance_case.pk))
    return {'provider_case_ids':cases}

def provider_initialize():
    settings.NATIVE_FINANCE={'providers':{'fixture-finance':provider_registry()},'stores':{}}
    call_command('initialize_native_finance_provider','fixture-finance',synthetic=True,verbosity=0)
    with check.assertRaises(Exception):call_command('initialize_native_finance_provider','fixture-finance',synthetic=True,verbosity=0)
    return {'initialized':True}

def fixture(configured=True):
    a,b,c,p,e,_,dest,domain_rules=domain.fixture()
    settings.NATIVE_FINANCE={'providers':{'fixture-finance':provider_registry()},'stores':{'fixture-companion':{'root':v['companion'],'revision':'fixture-v1'}}}
    for actor in [a,b]:
        for purpose in ['read','capture','operate','review','agent','configure']:
            Grant.objects.get_or_create(user=actor,case=c,action='reconstitution.native_finance.'+purpose)
        Grant.objects.get_or_create(user=actor,case=c,action='finance.handoff.read')
    # Each scenario explicitly provisions its current synthetic grant. The negative
    # scenario's revocation is tested in its own process and must not taint the next.
    Grant.objects.filter(user__in=[a,b],case=c,action='finance.handoff.read').update(active=True)
    values={'operator_id':a.pk,'operator_role':'PM','reviewer_id':b.pk,'reviewer_role':'PMO','provider_ref':'fixture-finance',
        'store_ref':'fixture-companion','destination_ref':p.payload['destination_ref'],'max_payload_bytes':1048576,'max_seconds':5,
        'observation_valid_seconds':3600,'review_valid_seconds':3600,'lease_seconds':300,'max_attempts':2,'allow_synthetic':True,'activation_mode':'inert_companion_only'}
    if configured:configure(a,c,values)
    return a,b,c,p,e,values,dest,domain_rules

def configure(a,c,values):
    cfg=draft_operator_policy(a,c.pk,COMPONENT,values,v['evidence'],timezone.now()-timedelta(seconds=1))
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active');return cfg

def mapping(a,c,p,e,index=0):
    rows=sorted((x for x in p.payload['inventory']['effects'] if x['family']=='handoff'),key=lambda x:x['job_id'])
    return d.capture(a,c.pk,p.pk,'mapping-'+str(index),rows[index]['effect_key'],'fixture-finance',e.pk)

def approved_mapping(a,b,c,m):d.review(b,c.pk,m.pk,'approve','Synthetic Finance source-owner exact original operation/payload mapping','mapping-review')

def controls():
    a,b,c,p,e,values,_,_=fixture(False);m=mapping(a,c,p,e)
    from adapters.reconstitution import ROUTES
    check.assertEqual(p.payload['inventory']['families'],sorted(ROUTES))
    with check.assertRaises(ValidationError):d.probe(a,c.pk,m.pk,'missing-policy')
    client=Client();client.force_login(a);url=reverse('native_finance',args=[c.pk]);response=client.get(url)
    check.assertContains(response,'MISSING');check.assertEqual(response['Cache-Control'],'no-store')
    check.assertEqual(client.post(url,{'action':'evidence','body':'Synthetic Finance mapping evidence from human','source':'synthetic:native-ui'}).status_code,302)
    configure(a,c,values)
    for change in [{'reviewer_id':a.pk},{'activation_mode':'enable'},{'max_seconds':0},{'allow_synthetic':False}]:
        with check.assertRaises(ValidationError):validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content={**values,**change}),c)
    validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content=values),c)
    check.assertEqual(agent.prepare(a,c.pk,p.pk,m.reference,m.effect_key,m.provider_ref,e.pk).pk,m.pk)
    outcomes=[]
    for i in range(3):
        item=m if i==0 else mapping(a,c,p,e,i)
        approved_mapping(a,b,c,item);o=d.probe(a,c.pk,item.pk,'native')
        outcomes.append(o.result['outcome']);check.assertTrue(o.result['direct_native_verification']);check.assertFalse(o.result['direct_vendor_verification'])
        check.assertNotEqual(item.payload['source_row_sha256'],item.payload['payload_sha256'])
        d.review(b,c.pk,item.pk,'approve','Synthetic Finance review preserving exact native outcome','observation-review',o.pk)
        check.assertEqual(d.probe(a,c.pk,item.pk,'native').pk,o.pk)
    check.assertEqual(outcomes,['present','conflict','unknown'])
    count=AgentRun.objects.count();result=agent.investigate(a,c.pk,m.pk);check.assertEqual(result['effect_tools'],[]);check.assertEqual(AgentRun.objects.count(),count)
    response=client.post(url,{'action':'investigate','mapping':m.pk});check.assertEqual(response.status_code,200)
    for private in ['CONFIDENTIAL RESTORED SOURCE BODY','Example completion content','milestone:1:finance:v1']:
        check.assertNotIn(private,response.content.decode())
    with check.assertRaises(PermissionDenied):d.review(a,c.pk,m.pk,'approve','Reject self approval','self')
    return {'outcomes':outcomes,'native':True}

def negatives():
    a,b,c,p,e,values,_,_=fixture();m=mapping(a,c,p,e);approved_mapping(a,b,c,m);o=d.probe(a,c.pk,m.pk,'native')
    with check.assertRaises(ValidationError):d.capture_packet(a,c.pk,m.pk,o.pk,0,'missing-destination')
    with check.assertRaises(DatabaseError),transaction.atomic():
        with connection.cursor() as cursor:cursor.execute('DELETE FROM workflows_nativefinancemapping WHERE id=%s',[m.pk])
    with check.assertRaises(DatabaseError),transaction.atomic():
        d.Observation.objects.create(mapping=m,operation_key='forged',pin=o.pin,result={**o.result,'direct_vendor_verification':True},actor=a)
    with transaction.atomic(),patch('apps.workflows.native_finance.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
        with check.assertRaises(ValidationError):d.current_observation(m,o,o.pin,values)
    foreign=Case.objects.create(tenant=c.tenant,title='Unrelated control case',kind='project',synthetic=True)
    client=Client();client.force_login(a);check.assertEqual(client.get(reverse('native_finance_report',args=[foreign.pk,m.pk])).status_code,404)
    with check.assertRaises(d.Mapping.DoesNotExist):d.probe(a,foreign.pk,m.pk,'foreign')
    with patch.dict(os.environ,{'PSL_NATIVE_FINANCE_IDENTITY_FIXTURE':base64.b64encode(os.urandom(32)).decode()}):
        with check.assertRaises(ValidationError):d.probe(a,c.pk,m.pk,'rotation')
        new_binding,_=adapter.binding(m)
        with check.assertRaises(ValidationError):adapter.verify(m,d.d.effect(p,m.effect_key),values,new_binding)
    altered=copy.deepcopy(settings.NATIVE_FINANCE);altered['providers']['fixture-finance']['database']=v['target']
    with override_settings(NATIVE_FINANCE=altered):
        with check.assertRaises(ValidationError):adapter.binding(m)
    # Inspect actual recovered database quarantine, not just the naming rejection.
    with n.connect(v['target']) as db:
        with check.assertRaises(ValidationError):adapter.session_identity(db,{**provider_registry(),'database':v['target']})
    cfg=d.rules(m)[0];transition(a,cfg.pk,'revoked')
    check.assertEqual(d.report(a,c.pk,m.pk)['policy_status'],'REVOKED')
    with check.assertRaises(ValidationError):d.probe(a,c.pk,m.pk,'revoked')
    Grant.objects.filter(user=a,case=c,action='finance.handoff.read').update(active=False)
    check.assertEqual(d.visible_mappings(a,c).count(),0)
    with check.assertRaises(PermissionDenied):
        with transaction.atomic():d.get(a,c.pk,m.pk)
    client=Client();client.force_login(a);response=client.get(reverse('native_finance',args=[c.pk]))
    check.assertEqual(response.status_code,200);check.assertNotContains(response,m.reference)
    return {'sql_guards':True,'scope_held':True,'quarantine_held':True}

def publication():
    a,b,c,p,e,values,dest,domain_rules=fixture();m=mapping(a,c,p,e);approved_mapping(a,b,c,m)
    o=d.probe(a,c.pk,m.pk,'native');check.assertEqual(o.result['outcome'],'present')
    d.review(b,c.pk,m.pk,'approve','Synthetic independent current native Finance observation review','native-review',o.pk)
    domain.configure(a,c,domain_rules)
    contract=d.domains.capture(a,c.pk,p.pk,'destination','destination',dest,e.pk)
    d.domains.review(b,c.pk,contract.pk,'approve','Synthetic intended destination with missing outbound','dest-review')
    observed=d.domains.probe(a,c.pk,contract.pk,'preflight');d.domains.review(b,c.pk,contract.pk,'approve','Synthetic reviewed destination prerequisite evidence','dest-observation',observed.pk)
    packet=d.capture_packet(a,c.pk,m.pk,o.pk,observed.pk,'companion')
    check.assertEqual(packet.payload['destination']['prerequisites']['outbound'],'missing')
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,packet.pk,'unreviewed')
    d.review(b,c.pk,m.pk,'approve','Synthetic independent exact companion publication review','packet-review',packet_id=packet.pk)
    barrier=Barrier(2)
    def reserve(_):
        close_old_connections()
        try:barrier.wait(timeout=30);return d.reserve(a,c.pk,packet.pk,'publish').pk
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(reserve,range(2)))
    check.assertEqual(ids[0],ids[1]);j=d.Job.objects.get(pk=ids[0])
    with patch.object(adapter,'deliver',side_effect=OSError('synthetic file failure')):check.assertTrue(d.run_once())
    j.refresh_from_db();check.assertEqual(j.status,'held');d.retry(a,c.pk,j.pk)
    with patch.object(d,'finish',side_effect=RuntimeError('synthetic control loss after actual file commit')):
        with check.assertRaises(RuntimeError):d.run_once()
    j.refresh_from_db();check.assertEqual(j.status,'leased');check.assertIsNotNone(adapter.lookup(j.intent))
    with check.assertRaises(DatabaseError),transaction.atomic():
        with connection.cursor() as cursor:cursor.execute('UPDATE workflows_nativefinancepublicationjob SET intent=%s WHERE id=%s',[json.dumps({**j.intent,'authorization':0}),j.pk])
    Grant.objects.filter(user=a,case=c,action='reconstitution.native_finance.operate').update(active=False)
    Grant.objects.filter(user=b,case=c,action='reconstitution.native_finance.review').update(active=False)
    d.Job.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
    return {'job':j.pk}

def reconcile():
    settings.NATIVE_FINANCE={'providers':{},'stores':{'fixture-companion':{'root':v['companion'],'revision':'fixture-v1'}}}
    check.assertTrue(d.run_once());j=d.Job.objects.get(pk=v['job']);check.assertEqual(j.status,'confirmed',j.error)
    raw=Path(v['companion'],j.operation_key+'.json').read_bytes()
    for value in [b'Example completion content',b'CONFIDENTIAL RESTORED SOURCE BODY',b'milestone:1:finance:v1']:check.assertNotIn(value,raw)
    return {'attempts':j.attempts,'files':len(list(Path(v['companion']).glob('*.json'))),'activation_enabled':j.receipt['activation_enabled']}

def invoice_variants():
    from apps.policy.invoice_receipt_validators import VARIANTS
    a,b,c,p,e,values,dest,criteria=fixture()
    for actor in [a,b]:
        for action in ['finance.read','reconstitution.domain.invoice.verify','reconstitution.domain.invoice.review']:
            Grant.objects.get_or_create(user=actor,case=c,action=action)
    rows=sorted((x for x in p.payload['inventory']['effects'] if x['family']=='invoice'),key=lambda x:x['job_id'])
    check.assertEqual(len(rows),8)
    m=d.capture(a,c.pk,p.pk,'invoice-first',rows[0]['effect_key'],'fixture-finance',e.pk)
    with check.assertRaises(ValidationError):approved_mapping(a,b,c,m)
    cfg=draft_operator_policy(a,c.pk,VARIANTS,{'variants':['issue','deliver','adjust','adjust_deliver'],'identifier_contract':'exact_incumbent_ids_v1'},v['evidence'],timezone.now())
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    outcomes=[];first=None
    for index,row in enumerate(rows):
        item=m if index==0 else d.capture(a,c.pk,p.pk,'invoice-'+str(index),row['effect_key'],'fixture-finance',e.pk)
        approved_mapping(a,b,c,item);o=d.probe(a,c.pk,item.pk,'native-invoice');outcomes.append(o.result['outcome'])
        check.assertEqual(o.result['outcome'],'present',item.payload['variant'])
        if first is None:first=o
    domain.configure(a,c,criteria)
    target=d.domains.capture(a,c.pk,p.pk,'destination','destination',dest,e.pk)
    d.domains.review(b,c.pk,target.pk,'approve','Synthetic exact destination contract review','destination-review')
    target_obs=d.domains.probe(a,c.pk,target.pk,'destination-probe')
    d.domains.review(b,c.pk,target.pk,'approve','Synthetic destination prerequisite states reviewed','destination-observation-review',target_obs.pk)
    d.review(b,c.pk,m.pk,'approve','Exact native invoice receipt reviewed','invoice-observation-review',first.pk)
    packet=d.capture_packet(a,c.pk,m.pk,first.pk,target_obs.pk,'invoice-companion')
    check.assertEqual(packet.payload['scope'],'single_invoice_companion')
    d.review(b,c.pk,m.pk,'approve','Exact inert invoice companion reviewed','invoice-packet-review',packet_id=packet.pk)
    job=d.reserve(a,c.pk,packet.pk,'invoice-publication');check.assertTrue(d.run_once());job.refresh_from_db();check.assertEqual(job.status,'confirmed',job.error)
    projection=d.followup_projection(a,c.pk,packet.pk)
    client=Client();client.force_login(a)
    response=client.post(reverse('native_finance',args=[c.pk]),{'action':'followup','packet':packet.pk});check.assertEqual(response.status_code,200)
    check.assertEqual(response.json(),projection);check.assertNotIn('lines',json.dumps(projection));check.assertNotIn('human',json.dumps(projection))
    with check.assertRaises(DatabaseError),transaction.atomic():
        d.Mapping.objects.filter(pk=m.pk).update(payload={**m.payload,'variant':'deliver'})
    return {'outcomes':outcomes,'projection':projection}

def source_accept():
    from apps.finance import receipt_followup as followup
    from apps.finance.models import InvoiceJob
    from apps.policy.invoice_receipt_validators import FOLLOWUP
    c=Case.objects.get(pk=v['projection']['source_case_id']);job=InvoiceJob.objects.filter(invoice__case=c).select_related('actor').first();a=job.actor
    e=add_evidence(a,c.pk,'integration_contract','Synthetic current Finance owner supplied reviewed metadata handoff','synthetic:current-source')
    r=followup.receive(a,c.pk,v['projection'],e.pk)
    with check.assertRaises(ValidationError):followup.decide(a,c.pk,r.pk,'investigate','Current owner investigation','before-policy')
    e=add_evidence(a,c.pk,'policy_decision','Synthetic current source owner criteria, never recovered authority','synthetic:current-source')
    cfg=draft_operator_policy(a,c.pk,FOLLOWUP,{'owner_id':a.pk,'owner_role':'Finance','resolutions':['investigate','link_current_intent','decline'],'request_valid_seconds':3600,'allow_synthetic':True},e.pk,timezone.now())
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    followup.decide(a,c.pk,r.pk,'link_current_intent','Current Finance owner linked an incumbent intent; no execution authorised','owner-link',job.pk)
    report=followup.report(a,c.pk,r.pk);check.assertTrue(report['decision_current']);check.assertFalse(report['execution_authorized'])
    return report

def followup_setup():
    from apps.policy.invoice_receipt_validators import VARIANTS
    a,b,c,p,e,values,dest,criteria=fixture()
    for actor in [a,b]:
        for action in ['finance.read','reconstitution.domain.invoice.verify','reconstitution.domain.invoice.review']:Grant.objects.get_or_create(user=actor,case=c,action=action)
    cfg=draft_operator_policy(a,c.pk,VARIANTS,{'variants':['issue'],'identifier_contract':'exact_incumbent_ids_v1'},v['evidence'],timezone.now())
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    row=min((x for x in p.payload['inventory']['effects'] if x['family']=='invoice'),key=lambda x:x['job_id'])
    m=d.capture(a,c.pk,p.pk,'readback-invoice',row['effect_key'],'fixture-finance',e.pk);approved_mapping(a,b,c,m)
    o=d.probe(a,c.pk,m.pk,'native');check.assertEqual(o.result['outcome'],'present')
    d.review(b,c.pk,m.pk,'approve','Synthetic exact native invoice receipt','invoice-observation',o.pk)
    domain.configure(a,c,criteria);target=d.domains.capture(a,c.pk,p.pk,'destination','destination',dest,e.pk)
    d.domains.review(b,c.pk,target.pk,'approve','Synthetic destination contract','destination')
    dest_obs=d.domains.probe(a,c.pk,target.pk,'destination');d.domains.review(b,c.pk,target.pk,'approve','Synthetic destination states','destination-observation',dest_obs.pk)
    packet=d.capture_packet(a,c.pk,m.pk,o.pk,dest_obs.pk,'readback-companion')
    d.review(b,c.pk,m.pk,'approve','Synthetic exact original companion','companion',packet_id=packet.pk)
    job=d.reserve(a,c.pk,packet.pk,'publish');check.assertTrue(d.run_once());job.refresh_from_db();check.assertEqual(job.status,'confirmed',job.error)
    return {'packet':packet.pk,'projection':d.followup_projection(a,c.pk,packet.pk)}

def resume_readback():
    from apps.workflows import finance_readback as readback
    a=get_user_model().objects.get(pk=v['operator']);b=get_user_model().objects.get(pk=v['reviewer']);c=Case.objects.get(pk=v['case'])
    settings.NATIVE_FINANCE={'providers':{'fixture-finance':provider_registry()},'stores':{'fixture-companion':{'root':v['companion'],'revision':'fixture-v1'}}}
    profile={'control_case':v['case'],'recovery_job_id':v['recovery'],'archived_case_ids':v['archive']['case_ids'],'destination_ref':'synthetic-operational-destination',
        'revision':'synthetic-profile-v1','receipt_path':str(Path(v['gateway'])/'current.json'),'receipt_provider_ref':'synthetic-gateway','receipt_key_ref':'synthetic-evidence-key','artifact_root':v['artifacts']}
    settings.RECONSTITUTION={'profiles':{'synthetic-profile':profile},'keys':{'synthetic-evidence-key':base64.b64decode(v['receipt_key'])}}
    return readback,a,b,c

def followup_probe():
    from apps.policy.followup_readback_validators import COMPONENT as READBACK,SCHEMA as READBACK_SCHEMA,validate_reference as validate_readback
    readback,a,b,c=resume_readback()
    if v.get('configure_readback'):
        with check.assertRaises(ValidationError):readback.probe(a,c.pk,v['packet'],'missing-policy')
        rules=json.loads(Path('fixtures/finance-followup-readback.json').read_text(encoding='utf-8'));rules.pop('classification')
        for bad in [{'max_seconds':0},{'allow_synthetic':False},{'implementation':'generic_digest'}]:
            with check.assertRaises(ValidationError):validate_readback(READBACK,SimpleNamespace(schema_ref=READBACK_SCHEMA,content={**rules,**bad}),c)
        cfg=draft_operator_policy(a,c.pk,READBACK,rules,v['evidence'],timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    if v.get('duplicates'):
        barrier=Barrier(2)
        def probe(_):
            close_old_connections()
            try:barrier.wait(timeout=30);return readback.probe(a,c.pk,v['packet'],v['readback_key'],include_successors=v.get('include_successors',False)).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(probe,range(2)))
        check.assertEqual(ids[0],ids[1]);o=readback.Observation.objects.get(pk=ids[0])
    else:o=readback.probe(a,c.pk,v['packet'],v['readback_key'],include_successors=v.get('include_successors',False))
    check.assertEqual(readback.probe(a,c.pk,v['packet'],v['readback_key'],include_successors=v.get('include_successors',False)).pk,o.pk)
    if v.get('review_readback'):
        readback.review(b,c.pk,o.pk,'approve','Synthetic exact historical/current source facts','approve')
        with check.assertRaises(PermissionDenied):readback.review(a,c.pk,o.pk,'approve','Self approval refused','self')
        report=readback.report(a,c.pk,o.pk);check.assertTrue(report['observation_current']);check.assertTrue(report['independent_review_current'])
        from apps.agents.finance_readback import investigate
        check.assertEqual(investigate(a,c.pk,o.pk)['effect_tools'],[])
        client=Client();client.force_login(a);response=client.post(reverse('native_finance',args=[c.pk]),{'action':'readback_investigate','observation_id':o.pk});check.assertEqual(response.status_code,200)
        for private in ['Current Finance owner linked','signed_delta','CONFIDENTIAL RESTORED SOURCE BODY','password_env']:check.assertNotIn(private,response.content.decode())
        with check.assertRaises(DatabaseError),transaction.atomic():readback.Observation.objects.filter(pk=o.pk).update(result={**o.result,'execution_authorized':True})
        with check.assertRaises(DatabaseError),transaction.atomic():readback.Review.objects.filter(observation=o).delete()
        if v.get('include_successors'):
            bad=copy.deepcopy(o.result);bad['successors']['lineage']=[{'note':'Private text is outside the metadata contract'}]
            with check.assertRaises(DatabaseError),transaction.atomic():
                readback.Observation.objects.create(packet=o.packet,operation_key='malformed-lineage',projection=o.projection,result=bad,pin=o.pin,actor=a)
    return {'observation':o.pk,'result':o.result}

def followup_old():
    readback,a,b,c=resume_readback();report=readback.report(a,c.pk,v['observation']);check.assertFalse(report['observation_current']);check.assertFalse(report['independent_review_current']);return report

def source_readback_receive():
    from apps.finance import receipt_followup as f
    c=Case.objects.get(pk=v['projection']['source_case_id']);job=f.InvoiceJob.objects.filter(invoice__case=c).select_related('actor').first();a=job.actor
    e=add_evidence(a,c.pk,'integration_contract','Synthetic source-owned handoff evidence','synthetic:readback')
    projection=v['projection'] if not v.get('conflict') else {**v['projection'],'outcome':'unknown'}
    r=f.receive(a,c.pk,projection,e.pk);return {'request':r.pk}

def source_readback_decline():
    from apps.finance import receipt_followup as f
    r=f.Request.objects.select_related('case').get(pk=v['request']);job=f.InvoiceJob.objects.filter(invoice__case=r.case).select_related('actor').first()
    f.decide(job.actor,r.case_id,r.pk,'decline','Synthetic current source-owner declined follow-up','decline');return {'declined':True}

def source_readback_revoke():
    from apps.finance import receipt_followup as f
    r=f.Request.objects.select_related('case').get(pk=v['request']);job=f.InvoiceJob.objects.filter(invoice__case=r.case).select_related('actor').first()
    Grant.objects.filter(user=job.actor,case=r.case,action='finance.receipt_followup.decide').update(active=False)
    return f.report(job.actor,r.case_id,r.pk)

def source_readback_lineage():
    from apps.finance import receipt_followup as f,followup_successors as lineage
    from tests.followup_successor_helpers import configure
    r=f.Request.objects.select_related('case').get(pk=v['request']);original=f.InvoiceJob.objects.get(invoice_id=r.projection['source_invoice_id'],kind='issue',generation=1)
    target=f.InvoiceJob.objects.filter(invoice_id=original.invoice_id,kind='adjust').order_by('pk').first();a=original.actor
    e=add_evidence(a,r.case_id,'integration_contract','Synthetic source-owned exact legal correction lineage','synthetic:successors')
    p=lineage.propose(a,r.case_id,r.pk,original.pk,target.pk,'legal_correction',e.pk,'Current Finance owner proposed an existing legal correction successor','native-successor')
    b,cfg,_=configure(a,r.case,r)
    lineage.review(b,r.case_id,p.pk,'approve',e.pk,'Independent lineage review only; no financial execution approval','native-successor-approve')
    result=lineage.report(a,r.case_id,r.pk);check.assertEqual(result['lineage'][0]['status'],'current');check.assertEqual(result['lineage'][0]['successor_receipt'],'present')
    return {'successor_proposal':p.pk,'successor_reviewer':b.pk}

def source_readback_lineage_revoke():
    from apps.finance import followup_successors as lineage
    p=lineage.Proposal.objects.select_related('actor','followup').get(pk=v['successor_proposal'])
    Grant.objects.filter(user_id=v['successor_reviewer'],case_id=p.followup.case_id,action='finance.receipt_followup.review_successor').update(active=False)
    return lineage.report(p.actor,p.followup.case_id,p.followup_id)

def transport_runtime():
    from apps.workflows import followup_transport as t
    readback,a,b,c=resume_readback()
    settings.READINESS_ENDPOINTS['endpoint:finance-inbox']={'url':v['transport_url'],'classification':'synthetic'}
    settings.READINESS_SECRET_REFS['secret:finance-inbox']={'env':'PSL_TEST_FINANCE_INBOX_KEY','revision':'fixture-v1'}
    os.environ['PSL_TEST_FINANCE_INBOX_KEY']=v['transport_secret']
    return t,a,b,c

def transport_prepare():
    from apps.policy.followup_transport_validators import OUTBOUND
    t,a,b,c=transport_runtime();Grant.objects.get_or_create(user=a,case=c,action='reconstitution.native_finance.transport')
    with check.assertRaises(ValidationError):t.reserve(a,c.pk,v['packet'],'before-transport-policy')
    rules=json.loads(Path('fixtures/finance-followup-transport.json').read_text())['outbound']
    cfg=draft_operator_policy(a,c.pk,OUTBOUND,rules,v['evidence'],timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    barrier=Barrier(2)
    def reserve(_):
        close_old_connections()
        try:barrier.wait(timeout=30);return t.reserve(a,c.pk,v['packet'],'signed-source-intake').pk
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(reserve,range(2)))
    check.assertEqual(ids[0],ids[1]);j=t.Job.objects.get(pk=ids[0])
    with check.assertRaises(DatabaseError),transaction.atomic():t.Job.objects.filter(pk=j.pk).update(intent={})
    client=Client();client.force_login(a);response=client.get(reverse('native_finance',args=[c.pk]));check.assertContains(response,'Signed source intake delivery')
    return {'transport_job':j.pk}

def transport_uncertain():
    from adapters.finance_followup_transport import FinanceFollowupTransport
    t,a,b,c=transport_runtime()
    class TimeoutAfterAccept(FinanceFollowupTransport):
        def deliver(self,job):super().deliver(job);raise TimeoutError('Synthetic lost response after actual source commit')
    check.assertTrue(t.run_once(TimeoutAfterAccept()));j=t.Job.objects.get(pk=v['transport_job']);check.assertEqual(j.status,'unknown')
    return t.report(a,c.pk,j.pk)

def transport_reconcile():
    from apps.workflows.operator_inventory import jobs,readable_manifest
    t,a,b,c=transport_runtime();check.assertTrue(t.run_once());j=t.Job.objects.get(pk=v['transport_job']);check.assertEqual(j.status,'confirmed')
    check.assertEqual(j.attempts,2);check.assertFalse(j.receipt['execution_authorized']);check.assertEqual(len([r for r in jobs(a,c)[0] if r['family']=='financefollowup']),1)
    client=Client();client.force_login(a);r=client.post(reverse('native_finance',args=[c.pk]),{'action':'transport_investigate','job':j.pk});check.assertEqual(r.status_code,200);check.assertEqual(r.json()['effect_tools'],[])
    with check.assertRaises(DatabaseError),transaction.atomic():t.Job.objects.filter(pk=j.pk).update(receipt={})
    result=t.report(a,c.pk,j.pk)
    manifest={'case_id':str(c.pk),'source_grants':[],'jobs':[{'family':'financefollowup','id':j.pk}]}
    readable_manifest(a,c,manifest)
    Grant.objects.filter(user=a,case=c,action='reconstitution.native_finance.transport').update(active=False)
    with check.assertRaises(PermissionDenied):readable_manifest(a,c,manifest)
    check.assertFalse(any(r['family']=='financefollowup' for r in jobs(a,c)[0]))
    return result

def source_readback_transport_revoke():
    from apps.finance.transport_models import FinanceAuthenticatedIntake
    from apps.finance import receipt_followup as f
    r=FinanceAuthenticatedIntake.objects.select_related('actor','followup').get()
    Grant.objects.filter(user=r.actor,case_id=r.followup.case_id,action='finance.receipt_followup.transport_receive').update(active=False)
    check.assertEqual(FinanceAuthenticatedIntake.objects.count(),1);check.assertEqual(f.Decision.objects.count(),0)
    return {'request':r.followup_id,'source_receipts':1,'source_owner_decisions':0}

if stage in ['provider_seed','provider_initialize','reconcile','source_accept'] or stage.startswith('source_readback_'):result=globals()[stage]()
else:
    server=domain.ThreadingHTTPServer(('127.0.0.1',0),domain.Provider);thread=Thread(target=server.serve_forever,daemon=True);thread.start();domain.registry(server)
    try:result=globals()[stage]()
    finally:server.shutdown();server.server_close();thread.join()
print(json.dumps(result))
