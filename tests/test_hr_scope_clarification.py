"""Run774 synthetic internal scope question contracts, not actual HR appointments."""
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.db import connection, transaction, DatabaseError, close_old_connections
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.core.models import Evidence, Audit
from apps.documents.contracts import digest
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.hrfinance_validators import SCOPE_ROUTE
from apps.finance import hrfinance as hr, hr_scope as scope
from apps.finance.hrfinance_models import HRReadSnapshot, HRHandoffRecord, HRDisclosure
from apps.finance.models import Invoice, CashReceipt
from apps.workflows.models import HumanTask, TaskEvent, Outbox
from apps.workflows import factory
from apps.agents.hrfinance import investigate
from .hrfinance_helpers import fixture, policy, body, capture
from .helpers import rev


def configure(f, **updates):
    value={'owner_id':f['hr'].pk,'action':'confirm_minimum_scope','question_version':1,
           'disclosure':'codes_and_source_identity_only',**updates}
    return policy(f['hr'],f['case'],SCOPE_ROUTE,value,f['e']['owner'])


def rejected(f, key='scope-rejected'):
    payload=json.loads(body(f));payload['rows'][0]['medical']='RAW-SECRET-774'
    return hr.capture(f['hr'],f['case'].pk,f['contract'].pk,key,json.dumps(payload),rev(f['case']))


def question(f, snapshot):
    return scope.request(f['hr'],f['case'].pk,snapshot.pk,rev(f['case']))


def answer(f, task, reply='minimum_scope_confirmed'):
    return scope.respond(f['hr'],f['case'].pk,task.pk,task.revision,reply,rev(f['case']))


class HRScopeClarificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()

    def test_missing_route_preserves_original_hold_and_creates_nothing(self):
        f=self.f;s=rejected(f)
        r=investigate(f['hr'],f['case'].pk,rev(f['case']))
        o=r.result['findings'][0]['contracts'][0]['snapshots'][0]
        self.assertEqual(o['scope_exception'],{'status':'held','reason':'scope_exception_owner_unconfigured'})
        with self.assertRaises(ValidationError):question(f,s)
        self.assertFalse(HumanTask.objects.exists());self.assertEqual(s.payload,{})

    def test_configured_exact_question_reply_leaves_all_native_effects_unchanged(self):
        f=self.f;configure(f);s=rejected(f)
        old={m.__name__:list(m.objects.values()) for m in (HRReadSnapshot,HRDisclosure,HRHandoffRecord,Invoice,CashReceipt,Outbox)}
        with patch('apps.finance.hrfinance.read_snapshot',side_effect=AssertionError('No row access')):
            t=question(f,s)
        self.assertEqual(t.context['owner_id'],f['hr'].pk)
        self.assertEqual(question(f,s).pk,t.pk)
        self.assertEqual(scope.projection(f['hr'],t)['status'],'awaiting_owner')
        response=answer(f,t);t.refresh_from_db()
        self.assertEqual(response.data,{'reply':'minimum_scope_confirmed','outcome':'await_proper_minimal_resubmission'})
        self.assertEqual(scope.projection(f['hr'],t)['status'],'await_proper_minimal_resubmission')
        self.assertEqual(question(f,s).status,'completed')
        for m in (HRReadSnapshot,HRDisclosure,HRHandoffRecord,Invoice,CashReceipt,Outbox):self.assertEqual(list(m.objects.values()),old[m.__name__])
        for value in [list(TaskEvent.objects.values_list('data',flat=True)),list(HumanTask.objects.values_list('context',flat=True)),list(Audit.objects.values_list('data',flat=True)),list(Evidence.objects.values_list('body',flat=True))]:
            self.assertNotIn('RAW-SECRET-774',json.dumps(value));self.assertNotIn('"medical"',json.dumps(value))
        with self.assertRaises(ValidationError):hr.current_snapshot(s)

    def test_route_does_not_infer_authority_or_accept_free_text(self):
        f=self.f
        for updates in ({'owner_id':f['finance'].pk},{'action':'approve'},{'disclosure':'all_fields'},{'question_version':2},{'body':'RAW-SECRET-774'}):
            with self.assertRaises(ValidationError):configure(f,**updates)
        self.assertFalse(HumanTask.objects.exists())

    def test_non_scope_and_accepted_snapshots_cannot_get_question(self):
        f=self.f;configure(f);s=capture(f)
        with self.assertRaises(ValidationError):question(f,s)
        bad=json.loads(body(f));bad['rows']=[]
        other=hr.capture(f['hr'],f['case'].pk,f['contract'].pk,'other',json.dumps(bad),rev(f['case']))
        with self.assertRaises(ValidationError):question(f,other)

    def test_replies_are_closed_owner_only_and_revision_checked(self):
        f=self.f;configure(f);t=question(f,rejected(f))
        with self.assertRaises(ValidationError):answer(f,t,'RAW-SECRET-774')
        Grant.objects.create(case=f['case'],user=f['finance'],action='hrfinance.respond')
        with self.assertRaises(PermissionDenied):scope.respond(f['finance'],f['case'].pk,t.pk,t.revision,scope.REPLIES[0],rev(f['case']))
        answer(f,t)
        with self.assertRaises(ValidationError):answer(f,t)
        self.assertEqual(TaskEvent.objects.filter(action='hr_scope.responded').count(),1)

    def test_route_supersession_requires_cancel_and_new_task_preserving_history(self):
        f=self.f;configure(f);s=rejected(f);old=question(f,s);context=deepcopy(old.context)
        configure(f)
        with self.assertRaises(ValidationError):answer(f,old)
        with self.assertRaises(ValidationError):question(f,s)
        scope.cancel(f['hr'],f['case'].pk,old.pk,old.revision,rev(f['case']))
        new=question(f,s);old.refresh_from_db()
        self.assertNotEqual(new.pk,old.pk);self.assertEqual(old.context,context);self.assertEqual(old.status,'cancelled')
        self.assertEqual(scope.projection(f['hr'],new)['status'],'awaiting_owner')

    def test_revoked_route_owner_and_source_allow_requester_cancellation(self):
        f=self.f;p=configure(f);s=rejected(f);t=question(f,s)
        transition(f['hr'],p.pk,'revoked')
        Grant.objects.filter(case=f['case'],user=f['hr'],action='hrfinance.respond').update(active=False)
        hr.decide(f['hr'],f['case'].pk,f['contract'].pk,'revoke','revoke',f['e']['hr_disclosure_decision'].pk,rev(f['case']))
        self.assertEqual(scope.projection(f['hr'],t)['status'],'held')
        scope.cancel(f['hr'],f['case'].pk,t.pk,t.revision,rev(f['case']))
        t.refresh_from_db();self.assertEqual(t.status,'cancelled')
        with self.assertRaises((ValidationError,PermissionDenied)):answer(f,t)

    def test_new_export_holds_question_and_does_not_rewrite_rejection(self):
        f=self.f;configure(f);s=rejected(f);t=question(f,s);good=capture(f,'proper-resubmission')
        self.assertEqual(good.status,'accepted');self.assertEqual(scope.projection(f['hr'],t)['status'],'held')
        with self.assertRaises(ValidationError):answer(f,t)
        s.refresh_from_db();self.assertEqual(s.payload,{});self.assertEqual(s.status,'rejected')
        self.assertFalse(HRHandoffRecord.objects.filter(snapshot=good,kind='receipt').exists())

    def test_raw_sql_status_event_forgery_and_history_mutation_denied(self):
        f=self.f;configure(f);t=question(f,rejected(f))
        statements=[
            ('UPDATE workflows_humantask SET status=\'completed\',revision=revision+1 WHERE id=%s',[t.pk]),
            ('UPDATE workflows_humantask SET claimed_by_id=%s WHERE id=%s',[f['finance'].pk,t.pk]),
            ('DELETE FROM workflows_taskevent WHERE task_id=%s',[t.pk]),
            ('DELETE FROM workflows_humantask WHERE id=%s',[t.pk]),
        ]
        for sql,params in statements:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as c:c.execute(sql,params)
        for actor,action,data in [(f['hr'],'factory.information_received',{}),(f['finance'],'hr_scope.responded',{'reply':scope.REPLIES[0],'outcome':'await_proper_minimal_resubmission'}),(f['hr'],'hr_scope.responded',{'reply':None,'outcome':'await_proper_minimal_resubmission'}),(f['hr'],'hr_scope.responded',{'reply':scope.REPLIES[0],'outcome':'await_proper_minimal_resubmission','body':'RAW-SECRET-774'})]:
            with self.assertRaises(DatabaseError),transaction.atomic():TaskEvent.objects.create(task=t,actor=actor,action=action,data=data)
        t.status='completed'
        self.assertEqual(scope.projection(f['hr'],t)['status'],'held')
        self.assertIsNone(scope.response_event(t))

    def test_raw_insert_requires_canonical_key_and_prior_question_cancellation(self):
        f=self.f;configure(f);snapshot=rejected(f)
        config,owner,authority=scope.route(f['case'])
        context=scope.packet(snapshot,config,owner,authority)
        with connection.cursor() as cursor:
            cursor.execute("SELECT encode(sha256(convert_to(psl_fixed_json(%s::jsonb),'UTF8')),'hex')",[json.dumps(context)])
            self.assertEqual(cursor.fetchone()[0],digest(context))
        values={'case':f['case'],'kind':'factory_information','context':context,
                'claimed_by':owner,'required_role':'Configured HR scope owner','created_by':f['hr']}
        with self.assertRaises(DatabaseError),transaction.atomic():
            HumanTask.objects.create(factory_key='hr-scope:alternate-key',**values)
        with self.assertRaises(DatabaseError),transaction.atomic():
            HumanTask.objects.create(factory_key='hr-scope:'+digest(context),**{**values,'required_role':'RAW-SECRET-774'})
        task=question(f,snapshot)
        with self.assertRaises(DatabaseError),transaction.atomic():
            HumanTask.objects.create(factory_key=task.factory_key,**values)
        configure(f)
        config,owner,authority=scope.route(f['case'])
        successor=scope.packet(snapshot,config,owner,authority)
        self.assertNotEqual(context,successor)
        with self.assertRaises(DatabaseError),transaction.atomic():
            HumanTask.objects.create(factory_key='hr-scope:'+digest(successor),**{**values,'context':successor})
        self.assertEqual(HumanTask.objects.filter(context__purpose=scope.PURPOSE,status='open').count(),1)
        scope.cancel(f['hr'],f['case'].pk,task.pk,task.revision,rev(f['case']))
        new=question(f,snapshot);self.assertNotEqual(new.pk,task.pk)

    def test_generic_factory_handlers_fail_closed(self):
        f=self.f;configure(f);t=question(f,rejected(f))
        for fn,args in [(factory.claim_task,(f['hr'],t.pk,t.revision)),(factory.release_task_claim,(f['hr'],t.pk,t.revision,'reason')),(factory.provide_information,(f['hr'],t.pk,t.revision,rev(f['case']),'hr_correction_response','RAW-SECRET-774','synthetic'))]:
            with self.assertRaises(ValidationError):fn(*args)
        self.assertFalse(TaskEvent.objects.filter(action='factory.information_received').exists())

    def test_private_queue_and_agent_check_current_read_grants(self):
        f=self.f;configure(f);t=question(f,rejected(f));self.client.force_login(f['hr'])
        url=reverse('hrfinance',args=[f['case'].pk]);res=self.client.get(url)
        self.assertContains(res,'Assigned to you');self.assertNotContains(res,'RAW-SECRET-774');self.assertEqual(res['Cache-Control'],'no-store')
        run=investigate(f['hr'],f['case'].pk,rev(f['case']))
        self.assertEqual(run.result['findings'][0]['contracts'][0]['snapshots'][0]['scope_exception']['task_id'],t.pk)
        Grant.objects.filter(case=f['case'],user=f['hr'],action='hrfinance.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,403)
        with self.assertRaises(PermissionDenied):scope.projection(f['hr'],t)
        with self.assertRaises(PermissionDenied):investigate(f['hr'],f['case'].pk,rev(f['case']))

    def test_source_requester_grant_loss_holds_reply_without_other_case_leaks(self):
        f=self.f;configure(f);s=rejected(f);t=question(f,s)
        Grant.objects.filter(case=f['case'],user=f['hr'],action='agent.hrfinance').update(active=False)
        with self.assertRaises(PermissionDenied):answer(f,t)
        self.assertEqual(scope.projection(f['finance'],t)['status'],'held')
        from .helpers import setup_case
        u,c=setup_case(username='other-scope')
        with self.assertRaises(ValidationError):scope.request(u,c.pk,s.pk,rev(c))
        with self.assertRaises(HumanTask.DoesNotExist):scope.respond(u,c.pk,t.pk,t.revision,scope.REPLIES[0],rev(c))

    def test_changed_explicit_owner_gets_successor_without_grant_expansion(self):
        from apps.policy.services import register_reference,active_component
        from apps.policy.hrfinance_validators import AUTHORITY
        from .helpers import activate
        f=self.f;new=get_user_model().objects.create_user(username='second-synthetic-hr')
        for action in ['case.read','hrfinance.read','hrfinance.respond']:Grant.objects.create(case=f['case'],user=new,action=action)
        role=register_reference(f['hr'],f['case'].pk,'hrf-role:second','schema:psl/role-assignment/v1',{'user_id':new.pk,'role':'HR'},f['e']['owner'].pk)
        refs=active_component('D05.role_principal_assignments',f['case']).envelope['value']+[role.ref]
        activate(f['hr'],f['case'],'D05.role_principal_assignments',refs,f['e']['owner'])
        rules=deepcopy(f['config']['authority']);rules['assignments'].append({'user_id':new.pk,'purpose':'respond','role':'HR'})
        policy(f['hr'],f['case'],AUTHORITY,rules,f['e']['owner'])
        f['contract']=hr.contract(f['finance'],f['case'].pk,f['need'].pk,'two-owner-contract',f['e']['hr_contract_source'].pk,rev(f['case']))
        hr.decide(f['hr'],f['case'].pk,f['contract'].pk,'approve','two-owner-approval',f['e']['hr_disclosure_decision'].pk,rev(f['case']))
        configure(f);s=rejected(f);old=question(f,s);old_context=deepcopy(old.context)
        configure(f,owner_id=new.pk)
        scope.cancel(f['hr'],f['case'].pk,old.pk,old.revision,rev(f['case']))
        task=question(f,s);self.assertEqual(task.claimed_by_id,new.pk)
        with self.assertRaises(PermissionDenied):answer(f,task)
        scope.respond(new,f['case'].pk,task.pk,task.revision,scope.REPLIES[0],rev(f['case']))
        old.refresh_from_db();self.assertEqual(old.context,old_context);self.assertEqual(old.status,'cancelled')
        self.assertFalse(Grant.objects.filter(case=f['case'],user=new,action='hrfinance.snapshot.read').exists())

    def test_response_grant_loss_holds_only_clarification(self):
        f=self.f;configure(f);s=rejected(f);t=question(f,s)
        Grant.objects.filter(case=f['case'],user=f['hr'],action='hrfinance.respond').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):answer(f,t)
        # Existing separate HR capture still functions: this optional question is not a new approval.
        good=capture(f,'independent-minimal-export');self.assertEqual(good.status,'accepted')
        scope.cancel(f['hr'],f['case'].pk,t.pk,t.revision,rev(f['case']))
        self.assertEqual(HRReadSnapshot.objects.get(pk=s.pk).payload,{})

    def test_UI_typed_request_reply_and_no_extra_fields(self):
        f=self.f;configure(f);s=rejected(f);self.client.force_login(f['hr']);url=reverse('hrfinance',args=[f['case'].pk])
        self.client.post(url,{'action':'scope_request','revision':rev(f['case']),'snapshot':s.pk})
        t=HumanTask.objects.get(context__purpose=scope.PURPOSE)
        res=self.client.post(url,{'action':'scope_reply','revision':rev(f['case']),'scope_task':t.pk,'task_revision':t.revision,'reply':scope.REPLIES[1],'body':'RAW-SECRET-774'},follow=True)
        self.assertNotContains(res,'RAW-SECRET-774');self.assertContains(res,'Unexpected command fields')
        self.client.post(url,{'action':'scope_reply','revision':rev(f['case']),'scope_task':t.pk,'task_revision':t.revision,'reply':scope.REPLIES[1]})
        t.refresh_from_db();self.assertEqual(t.status,'completed');self.assertEqual(scope.response_event(t).data['reply'],scope.REPLIES[1])


class HRScopeClarificationRaceTests(TransactionTestCase):
    def test_concurrent_duplicate_requests_and_replies_serialize(self):
        f=fixture();configure(f);s=rejected(f)
        def race(fn):
            barrier=Barrier(2)
            def worker():
                close_old_connections()
                try:
                    barrier.wait();return fn()
                except ValidationError:return 'stale'
                finally:close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(lambda _:worker(),range(2)))
        expected=rev(f['case'])
        results=race(lambda:scope.request(f['hr'],f['case'].pk,s.pk,expected).pk)
        self.assertEqual(results.count('stale'),1);self.assertEqual(HumanTask.objects.filter(context__purpose=scope.PURPOSE).count(),1)
        t=HumanTask.objects.get(context__purpose=scope.PURPOSE);expected=rev(f['case'])
        results=race(lambda:scope.respond(f['hr'],f['case'].pk,t.pk,t.revision,scope.REPLIES[0],expected).pk)
        self.assertEqual(results.count('stale'),1);self.assertEqual(TaskEvent.objects.filter(action='hr_scope.responded').count(),1)

    def test_raw_concurrent_duplicate_requests_are_serialized_and_stale_open_route_blocks(self):
        f=fixture();configure(f);snapshot=rejected(f)
        config,owner,authority=scope.route(f['case']);context=scope.packet(snapshot,config,owner,authority)
        def race(packet):
            barrier=Barrier(2)
            def worker():
                close_old_connections()
                try:
                    barrier.wait()
                    with transaction.atomic():
                        return HumanTask.objects.create(case_id=f['case'].pk,kind='factory_information',
                            factory_key='hr-scope:'+digest(packet),context=packet,claimed_by_id=owner.pk,
                            required_role='Configured HR scope owner',created_by_id=f['hr'].pk).pk
                except DatabaseError:return 'rejected'
                finally:close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(lambda _:worker(),range(2)))
        outcomes=race(context)
        self.assertEqual(outcomes.count('rejected'),1)
        configure(f)
        config,owner,authority=scope.route(f['case']);successor=scope.packet(snapshot,config,owner,authority)
        self.assertEqual(race(successor),['rejected','rejected'])
        self.assertEqual(HumanTask.objects.filter(context__purpose=scope.PURPOSE,status='open').count(),1)

    def test_raw_question_creation_rejects_repeatable_read(self):
        f=fixture();configure(f);snapshot=rejected(f)
        config,owner,authority=scope.route(f['case']);context=scope.packet(snapshot,config,owner,authority)
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            HumanTask.objects.create(case=f['case'],kind='factory_information',factory_key='hr-scope:'+digest(context),
                context=context,claimed_by=owner,required_role='Configured HR scope owner',created_by=f['hr'])
        self.assertFalse(HumanTask.objects.filter(context__purpose=scope.PURPOSE).exists())

    def test_raw_response_and_cancellation_events_reject_stale_snapshot_isolation(self):
        f=fixture();configure(f);task=question(f,rejected(f))
        for level in ['REPEATABLE READ','SERIALIZABLE']:
            for action,data in [('hr_scope.responded',{'reply':scope.REPLIES[0],'outcome':'await_proper_minimal_resubmission'}),('hr_scope.cancelled',{})]:
                with self.assertRaises(DatabaseError),transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute('SET TRANSACTION ISOLATION LEVEL '+level)
                    TaskEvent.objects.create(task=task,actor=f['hr'],action=action,data=data)
        self.assertFalse(TaskEvent.objects.filter(task=task,action__in=['hr_scope.responded','hr_scope.cancelled']).exists())
        task.refresh_from_db();self.assertEqual(task.status,'open')
        answer(f,task)
