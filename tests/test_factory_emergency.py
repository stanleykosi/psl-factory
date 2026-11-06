"""Native P61/P62 station connection; only outward publication transport is mocked."""
import json
from pathlib import Path
from unittest.mock import patch
from tests.test_authority_recovery import RecoveryFixture
from datetime import timedelta,datetime
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.documents.controlled import register_template
from apps.documents.models import Publication,PublicationReceipt,PublicationJob
from apps.pmo.models import EmergencyAuthorization,EmergencyOutcome,EmergencyRetrospectiveRecord,ChangeClosure
from apps.pmo import emergencies as native
from apps.workflows import factory,factory_emergency as emergency
from apps.workflows.models import FactoryWork
from tests import test_emergencies as native_tests
from tests.helpers import rev
from tests.document_helpers import artifact

class FactoryEmergencyTests(native_tests.EmergencyFixture,TestCase):
    def setUp(self):
        super().setUp()
        self.template=register_template(self.actor,self.case.pk,'Emergency retrospective report',{'document_type':'project_artifact','required_fields':['executive_summary','status'],'audience_fields':{'client':['executive_summary','status','next_steps'],'internal':['executive_summary','status','next_steps']}},self.e['policy_decision'].pk,rev(self.case))
        artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[self.template.pk],'repository':'internal-versioned','retention_days':30},self.e['policy_decision'])
        value=json.loads(Path('fixtures/factory-emergency.json').read_text());value.pop('classification');value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk)
        config=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_emergency_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')
        self.inputs={'template_id':self.template.pk,'authorization_id':None,'outcome_id':None,'audience':'client'}
    def configure_long_clock_fixture(self):
        value=json.loads(Path('fixtures/factory-emergency.json').read_text());value.pop('classification')
        value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk,max_age_seconds=604800)
        config=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_emergency_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')
    def start_work(self,auth=None,actual=None):
        self.inputs.update(authorization_id=auth.pk if auth else None,outcome_id=actual.pk if actual else None)
        self.work=emergency.start(self.actor,self.case.pk,'EMERGENCY-1',self.profile.pk,self.inputs,'Emergency evidence and retrospective',rev(self.case));return self.work
    def select(self,auth=None,actual=None):
        self.work.refresh_from_db();self.inputs.update(authorization_id=auth.pk if auth else None,outcome_id=actual.pk if actual else None)
        emergency.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.profile.pk,self.inputs,'Human explicitly selects exact native evidence');self.work.refresh_from_db()
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db()
    def human(self,action,**values):
        self.work.refresh_from_db();return emergency.human_action(self.actor,self.work.pk,self.work.revision,rev(self.case),self.profile.pk,action,values)
    def ready_work(self,mode='coexist'):
        auth=self.authorized(mode);actual=self.outcome(auth);self.clocks();self.reviewed(actual)
        if mode=='defer':self.glpi()
        record=native.reconcile_retrospective(self.actor,self.case.pk,actual.pk,rev(self.case));self.start_work(auth,actual);return auth,actual,record
    def review_report(self):
        self.work.refresh_from_db();v=emergency.document(self.work);self.assertIsNotNone(v,self.work.finding)
        emergency.review(self.actor,self.work.pk,self.work.revision,rev(self.case),v.pk,'approve','Actual human outward review of exact retrospective report')
    def finish_report(self):
        self.advance();self.review_report();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=emergency.verify(self.work);self.assertFalse(proof['deployment_dispatched']);self.assertFalse(proof['ordinary_change_closed']);self.assertTrue(proof['authorization_preceded_implementation']);self.assertEqual(len(proof['receipt_ids']),1);self.assertFalse(ChangeClosure.objects.exists());return proof

    def test_full_human_preauthorization_actual_capture_review_retrospective_and_report(self):
        self.start_work();self.advance();self.assertFalse(EmergencyAuthorization.objects.exists());self.assertFalse(EmergencyOutcome.objects.exists())
        self.policies('coexist');self.glpi()
        for role in ['Incident Lead','Engineering Lead','CTO']:
            self.human('preauthorization_decision',role=role,authority_role='Engineering Lead',verdict='approve',evidence=self.decision.pk,note='Actual prescribed human preauthorization decision')
        auth=self.human('authorize');self.select(auth);self.advance();self.assertEqual(emergency.report(self.work)['stage'],'implementation')
        self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk]);self.assertContains(self.client.get(url),'Timestamp time zone:')
        response=self.client.post(url,{'action':'capture_outcome','revision':self.work.revision,'case_revision':rev(self.case),'profile':self.profile.pk,'implemented_at':timezone.now().isoformat(),'evidence':self.implementation.pk,'note':'Human records actual external implementation, not a dispatch request'})
        self.assertEqual(response.status_code,302);actual=EmergencyOutcome.objects.get(profile=self.profile);self.assertGreaterEqual(actual.implemented_at,auth.created_at)
        self.select(auth,actual);self.clocks()
        self.human('record_review',evidence=self.review_evidence.pk,note='Actual human post-implementation review')
        for role in ['Product','Engineering Lead']:self.human('retrospective_decision',role=role,verdict='approve',evidence=self.decision.pk,note='Actual review-bound retrospective decision')
        record=self.human('reconcile_retrospective');proof=self.finish_report();self.assertEqual(proof['retrospective_record'],record.pk)
        before=self.work.revision;self.assertContains(self.client.get(url),'Inspect the recorded retrospective outcome');self.work.refresh_from_db();self.assertEqual(self.work.revision,before)
        self.assertTrue(self.work.activities.filter(kind='ACT04',status='succeeded').exists())

    def test_replace_policy_is_explicit_and_report_never_grants_deployment_or_ordinary_closure(self):
        auth,actual,record=self.ready_work('replace');self.assertEqual(auth.snapshot['glpi'],[]);proof=self.finish_report();self.assertEqual(proof['retrospective_status'],record.snapshot['status'])

    def test_deferred_glpi_holds_retrospective_only_until_real_native_gate_evidence(self):
        auth=self.authorized('defer');actual=self.outcome(auth);self.clocks();self.reviewed(actual);self.start_work(auth,actual);self.advance()
        self.assertIn('GLPI',self.work.finding);self.assertIsNone(emergency.document(self.work));self.assertFalse(EmergencyRetrospectiveRecord.objects.exists())
        self.glpi();self.human('reconcile_retrospective');self.finish_report()

    def test_actual_late_unauthorized_outcome_is_retained_and_cannot_be_repaired_retroactively(self):
        actual=self.outcome(implemented=timezone.now()-timedelta(days=3));self.clocks();self.reviewed(actual);self.start_work(actual=actual);self.advance()
        status=emergency.report(self.work);self.assertTrue(status['timing']['log_late']);self.assertFalse(status['authorization_preceded_implementation']);self.assertIn('cannot replace',self.work.finding)
        self.assertIsNone(emergency.document(self.work));self.assertFalse(EmergencyRetrospectiveRecord.objects.exists())
        with self.assertRaises(ValidationError):self.human('authorize')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.client.force_login(self.actor);self.assertContains(self.client.get(reverse('factory_detail',args=[self.work.pk])),'Recorded authorization preceded implementation: No')

    def test_future_capture_and_wrong_profile_selection_rejected_without_creating_outcome(self):
        self.start_work()
        with self.assertRaises(ValidationError):self.human('capture_outcome',implemented_at=timezone.now()+timedelta(hours=1),evidence=self.implementation.pk,note='Future values cannot attest an actual event')
        self.assertFalse(EmergencyOutcome.objects.exists())
        with self.assertRaises(ValidationError):emergency.start(self.actor,self.case.pk,'WRONG',self.profile.pk,dict(self.inputs,authorization_id=999),'Foreign authority')

    def test_withdrawn_preauthorizer_grant_holds_report_without_erasing_actual_outcome(self):
        auth,actual,record=self.ready_work();Grant.objects.filter(case=self.case,user=self.actor,action='emergency.decide').update(active=False)
        self.advance();self.assertIsNone(emergency.document(self.work));self.assertNotEqual(self.work.status,'verified');self.assertTrue(EmergencyOutcome.objects.filter(pk=actual.pk).exists())

    def test_lost_report_response_reconciles_original_receipt_before_any_replacement(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        self.ready_work();self.advance();self.review_report()
        for _ in range(15):
            factory.run_once(self.work.pk,adapter=PublicationTimeoutAfterAccept());self.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=self.work,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=self.work);receipt=PublicationReceipt.objects.get(publication=job.publication);self.assertEqual(job.status,'unknown')
        with self.assertRaises(ValidationError):emergency.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.profile.pk,self.inputs,'Cannot replace unresolved effect')
        emergency.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db();spent=self.work.budget_used
        emergency.reconcile(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db();job.refresh_from_db()
        self.assertEqual(job.status,'confirmed');self.assertEqual(self.work.status,'followup_needed');self.assertEqual(self.work.budget_used,spent);self.assertEqual(PublicationReceipt.objects.get(publication=job.publication).pk,receipt.pk);self.assertEqual(Publication.objects.filter(factory_work=self.work).count(),1)

    def test_returned_report_requires_explicit_source_review_and_new_native_document(self):
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},self.e['policy_decision'])
        self.ready_work();self.advance();v=emergency.document(self.work);emergency.review(self.actor,self.work.pk,self.work.revision,rev(self.case),v.pk,'return','Actual outward report needs a reviewed replacement')
        self.advance();emergency.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.profile.pk,self.inputs,'Human explicitly requests replacement of returned report');self.advance();new=emergency.document(self.work);self.assertNotEqual(v.pk,new.pk);self.review_report();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)

    def test_post_reconciliation_authority_recovery_replaces_report_and_invalidation_holds(self):
        auth,actual,record=self.ready_work();RecoveryFixture.recovery_policy(self)
        self.advance();old=emergency.document(self.work);original=dict(record.snapshot)
        Grant.objects.filter(case=self.case,user=self.actor,action='emergency.decide').update(active=False)
        request=RecoveryFixture.request(self,actual);recovery=RecoveryFixture.approve(self,request)
        emergency.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.profile.pk,self.inputs,'Current human recovery requires newly reviewed report')
        self.finish_report();self.assertNotEqual(emergency.document(self.work).pk,old.pk)
        record.refresh_from_db();self.assertEqual(record.snapshot,original);self.assertNotEqual(record.snapshot.get('authority_recovery_id'),recovery.pk)
        Grant.objects.filter(case=self.case,user=self.actor,action='authority.decide').update(active=False)
        with self.assertRaises(PermissionDenied):emergency.verify(self.work)
        self.assertTrue(emergency.projection(self.actor,self.work)['readiness_changed'])

    def test_deadline_passing_after_reconciliation_preserves_original_completion(self):
        self.configure_long_clock_fixture();auth,actual,record=self.ready_work();original=dict(record.snapshot)
        later=datetime.fromisoformat(record.snapshot['timing']['retrospective_due_at'])+timedelta(hours=1)
        with patch('django.utils.timezone.now',return_value=later):
            self.finish_report()
        record.refresh_from_db();self.assertEqual(record.snapshot,original);self.assertEqual(record.snapshot['status'],'evidenced_on_time')

    def test_authorized_late_retrospective_keeps_exception_status(self):
        self.configure_long_clock_fixture();auth=self.authorized();actual=self.outcome(auth);self.clocks()
        later=datetime.fromisoformat(native.timing(self.case,actual)['retrospective_due_at'])+timedelta(hours=1)
        with patch('django.utils.timezone.now',return_value=later):
            self.reviewed(actual);record=native.reconcile_retrospective(self.actor,self.case.pk,actual.pk,rev(self.case))
            self.start_work(auth,actual);proof=self.finish_report()
        self.assertEqual(record.snapshot['status'],'completed_with_lateness_exception');self.assertEqual(proof['retrospective_status'],record.snapshot['status'])

    def test_changed_recipient_policy_and_current_profile_hold_existing_verification(self):
        from tests.helpers import activate
        from apps.policy.services import active_component,register_reference
        from django.contrib.auth import get_user_model
        self.ready_work();self.finish_report()
        current=active_component('D11.recipient_grant_refs',self.case)
        recipient=get_user_model().objects.create_user('new-emergency-recipient')
        Grant.objects.create(case=self.case,user=recipient,action='document.receive:client')
        reference=register_reference(self.actor,self.case.pk,'emergency:new-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':recipient.pk},self.e['policy_decision'].pk)
        activate(self.actor,self.case,'D11.recipient_grant_refs',current.envelope['value']+[reference.ref],self.e['policy_decision'])
        with self.assertRaises(ValidationError):emergency.verify(self.work)
        native.capture_profile(self.actor,self.case.pk,self.cv.pk,self.candidate.pk,True,False,self.classification.pk,'New incident facts require their own native source',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'profile changed'):emergency.source(self.work)

    def test_profile_settings_and_private_work_read_boundary(self):
        self.start_work();self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('factory_configuration',args=[self.case.pk])+'?definition=pmo-emergency/v1'),'Existing Emergency report preparer')
        Grant.objects.filter(case=self.case,user=self.actor,action='emergency.read').update(active=False)
        with self.assertRaises(PermissionDenied):emergency.source(self.work)
        self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,404)
