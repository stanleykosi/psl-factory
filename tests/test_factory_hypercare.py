import json
from pathlib import Path
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from datetime import timedelta
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo import delivery,delivery_closure as closure
from apps.pmo.models import DeliveryRecord
from apps.pmo.delivery_documents import draft_delivery_document
from apps.workflows import factory,factory_hypercare
from apps.workflows.models import FactoryWork,HumanTask
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev


def setup(configure=True):
    f=DeliveryFixture();f.setup_delivery()
    if configure:
        value=json.loads(Path('fixtures/factory-hypercare.json').read_text());value.pop('classification')
        p=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_hypercare_execution',value,f.e['policy_decision'].pk,timezone.now())
        transition(f.actor,p.pk,'validated');transition(f.actor,p.pk,'active');f.execution_profile=p
    f.work=factory_hypercare.start(f.actor,f.case.pk,'HYPERCARE-1',f.d.pk,'Release follow-up example',rev(f.case));return f


class FactoryHypercareTests(TestCase):
    def test_technical_policy_refuses_business_authority_invalid_allowance_and_private_source_requirements(self):
        from apps.policy.factory_validators import validate_reference,HYPERCARE_COMPONENT,HYPERCARE_SCHEMA
        from types import SimpleNamespace
        f=setup(configure=False);value=json.loads(Path('fixtures/factory-hypercare.json').read_text());value.pop('classification')
        for changes in [{'executor_id':f.actor.pk},{'review_role':'PM'},{'max_tokens':1},
            {'required_evidence_kinds':['agent_private_delivery_notes']},{'minimum_hours':0}]:
            with self.assertRaises(ValidationError):validate_reference(HYPERCARE_COMPONENT,SimpleNamespace(schema_ref=HYPERCARE_SCHEMA,content=dict(value,**changes)),f.case)
        self.assertEqual(validate_reference(HYPERCARE_COMPONENT,SimpleNamespace(schema_ref=HYPERCARE_SCHEMA,content=value),f.case),value)
        self.assertEqual(f.work.budget_used,0);self.assertIsNone(f.work.policy_id)

    def test_superseded_accepted_document_invalidates_readback_without_erasing_acceptance(self):
        from apps.documents.controlled import create_version
        from apps.pmo.models import DeliveryDocumentBinding
        f=setup();f.accepted();f.criteria();f.observations();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        accepted=closure.accepted_go_live(f.d);binding=DeliveryDocumentBinding.objects.get(dossier=f.d,purpose='go_live');v=binding.version
        create_version(f.actor,f.case.pk,v.template_id,v.document.title,v.audience,v.fields,rev(f.case),document_id=v.document_id)
        with self.assertRaises(ValidationError):closure.accepted_go_live(f.d)
        self.assertTrue(factory_hypercare.projection(f.actor,f.work)['readiness_changed'])
        self.assertTrue(DeliveryRecord.objects.filter(pk=accepted.pk).exists())

    def test_configured_elapsed_period_and_metric_units_remain_native_qualification_controls(self):
        from tests.test_delivery import CRITERIA
        f=setup();f.accepted();f.criteria(dict(CRITERIA,minimum_hours=24));f.observations()
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertIs(factory_hypercare.assessed(f.work).snapshot['qualified'],False)
        self.assertTrue(any('period' in x for x in factory_hypercare.assessed(f.work).snapshot['findings']))
        f.criteria();f.source('hypercare_engineering',{'observed_at':timezone.now().isoformat(),'confirmed':True,'metrics':{'errors':{'value':0,'unit':'percent'}}})
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertTrue(any('unit differs' in x for x in factory_hypercare.assessed(f.work).snapshot['findings']))

    def test_source_successor_removes_current_outcome_and_reassessment_keeps_history_and_allowance(self):
        f=setup();f.accepted();f.criteria();f.observations();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        original=factory_hypercare.assessed(f.work);spent=f.work.budget_used
        f.observations(errors=3)
        self.assertTrue(factory_hypercare.projection(f.actor,f.work)['readiness_changed'])
        with self.assertRaises(ValidationError):factory_hypercare.verify(f.work)
        self.client.force_login(f.actor)
        self.assertNotContains(self.client.get(reverse('home')+'?queue=verified'),f.work.request['reference'])
        factory_hypercare.reassess(f.actor,f.work.pk,f.work.revision,'Review changed Engineering source observations')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertIs(factory_hypercare.assessed(f.work).snapshot['qualified'],False)
        self.assertTrue(DeliveryRecord.objects.filter(pk=original.pk).exists());self.assertGreater(f.work.budget_used,spent)
        f.observations();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(f.work.budget_limit,20000)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').count(),3)

    def test_actual_event_rejects_future_naive_private_stale_and_revoked_requests(self):
        f=setup(configure=False);ready=f.ready();data={'readiness':ready.pk,'released_at':timezone.now().isoformat(),
            'reference':'SYNTHETIC-ACTUAL','evidence':f.e['completion'].pk,'note':'Observed source event'}
        expected=f.work.revision;case_expected=rev(f.case)
        for instant in [(timezone.now()+timedelta(days=1)).isoformat(),'2026-11-01T10:00:00']:
            with self.assertRaises(ValidationError):factory_hypercare.observe(f.actor,f.work.pk,expected,case_expected,'release',dict(data,released_at=instant))
        private=add_evidence(f.actor,f.case.pk,'agent_private_event','Private event text','synthetic:private')
        with self.assertRaises(ValidationError):factory_hypercare.observe(f.actor,f.work.pk,expected,rev(f.case),'release',dict(data,evidence=private.pk))
        with self.assertRaises(ValidationError):factory_hypercare.observe(f.actor,f.work.pk,expected,case_expected,'release',data)
        Grant.objects.filter(case=f.case,user=f.actor,action='delivery.release_record').update(active=False)
        self.assertFalse(factory_hypercare.projection(f.actor,f.work)['can_record_release'])
        with self.assertRaises(PermissionDenied):factory_hypercare.observe(f.actor,f.work.pk,expected,rev(f.case),'release',data)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').exists())
    def test_recorded_release_without_prior_readiness_stays_a_source_owned_exception(self):
        f=setup();factory_hypercare.observe(f.actor,f.work.pk,f.work.revision,rev(f.case),'release',
            {'readiness':None,'released_at':timezone.now().isoformat(),'reference':'SYNTHETIC-UNREADY',
                'evidence':f.e['completion'].pk,'note':'Truthful event; no readiness existed'})
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();panel=factory_hypercare.projection(f.actor,f.work)
        self.assertEqual(f.work.status,'waiting');self.assertFalse(panel['can_record_release'])
        self.assertIn('source owner',panel['checks']['release']['summary'])
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').exists())
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())

    def test_cancel_during_planning_retains_attempt_without_native_assessment(self):
        f=setup();f.accepted();f.criteria();f.observations()
        class Cancel:
            def choose(self,context):
                f.work.refresh_from_db();factory.manage(f.actor,f.work.pk,f.work.revision,'cancel')
                return {'activity':context['eligible'][0],'citations':context['evidence_ids']}
        factory.run_once(f.work.pk,provider=Cancel());f.work.refresh_from_db()
        self.assertTrue(f.work.cancel_requested);self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())
        self.assertTrue(f.work.activities.filter(attempts__isnull=False).exists())

    def test_reader_projection_excludes_private_bodies_and_revoked_producer_cannot_continue(self):
        from django.contrib.auth import get_user_model
        f=setup();private=add_evidence(f.actor,f.case.pk,'agent_private_delivery_notes','PRIVATE-HYPERCARE-SECRET','synthetic:private')
        with self.assertRaises(ValidationError):f.source('technical_design',evidence=private)
        restricted=add_evidence(f.actor,f.case.pk,'p14_inputs','PRIVATE-HYPERCARE-SECRET','synthetic:private-cost-reference')
        f.source('technical_design',evidence=restricted)
        reader=get_user_model().objects.create_user(username='hypercare-reader')
        Grant.objects.bulk_create([Grant(case=f.case,user=reader,action=a) for a in ['case.read','delivery.read','factory.read']])
        self.client.force_login(reader);url=reverse('factory_detail',args=[f.work.pk])
        page=self.client.get(url);self.assertEqual(page.status_code,200);self.assertNotContains(page,'PRIVATE-HYPERCARE-SECRET')
        self.assertNotContains(page,'Record actual release evidence');self.assertNotContains(page,'Continue eligible work')
        Grant.objects.filter(case=f.case,user=f.actor,action='factory.start').update(active=False)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'blocked')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())

    def test_agent_waits_for_actual_release_then_assesses_and_verifies_qualified_observations(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'waiting',f.work.finding);spent=f.work.budget_used
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').exists())
        f.accepted();f.criteria();f.observations();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)
        row=factory_hypercare.assessed(f.work);self.assertEqual(row.snapshot,closure.hypercare_inputs(f.d));self.assertIs(row.snapshot['qualified'],True)
        proof=factory_hypercare.verify(f.work);self.assertFalse(proof['closure_approved']);self.assertFalse(proof['financial_release_granted']);self.assertFalse(proof['deployment_dispatched']);self.assertFalse(proof['external_authenticity_verified'])
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists());self.assertFalse(HumanTask.objects.filter(case=f.case,kind='factory_review').exists())

    def test_actual_release_ui_remains_available_before_execution_and_stability_configuration(self):
        f=setup(configure=False);ready=f.ready();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'configuration_needed');self.assertEqual(f.work.budget_used,0)
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk])
        self.assertContains(self.client.get(url),'Record the observed release')
        data={'action':'hypercare_observation','kind':'release','revision':f.work.revision,'case_revision':rev(f.case),
            'readiness':ready.pk,'released_at':timezone.now().isoformat(),'reference':'SYNTHETIC-OBSERVED-RELEASE',
            'evidence':f.e['completion'].pk,'note':'Human source fixture attests the actual release, no deployment command'}
        self.assertRedirects(self.client.post(url,data),url);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'configuration_needed');self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').count(),1)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())
        self.assertContains(self.client.get(reverse('factory_create')+'?definition=delivery-hypercare/v1&case='+str(f.case.pk)),'Start release follow-up')
        self.assertContains(self.client.get(reverse('factory_configuration',args=[f.case.pk])+'?definition=delivery-hypercare/v1'),'Release observations and hypercare')

    def test_unknown_and_negative_observations_are_recorded_without_false_qualification(self):
        f=setup();f.accepted();f.criteria();f.observations(errors=None,confirmed=None)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();row=factory_hypercare.assessed(f.work)
        self.assertEqual(f.work.status,'waiting',f.work.finding);self.assertIsNone(row.snapshot['qualified']);spent=f.work.budget_used
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.budget_used,spent)
        f.observations(errors=2,availability=99,confirmed=True);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'waiting',f.work.finding);self.assertIs(factory_hypercare.assessed(f.work).snapshot['qualified'],False)
        f.observations();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').count(),3)
        self.assertEqual(f.work.budget_limit,20000)

    def test_current_go_live_receipt_and_distinct_signature_evidence_are_human_controlled(self):
        f=setup();f.release()
        data={key:f.evidence(kind).pk for key,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
        version=draft_delivery_document(f.actor,f.case.pk,f.d.pk,'go_live',f.t.pk,data,rev(f.case));receipt=f.publish(version)
        pm=f.evidence('signature','Synthetic actual PM signature for this report');client=f.evidence('signature','Synthetic actual Client signature for this report')
        panel=factory_hypercare.projection(f.actor,f.work);self.assertTrue(panel['can_accept_go_live'])
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk])
        payload={'action':'hypercare_observation','kind':'acceptance','revision':f.work.revision,'case_revision':rev(f.case),
            'receipt':receipt.pk,'pm_signature':pm.pk,'client_signature':pm.pk,'attestation':json.dumps(f.attestation(receipt,pm,client)),'packet':panel['acceptance_packet'],'note':'Actual fixture go-live source observation'}
        page=self.client.get(url);self.assertContains(page,'Review the signature evidence')
        self.assertContains(page,'Synthetic actual PM signature for this report');self.assertContains(page,'<h4>Executive summary</h4>',html=True)
        self.assertNotContains(page,'&#x27;sections&#x27;:')
        self.assertContains(self.client.post(url,payload),'distinct exact signature evidence')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='go_live').exists())
        payload.update(client_signature=client.pk,packet='0'*64)
        self.assertContains(self.client.post(url,payload),'STALE_VERSION');self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='go_live').exists())
        payload['packet']=panel['acceptance_packet'];self.assertRedirects(self.client.post(url,payload),url)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='go_live').count(),1)

    def test_missing_business_criterion_holds_only_assessment_and_resumes_after_reviewed_configuration(self):
        f=setup();f.accepted();f.observations();factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'configuration_needed',f.work.finding);self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())
        self.assertTrue(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').exists())
        f.criteria();self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]))
        self.assertContains(page,'Prerequisites need recheck');self.assertNotContains(page,'A current stability period, confirmation and metric rule is required.')
        factory.manage(f.actor,f.work.pk,f.work.revision,'resume');factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding)

    def test_new_form_keeps_one_candidate_allowance_and_unregistered_approval_is_rejected(self):
        f=setup();same=factory_hypercare.start(f.actor,f.case.pk,'NEW-FORM',f.d.pk,'Same hypercare intent',rev(f.case));self.assertEqual(same.pk,f.work.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        class Malicious:
            def choose(self,context):return {'activity':'approval.observe','citations':context['evidence_ids']}
        factory.run_once(f.work.pk,provider=Malicious());f.work.refresh_from_db();self.assertEqual(f.work.status,'blocked')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').exists())


class FactoryHypercareConcurrencyTests(TransactionTestCase):
    def test_actual_event_race_preserves_one_native_record(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        f=setup();ready=f.ready();barrier=Barrier(2);expected=f.work.revision;case_expected=rev(f.case)
        data={'readiness':ready.pk,'released_at':timezone.now().isoformat(),'reference':'SYNTHETIC-RACE',
            'evidence':f.e['completion'].pk,'note':'Concurrent observations of one actual event'}
        def enter(n):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                factory_hypercare.observe(f.actor,f.work.pk,expected,case_expected,'release',data)
                return 'recorded'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(enter,[1,2]))
        self.assertEqual(sorted(results),['recorded','stale']);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='release_outcome').count(),1)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())

    def test_real_process_exit_rolls_back_assessment_and_recovers_without_resetting_allowance(self):
        import os,sys,subprocess
        f=setup();f.accepted();f.criteria();f.observations();env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'interrupt_after_action'],env=env,capture_output=True,timeout=90)
        self.assertEqual(result.returncode,38,result.stderr.decode());f.work.refresh_from_db();spent=f.work.budget_used
        self.assertGreater(spent,0);self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').exists())
        self.assertTrue(f.work.activities.filter(attempts__phase='started').exists())
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        resumed=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'resume'],env=env,capture_output=True,timeout=90)
        self.assertEqual(resumed.returncode,0,resumed.stderr.decode());factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertGreater(f.work.budget_used,spent)
        self.assertEqual(f.work.budget_limit,20000);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='hypercare').count(),1)
