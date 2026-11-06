import copy
import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, transaction, connection
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case, Evidence, Audit
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.models import Configuration, ScopeVersion, ScopeState, ScopeApplication
from apps.policy import scopes
from apps.policy.services import save_draft, transition, resolve, register_reference, reference_values
from apps.agents.policy_scope import investigate
from adapters.policy_scope import bind
from tests.helpers import setup_case, envelope, activate, signed, rev

COMPONENT='D04.iana_timezone'


def fixture():
    actor, source = setup_case(username='scope-human')
    target = Case.objects.create(tenant=source.tenant,title='Target project',kind='project',synthetic=True)
    for action in Grant.objects.filter(user=actor,case=source).values_list('action',flat=True):
        Grant.objects.create(user=actor,case=target,action=action)
    se = add_evidence(actor,source.pk,'policy_decision','Synthetic source criteria, no real appointment','synthetic:scope')
    te = add_evidence(actor,target.pk,'policy_decision','Synthetic target decision','synthetic:scope')
    return actor,source,target,se,te


def source_version(actor,case,evidence,kind='organization',ref=None,paths=None,env=None):
    cfg=save_draft(actor,case.pk,env or envelope(case,COMPONENT,'UTC',evidence))
    transition(actor,cfg.pk,'validated')
    src=scopes.create(actor,cfg.pk,kind,ref or (case.tenant if kind=='organization' else str(case.pk)),paths or [])
    scopes.transition(actor,src.pk,'validated');scopes.transition(actor,src.pk,'active')
    return src


class PolicyScopeTests(TestCase):
    def setUp(self):
        self.a,self.s,self.t,self.se,self.te=fixture()

    def applied(self,src=None):
        src=src or source_version(self.a,self.s,self.se)
        cfg=scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
        transition(self.a,cfg.pk,'validated');transition(self.a,cfg.pk,'active')
        return src,cfg

    def test_explicit_application_preserves_local_fk_and_narrow_holds(self):
        src=source_version(self.a,self.s,self.se)
        self.assertEqual(resolve(COMPONENT,self.t).status,'MISSING')
        cfg=scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
        self.assertEqual(resolve(COMPONENT,self.t).status,'MISSING')
        transition(self.a,cfg.pk,'validated');transition(self.a,cfg.pk,'active')
        self.assertEqual(resolve(COMPONENT,self.t).configuration.pk,cfg.pk)
        self.assertEqual(cfg.envelope['subject_scope']['ref'],str(self.t.pk))
        self.assertEqual(ScopeApplication.objects.get(configuration=cfg).source_id,src.pk)
        self.assertEqual(resolve('D13.human_authority_role_ref',self.t).status,'MISSING')
        self.assertEqual(scopes.resolve_source(self.a,self.s.pk,COMPONENT,'organization',self.s.tenant,expected_revision=src.revision).configuration.pk,src.pk)
        self.assertEqual(scopes.resolve_source(self.a,self.s.pk,COMPONENT,'organization',self.s.tenant,expected_revision=99).status,'INVALID')
        self.assertEqual(scopes.resolve_source(self.a,self.s.pk,COMPONENT,'contract','evidence:unknown').status,'MISSING')
        with self.assertRaises(ValidationError):transition(self.a,src.configuration_id,'active')
        with self.assertRaises(ValidationError):scopes.create(self.a,cfg.pk,'organization',self.t.tenant,[])

    def test_four_scope_identities_and_no_cross_case_precedence(self):
        for kind,ref in [('project',str(self.s.pk)),('contract','evidence:'+str(add_evidence(self.a,self.s.pk,'sow','Draft SOW','synthetic').pk))]:
            src=source_version(self.a,self.s,self.se,kind,ref)
            with self.assertRaises(ValidationError):scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
            local=scopes.apply(self.a,src.pk,self.s.pk,self.se.pk,[])
            transition(self.a,local.pk,'validated');transition(self.a,local.pk,'active')
            self.assertEqual(resolve(COMPONENT,self.s).configuration.pk,local.pk)
        self.s.kind='support';self.s.save(update_fields=['kind'])
        service=source_version(self.a,self.s,self.se,'service')
        local=scopes.apply(self.a,service.pk,self.s.pk,self.se.pk,[])
        transition(self.a,local.pk,'validated');transition(self.a,local.pk,'active')
        self.assertEqual(scopes.source_health(service),'ACTIVE')

    def test_invalid_scope_and_unrecorded_contract_rejected(self):
        cfg=save_draft(self.a,self.s.pk,envelope(self.s,COMPONENT,'UTC',self.se));transition(self.a,cfg.pk,'validated')
        for kind,ref in [('organization','other'),('project',str(self.t.pk)),('service',str(self.s.pk)),('contract','evidence:999999'),('arbitrary','text')]:
            with self.assertRaises(ValidationError):scopes.create(self.a,cfg.pk,kind,ref,[])
        self.assertEqual(ScopeVersion.objects.count(),0)

    def test_revoked_superseded_expired_and_explicit_local_successor(self):
        src,cfg=self.applied()
        new=source_version(self.a,self.s,self.se)
        self.assertEqual(scopes.state(src),'superseded')
        self.assertEqual(resolve(COMPONENT,self.t).status,'INVALID')
        self.assertEqual(Configuration.objects.get(pk=cfg.pk).envelope,cfg.envelope)
        src2,cfg2=self.applied(new)
        self.assertEqual(resolve(COMPONENT,self.t,expected_revision=cfg.revision).status,'INVALID')
        scopes.transition(self.a,new.pk,'revoked')
        self.assertEqual(resolve(COMPONENT,self.t).status,'REVOKED')
        local=activate(self.a,self.t,COMPONENT,'Africa/Lagos',self.te)
        self.assertEqual(resolve(COMPONENT,self.t).configuration.pk,local.pk)
        env=envelope(self.s,COMPONENT,'UTC',self.se);env['effective_until']=(timezone.now()+timedelta(hours=1)).isoformat()
        expiring=source_version(self.a,self.s,self.se,env=env)
        _,derived=self.applied(expiring)
        self.assertEqual(resolve(COMPONENT,self.t,at=timezone.now()+timedelta(days=1)).status,'EXPIRED')

    def test_current_source_target_access_and_classification(self):
        src=source_version(self.a,self.s,self.se)
        for field,value in [('tenant','foreign'),('synthetic',False)]:
            old=getattr(self.t,field);setattr(self.t,field,value);self.t.save(update_fields=[field])
            with self.assertRaises(PermissionDenied):scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
            setattr(self.t,field,old);self.t.save(update_fields=[field])
        Grant.objects.filter(user=self.a,case=self.s,action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
        Grant.objects.filter(user=self.a,case=self.s,action='policy.read').update(active=True)
        src,cfg=self.applied(src)
        Grant.objects.filter(user=self.a,case=self.s,action='policy.activate').update(active=False)
        self.assertEqual(resolve(COMPONENT,self.t).status,'INVALID')
        Grant.objects.filter(user=self.a,case=self.s,action='policy.activate').update(active=True)
        Grant.objects.filter(user=self.a,case=self.t,action='policy.configure').update(active=False)
        self.assertEqual(resolve(COMPONENT,self.t).status,'INVALID')

    def test_registered_reference_binding_revalidates_real_target_schema(self):
        component='D04.working_calendar_ref'
        ref=register_reference(self.a,self.s.pk,'calendar','schema:psl/working-calendar/v1',{'weekdays':[0,1,2,3,4],'holidays':[],'due_time':'17:00'},self.se.pk)
        env=envelope(self.s,component,ref.ref,self.se)
        src=source_version(self.a,self.s,self.se,paths=['/0/due_time'],env=env)
        with self.assertRaises(ValidationError):scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
        before=Configuration.objects.count()
        with self.assertRaises(ValidationError):scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[{'path':'/0/due_time','value':'99:00'}])
        self.assertEqual(Configuration.objects.count(),before)
        cfg=scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[{'path':'/0/due_time','value':'16:30'}])
        transition(self.a,cfg.pk,'validated');transition(self.a,cfg.pk,'active')
        self.assertEqual(reference_values(cfg)[0]['due_time'],'16:30')
        self.assertEqual(reference_values(src.configuration)[0]['due_time'],'17:00')
        self.assertEqual(resolve(component,self.t).status,'ACTIVE')

    def test_binding_protocol_is_finite_closed_and_scalar(self):
        values=[{'id':1,'text':'old','nested':{'x':3}}]
        for paths,bindings in [(['/0'],[]),(['/missing'],[]),(['/0/id'],[{'path':'/0/id','value':True}]),(['/0/id'],[{'path':'/0/id','value':float('nan')}]),(['/0/id'],[{'path':'/0/text','value':'new'}]),(['/0/id'],[{'path':'/0/id','value':2,'code':'x'}]),(['/0/id','/0/id'],[])]:
            with self.assertRaises(ValidationError):bind(values,paths,bindings)
        self.assertEqual(values[0]['id'],1)

    def test_source_lifecycle_staleness_and_activation_rechecks_origin(self):
        src=source_version(self.a,self.s,self.se)
        cfg=scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
        transition(self.a,cfg.pk,'validated')
        scopes.transition(self.a,src.pk,'revoked')
        with self.assertRaises(ValidationError):transition(self.a,cfg.pk,'active')
        self.assertEqual(resolve(COMPONENT,self.t).status,'MISSING')
        with self.assertRaises(ValidationError):scopes.transition(self.a,src.pk,'active')

    def test_new_drafts_do_not_displace_published_source_and_stale_draft_cannot_publish(self):
        first=source_version(self.a,self.s,self.se)
        drafts=[]
        for _ in range(2):
            cfg=save_draft(self.a,self.s.pk,envelope(self.s,COMPONENT,'UTC',self.se));transition(self.a,cfg.pk,'validated')
            draft=scopes.create(self.a,cfg.pk,'organization',self.s.tenant,[])
            scopes.transition(self.a,draft.pk,'validated');drafts.append(draft)
        self.assertEqual(scopes.source_health(first),'ACTIVE')
        with self.assertRaises(ValidationError):scopes.transition(self.a,drafts[0].pk,'active')
        scopes.transition(self.a,drafts[1].pk,'active')
        self.assertEqual(scopes.source_health(first),'INVALID')

    def test_actual_pmo_decisions_pin_local_policy_and_revoked_origin_holds_signature_only(self):
        from tests.helpers import prepared,roles
        from apps.pmo.services import decide,sign_baseline
        from apps.pmo.models import Decision,Baseline
        from apps.policy.services import PolicyHold
        ev=prepared(self.a,self.t)
        role_config=roles(self.a,self.s,self.se)
        src=source_version(self.a,self.s,self.se,env=envelope(self.s,'D05.role_principal_assignments',role_config.envelope['value'],self.se))
        cfg=scopes.apply(self.a,src.pk,self.t.pk,self.te.pk,[])
        transition(self.a,cfg.pk,'validated');transition(self.a,cfg.pk,'active')
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(self.a,self.t.pk,role,rev(self.t))
        self.assertEqual(set(Decision.objects.values_list('policy_id',flat=True)),{cfg.pk})
        scopes.transition(self.a,src.pk,'revoked')
        with self.assertRaises(PolicyHold):sign_baseline(self.a,self.t.pk,ev['signature'].pk,rev(self.t))
        self.assertIsNone(Baseline.objects.get(case=self.t).signed_id)
        self.assertEqual(Decision.objects.count(),4)
        add_evidence(self.a,self.t.pk,'document','Unrelated document work continues','synthetic:scope')

    def test_postgresql_immutable_history_and_edge_guards(self):
        src,cfg=self.applied()
        self.assertEqual(connection.vendor,'postgresql')
        for model in [ScopeVersion,ScopeState,ScopeApplication]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().delete()
        with self.assertRaises(DatabaseError),transaction.atomic():ScopeVersion.objects.filter(pk=src.pk).update(ref='tampered')
        with self.assertRaises(DatabaseError),transaction.atomic():ScopeState.objects.create(source=src,state='draft',actor=self.a)
        cfg=save_draft(self.a,self.s.pk,envelope(self.s,COMPONENT,'UTC',self.se));transition(self.a,cfg.pk,'validated')
        draft=scopes.create(self.a,cfg.pk,'organization',self.s.tenant,[])
        with self.assertRaises(DatabaseError),transaction.atomic():ScopeState.objects.create(source=draft,state='revoked',actor=self.a)
        cfg2=save_draft(self.a,self.s.pk,envelope(self.s,COMPONENT,'UTC',self.se));transition(self.a,cfg2.pk,'validated')
        with self.assertRaises(DatabaseError),transaction.atomic():
            unstarted=ScopeVersion.objects.create(configuration=cfg2,kind='organization',ref=self.s.tenant,revision=3,binding_paths=[],created_by=self.a)
            ScopeState.objects.create(source=unstarted,state='validated',actor=self.a)
        with self.assertRaises(DatabaseError),transaction.atomic():ScopeApplication.objects.create(configuration=src.configuration,source=src,bindings=[],actor=self.a)

    def test_ui_csrf_authority_errors_and_bounded_agent(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        url=reverse('policy_scopes',args=[self.s.pk]);response=client.get(url)
        self.assertContains(response,'Explicit policy scopes')
        self.assertEqual(client.post(url,{'action':'create'}).status_code,403)
        cfg=save_draft(self.a,self.s.pk,envelope(self.s,COMPONENT,'UTC',self.se));transition(self.a,cfg.pk,'validated')
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(url,{'action':'create','configuration':cfg.pk,'kind':'organization','ref':self.s.tenant,'binding_paths':'[]','csrfmiddlewaretoken':token}).status_code,302)
        src=ScopeVersion.objects.get()
        for action in ['validated','active']:
            self.assertEqual(client.post(url,{'action':action,'source':src.pk,'csrfmiddlewaretoken':token}).status_code,302)
        self.assertEqual(client.post(reverse('policy_scopes',args=[self.t.pk]),{'action':'apply','source':src.pk,'decision':self.te.pk,'bindings':'[]','csrfmiddlewaretoken':token}).status_code,302)
        report=investigate(self.a,self.t.pk);self.assertEqual(report['effect_tools'],[])
        self.assertEqual(len(report['evidence']['applications']),1)
        Grant.objects.filter(user=self.a,case=self.s,action='policy.read').update(active=False)
        self.assertEqual(client.get(url).status_code,403)

    def test_archived_scope_history_cannot_restore_authority(self):
        src,cfg=self.applied()
        # Same account/grant transformation performed by the native archive adapter.
        get_user_model().objects.filter(pk=self.a.pk).update(is_active=False,password='!')
        Grant.objects.all().delete()
        self.assertEqual(ScopeVersion.objects.count(),1)
        self.assertEqual(ScopeApplication.objects.count(),1)
        self.assertEqual(scopes.source_health(src),'INVALID')
        self.assertEqual(resolve(COMPONENT,self.t).status,'INVALID')

    def test_committed_uncertain_effect_reconciles_after_scope_revocation(self):
        from apps.pmo.services import complete_milestone
        from apps.workflows.services import run_once
        from apps.workflows.models import Outbox
        from apps.finance.models import Handoff
        from adapters.finance import TimeoutAfterAccept
        e=signed(self.a,self.t)
        src,cfg=self.applied()
        complete_milestone(self.a,self.t.pk,'Scoped recovery regression',e['completion'].pk,rev(self.t))
        run_once(TimeoutAfterAccept(),case_id=self.t.pk)
        self.assertEqual(Outbox.objects.get().status,'unknown')
        scopes.transition(self.a,src.pk,'revoked')
        Grant.objects.filter(user=self.a,case=self.t,action='milestone.complete').update(active=False)
        self.assertEqual(resolve(COMPONENT,self.t).status,'REVOKED')
        run_once(TimeoutAfterAccept(),case_id=self.t.pk)
        self.assertEqual(Outbox.objects.get().status,'confirmed');self.assertEqual(Handoff.objects.count(),1)


class ScopeConcurrencyTests(TransactionTestCase):
    def test_two_applications_serialize_local_revisions(self):
        a,s,t,se,te=fixture();src=source_version(a,s,se);barrier=Barrier(2)
        def worker(_):
            close_old_connections();u=get_user_model().objects.get(pk=a.pk);barrier.wait()
            try:return scopes.apply(u,src.pk,t.pk,te.pk,[]).revision
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(worker,range(2)))
        self.assertEqual(sorted(result),[1,2]);self.assertEqual(ScopeApplication.objects.count(),2)

    def test_revocation_waits_for_runtime_transaction_boundary(self):
        a,s,t,se,te=fixture();src=source_version(a,s,se)
        cfg=scopes.apply(a,src.pk,t.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        acquired,started,finished=Event(),Event(),Event()
        def reader():
            close_old_connections()
            try:
                with transaction.atomic():
                    self.assertEqual(resolve(COMPONENT,t).status,'ACTIVE');acquired.set()
                    self.assertTrue(started.wait(10));self.assertFalse(finished.wait(.2))
            finally:close_old_connections()
        def revoker():
            close_old_connections()
            try:
                self.assertTrue(acquired.wait(10));started.set()
                scopes.transition(get_user_model().objects.get(pk=a.pk),src.pk,'revoked');finished.set()
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(reader),pool.submit(revoker)]
            for future in futures:future.result(timeout=30)
        self.assertTrue(finished.is_set());self.assertEqual(resolve(COMPONENT,t).status,'REVOKED')
