"""Real PostgreSQL reconstitution scenario subprocess; secrets are stdin-only."""
import json,sys,os,base64,copy,hmac,hashlib
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import django
django.setup()
import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,close_old_connections
from django.test import Client,override_settings
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.reconstitution_validators import COMPONENT,SCHEMA,DISPOSITIONS,validate_reference
from apps.workflows import reconstitution as d,cold_recovery as cold
from apps.agents import reconstitution as agent
from apps.agents.models import AgentRun
from adapters import native_application_archive as n,reconstitution as adapter
from tests import cold_recovery_scenario as old

v={};stage=None;check=old.check


def recover():
    a,b,c,e,values,p=old.fixture();old.configure(a,c,e,values);old.approve(b,c,p)
    j=cold.reserve(a,c.pk,p.pk);check.assertTrue(cold.run_once());j.refresh_from_db();check.assertEqual(j.status,'confirmed',j.error)
    cold.review(b,c.pk,p.pk,'recovered','approve','Synthetic independent actual isolated recovery review','recovered')
    for u in [a,b]:
        for action in ['archive','read','capture','review','agent','configure','operate']:
            Grant.objects.get_or_create(case=c,user=u,action='reconstitution.'+action)
    return {'operator':a.pk,'reviewer':b.pk,'case':str(c.pk),'evidence':e.pk,'recovery':j.pk,'principals':settings.COLD_RECOVERY['principals']}


def fixture(configured=True):
    with check.assertRaises(psycopg.OperationalError):n.connect(v['source'])
    a=get_user_model().objects.get(pk=v['operator']);b=get_user_model().objects.get(pk=v['reviewer']);c=Case.objects.get(pk=v['case'])
    r=cold.Job.objects.select_related('plan__case').get(pk=v['recovery'])
    profile={'control_case':v['case'],'recovery_job_id':r.pk,'archived_case_ids':v['archive']['case_ids'],'destination_ref':'synthetic-operational-destination',
        'revision':'synthetic-profile-v1','receipt_path':str(Path(v['gateway'])/'current.json'),'receipt_provider_ref':'synthetic-gateway','receipt_key_ref':'synthetic-evidence-key','artifact_root':v['artifacts']}
    settings.RECONSTITUTION={'profiles':{'synthetic-profile':profile},'keys':{'synthetic-evidence-key':base64.b64decode(v['receipt_key'])}}
    values=dict(profile_ref='synthetic-profile',destination_ref=profile['destination_ref'],operator_id=a.pk,operator_role='PM',reviewer_id=b.pk,reviewer_role='PMO',
        allowed_dispositions=DISPOSITIONS,max_records=100,receipt_max_bytes=1048576,receipt_freshness_seconds=3600,review_valid_seconds=3600,lease_seconds=300,max_attempts=2,activation_mode='reviewed_plan_only',allow_synthetic=True)
    p=d.capture(a,c.pk,r.pk,v['reference'],'synthetic-profile')
    if configured:configure(a,c,values)
    return a,b,c,p,values


def configure(a,c,values):
    cfg=draft_operator_policy(a,c.pk,COMPONENT,values,v['evidence'],timezone.now()-timedelta(seconds=1))
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active');return cfg


def gateway(rows=(),expired=False,changes=None):
    now=timezone.now()
    body={'format':'psl.receipt-evidence.v1','provider_ref':'synthetic-gateway','archive_sha256':v['archive']['sha256'],'revision':'synthetic-receipt-v1','observed_at':(now-timedelta(hours=2) if expired else now-timedelta(seconds=1)).isoformat(),'expires_at':(now-timedelta(seconds=1) if expired else now+timedelta(hours=1)).isoformat(),
        'records':[{'effect_key':r['effect_key'],'family':r['family'],'operation_sha256':r['operation_sha256'],'intent_sha256':r['intent_sha256'],'receipt_sha256':n.digest({'synthetic-receipt-for':r['effect_key']})} for r in rows]}
    if changes:body.update(changes)
    envelope={'body':body,'signature':hmac.new(base64.b64decode(v['receipt_key']),n.encoded(body),hashlib.sha256).hexdigest()}
    Path(v['gateway'],'current.json').write_bytes(n.encoded(envelope))


def probe(a,c,p,row,key):
    j=d.reserve(a,c.pk,p.pk,'receipt',key,row['effect_key']);check.assertTrue(d.run_once());j.refresh_from_db();check.assertEqual(j.status,'confirmed',j.error);return j


def disposition_all(b,c,p,verdict='retain_quarantine'):
    for row in p.payload['inventory']['effects']:
        d.dispose(b,c.pk,p.pk,row['effect_key'],verdict,'Synthetic deliberate human disposition; no cancellation/debt waiver','decision-'+row['effect_key'])


def controls():
    a,b,c,p,values=fixture(False)
    rows=p.payload['inventory']['effects'];check.assertEqual(len(p.payload['inventory']['families']),15) # Original14 plus native Finance companion publication.
    check.assertEqual({x['status'] for x in rows if x['family']=='handoff'},{'confirmed','pending','unknown'})
    check.assertTrue(next(x for x in rows if x['family']=='handoff' and x['status']=='confirmed')['historical_receipt_present'])
    check.assertTrue(all(set(x)=={'family','job_id','case_id','status','fence','attempts','operation_sha256','intent_sha256','historical_receipt_present','effect_key'} for x in rows))
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk,'receipt','missing',rows[0]['effect_key'])
    client=Client();client.force_login(a);url=reverse('reconstitution',args=[c.pk])
    response=client.get(url);check.assertEqual(response.status_code,200);check.assertContains(response,'MISSING');check.assertEqual(response['Cache-Control'],'no-store')
    check.assertNotContains(response,'CONFIDENTIAL RESTORED SOURCE BODY')
    count=AgentRun.objects.count();check.assertEqual(agent.prepare(a,c.pk,p.recovery_id,p.reference,'synthetic-profile').pk,p.pk)
    response=client.post(url,{'action':'investigate','plan':p.pk});check.assertEqual(response.status_code,200);check.assertEqual(response.json()['effect_tools'],[]);check.assertEqual(AgentRun.objects.count(),count)
    for changes in [{'operator_id':b.pk},{'operator_role':'PMO'},{'allow_synthetic':False},{'max_records':0},{'activation_mode':'activate'},{'allowed_dispositions':['retry']},{'receipt_freshness_seconds':None},{'command':'forbidden'}]:
        with check.assertRaises(ValidationError):validate_reference(COMPONENT,type('R',(),{'schema_ref':SCHEMA,'content':{**values,**changes}})(),c)
    check.assertEqual(client.post(url,{'action':'policy','content':json.dumps(values),'evidence':v['evidence']}).status_code,302)
    from apps.policy.models import Configuration
    cfg=Configuration.objects.filter(case=c,component=COMPONENT).latest('pk')
    for state in ['validated','active']:check.assertEqual(client.post(reverse('policy',args=[c.pk]),{'action':state,'configuration':cfg.pk}).status_code,302)
    check.assertEqual(d.capture(a,c.pk,p.recovery_id,p.reference,'synthetic-profile').pk,p.pk)
    return {'inventory_complete':True,'source_unavailable':True}


def receipts():
    a,b,c,p,values=fixture();row=next(x for x in p.payload['inventory']['effects'] if x['status']=='unknown' and x['family']=='handoff')
    gateway();j=probe(a,c,p,row,'absent')
    check.assertEqual(j.receipt['payload']['outcome'],'unknown')
    with check.assertRaises(ValidationError):d.dispose(b,c.pk,p.pk,row['effect_key'],'receipt_confirmed','A missing selection must be a typed hold','missing-probe')
    with check.assertRaises(ValidationError):d.dispose(b,c.pk,p.pk,row['effect_key'],'receipt_confirmed','Cannot infer non-execution','forbidden-absent',j.pk)
    d.dispose(b,c.pk,p.pk,row['effect_key'],'unresolved','Human keeps uncertain effect held','unknown')
    gateway([row]);j=probe(a,c,p,row,'present')
    client=Client();client.force_login(b)
    check.assertEqual(client.post(reverse('reconstitution',args=[c.pk]),{'action':'dispose','plan':p.pk,'effect_key':row['effect_key'],'verdict':'receipt_confirmed','probe':j.pk,'rationale':'Reviewed authenticated synthetic gateway evidence','operation_key':'confirmed-ui'}).status_code,302)
    check.assertEqual(d.Disposition.objects.filter(plan=p,effect_key=row['effect_key']).latest('pk').verdict,'receipt_confirmed')
    gateway([row],expired=True)
    with check.assertRaises(ValidationError):d.current_probe(p,j,row,values)
    gateway([row]);path=Path(v['gateway'],'current.json');envelope=json.loads(path.read_bytes());envelope['signature']='0'*64;path.write_bytes(n.encoded(envelope))
    with check.assertRaises(ValidationError):adapter.gateway(p.recovery,'synthetic-profile',row,values)
    gateway([row],changes={'archive_sha256':'0'*64})
    with check.assertRaises(ValidationError):adapter.gateway(p.recovery,'synthetic-profile',row,values)
    gateway([row],changes={'records':[{'effect_key':'0'*64,'family':row['family'],'operation_sha256':row['operation_sha256'],'intent_sha256':row['intent_sha256'],'receipt_sha256':'a'*64}]})
    check.assertEqual(adapter.gateway(p.recovery,'synthetic-profile',row,values)['outcome'],'unknown')
    gateway([row],changes={'records':[{'effect_key':row['effect_key'],'family':row['family'],'operation_sha256':row['operation_sha256'],'intent_sha256':'0'*64,'receipt_sha256':'a'*64}]})
    check.assertEqual(adapter.gateway(p.recovery,'synthetic-profile',row,values)['outcome'],'unknown')
    check.assertEqual(adapter.inventory(p.recovery,'synthetic-profile'),p.payload['inventory'])
    return {'unknown_not_retried':True,'invalid_evidence_rejected':True}


def publication():
    a,b,c,p,values=fixture();gateway()
    with check.assertRaises(PermissionDenied):d.review(a,c.pk,p.pk,'approve','Forbidden self approval','self')
    with check.assertRaises(ValidationError):d.review(b,c.pk,p.pk,'approve','Missing decisions','incomplete')
    disposition_all(b,c,p)
    client=Client();client.force_login(b);url=reverse('reconstitution',args=[c.pk])
    check.assertEqual(client.post(url,{'action':'review','plan':p.pk,'verdict':'approve','rationale':'Independent complete inert packet review','operation_key':'packet-ui'}).status_code,302)
    client.force_login(a);check.assertEqual(client.post(url,{'action':'reserve','plan':p.pk,'kind':'publish','effect_key':'all','operation_key':'publish-ui'}).status_code,302)
    check.assertTrue(d.run_once());j=d.Job.objects.get(plan=p,kind='publish');check.assertEqual(j.status,'confirmed',j.error)
    result=d.report(a,c.pk,p.pk);check.assertTrue(result['review_current']);check.assertFalse(result['manifest']['activation_enabled']);check.assertFalse(result['manifest']['debt_waived'])
    with transaction.atomic():
        evidence=d.pin(p,a);packet=d.manifest(p,a,evidence);review=d.Review.objects.filter(plan=p).latest('pk')
        with patch('apps.workflows.reconstitution.timezone.now',return_value=review.created_at+timedelta(seconds=values['review_valid_seconds']+1)):
            with check.assertRaises(ValidationError):d.approved(p,a,evidence,packet)
    row=p.payload['inventory']['effects'][0]
    d.dispose(b,c.pk,p.pk,row['effect_key'],'replacement_required','Requires new business approvals; no archived retry','replacement')
    check.assertFalse(d.report(a,c.pk,p.pk)['review_current'])
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk,'publish','stale-publication')
    check.assertEqual(adapter.inventory(p.recovery,'synthetic-profile'),p.payload['inventory'])
    return {'reviewed':True,'activation_enabled':False,'stale_review_rejected':True}


def crash():
    a,b,c,p,values=fixture();gateway();disposition_all(b,c,p);d.review(b,c.pk,p.pk,'approve','Synthetic complete packet for durable publication','crash-review')
    barrier=Barrier(2)
    def reserve(_):
        close_old_connections();u=get_user_model().objects.get(pk=a.pk);barrier.wait()
        try:return d.reserve(u,c.pk,p.pk,'publish','duplicate').pk
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(reserve,range(2)))
    check.assertEqual(ids[0],ids[1]);j=d.Job.objects.get(pk=ids[0])
    with patch('adapters.reconstitution.deliver',side_effect=OSError('synthetic pre-file transport fault')):check.assertTrue(d.run_once())
    j.refresh_from_db();check.assertEqual(j.status,'held');d.retry(a,c.pk,j.pk)
    with patch('apps.workflows.reconstitution.finish',side_effect=RuntimeError('synthetic process loss after actual immutable file write')):
        with check.assertRaises(RuntimeError):d.run_once()
    j.refresh_from_db();check.assertEqual(j.status,'leased');check.assertIsNotNone(adapter.lookup(p.recovery,j.intent))
    # Fresh worker reconciles existing exact bytes despite revoked new-effect authority/budget.
    Grant.objects.filter(user=a,case=c,action='reconstitution.operate').update(active=False)
    d.Job.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
    return {'job':j.pk,'plan':p.pk,'saved_principals':settings.COLD_RECOVERY['principals']}


def reconcile():
    a=get_user_model().objects.get(pk=v['operator']);check.assertTrue(d.run_once());j=d.Job.objects.select_related('plan__recovery__plan').get(pk=v['job'])
    check.assertEqual(j.status,'confirmed');check.assertEqual(j.attempts,3);check.assertEqual(j.receipt,adapter.lookup(j.plan.recovery,j.intent))
    check.assertFalse(Grant.objects.get(user=a,case_id=v['case'],action='reconstitution.operate').active)
    return {'attempts':j.attempts,'artifact_count':len(list(Path(v['artifacts']).glob('*.json')))}


def guards():
    a,b,c,p,values=fixture();gateway();row=p.payload['inventory']['effects'][0]
    # Previous scenario revocation must not grant any current effect; capture/review/SQL checks stay independent.
    for model,pk,changes in [(d.Plan,p.pk,{'payload':{}})]:
        with check.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).update(**changes)
    with check.assertRaises(DatabaseError),transaction.atomic():d.Disposition.objects.create(plan=p,effect_key=row['effect_key'],version=1,verdict='receipt_confirmed',operation_key='forged',rationale='forged',pin=d.pin(p,b),actor=b)
    d.dispose(b,c.pk,p.pk,row['effect_key'],'retain_quarantine','Explicit human quarantine','guard-decision')
    decision=d.Disposition.objects.filter(plan=p).get()
    with check.assertRaises(DatabaseError),transaction.atomic():d.Disposition.objects.filter(pk=decision.pk).update(verdict='unresolved')
    job=d.Job.objects.filter(plan__case=c,status='confirmed').first()
    with check.assertRaises(DatabaseError),transaction.atomic():d.Job.objects.filter(pk=job.pk).update(intent={})
    with check.assertRaises(DatabaseError),transaction.atomic():d.Job.objects.filter(pk=job.pk).update(receipt={'activation_enabled':True})
    review=d.Review.objects.filter(plan__case=c).first()
    with check.assertRaises(DatabaseError),transaction.atomic():d.Review.objects.filter(pk=review.pk).update(verdict='hold')
    foreign=Case.objects.create(tenant='foreign',title='Private foreign control case',kind='support',synthetic=True)
    client=Client();client.force_login(a);check.assertEqual(client.get(reverse('reconstitution',args=[foreign.pk])).status_code,404)
    changed=copy.deepcopy(settings.RECONSTITUTION);changed['profiles']['synthetic-profile']['archived_case_ids']=[]
    with override_settings(RECONSTITUTION=changed),check.assertRaises(ValidationError):d.capture(a,c.pk,p.recovery_id,'bad-inventory','synthetic-profile')
    intruder=get_user_model().objects.create_user(username='no-archive-'+v['reference'])
    settings.COLD_RECOVERY['principals'][str(intruder.pk)]={'username':intruder.username,'purposes':['read']}
    for action in ['case.read','cold.read','reconstitution.read']:Grant.objects.create(user=intruder,case=c,action=action)
    client.force_login(intruder)
    check.assertEqual(client.get(reverse('reconstitution_report',args=[c.pk,p.pk])).status_code,403)
    return {'guards':True,'foreign_scope_rejected':True}


def authority():
    a,b,c,p,values=fixture();gateway()
    # Revocations in earlier scenarios intentionally persist; they never renew archived authority.
    Grant.objects.filter(user=b,case=c,action='reconstitution.review').update(active=False)
    with check.assertRaises(PermissionDenied):d.dispose(b,c.pk,p.pk,p.payload['inventory']['effects'][0]['effect_key'],'unresolved','Revoked human','revoked')
    from apps.policy.models import Configuration
    cfg=Configuration.objects.filter(case=c,component=COMPONENT).latest('pk');transition(a,cfg.pk,'revoked')
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk,'publish','revoked-policy')
    from apps.policy.services import active_component,decision_authority
    roles=active_component('D05.role_principal_assignments',c);transition(a,roles.pk,'revoked')
    with check.assertRaises(ValidationError):decision_authority(b,c,'PMO')
    return {'authority_rejected':True}


if __name__=='__main__':
    v=json.load(sys.stdin);stage=sys.argv[1];old.v=v
if stage=='source':result=old.source()
elif stage is not None:
    settings.COLD_RECOVERY=old.runtime()
    if stage=='initialize':
        call_command('migrate',verbosity=0,interactive=False);call_command('initialize_cold_control',verbosity=0);result={'initialized':True}
    elif stage=='recover':result=recover()
    else:
        # Configure profile/principals even for a fresh-process receipt reconciliation.
        if stage=='reconcile':
            r=cold.Job.objects.select_related('plan__case').get(pk=v['recovery'])
            settings.RECONSTITUTION={'profiles':{'synthetic-profile':{'control_case':v['case'],'recovery_job_id':r.pk,'archived_case_ids':v['archive']['case_ids'],'destination_ref':'synthetic-operational-destination','revision':'synthetic-profile-v1','receipt_path':str(Path(v['gateway'])/'current.json'),'receipt_provider_ref':'synthetic-gateway','receipt_key_ref':'synthetic-evidence-key','artifact_root':v['artifacts']}},'keys':{'synthetic-evidence-key':base64.b64decode(v['receipt_key'])}}
        result=globals()[stage]()
if stage is not None:print(json.dumps(result))
