import json
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import connection,transaction,DatabaseError
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo import delivery
from apps.pmo.models import DeliveryRecord,DeliverySourceVerification
from apps.workflows import factory,factory_delivery
from apps.workflows.models import FactoryWork,HumanTask
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev


def setup(configure=True):
    f=DeliveryFixture();f.setup_delivery()
    if configure:
        value=json.loads(Path('fixtures/factory-delivery.json').read_text());value.pop('classification')
        p=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_delivery_execution',value,f.e['policy_decision'].pk,timezone.now())
        transition(f.actor,p.pk,'validated');transition(f.actor,p.pk,'active');f.execution_profile=p
    f.work=factory_delivery.start(f.actor,f.case.pk,'DELIVERY-1',f.d.pk,'Delivery factory example',rev(f.case))
    return f

def release_sources(f):
    f.plan();f.gates(delivery.UPSTREAM_GATES)
    delivery.record_release_request(f.actor,f.case.pk,f.d.pk,'SYNTHETIC-GLPI-1',f.e['requirements'].pk,'Recorded fixture deployment request reference',rev(f.case))
    f.gates(delivery.GLPI_GATES,'SYNTHETIC-GLPI-1')


class FactoryDeliveryTests(TestCase):
    def test_planning_decision_binds_rendered_case_sources_authority_and_public_evidence(self):
        f=setup()
        for kind in delivery.PLANNING:f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        panel=factory_delivery.projection(f.actor,f.work);old_packet=panel['decision_packet'];old_case=rev(f.case);old_work=f.work.revision
        f.source('technical_design') # New source/verification, same evidence body and unchanged Work revision.
        f.work.refresh_from_db();self.assertEqual(f.work.revision,old_work)
        with self.assertRaisesMessage(ValidationError,'Stale revision; refresh before retrying'):
            factory_delivery.decide(f.actor,f.work.pk,old_work,'approve',f.e['plan'].pk,'Old project version',old_case,old_packet)
        with self.assertRaisesMessage(ValidationError,'STALE_VERSION'):
            factory_delivery.decide(f.actor,f.work.pk,old_work,'approve',f.e['plan'].pk,'Old source packet',rev(f.case),old_packet)
        private=add_evidence(f.actor,f.case.pk,'p14_inputs','SYNTHETIC-PRIVATE-DECISION-EVIDENCE','synthetic:unavailable-choice')
        packet=factory_delivery.projection(f.actor,f.work)['decision_packet']
        with self.assertRaisesMessage(ValidationError,'public delivery decision source'):
            factory_delivery.decide(f.actor,f.work.pk,old_work,'approve',private.pk,'Guessed private evidence ID',rev(f.case),packet)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').exists())
        factory_delivery.decide(f.actor,f.work.pk,old_work,'approve',f.e['plan'].pk,'Exact current public source packet',rev(f.case),packet)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').count(),1)

    def test_only_configured_decision_verdicts_appear_and_native_return_never_approves(self):
        from tests.document_helpers import artifact
        f=setup()
        for kind in delivery.PLANNING:f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        self.assertEqual(factory_delivery.projection(f.actor,f.work)['allowed_verdicts'],['approve'])
        artifact(f.actor,f.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return','reject']}]},f.e['policy_decision'])
        panel=factory_delivery.projection(f.actor,f.work);self.assertEqual(panel['allowed_verdicts'],['approve','return','reject'])
        factory_delivery.decide(f.actor,f.work.pk,f.work.revision,'return',f.e['plan'].pk,'Source owner must correct the plan',rev(f.case),panel['decision_packet'])
        with self.assertRaises(ValidationError):delivery.approved_plan(f.d)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())

    def test_delivery_reader_never_receives_private_source_bodies_or_agent_history(self):
        from django.contrib.auth import get_user_model
        f=setup();private=add_evidence(f.actor,f.case.pk,'p14_inputs','SYNTHETIC-PRIVATE-COST-OPERANDS','synthetic:private-delivery-reference')
        f.source('technical_design',evidence=private)
        factory.run_until_wait(f.work.pk)
        reader=get_user_model().objects.create_user(username='synthetic-delivery-reader')
        Grant.objects.bulk_create([Grant(case=f.case,user=reader,action=action) for action in ['case.read','delivery.read','factory.read']])
        panel=factory_delivery.projection(reader,f.work)
        self.assertNotIn(private.pk,[e.pk for e in panel['public_sources']]);self.assertFalse(panel['can_decide'])
        self.client.force_login(reader);page=self.client.get(reverse('factory_detail',args=[f.work.pk]))
        self.assertEqual(page.status_code,200);self.assertNotContains(page,'SYNTHETIC-PRIVATE-COST-OPERANDS')
        generic=self.client.get(reverse('case',args=[f.case.pk]));self.assertEqual(list(generic.context['runs']),[])

    def test_changed_gate_requires_reviewed_reassessment_and_fresh_native_request(self):
        from apps.pmo.gates import record_gate,verify_gate
        f=setup();release_sources(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);spent=f.work.budget_used;old=factory_delivery.prepared(f.work)
        gate=record_gate(f.actor,f.case.pk,f.candidate.pk,'qa_exit','SYNTHETIC-QA-2',f.e['requirements'].pk,rev(f.case))
        verify_gate(f.actor,f.case.pk,gate.pk,rev(f.case))
        with self.assertRaises(ValidationError):factory_delivery.verify(f.work)
        self.client.force_login(f.actor);self.assertContains(self.client.get(reverse('home')+'?queue=exceptions'),'Prior release evidence needs review')
        self.assertNotContains(self.client.get(reverse('home')+'?queue=verified'),'Delivery factory example')
        self.assertNotContains(self.client.get(reverse('factory_detail',args=[f.work.pk])),'The current source approvals and release readiness record match.')
        factory_delivery.reassess(f.actor,f.work.pk,f.work.revision,'Review the actual successor source gate')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').count(),1)
        delivery.record_release_request(f.actor,f.case.pk,f.d.pk,'SYNTHETIC-GLPI-2',f.e['requirements'].pk,'Actual fixture successor request after upstream change',rev(f.case))
        f.gates(delivery.GLPI_GATES,'SYNTHETIC-GLPI-2');factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertNotEqual(factory_delivery.prepared(f.work).pk,old.pk)
        self.assertTrue(DeliveryRecord.objects.filter(pk=old.pk).exists());self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)
        self.assertEqual(FactoryWork.objects.filter(case=f.case).count(),1)
        self.assertContains(self.client.get(reverse('home')+'?queue=verified'),'Delivery factory example')

    def test_actual_release_without_prior_readiness_cannot_be_retroactively_prepared(self):
        f=setup();release_sources(f)
        delivery.capture_release(f.actor,f.case.pk,f.d.pk,None,timezone.now(),'SYNTHETIC-OBSERVED-RELEASE',f.e['completion'].pk,'Actual fixture event without readiness',rev(f.case))
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'waiting',f.work.finding);self.assertIn('actual release',f.work.finding.lower())
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())

    def test_cancellation_while_planning_retains_attempt_without_preparing_readiness(self):
        f=setup();release_sources(f)
        class Cancel:
            def choose(self,context):
                f.work.refresh_from_db();factory.manage(f.actor,f.work.pk,f.work.revision,'cancel')
                return {'activity':context['eligible'][0],'citations':context['evidence_ids']}
        factory.run_once(f.work.pk,provider=Cancel());f.work.refresh_from_db()
        self.assertEqual(f.work.status,'cancelled');self.assertEqual(f.work.budget_used,100)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())

    def test_agent_waits_for_native_gates_then_prepares_and_verifies_readiness(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();w=f.work
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'waiting',w.finding);self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())
        spent=w.budget_used;release_sources(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding);self.assertGreater(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)
        ready=factory_delivery.prepared(w);self.assertIsNotNone(ready)
        self.assertEqual(ready.snapshot,delivery.readiness_inputs(f.d))
        proof=factory_delivery.verify(w);self.assertFalse(proof['deployment_authorized']);self.assertFalse(proof['financial_release_granted']);self.assertFalse(proof['external_authenticity_verified'])
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').count(),1)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').exists())
        self.assertFalse(HumanTask.objects.filter(case=f.case,kind='factory_review').exists())

    def test_native_planning_decision_is_available_in_primary_ui_without_finance(self):
        f=setup();w=f.work
        for kind in delivery.PLANNING:f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        Grant.objects.filter(case=f.case,user=f.actor,action='finance.read').update(active=False)
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertTrue(factory_delivery.projection(f.actor,w)['can_decide'])
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[w.pk])+'?queue=decisions&q=Delivery'
        self.assertContains(self.client.get(url),'Planning exit decision')
        data={'action':'delivery_decision','revision':w.revision,'case_revision':rev(f.case),'packet':factory_delivery.projection(f.actor,w)['decision_packet'],'verdict':'approve','evidence':f.e['plan'].pk,'note':'Synthetic PMO Lead exact Planning exit'}
        self.assertRedirects(self.client.post(url,data),url)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').count(),1)
        self.assertContains(self.client.post(url,data),'Stale revision; refresh before retrying')
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').count(),1)
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'waiting',w.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='kickoff').exists())
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())
        self.assertContains(self.client.get(reverse('factory_create')+'?definition=delivery-release/v1&case='+str(f.case.pk)),'Delivery candidate')
        self.assertContains(self.client.get(reverse('factory_configuration',args=[f.case.pk])+'?definition=delivery-release/v1'),'Delivery gates and release evidence')

    def test_capture_before_policy_and_missing_approver_do_not_invent_decisions(self):
        f=setup(configure=False);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'configuration_needed');self.assertEqual(f.work.budget_used,0)
        value=json.loads(Path('fixtures/factory-delivery.json').read_text());value.pop('classification')
        p=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_delivery_execution',value,f.e['policy_decision'].pk,timezone.now())
        transition(f.actor,p.pk,'validated');transition(f.actor,p.pk,'active')
        factory.manage(f.actor,f.work.pk,f.work.revision,'resume')
        for kind in delivery.PLANNING:f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        Grant.objects.filter(case=f.case,user=f.actor,action='delivery.planning_decide').update(active=False)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'owner_needed',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').exists())
        self.assertEqual(FactoryWork.objects.filter(case=f.case).count(),1)

    def test_idempotent_intake_forged_source_and_false_completion_guards(self):
        f=setup();w=f.work
        same=factory_delivery.start(f.actor,f.case.pk,'OTHER-FORM',f.d.pk,'Same delivery intent',rev(f.case))
        self.assertEqual(same.pk,w.pk)
        with self.assertRaises(ValidationError):factory_delivery.start(f.actor,f.case.pk,'DELIVERY-1',f.d.pk,'Changed original-key payload',rev(f.case))
        forged=add_evidence(f.actor,f.case.pk,factory_delivery.KIND,w.source_head.body,'synthetic:forged-delivery')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(source_head=forged)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(status='verified')

    def test_agent_cannot_approve_or_authenticate_unverified_source_evidence(self):
        f=setup();f.source('technical_design',verify=False)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'waiting',f.work.finding);self.assertFalse(DeliverySourceVerification.objects.filter(source__dossier=f.d).exists())
        class Malicious:
            def choose(self,context):return {'activity':'approval.observe','citations':context['evidence_ids']}
        source=f.source('registration',verify=False)
        factory.run_once(f.work.pk,provider=Malicious());f.work.refresh_from_db()
        self.assertEqual(f.work.status,'blocked');self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').exists())

    def test_revoked_intake_producer_retains_operator_readback_without_execution_authority(self):
        f=setup();Grant.objects.filter(case=f.case,user=f.actor,action='factory.start').update(active=False)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'blocked')
        self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]))
        self.assertEqual(page.status_code,200);self.assertContains(page,'Intake')
        self.assertFalse(factory_delivery.projection(f.actor,f.work)['can_decide'])


from django.test import TransactionTestCase

class FactoryDeliveryConcurrencyTests(TransactionTestCase):
    def test_real_process_interruption_after_native_preparation_rolls_back_then_recovers_once(self):
        import os,sys,subprocess
        from datetime import timedelta
        f=setup();release_sources(f);env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'interrupt_after_action'],env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,38,result.stderr.decode())
        f.work.refresh_from_db();spent=f.work.budget_used;self.assertGreaterEqual(spent,200)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())
        self.assertTrue(f.work.activities.filter(attempts__phase='started').exists())
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        resumed=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'resume'],env=env,capture_output=True,timeout=60)
        self.assertEqual(resumed.returncode,0,resumed.stderr.decode())
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').count(),1)
        self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)

    def test_racing_forms_retain_one_candidate_intake_and_allowance(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.contrib.auth import get_user_model
        from apps.core.models import Evidence
        f=setup();barrier=Barrier(2)
        def enter(n):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f.actor.pk);barrier.wait(timeout=10)
                return factory_delivery.start(actor,f.case.pk,'FORM-'+str(n),f.d.pk,'Same native delivery intent').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(enter,[1,2]))
        self.assertEqual(ids,[f.work.pk]*2);self.assertEqual(Evidence.objects.filter(case=f.case,kind=factory_delivery.KIND).count(),1)

    def test_planning_decision_and_cancellation_share_current_work_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        f=setup()
        for kind in delivery.PLANNING:f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();expected=f.work.revision;case_expected=rev(f.case);packet=factory_delivery.projection(f.actor,f.work)['decision_packet'];barrier=Barrier(2)
        def act(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if kind=='cancel':factory.manage(f.actor,f.work.pk,expected,'cancel')
                else:factory_delivery.decide(f.actor,f.work.pk,expected,'approve',f.e['plan'].pk,'Synthetic concurrent native Planning decision',case_expected,packet)
                return kind
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(act,['cancel','approve']))
        self.assertEqual(results.count('stale'),1,results);f.work.refresh_from_db()
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='planning_decision').count(),0 if f.work.cancel_requested else 1)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())
