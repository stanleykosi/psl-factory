import copy,json,uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError,connection,close_old_connections
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.urls import reverse
from apps.core.models import Evidence,Audit
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy import pilot,pilot_validators
from apps.policy.models import PilotContract,PilotObservation,Configuration
from apps.policy.services import transition
from apps.agents.pilot import investigate
from adapters import pilot_preflight as adapter
from tests.helpers import setup_case,activate


def selection(actor,case):
    from django.conf import settings
    p=json.loads((settings.BASE_DIR/'fixtures/pilot-preflight.json').read_text(encoding='utf-8'))['base']
    return dict(p,case_id=str(case.pk),participants=[{'user_id':actor.pk,'actions':['case.read']}])


class PilotTests(TestCase):
    def setUp(self):
        self.a,self.c=setup_case(username='pilot-author');self.p=selection(self.a,self.c)

    def record(self):
        contract=pilot.configure(self.a,self.c.pk,self.p)
        return contract,pilot.capture(self.a,self.c.pk,contract.pk)

    def test_selected_read_only_pack_idempotence_unknowns_and_no_business_writes(self):
        before=(Evidence.objects.count(),Configuration.objects.count(),self.c.revision)
        c,r=self.record();self.assertEqual(pilot.capture(self.a,self.c.pk,c.pk).pk,r.pk)
        report=pilot.inspect(self.a,self.c.pk,r.pk)
        self.assertTrue(report['current']);self.assertEqual(report['snapshot']['policies'][0]['dependencies'],[])
        self.assertFalse(report['operational_acceptance']);self.assertEqual(report['snapshot']['boundaries']['effect_tools'],[])
        self.assertFalse(report['snapshot']['coverage']['complete_122_acceptance'])
        self.c.refresh_from_db();self.assertEqual((Evidence.objects.count(),Configuration.objects.count(),self.c.revision),before)
        self.assertEqual(Audit.objects.filter(action__startswith='agent.data.pilot').count(),2)
        self.assertEqual(investigate(self.a,self.c.pk,r.pk)['effect_tools'],[])

    def test_typed_validator_rejects_unknowns_effects_duplicates_and_budgets(self):
        for key,value in [('read_only',False),('operations',['arbitrary.dispatch']),('case_id',str(uuid.uuid4())),
            ('process_ids',['P999']),('integrations',list(range(1,22))),('jobs',[{'family':'arbitrary','id':1}])]:
            p=copy.deepcopy(self.p);p[key]=value
            with self.assertRaises(ValidationError):pilot.configure(self.a,self.c.pk,p)
        p=copy.deepcopy(self.p);p['secret']='must not be accepted'
        with self.assertRaises(ValidationError):pilot.configure(self.a,self.c.pk,p)
        p=copy.deepcopy(self.p);p['participants']*=2
        with self.assertRaises(ValidationError):pilot.configure(self.a,self.c.pk,p)
        self.assertEqual(PilotContract.objects.count(),0)

    def test_only_selected_dependencies_and_policy_heads_invalidate(self):
        self.p['operations']=['workflow.clock.evaluate','payment_exception.prepare_track']
        c,r=self.record();policies=r.snapshot['policies']
        self.assertEqual(len(policies[0]['dependencies']),4)
        self.assertFalse(policies[0]['policy_ready']);self.assertTrue(policies[1]['policy_ready'])
        self.assertNotIn('D13.payment_denominator_rule_ref',json.dumps(policies))
        e=add_evidence(self.a,self.c.pk,'policy_decision','Explicit synthetic timezone evidence','synthetic:pilot')
        p=activate(self.a,self.c,'D04.iana_timezone','UTC',e)
        self.assertFalse(pilot.inspect(self.a,self.c.pk,r.pk)['current'])
        successor=pilot.capture(self.a,self.c.pk,c.pk)
        timezone_row=next(v for v in successor.snapshot['policies'][0]['dependencies'] if v['component']=='D04.iana_timezone')
        self.assertEqual(timezone_row['configuration'],p.pk);self.assertEqual(timezone_row['status'],'ACTIVE')
        transition(self.a,p.pk,'revoked');self.assertFalse(pilot.inspect(self.a,self.c.pk,successor.pk)['current'])

    def test_current_participant_grants_and_inactive_users_are_holds(self):
        c,r=self.record();Grant.objects.filter(case=self.c,user=self.a,action='case.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.inspect(self.a,self.c.pk,r.pk)
        Grant.objects.filter(case=self.c,user=self.a,action='case.read').update(active=True)
        b=get_user_model().objects.create_user(username='pilot-participant')
        Grant.objects.create(case=self.c,user=b,action='case.read')
        p=copy.deepcopy(self.p);p['participants'].append({'user_id':b.pk,'actions':['finance.read']})
        contract=pilot.configure(self.a,self.c.pk,p,c.pk);r=pilot.capture(self.a,self.c.pk,contract.pk)
        self.assertEqual(r.snapshot['participants'][1]['missing'],['finance.read'])
        b.is_active=False;b.save(update_fields=['is_active'])
        self.assertFalse(pilot.inspect(self.a,self.c.pk,r.pk)['current'])
        n=pilot.capture(self.a,self.c.pk,contract.pk)
        self.assertEqual(n.snapshot['participants'][1]['missing'],['case.read','finance.read'])

    def test_author_revocation_source_changes_contract_successors_and_expiry(self):
        from datetime import timedelta
        from django.utils import timezone
        c,r=self.record()
        Grant.objects.filter(case=self.c,user=self.a,action='pilot.configure').update(active=False)
        self.assertFalse(pilot.inspect(self.a,self.c.pk,r.pk)['current'])
        Grant.objects.filter(case=self.c,user=self.a,action='pilot.configure').update(active=True)
        with patch('apps.policy.pilot.timezone.now',return_value=timezone.now()+timedelta(minutes=16)):
            self.assertFalse(pilot.inspect(self.a,self.c.pk,r.pk)['current'])
            refreshed=pilot.capture(self.a,self.c.pk,c.pk)
            self.assertNotEqual(refreshed.pk,r.pk)
            self.assertTrue(pilot.inspect(self.a,self.c.pk,refreshed.pk)['current'])
        technical=adapter.technical();technical['source_identity']='changed'
        with patch('adapters.pilot_preflight.technical',return_value=technical):
            self.assertFalse(pilot.inspect(self.a,self.c.pk,r.pk)['current'])
        with self.assertRaises(ValidationError):pilot.configure(self.a,self.c.pk,self.p)
        pilot.configure(self.a,self.c.pk,self.p,c.pk)
        self.assertTrue(pilot.inspect(self.a,self.c.pk,r.pk)['superseded'])
        with self.assertRaises(ValidationError):pilot.capture(self.a,self.c.pk,c.pk)

    def test_case_lookup_boundary_and_foreign_participants(self):
        c,r=self.record();b,foreign=setup_case(username='pilot-foreign')
        for pk in [r.pk,999999]:
            with patch('apps.policy.pilot.PilotObservation.objects.select_related') as query:
                with self.assertRaises(PermissionDenied):pilot.inspect(b,self.c.pk,pk)
                query.assert_not_called()
        p=copy.deepcopy(self.p);p['participants']=[{'user_id':b.pk,'actions':['case.read']}]
        with self.assertRaises(ValidationError):pilot.configure(self.a,self.c.pk,p,c.pk)
        with self.assertRaises(ValidationError):pilot.capture(b,foreign.pk,c.pk)

    def test_postgresql_history_and_identity_guards(self):
        c,r=self.record()
        for model,pk,field,value in [(PilotContract,c.pk,'version',2),(PilotObservation,r.pk,'sha256','0'*64)]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).update(**{field:value})
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).delete()
        with self.assertRaises(DatabaseError),transaction.atomic():
            PilotContract.objects.create(case=self.c,version=2,payload=dict(self.p,read_only=False),sha256='0'*64,actor=self.a)
        s=copy.deepcopy(r.snapshot);s['boundaries']['operational_acceptance']=True
        with self.assertRaises(DatabaseError),transaction.atomic():
            PilotObservation.objects.create(contract=c,snapshot=s,sha256='0'*64,operation_key='1'*64,actor=self.a)

    def test_actual_csrf_ui_capture_export_agent_and_no_get_writes(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        url=reverse('pilot_preflight',args=[self.c.pk]);response=client.get(url)
        self.assertContains(response,'Owner values remain deferred');self.assertEqual(response['Cache-Control'],'no-store')
        data={'process_ids':['P01'],'operations':['payment_exception.prepare_track'],'participants':[str(self.a.pk)],'actions':['case.read']}
        self.assertEqual(client.post(url,data).status_code,403)
        data['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
        response=client.post(url,data);self.assertEqual(response.status_code,302)
        c=PilotContract.objects.get();target=reverse('pilot_contract',args=[self.c.pk,c.pk])
        self.assertEqual(client.post(target,{'csrfmiddlewaretoken':data['csrfmiddlewaretoken']}).status_code,302)
        r=PilotObservation.objects.get();before=(Audit.objects.count(),Evidence.objects.count(),PilotObservation.objects.count())
        url=reverse('pilot_observation',args=[self.c.pk,r.pk]);self.assertContains(client.get(url),'Bounded investigator')
        exported=client.get(url+'?export=1');self.assertTrue(exported.json()['current']);self.assertEqual(exported['Cache-Control'],'no-store')
        self.assertEqual(before,(Audit.objects.count(),Evidence.objects.count(),PilotObservation.objects.count()))
        Grant.objects.filter(case=self.c,user=self.a,action='pilot.read').update(active=False)
        self.assertEqual(client.get(url+'?export=1').status_code,403)

    def test_technical_findings_are_observed_and_redacted(self):
        with override_settings(DEBUG=True,SECRET_KEY='synthetic-private-secret',SESSION_COOKIE_SECURE=False):
            value=adapter.technical()
        self.assertTrue(value['debug_enabled']);self.assertTrue(value['deployment_checks'])
        self.assertNotIn('synthetic-private-secret',json.dumps(value));self.assertEqual(value['worker_identity'],'UNVERIFIED')

    def test_inactive_archived_style_actor_cannot_read_history_or_regain_authority(self):
        c,r=self.record();self.a.is_active=False;self.a.is_superuser=True;self.a.save(update_fields=['is_active','is_superuser'])
        Grant.objects.filter(user=self.a,case=self.c).delete()
        with self.assertRaises(PermissionDenied):pilot.inspect(self.a,self.c.pk,r.pk)
        with self.assertRaises(PermissionDenied):pilot.capture(self.a,self.c.pk,c.pk)


@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class NativePilotTests(TestCase):
    def test_actual_readiness_health_review_and_revision_change_without_probe_or_write(self):
        from tests.readiness_helpers import fixture,ready,probe
        from apps.workflows.readiness_models import IntegrationProbe
        f=fixture(prefix='pilot-integration');ready(f)
        a,c=f['actor'],f['case'];p=selection(a,c);p['integrations']=[f['contract'].pk]
        contract=pilot.configure(a,c.pk,p);r=pilot.capture(a,c.pk,contract.pk)
        before=IntegrationProbe.objects.count();value=pilot.inspect(a,c.pk,r.pk)
        integration=value['snapshot']['integrations'][0]
        self.assertTrue(integration['current_ready']);self.assertTrue(integration['review_current'])
        self.assertFalse(integration['operational_ready']);self.assertNotIn('credential_ref',integration)
        self.assertEqual(IntegrationProbe.objects.count(),before)
        probe(f,key='new-health');self.assertFalse(pilot.inspect(a,c.pk,r.pk)['current'])
        Grant.objects.filter(case=c,user=a,action='integration.source.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.inspect(a,c.pk,r.pk)

    def test_actual_unknown_handoff_receipt_head_is_observed_without_replay(self):
        from tests.readiness_helpers import fixture,handoff
        from adapters.finance import TimeoutAfterAccept
        from apps.workflows.services import run_once
        from apps.finance.models import Handoff
        f=fixture(prefix='pilot-effect');a,c=f['actor'],f['case'];job=handoff(f)
        p=selection(a,c);p['jobs']=[{'family':'handoff','id':job.pk}]
        contract=pilot.configure(a,c.pk,p);r=pilot.capture(a,c.pk,contract.pk)
        self.assertFalse(r.snapshot['jobs'][0]['receipt_verified']);self.assertEqual(Handoff.objects.count(),0)
        run_once(TimeoutAfterAccept(),case_id=c.pk)
        report=pilot.inspect(a,c.pk,r.pk);self.assertFalse(report['current']);job.refresh_from_db()
        self.assertEqual(job.status,'unknown');self.assertEqual(job.attempts,1)
        successor=pilot.capture(a,c.pk,contract.pk)
        self.assertTrue(successor.snapshot['jobs'][0]['receipt_verified']);self.assertFalse(successor.snapshot['jobs'][0]['replay_permitted'])
        self.assertEqual(Handoff.objects.count(),1)
        self.assertTrue(any('receipt-first' in s for s in investigate(a,c.pk,successor.pk)['findings']))
        Grant.objects.filter(case=c,user=a,action='milestone.complete').update(active=False)
        run_once(case_id=c.pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(Handoff.objects.count(),1);self.assertFalse(pilot.inspect(a,c.pk,successor.pk)['current'])

    def test_foreign_integration_and_domain_job_denied(self):
        from tests.readiness_helpers import fixture,handoff
        f=fixture(prefix='pilot-private');job=handoff(f);a,c=setup_case(username='pilot-other')
        p=selection(a,c);p['integrations']=[f['contract'].pk]
        with self.assertRaises(ValidationError):pilot.configure(a,c.pk,p)
        p['integrations']=[];p['jobs']=[{'family':'handoff','id':job.pk}]
        with self.assertRaises(ValidationError):pilot.configure(a,c.pk,p)
        p=selection(f['actor'],f['case']);p['jobs']=[{'family':'handoff','id':job.pk}]
        Grant.objects.filter(case=f['case'],user=f['actor'],action='workflow.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.configure(f['actor'],f['case'].pk,p)

    def test_current_scoped_policy_source_rights_are_required_to_export(self):
        from tests.test_policy_scopes import source_version
        from apps.policy import scopes
        a,c=setup_case(username='pilot-target');b,source=setup_case(username='pilot-source')
        source_e=add_evidence(b,source.pk,'policy_decision','Synthetic source timezone','synthetic:pilot')
        local_e=add_evidence(a,c.pk,'policy_decision','Synthetic local application','synthetic:pilot')
        for action in ['case.read','policy.read']:Grant.objects.create(user=a,case=source,action=action)
        src=source_version(b,source,source_e)
        cfg=scopes.apply(a,src.pk,c.pk,local_e.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        p=selection(a,c);p['operations']=['workflow.clock.evaluate']
        contract=pilot.configure(a,c.pk,p);r=pilot.capture(a,c.pk,contract.pk)
        Grant.objects.filter(user=a,case=source,action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.inspect(a,c.pk,r.pk)

    def test_private_response_job_access_is_native_and_export_rechecks_it(self):
        from tests.readiness_helpers import endpoint
        from tests.support_release_helpers import ready,release
        with endpoint():
            f=ready('pilot-support');j=release(f)
        a,c=f['actor'],f['case'];p=selection(a,c);p['process_ids']=['B14'];p['jobs']=[{'family':'supportresponse','id':j.pk}]
        contract=pilot.configure(a,c.pk,p);r=pilot.capture(a,c.pk,contract.pk)
        self.assertNotIn('payload',r.snapshot['jobs'][0]);self.assertEqual(r.snapshot['jobs'][0]['status'],'pending')
        Grant.objects.filter(user=a,case=c,action='support.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.inspect(a,c.pk,r.pk)

    def test_selected_protection_proof_metadata_never_claims_native_restore(self):
        from tests.operator_helpers import fixture,proof
        from apps.workflows.operator_models import RecoveryJob
        f=fixture(prefix='pilot-protection');a,c=f['actor'],f['case'];proof(f)
        j=RecoveryJob.objects.create(plan=f['plan'],kind='restore',generation=1,operation_key='pilot-protection-unknown',intent={},actor=a,status='uncertain')
        p=selection(a,c);p['jobs']=[{'family':'protection','id':j.pk}]
        contract=pilot.configure(a,c.pk,p);r=pilot.capture(a,c.pk,contract.pk)
        recovery=r.snapshot['jobs'][0]['recovery_evidence']
        self.assertIsNotNone(recovery['proof']);self.assertFalse(recovery['native_restore_verified'])
        Grant.objects.filter(user=a,case=c,action='ops.proof.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.inspect(a,c.pk,r.pk)

    def test_synthetic_provider_evaluation_is_classified_without_new_network_calls(self):
        from tests.readiness_helpers import fixture,endpoint,probe
        from apps.workflows import readiness as d
        f=fixture(prefix='pilot-provider',kind='provider');a,c=f['actor'],f['case']
        with endpoint() as state:
            probe(f);probe(f,'evaluation');r=d.assess(a,c.pk,f['contract'].pk,'pilot-provider')
            d.review(f['reviewer'],c.pk,r.pk,'confirm','pilot-provider',f['review_evidence'].pk)
            calls=state['calls'];p=selection(a,c);p['integrations']=[f['contract'].pk]
            contract=pilot.configure(a,c.pk,p);pack=pilot.capture(a,c.pk,contract.pk)
            result=pilot.inspect(a,c.pk,pack.pk)['snapshot']['integrations'][0]
            self.assertEqual(result['recorded_probe_classification'],'synthetic_authenticated_http')
            self.assertFalse(result['real_model_evaluated']);self.assertFalse(result['operational_ready'])
            self.assertEqual(state['calls'],calls);self.assertNotIn(state['secret'],json.dumps(result))


class PilotConcurrencyTests(TransactionTestCase):
    def test_concurrent_captures_deduplicate_and_successors_require_explicit_head(self):
        a,c=setup_case(username='pilot-concurrent');p=selection(a,c);contract=pilot.configure(a,c.pk,p)
        barrier=Barrier(2)
        def capture(_):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=a.pk);barrier.wait()
                return pilot.capture(actor,c.pk,contract.pk).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(capture,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(PilotObservation.objects.count(),1)
