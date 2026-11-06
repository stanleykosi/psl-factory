"""Subprocess test harness. Runtime secrets travel on stdin, never argv/evidence output."""
import base64
import copy
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import django
django.setup()
import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction, DatabaseError, close_old_connections
from django.test import Client, override_settings, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference, transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.cold_recovery_validators import COMPONENT, SCHEMA, validate_reference
from apps.agents.models import AgentRun
from apps.agents import cold_recovery as agent
from apps.workflows import cold_recovery as d
from adapters import native_application_archive as n, cold_application_recovery as adapter
from tests.helpers import setup_case, activate

check = SimpleTestCase()
v = {}
stage = None


def source():
    call_command('migrate', verbosity=0, interactive=False)
    from apps.workflows import application_recovery as original
    from apps.policy.application_recovery_validators import COMPONENT as ORIGINAL
    a,c = setup_case(username='archived-old-operator')
    b = get_user_model().objects.create_user(username='archived-old-reviewer')
    if v.get('with_reconstitution_effects'):
        from tests.helpers import signed,rev
        from apps.pmo.services import complete_milestone
        from apps.workflows.services import run_once
        from adapters.finance import TimeoutAfterAccept
        ev=signed(a,c)
        complete_milestone(a,c.pk,'Confirmed source milestone',ev['completion'].pk,rev(c));check.assertTrue(run_once())
        complete_milestone(a,c.pk,'Uncertain source milestone',ev['completion'].pk,rev(c));check.assertTrue(run_once(TimeoutAfterAccept()))
        complete_milestone(a,c.pk,'Pending source milestone',ev['completion'].pk,rev(c))
        owner,private_case=setup_case(kind='support',username='archived-private-support-person')
        add_evidence(owner,private_case.pk,'document','CONFIDENTIAL RESTORED SOURCE BODY','synthetic:private-recovery-evidence')
    invoice_case=None
    if v.get('with_invoice_variants'):
        from tests.invoice_variant_helpers import documents
        _,invoice_case,_,_,_=documents()
    if v.get('with_native_validation'):
        from tests.test_native_validation import fixture as native_fixture,ready as native_ready
        from tests.validation_helpers import review as native_review
        f=native_fixture();native_ready(f);accepted=native_review(f,'acceptance')
        from apps.policy import pilot
        from tests.test_pilot_preflight import selection as pilot_selection
        payload=dict(pilot_selection(f['actor'],f['case']),format='psl.pilot-contract/v2',
            process_ids=f['package'].payload['process_ids'],acceptance_reviews=[accepted.pk])
        selected=pilot.configure(f['actor'],f['case'].pk,payload)
        pilot.capture(f['actor'],f['case'].pk,selected.pk)
        if v.get('with_private_impact'):
            from tests.document_helpers import artifact,DEFINITION,reserved
            from apps.documents import controlled,delivery
            from apps.policy import impact
            from tests.helpers import rev
            person,scope,proof=f['actor'],f['case'],f['decision_evidence']
            template=controlled.register_template(person,scope.pk,'Archived impact report',DEFINITION,proof.pk,rev(scope))
            recipient=get_user_model().objects.create_user(username='archived-impact-recipient')
            Grant.objects.create(user=recipient,case=scope,action='document.receive:client')
            ref=register_reference(person,scope.pk,'archived-impact-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':recipient.pk},proof.pk)
            activate(person,scope,'D11.recipient_grant_refs',[ref.ref],proof)
            rules={'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30}
            old=artifact(person,scope,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',rules,proof)
            source=add_evidence(person,scope.pk,'completion','Delivery is progressing. Internal incident trace is private.','synthetic:private-impact-archive')
            publication=reserved(person,scope,template,source);check.assertTrue(delivery.run_publication_once())
            new=artifact(person,scope,old.component,'schema:psl/document-storage/v1',rules,proof)
            for action in ['case.read','policy.read','policy.activate','document.read']:
                Grant.objects.get_or_create(user=f['acceptor'],case=scope,action=action)
            impact_row=impact.capture(person,scope.pk,old.pk,new.pk,['documents.publication_effects'],proof.pk,'Preserve real native publication impact history')
            impact.review(f['acceptor'],scope.pk,impact_row.pk,'accept',proof.pk,'Historical delivery proof only, no new release')
            if v.get('with_document_guard'):
                from apps.policy import pilot_bindings
                from adapters import pilot_preflight
                selected_payload=pilot_selection(person,scope);selected_payload['operations']=['document.publish']
                doc_contract=pilot.configure(person,scope.pk,selected_payload,selected.pk)
                technical=pilot_preflight.technical()
                doc_binding=pilot_bindings.configure(person,scope.pk,doc_contract.pk,{'format':'psl.pilot-bindings/v1',
                    'guards':[{'operation':'document.publish','user_id':person.pk,'arguments':{'version_id':publication.version_id,'expected_revision':rev(scope)}}],
                    'deployment':{'ref':'cold-document-guard','revision':'fixture-v1','web_key_ref':'fixture-document-web','worker_key_ref':'fixture-document-worker',
                        'families':['publication'],'freshness_seconds':300,'expected':{k:technical[k] for k in ['source_identity','schema_identity','database_identity']}}})
                for action in ['pilot.read','pilot.binding.review']:Grant.objects.get_or_create(user=f['acceptor'],case=scope,action=action)
                pilot_bindings.review(f['acceptor'],scope.pk,doc_binding.pk,'accept','Historical publication metadata only, no retry or new release')
                doc_pack=pilot.capture(person,scope.pk,doc_contract.pk)
                check.assertEqual(doc_pack.snapshot['bindings']['native_guards'][0]['head']['document']['receipt_state'],'verified_internal_receipt')
    if v.get('with_role_eligibility'):
        from apps.policy import role_assignments
        from apps.policy.services import role_policy
        role_owner,role_case=setup_case(username='archived-v2-role-owner')
        role_evidence=add_evidence(role_owner,role_case.pk,'policy_decision','Explicit synthetic archived role eligibility, not a real nomination','synthetic:role-archive')
        window={'roles':['PM','Head of PMO'],'valid_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'valid_until':(timezone.now()+timedelta(hours=1)).isoformat()}
        assignments=[{'role':role,'user_id':role_owner.pk,'eligibility':window} for role in window['roles']]
        if v.get('with_role_guard'):
            delegate=get_user_model().objects.create_user(username='archived-v2-role-delegate')
            Grant.objects.create(user=delegate,case=role_case,action='case.read')
            assignments.append({'role':'Finance','user_id':delegate.pk})
        role_cfg=role_assignments.draft(role_owner,role_case.pk,assignments,role_evidence.pk,timezone.now()-timedelta(seconds=1))
        transition(role_owner,role_cfg.pk,'validated');transition(role_owner,role_cfg.pk,'active')
        check.assertEqual(role_policy(role_owner,role_case,'PM').pk,role_cfg.pk)
        if v.get('with_role_guard'):
            from apps.policy import pilot,pilot_bindings
            from adapters import pilot_preflight
            from tests.test_pilot_preflight import selection as pilot_selection
            from tests.helpers import rev
            rule={'role':'Head of PMO','principal_id':role_owner.pk,'delegate_id':delegate.pk,
                'valid_from':window['valid_from'],'valid_until':(timezone.now()+timedelta(hours=2)).isoformat(),
                'delegate_eligibility':dict(window,roles=['Finance','Head of PMO'])}
            delegation=role_assignments.draft_delegations(role_owner,role_case.pk,[rule],role_evidence.pk,timezone.now()-timedelta(seconds=1))
            transition(role_owner,delegation.pk,'validated');transition(role_owner,delegation.pk,'active')
            payload=pilot_selection(role_owner,role_case);payload['operations']=['role.decision.evaluate'];payload['participants'].append({'user_id':delegate.pk,'actions':['case.read']})
            contract=pilot.configure(role_owner,role_case.pk,payload);technical=pilot_preflight.technical()
            binding=pilot_bindings.configure(role_owner,role_case.pk,contract.pk,{'format':'psl.pilot-bindings/v1',
                'guards':[{'operation':'role.decision.evaluate','user_id':delegate.pk,'arguments':{'role':'Head of PMO','decision_action':'approve','delegated':True,'expected_revision':rev(role_case)}}],
                'deployment':{'ref':'cold-role-guard','revision':'fixture-v1','web_key_ref':'fixture-role-web','worker_key_ref':'fixture-role-worker',
                    'families':['handoff'],'freshness_seconds':300,'expected':{key:technical[key] for key in ['source_identity','schema_identity','database_identity']}}})
            for action in ['case.read','policy.read','pilot.read','pilot.binding.review']:Grant.objects.get_or_create(user=b,case=role_case,action=action)
            pilot_bindings.review(b,role_case.pk,binding.pk,'accept','Qualification metadata only, no business decision or action grants')
            pack=pilot.capture(role_owner,role_case.pk,contract.pk)
            check.assertEqual(pack.snapshot['bindings']['native_guards'][0]['state'],'READY_AT_OBSERVATION')
    if v.get('with_clock_guard'):
        from tests.meeting_helpers import configure_clock
        from tests.helpers import rev
        from apps.pmo.meetings import create_action,record_meeting
        from apps.policy import pilot,pilot_bindings
        from adapters import pilot_preflight
        from tests.test_pilot_preflight import selection as pilot_selection
        person,scope=setup_case(username='archived-clock-owner')
        proof=add_evidence(person,scope.pk,'policy_decision','Synthetic archived clock rules','synthetic:clock-archive')
        notes=add_evidence(person,scope.pk,'meeting_notes','Private archived meeting evidence','synthetic:clock-meeting')
        meeting=record_meeting(person,scope.pk,'ARCHIVED-MEETING','status',timezone.now()-timedelta(hours=1),
            'Source meeting','Archived exact action inputs',[person.pk],[],notes.pk,rev(scope))
        configure_clock(person,scope,proof)
        item=create_action(person,scope.pk,'ARCHIVED-CLOCK','Private archived action',person.pk,None,notes.pk,
            'Exact historical inputs',rev(scope),meeting.meeting_id,True)
        selected_payload=pilot_selection(person,scope);selected_payload['operations']=['workflow.clock.evaluate']
        contract=pilot.configure(person,scope.pk,selected_payload);technical=pilot_preflight.technical()
        binding=pilot_bindings.configure(person,scope.pk,contract.pk,{'format':'psl.pilot-bindings/v1',
            'guards':[{'operation':'workflow.clock.evaluate','user_id':person.pk,'arguments':{'action_state_id':item.current_id,'expected_revision':rev(scope)}}],
            'deployment':{'ref':'cold-clock-guard','revision':'fixture-v1','web_key_ref':'fixture-clock-web','worker_key_ref':'fixture-clock-worker',
                'families':['publication'],'freshness_seconds':300,'expected':{k:technical[k] for k in ['source_identity','schema_identity','database_identity']}}})
        for action in ['case.read','policy.read','pilot.read','pilot.binding.review','meeting.read']:Grant.objects.get_or_create(user=b,case=scope,action=action)
        pilot_bindings.review(b,scope.pk,binding.pk,'accept','Exact clock input history; no restored authority or deadline adoption')
        pack=pilot.capture(person,scope.pk,contract.pk)
        check.assertEqual(pack.snapshot['bindings']['native_guards'][0]['state'],'READY_AT_OBSERVATION')
    for u in [a,b]:
        for action in ['case.read','recovery.read','recovery.database','recovery.capture','recovery.review','recovery.operate','recovery.attachment']:
            Grant.objects.get_or_create(user=u,case=c,action=action)
        for archived_case in Case.objects.all():
            Grant.objects.get_or_create(user=u,case=archived_case,action='recovery.database')
    r = Path(v['root'])
    settings.APPLICATION_RECOVERY = {'sources':{'old-source':{'database':v['source'],'archives':str(r/'archives'),'attachments':str(r/'attachments'),'revision':'synthetic-v1'}},
        'targets':{'old-target':{'database':'test_psl_recovery_unused_'+uuid4().hex[:8],'attachments':str(r/'old-target-files'),'revision':'synthetic-v1'}},
        'keys':{'synthetic-key':base64.b64decode(v['key'])},'principals':[a.pk,b.pk],
        'build_ref':'synthetic-reviewed-build','pg_bin':v['pg_bin']}
    e = add_evidence(a,c.pk,'policy_decision','Synthetic archive policy evidence, no real appointment','synthetic:cold-source')
    from tests.helpers import envelope
    from apps.policy.services import save_draft, resolve
    from apps.policy import scopes
    scoped=save_draft(a,c.pk,envelope(c,'D04.iana_timezone','UTC',e));transition(a,scoped.pk,'validated')
    origin=scopes.create(a,scoped.pk,'organization',c.tenant,[])
    scopes.transition(a,origin.pk,'validated');scopes.transition(a,origin.pk,'active')
    local=scopes.apply(a,origin.pk,c.pk,e.pk,[])
    transition(a,local.pk,'validated');transition(a,local.pk,'active')
    check.assertEqual(resolve('D04.iana_timezone',c).configuration.pk,local.pk)
    from apps.policy import impact
    successor=activate(a,c,'D04.iana_timezone','UTC',e)
    for action in ['policy.read','policy.activate']:
        Grant.objects.get_or_create(user=b,case=c,action=action)
    assessment=impact.capture(a,c.pk,local.pk,successor.pk,['pmo.decisions'],e.pk,'Archived engineering review remains historical')
    impact.review(b,c.pk,assessment.pk,'accept',e.pk,'Synthetic bounded review; no business approval or authority restoration')
    refs = [register_reference(a,c.pk,'native-role:'+str(u.pk),'schema:psl/role-assignment/v1',{'user_id':u.pk,'role':role},e.pk).ref for u,role in [(a,'PM'),(b,'PMO')]]
    activate(a,c,'D05.role_principal_assignments',refs,e)
    from apps.policy import pilot
    from apps.policy import pilot_bindings
    from adapters import pilot_preflight
    from tests.helpers import project_evidence,rev
    project_sources=project_evidence(a,c)
    selection={'format':'psl.pilot-contract/v1','case_id':str(c.pk),'read_only':True,'process_ids':['P13'],
        'operations':['pmo.baseline.prepare'],'participants':[{'user_id':a.pk,'actions':['case.read']}],
        'integrations':[],'jobs':[]}
    pilot_contract=pilot.configure(a,c.pk,selection)
    actual=pilot_preflight.technical()
    native_binding=pilot_bindings.configure(a,c.pk,pilot_contract.pk,{'format':'psl.pilot-bindings/v1',
        'guards':[{'operation':'pmo.baseline.prepare','user_id':a.pk,'arguments':{'expected_revision':rev(c),
            'plan_id':project_sources['plan'].pk,'cost_id':project_sources['costing'].pk,'sow_id':project_sources['sow'].pk}}],
        'deployment':{'ref':'cold-fixture','revision':'fixture-v1','web_key_ref':'fixture-web','worker_key_ref':'fixture-worker',
            'families':['handoff'],'freshness_seconds':300,'expected':{k:actual[k] for k in ['source_identity','schema_identity','database_identity']}}})
    for action in ['case.read','policy.read','pilot.read','pilot.binding.review','planning.read']:
        Grant.objects.get_or_create(user=b,case=c,action=action)
    pilot_bindings.review(b,c.pk,native_binding.pk,'accept','Synthetic engineering review, never business approval')
    profile={'fixture-web':{'deployment_ref':'cold-fixture','revision':'fixture-v1','role':'web','principal_id':a.pk,
        'case_id':str(c.pk),'classification':'synthetic','families':[],'secret_env':'PSL_PILOT_ARCHIVE_WEB',
        'storage_revision':'fixture-v1','retention_revision':'fixture-v1','monitoring_revision':'fixture-v1'}}
    with override_settings(PILOT_RUNTIME_IDENTITIES=profile),patch.dict(os.environ,{'PSL_PILOT_ARCHIVE_WEB':'explicit-synthetic-archive-web-key-material-00001'}):
        client=Client(enforce_csrf_checks=True);client.force_login(a)
        url=reverse('pilot_binding',args=[c.pk,native_binding.pk]);check.assertEqual(client.get(url).status_code,200)
        check.assertEqual(client.post(url,{'command':'observe_web','csrfmiddlewaretoken':client.cookies['csrftoken'].value}).status_code,302)
    pilot.capture(a,c.pk,pilot_contract.pk)
    attachment = original.attach(a,c.pk,'old-source','Synthetic cold recovery attachment',b'cold-source-file-bytes')
    values = dict(source_ref='old-source',target_ref='old-target',key_ref='synthetic-key',operator_id=a.pk,operator_role='PM',reviewer_id=b.pk,reviewer_role='PMO',attachment_ids=[attachment.pk],max_archive_bytes=33554432,max_attachment_bytes=1048576,max_seconds=30,lease_seconds=180,max_attempts=2,retention_days=7,authorization_valid_seconds=3600,archive_valid_seconds=3600,allow_synthetic=True)
    cfg = draft_operator_policy(a,c.pk,ORIGINAL,values,e.pk,timezone.now()-timedelta(seconds=1))
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    p = original.capture(a,c.pk,'source-archive',{k:values[k] for k in ['source_ref','target_ref','key_ref']})
    original.review(b,c.pk,p.pk,'authorize','approve','Synthetic source archive authorization','source-review')
    j = original.reserve(a,c.pk,p.pk,'archive')
    check.assertTrue(original.run_once())
    j.refresh_from_db();check.assertEqual(j.status,'confirmed',j.error)
    return {'operation_key':j.operation_key,'sha256':j.receipt['archive_sha256'],'case_ids':[str(x) for x in Case.objects.order_by('pk').values_list('pk',flat=True)],'invoice_case_id':str(invoice_case.pk) if invoice_case else None}


def runtime():
    root = Path(v['root'])
    return {'control_ref':'synthetic-fresh-control','control_database':v['control'],
        'control_secret':base64.b64decode(v['secret']), 'principals':v.get('principals',{}),
        'archives':{'sealed-source':{'database':v['source'],'archives':str(root/'archives'),
            'operation_key':v['archive']['operation_key'],'sha256':v['archive']['sha256'],'revision':'synthetic-v1'}},
        'targets':{'isolated-target':{'database':v.get('target','test_psl_recovery_unused'),
            'attachments':v.get('target_files',str(root/'old-target-files')),'revision':'synthetic-v1'}},
        'keys':{'synthetic-key':base64.b64decode(v['key'])},'build_ref':'synthetic-reviewed-build','pg_bin':v['pg_bin']}


def fixture():
    # Actual PostgreSQL refuses the separately owned original source, rather than mocking its authority.
    with check.assertRaises(psycopg.OperationalError):
        n.connect(v['source'])
    a,c = setup_case(username='fresh-operator-'+uuid4().hex[:12])
    b = get_user_model().objects.create_user(username='fresh-reviewer-'+uuid4().hex[:12])
    settings.COLD_RECOVERY['principals'] = {str(u.pk):{'username':u.username,'purposes':['read','capture','operate','review','agent','configure']} for u in [a,b]}
    for u in [a,b]:
        for action in ['case.read','cold.read','cold.capture','cold.operate','cold.review','cold.agent','cold.configure']:
            Grant.objects.get_or_create(user=u,case=c,action=action)
    ev = add_evidence(a,c.pk,'policy_decision','Synthetic fresh independent cold recovery criteria','synthetic:fresh-control')
    refs=[register_reference(a,c.pk,'fresh-role:'+str(u.pk),'schema:psl/role-assignment/v1',{'user_id':u.pk,'role':role},ev.pk).ref for u,role in [(a,'PM'),(b,'PMO')]]
    activate(a,c,'D05.role_principal_assignments',refs,ev)
    values=dict(archive_ref='sealed-source',target_ref='isolated-target',key_ref='synthetic-key',operator_id=a.pk,operator_role='PM',reviewer_id=b.pk,reviewer_role='PMO',max_archive_bytes=33554432,max_seconds=30,lease_seconds=180,max_attempts=2,authorization_valid_seconds=3600,archive_valid_seconds=3600,allow_synthetic=True)
    p=d.capture(a,c.pk,'cold-request',{k:values[k] for k in ['archive_ref','target_ref','key_ref']})
    return a,b,c,ev,values,p


def configure(a,c,ev,values):
    cfg=draft_operator_policy(a,c.pk,COMPONENT,values,ev.pk,timezone.now()-timedelta(seconds=1))
    transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    return cfg


def approve(b,c,p,key='fresh-approval'):
    return d.review(b,c.pk,p.pk,'authorize','approve','Synthetic independent fresh-authority review',key)


def controls():
    a,b,c,ev,values,p=fixture()
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk)
    client=Client();client.force_login(a)
    url=reverse('cold_recovery',args=[c.pk])
    response=client.get(url);check.assertEqual(response.status_code,200);check.assertContains(response,'MISSING');check.assertEqual(response['Cache-Control'],'no-store')
    check.assertEqual(client.post(url,{'action':'capture','reference':'ui-request',**{k:values[k] for k in ['archive_ref','target_ref','key_ref']}}).status_code,302)
    count=AgentRun.objects.count()
    check.assertEqual(agent.prepare(a,c.pk,p.reference,**{k:values[k] for k in ['archive_ref','target_ref','key_ref']}).pk,p.pk)
    response=client.post(url,{'action':'investigate','plan':p.pk});check.assertEqual(response.status_code,200);check.assertEqual(response.json()['effect_tools'],[]);check.assertEqual(AgentRun.objects.count(),count)
    check.assertIn({'component':COMPONENT,'status':'MISSING'},response.json()['policy_dependencies'])
    check.assertEqual(response.json()['bindings']['archive_sha256'],v['archive']['sha256'])
    from config.cold_runtime import load
    profile=Path(v['root'])/'synthetic-profile.json'
    config=copy.deepcopy(settings.COLD_RECOVERY)
    config.pop('keys');config.pop('control_secret')
    config.update(control_secret_env='PSL_COLD_CONTROL_TEST',key_env={'synthetic-key':'PSL_RECOVERY_KEY_TEST'})
    profile.write_text(json.dumps(config),encoding='utf-8')
    with patch.dict(os.environ,{'PSL_COLD_RECOVERY_PROFILE':str(profile),'PSL_COLD_CONTROL_TEST':v['secret'],'PSL_RECOVERY_KEY_TEST':v['key']}):
        check.assertEqual(load()['control_database'],v['control'])
        config['principals'][str(a.pk)]['purposes']=['arbitrary-effect']
        profile.write_text(json.dumps(config),encoding='utf-8')
        with check.assertRaises(RuntimeError):load()
    for change in [{'reviewer_id':a.pk},{'max_seconds':0},{'lease_seconds':10},{'allow_synthetic':False},{'max_attempts':None},{'shell':'forbidden'}]:
        with check.assertRaises(ValidationError):validate_reference(COMPONENT,type('R',(),{'schema_ref':SCHEMA,'content':{**values,**change}})(),c)
    # Exercise actual HTTP draft, versioned validation/activation, independent approval and queue.
    check.assertEqual(client.post(url,{'action':'policy','content':json.dumps(values),'evidence_id':ev.pk}).status_code,302)
    from apps.policy.models import Configuration
    cfg=Configuration.objects.get(case=c,component=COMPONENT)
    for state in ['validated','active']:
        check.assertEqual(client.post(reverse('policy',args=[c.pk]),{'action':state,'configuration':cfg.pk}).status_code,302)
    client.force_login(b)
    check.assertEqual(client.post(url,{'action':'review','plan':p.pk,'phase':'authorize','decision':'approve','rationale':'Fresh synthetic human decision','operation_key':'ui-approval'}).status_code,302)
    client.force_login(a)
    check.assertEqual(client.post(url,{'action':'reserve','plan':p.pk}).status_code,302)
    j=d.Job.objects.get(plan=p)
    for model,pk,changes in [(d.Plan,p.pk,{'payload':{}}),(d.Review,d.Review.objects.get(plan=p).pk,{'decision':'hold'}),(d.Job,j.pk,{'intent':{}}),(d.Job,j.pk,{'status':'confirmed','receipt':{'live_authority_restored':True}}),(d.Identity,'synthetic-fresh-control',{'secret_sha256':'0'*64})]:
        with check.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).update(**changes)
    with check.assertRaises(DatabaseError),transaction.atomic():d.Review.objects.create(plan=p,phase='authorize',decision='approve',operation_key='forged-self',pin=d.pin(p),rationale='forged',actor=a)
    foreign=Case.objects.create(tenant='foreign',title='Foreign confidential control case',kind='support',synthetic=True)
    check.assertEqual(client.get(reverse('cold_recovery',args=[foreign.pk])).status_code,404)
    check.assertEqual(client.get(reverse('cold_recovery_report',args=[foreign.pk,p.pk])).status_code,404)
    Grant.objects.filter(user=a,case=c,action='cold.read').update(active=False)
    check.assertEqual(client.get(url).status_code,403)
    return {'source_unavailable':True,'missing_policy_capture':True,'sql_guards':True}


def authority():
    a,b,c,ev,values,p=fixture();cfg=configure(a,c,ev,values)
    with check.assertRaises(PermissionDenied):approve(a,c,p)
    r=approve(b,c,p)
    with patch('apps.workflows.cold_recovery.timezone.now',return_value=r.created_at+timedelta(seconds=3601)):
        with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk)
    original=copy.deepcopy(settings.COLD_RECOVERY)
    for mutate in ['purpose','secret','key','archive','database']:
        changed=copy.deepcopy(original)
        if mutate=='purpose':changed['principals'][str(b.pk)]['purposes']=['read']
        if mutate=='secret':changed['control_secret']=os.urandom(32)
        if mutate=='key':changed['keys']['synthetic-key']=os.urandom(32)
        if mutate=='archive':changed['archives']['sealed-source']['sha256']='0'*64
        if mutate=='database':changed['control_database']=v['source']
        with override_settings(COLD_RECOVERY=changed),check.assertRaises((ValidationError,PermissionDenied)):d.reserve(a,c.pk,p.pk)
    transition(a,cfg.pk,'revoked')
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk)
    cfg=configure(a,c,ev,values)
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk)  # A new policy cannot reuse the old human pin.
    approve(b,c,p,'new-policy-approval')
    d.review(b,c.pk,p.pk,'authorize','hold','Fresh human hold supersedes authorization','fresh-hold')
    with check.assertRaises(ValidationError):d.reserve(a,c.pk,p.pk)
    approve(b,c,p,'post-hold-approval')
    Grant.objects.filter(user=b,case=c,action='cold.review').update(active=False)
    with check.assertRaises(PermissionDenied):d.reserve(a,c.pk,p.pk)
    # Archived user names/IDs are not present in the independently provisioned authority database.
    check.assertFalse(get_user_model().objects.filter(username__startswith='archived-old-').exists())
    check.assertFalse(d.Job.objects.filter(plan=p).exists())
    return {'authority_rejected':True}


def crash():
    a,b,c,ev,values,p=fixture();configure(a,c,ev,values);approve(b,c,p)
    j=d.reserve(a,c.pk,p.pk)
    original=n.cli
    def fail(command,args,database,timeout,**kwargs):
        if command=='psql':
            file=Path(next(x.split('=',1)[1] for x in args if x.endswith('receipt.sql')))
            with file.open('a',encoding='utf-8') as out:out.write('\nSELECT 1/0;\n')
        return original(command,args,database,timeout,**kwargs)
    with patch('adapters.native_application_archive.cli',side_effect=fail):check.assertTrue(d.run_once())
    j.refresh_from_db();check.assertEqual(j.status,'held')
    with n.connect(v['target']) as db:
        check.assertEqual(n.tables(db),[])
        check.assertEqual(db.execute("SELECT current_setting('psl.recovery_quarantined')").fetchone()[0],'on')
    client=Client();client.force_login(a)
    check.assertEqual(client.post(reverse('cold_recovery',args=[c.pk]),{'action':'retry','job':j.pk}).status_code,302)
    with patch('apps.workflows.cold_recovery.finish',side_effect=RuntimeError('synthetic process loss after actual target commit')):
        with check.assertRaises(RuntimeError):d.run_once()
    j.refresh_from_db();check.assertEqual(j.status,'leased');check.assertIsNotNone(adapter.receipt(j.intent))
    Grant.objects.filter(user=a,case=c,action='cold.operate').update(active=False)
    Grant.objects.filter(user=b,case=c,action='cold.review').update(active=False)
    d.Job.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
    return {'job':j.pk,'case':str(c.pk),'plan':p.pk,'reader':a.pk,'principals':settings.COLD_RECOVERY['principals']}


def reconcile():
    check.assertTrue(d.run_once())
    j=d.Job.objects.get(pk=v['job']);check.assertEqual(j.status,'confirmed');check.assertEqual(j.attempts,3)
    check.assertEqual(j.receipt,adapter.receipt(j.intent))
    a=get_user_model().objects.get(pk=v['reader'])
    check.assertFalse(Grant.objects.get(user=a,case_id=v['case'],action='cold.operate').active)
    result=d.report(a,v['case'],v['plan']);check.assertFalse(result['authorization_current']);check.assertTrue(result['physical_receipt_current'])
    return result


def concurrency():
    a,b,c,ev,values,p=fixture();configure(a,c,ev,values);approve(b,c,p)
    barrier=Barrier(2)
    def reserve(_):
        close_old_connections();u=get_user_model().objects.get(pk=a.pk);barrier.wait()
        try:return d.reserve(u,c.pk,p.pk).pk
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(reserve,range(2)))
    check.assertEqual(ids[0],ids[1]);barrier=Barrier(2)
    def worker(_):
        close_old_connections();barrier.wait()
        try:return d.run_once()
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(worker,range(2)))
    j=d.Job.objects.get(plan=p);check.assertEqual(j.status,'confirmed',j.error);check.assertEqual(j.attempts,1)
    d.review(b,c.pk,p.pk,'recovered','approve','Independent review of real isolated bytes and SQL','recovered-approval')
    result=d.report(a,c.pk,p.pk);check.assertTrue(result['human_recovered_review_current']);check.assertFalse(result['production_activation'])
    from adapters.pilot_physical import read as physical
    projection=physical(a,c,'cold',j.pk)
    check.assertTrue(projection['recovery_evidence']['native_restore_verified']);check.assertFalse(projection['replay_permitted'])
    check.assertNotIn('target',projection['recovery_evidence']);check.assertFalse(projection['recovery_evidence']['live_authority_restored'])
    # Restored accounts/grants remain inert despite active fresh control principals.
    with n.connect(v['target']) as db:
        check.assertEqual(db.execute('SELECT count(*) FROM auth_user WHERE is_active OR password<>%s',['!']).fetchone()[0],0)
        check.assertEqual(db.execute('SELECT count(*) FROM identity_grant').fetchone()[0],0)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_scopeversion').fetchone()[0],1)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_scopeapplication').fetchone()[0],1)
        check.assertEqual(db.execute("SELECT count(*) FROM policy_scopestate WHERE state='active'").fetchone()[0],1)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_impactassessment').fetchone()[0],2 if v.get('with_private_impact') else 1)
        check.assertEqual(db.execute("SELECT count(*) FROM policy_impactreview WHERE verdict='accept'").fetchone()[0],2 if v.get('with_private_impact') else 1)
        if v.get('with_private_impact'):
            check.assertEqual(db.execute("SELECT count(*) FROM policy_impactassessment WHERE observation->'domains'->'documents.publication_effects'->0->>'state'='committed_effect'").fetchone()[0],1)
        if v.get('with_role_eligibility'):
            check.assertEqual(db.execute("SELECT count(*) FROM policy_registeredreference WHERE schema_ref='schema:psl/role-assignment/v2' AND content->'eligibility'->'roles' @> '[\"PM\",\"Head of PMO\"]'::jsonb").fetchone()[0],2)
        if v.get('with_role_guard'):
            check.assertEqual(db.execute("SELECT count(*) FROM policy_registeredreference WHERE schema_ref='schema:psl/decision-delegation/v2'").fetchone()[0],1)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_impactreview r JOIN auth_user u ON u.id=r.actor_id WHERE u.is_active').fetchone()[0],0)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_pilotcontract').fetchone()[0],1+bool(v.get('with_native_validation'))+bool(v.get('with_document_guard'))+bool(v.get('with_role_guard'))+bool(v.get('with_clock_guard')))
        check.assertEqual(db.execute('SELECT count(*) FROM policy_pilotobservation').fetchone()[0],1+bool(v.get('with_native_validation'))+bool(v.get('with_document_guard'))+bool(v.get('with_role_guard'))+bool(v.get('with_clock_guard')))
        check.assertEqual(db.execute('SELECT count(*) FROM policy_pilotobservation r JOIN auth_user u ON u.id=r.actor_id WHERE u.is_active').fetchone()[0],0)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_pilotbinding').fetchone()[0],1+bool(v.get('with_document_guard'))+bool(v.get('with_role_guard'))+bool(v.get('with_clock_guard')))
        check.assertEqual(db.execute("SELECT count(*) FROM policy_pilotbindingreview WHERE verdict='accept'").fetchone()[0],1+bool(v.get('with_document_guard'))+bool(v.get('with_role_guard'))+bool(v.get('with_clock_guard')))
        if v.get('with_clock_guard'):
            check.assertEqual(db.execute("SELECT count(*) FROM policy_pilotobservation WHERE snapshot->'bindings'->'native_guards'->0->>'operation'='workflow.clock.evaluate' AND snapshot->'bindings'->'native_guards'->0->'clock_calculation'->>'scope'='base_due_reassessment_only'").fetchone()[0],1)
            check.assertEqual(db.execute("SELECT count(*) FROM pmo_actionstate WHERE clock_meta->>'format'='psl.action-clock-input/v1' AND clock_meta->>'assignment_at' IS NOT NULL AND clock_meta->>'meeting_version' IS NOT NULL").fetchone()[0],1)
        if v.get('with_document_guard'):
            check.assertEqual(db.execute("SELECT count(*) FROM policy_pilotobservation WHERE snapshot->'bindings'->'native_guards'->0->>'operation'='document.publish' AND snapshot->'bindings'->'native_guards'->0->'head'->'document'->>'receipt_state'='verified_internal_receipt'").fetchone()[0],1)
        if v.get('with_role_guard'):
            check.assertEqual(db.execute("SELECT count(*) FROM policy_pilotobservation WHERE snapshot->'bindings'->'native_guards'->0->>'operation'='role.decision.evaluate' AND snapshot->'bindings'->'native_guards'->0->>'state'='READY_AT_OBSERVATION' AND snapshot->'bindings'->'native_guards'->0->'head'->'role_evaluation'->'business_approval'='false'::jsonb").fetchone()[0],1)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_pilotruntimereceipt').fetchone()[0],1)
        check.assertEqual(db.execute('SELECT count(*) FROM policy_pilotbindingreview r JOIN auth_user u ON u.id=r.actor_id WHERE u.is_active').fetchone()[0],0)
        if v.get('with_native_validation'):
            check.assertEqual(db.execute("SELECT count(*) FROM documents_validationreplay WHERE provenance->>'format' IN ('psl.native-validation/v1','psl.native-validation/v2')").fetchone()[0],2)
            check.assertEqual(db.execute("SELECT count(*) FROM documents_validationreview WHERE kind='acceptance' AND verdict='approve'").fetchone()[0],1)
            check.assertEqual(db.execute('SELECT count(*) FROM documents_validationreplay r JOIN auth_user u ON u.id=r.actor_id WHERE u.is_active').fetchone()[0],0)
    env=os.environ.copy();env.update(PGDATABASE=v['target'],DJANGO_SETTINGS_MODULE='config.settings')
    refused=subprocess.run([sys.executable,'manage.py','check'],capture_output=True,text=True,env=env,timeout=30)
    check.assertNotEqual(refused.returncode,0);check.assertIn('Quarantined recovery database',refused.stderr)
    root=Path(v['target_files'])
    owned=next(p for p in root.iterdir() if p.name!='.psl-recovery-intent')
    owned.write_bytes(b'synthetic-corrupted-recovered-file')
    invalid=d.report(a,c.pk,p.pk)
    check.assertFalse(invalid['physical_receipt_current']);check.assertFalse(invalid['human_recovered_review_current'])
    check.assertFalse(physical(a,c,'cold',j.pk)['receipt_verified'])
    result['physical_tamper_invalidated']=True
    result['impact_history_preserved']=True
    result['pilot_history_preserved']=True
    result['pilot_bindings_history_preserved']=True
    result['native_validation_history_preserved']=bool(v.get('with_native_validation'))
    result['private_impact_history_preserved']=bool(v.get('with_private_impact'))
    result['role_eligibility_history_preserved']=bool(v.get('with_role_eligibility'))
    result['document_guard_history_preserved']=bool(v.get('with_document_guard'))
    result['role_guard_history_preserved']=bool(v.get('with_role_guard'))
    result['clock_guard_history_preserved']=bool(v.get('with_clock_guard'))
    result['jobs']=d.Job.objects.filter(plan=p).count()
    return result


def reject_bootstrap():
    call_command('migrate',verbosity=0,interactive=False)
    get_user_model().objects.create_user(username='archived-style-imported-person')
    with check.assertRaises(CommandError):call_command('initialize_cold_control',verbosity=0)
    check.assertEqual(d.Identity.objects.count(),0)
    check.assertEqual(get_user_model().objects.count(),1)
    return {'preexisting_people_rejected':True}


if __name__=='__main__':
    v=json.load(sys.stdin);stage=sys.argv[1]
    if stage=='source':result=source()
    else:
        settings.COLD_RECOVERY=runtime()
        if stage=='initialize':
            call_command('migrate',verbosity=0,interactive=False)
            call_command('initialize_cold_control',verbosity=0)
            result={'initialized':True}
        else:result=globals()[stage]()
    print(json.dumps(result))
