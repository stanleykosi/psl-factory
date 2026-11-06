"""Independent native controlled-change connection, external delivery mock only."""
import json
from pathlib import Path
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction,connection
from django.utils import timezone
from django.urls import reverse
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo.changes import log_change,assess_change
from apps.pmo.models import ChangeClosure,ChangeAuthorization
from apps.documents.models import Publication,PublicationReceipt,PublicationJob
from apps.workflows import factory,factory_change as change
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests import test_commercial_changes as native_tests

class FactoryChangeTests(TestCase):
    assessments=native_tests.ControlledChangeTests.assessments
    authorized=native_tests.ChangeExecutionTests.authorized
    ready=native_tests.ChangeExecutionTests.ready
    change_template=native_tests.ChangeExecutionTests.change_template
    def setUp(self):
        native_tests.ControlledChangeTests.setUp(self)
        self.template=self.change_template()
        value=json.loads(Path('fixtures/factory-change.json').read_text());value.pop('classification')
        value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk)
        self.profile=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_change_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.actor,self.profile.pk,'validated');transition(self.actor,self.profile.pk,'active')
    def start(self,auth=None,version=None):
        self.inputs={'template_id':self.template.pk,'authorization_id':auth.pk if auth else None}
        self.work=change.start(self.actor,self.case.pk,'CHANGE-1',(version or self.cv).pk,self.inputs,'Controlled change',rev(self.case));return self.work
    def advance(self):
        factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def review(self,purpose):
        self.work.refresh_from_db();v=change.document(self.work,purpose);self.assertIsNotNone(v,self.work.finding)
        change.review(self.actor,self.work.pk,self.work.revision,rev(self.case),v.pk,'approve','Human reviewed the exact controlled change')
    def test_complete_native_flow_requires_human_assessment_review_execution_signatures_and_receipts(self):
        self.start();self.advance();self.assertEqual(change.report(self.work)['stage'],'impact');self.assertEqual(ChangeAuthorization.objects.count(),0)
        auth=self.authorized();self.work.refresh_from_db()
        change.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.cv.pk,dict(self.inputs,authorization_id=auth.pk),'Human selected exact native authorization')
        self.advance();self.review('notice');self.advance();self.assertEqual(change.report(self.work)['stage'],'execution')
        self.assertFalse(ChangeClosure.objects.exists());self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),1)
        self.ready(auth);self.advance();self.review('go_live');self.advance();self.assertEqual(change.report(self.work)['stage'],'signatures')
        pm=add_evidence(self.actor,self.case.pk,'signature','Synthetic PM signature of exact report','synthetic:PM')
        client=add_evidence(self.actor,self.case.pk,'signature','Synthetic Client signature of exact report','synthetic:Client')
        receipt=PublicationReceipt.objects.get(publication__version=change.document(self.work,'go_live'))
        self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk])
        before=self.work.revision;self.assertContains(self.client.get(url),'Record actual signed closure');self.work.refresh_from_db();self.assertEqual(self.work.revision,before)
        response=self.client.post(url,{'action':'close','revision':self.work.revision,'case_revision':rev(self.case),'receipt':receipt.pk,'pm_signature':pm.pk,'client_signature':client.pk,'note':'Actual PM attests supplied signatures on this exact delivered version'})
        self.assertEqual(response.status_code,302);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        self.assertEqual(len(change.verify(self.work)['receipt_ids']),2);self.assertFalse(change.verify(self.work)['deployment_authorized'])
        page=self.client.get(url);self.assertContains(page,'Inspect the recorded signed closure');self.assertNotContains(page,'<h2>Review source-owned changes</h2>',html=True);self.assertContains(page,'Executive summary');self.assertContains(page,'within this document')
        self.assertEqual(connection.vendor,'postgresql')
    def test_idempotent_intake_and_cross_case_or_revision_references_rejected(self):
        self.start();old=self.work.pk
        self.assertEqual(change.start(self.actor,self.case.pk,'OTHER',self.cv.pk,self.inputs,'Same native business intent').pk,old)
        self.assertEqual(FactoryWork.objects.filter(case=self.case).count(),1)
        with self.assertRaises(ValidationError):change.start(self.actor,self.case.pk,'CHANGE-1',self.cv.pk,dict(self.inputs,authorization_id=999),'Controlled change')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=old).update(status='verified')
    def test_emergency_holds_on_separate_native_route_without_ordinary_authorization(self):
        incident=add_evidence(self.actor,self.case.pk,'incident','Synthetic critical incident','synthetic:incident')
        v=log_change(self.actor,self.case.pk,'CR-001','Emergency','Production','Actual incident','Incident evidence',self.source.pk,rev(self.case),incident.pk)
        self.start(version=v);self.advance();self.assertIn('P61/P62',self.work.finding);self.assertFalse(ChangeAuthorization.objects.exists());self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())
    def test_standard_catalogue_is_not_invented(self):
        v=log_change(self.actor,self.case.pk,'CR-001','Standard','Delivery','Catalogue candidate','Owner evidence',self.source.pk,rev(self.case))
        self.start(version=v);self.advance();self.assertNotEqual(self.work.status,'verified');self.assertFalse(ChangeAuthorization.objects.exists())
    def test_revoked_source_reader_cannot_continue_or_read_console(self):
        self.start();Grant.objects.filter(case=self.case,user=self.actor,action='change.read').update(active=False)
        with self.assertRaises(PermissionDenied):change.source(self.work)
        self.client.force_login(self.actor);self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,404)
    def test_changed_assessment_invalidates_authorization_and_no_draft_is_prepared(self):
        auth=self.authorized();self.start(auth)
        assess_change(self.actor,self.case.pk,self.cv.pk,'QA',False,False,False,self.source.pk,'Fresh owner assessment',rev(self.case))
        self.advance();self.assertIsNone(change.document(self.work,'notice'));self.assertNotEqual(self.work.status,'verified')
    def test_source_correction_does_not_reset_budget_and_history_is_retained(self):
        self.start();self.advance();spent=self.work.budget_used;head=self.work.source_head_id
        auth=self.authorized();self.work.refresh_from_db()
        change.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.cv.pk,dict(self.inputs,authorization_id=auth.pk),'Native human approval selected')
        self.work.refresh_from_db();self.assertEqual(self.work.budget_used,spent);self.assertNotEqual(self.work.source_head_id,head);self.assertTrue(self.work.activities.exists())
    def test_missing_preparer_is_precise_hold_without_authority_grant(self):
        auth=self.authorized();self.start(auth)
        Grant.objects.filter(case=self.case,user=self.actor,action='document.draft').update(active=False)
        self.advance();self.assertEqual(self.work.status,'owner_needed',self.work.finding);self.assertIsNone(change.document(self.work,'notice'))

    def test_lost_delivery_response_must_reconcile_original_effect_before_correction(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        auth=self.authorized();self.start(auth);self.advance();self.review('notice')
        for _ in range(16):
            factory.run_once(self.work.pk,adapter=PublicationTimeoutAfterAccept());self.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=self.work,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=self.work);receipt=PublicationReceipt.objects.get(publication=job.publication)
        self.assertEqual(job.status,'unknown')
        with self.assertRaises(ValidationError):change.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.cv.pk,self.inputs,'No replacement while receipt is uncertain')
        change.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db();spent=self.work.budget_used
        change.reconcile(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db();job.refresh_from_db()
        self.assertEqual(job.status,'confirmed');self.assertEqual(self.work.status,'followup_needed');self.assertEqual(self.work.budget_used,spent)
        self.assertEqual(Publication.objects.filter(factory_work=self.work).count(),1);self.assertEqual(PublicationReceipt.objects.get(publication=job.publication).pk,receipt.pk)
        self.assertFalse(ChangeClosure.objects.exists())

    def test_returned_document_rework_retains_old_draft_and_requires_fresh_review(self):
        from tests.document_helpers import artifact
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},self.e['policy_decision'])
        auth=self.authorized();self.start(auth);self.advance();v=change.document(self.work,'notice');spent=self.work.budget_used
        change.review(self.actor,self.work.pk,self.work.revision,rev(self.case),v.pk,'return','Human returned this exact report for correction')
        self.advance();self.assertEqual(change.document(self.work,'notice').pk,v.pk)
        change.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.cv.pk,self.inputs,'Reviewed redraft of returned exact document')
        self.advance();new=change.document(self.work,'notice');self.assertNotEqual(v.pk,new.pk);self.assertGreater(self.work.budget_used,spent)
        self.client.force_login(self.actor);page=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertContains(page,'Earlier source-package documents');self.assertContains(page,f'Exact earlier version {v.pk}');self.assertContains(page,'Replacements may start at version 1')
        self.assertFalse(Publication.objects.filter(version=v).exists());self.review('notice');self.advance()
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),1)

    def test_exact_work_human_commands_and_configuration_console(self):
        self.start();self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk])
        self.assertContains(self.client.get(url),'Record your owner impact assessment')
        response=self.client.post(url,{'action':'assess','revision':self.work.revision,'case_revision':rev(self.case),'change_version':self.cv.pk,'contributor':'QA','cost_impact':'unknown','timeline_impact':'false','client_facing':'false','evidence':self.source.pk,'note':'QA owner declares cost unknown'})
        self.assertEqual(response.status_code,302);self.assertIsNone(self.cv.assessments.get().cost_impact)
        with self.assertRaises(ValidationError):change.human_action(self.actor,self.work.pk,self.work.revision,rev(self.case),self.cv.pk+999,'authorize',{})
        settings=reverse('factory_configuration',args=[self.case.pk])+'?definition=pmo-change/v1'
        self.assertContains(self.client.get(settings),'Existing change preparer')
        self.assertContains(self.client.get(settings),'Controlled document publisher')

    def test_unobserved_publication_cannot_bind_to_factory_work(self):
        from apps.pmo.change_execution import draft_change_document
        auth=self.authorized();self.start(auth);self.advance()
        foreign=draft_change_document(self.actor,self.case.pk,auth.pk,self.template.pk,'notice',rev(self.case))
        with self.assertRaises(ValidationError):change.publication_scope(self.actor,self.case,foreign,self.work.pk)

    def test_withdrawn_decision_authority_invalidates_selected_authorization(self):
        auth=self.authorized();self.start(auth)
        Grant.objects.filter(case=self.case,user=self.actor,action='change.decide').update(active=False)
        self.advance();self.assertIsNone(change.document(self.work,'notice'));self.assertNotEqual(self.work.status,'verified')

    def reserve_notice(self):
        auth=self.authorized();self.start(auth);self.advance();self.review('notice')
        for _ in range(10):
            factory.run_once(self.work.pk);self.work.refresh_from_db()
            job=PublicationJob.objects.filter(publication__factory_work=self.work,status='pending').first()
            if job:return job
        self.fail('Expected reserved, undispatched native notice')

    def test_cancelled_undelivered_publication_permits_explicit_same_source_redraft(self):
        job=self.reserve_notice();old=change.document(self.work,'notice');spent=self.work.budget_used
        change.operate(self.actor,self.work.pk,self.work.revision,rev(self.case),job.pk,'cancel','Human stops this undispatched exact document');self.work.refresh_from_db()
        change.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.cv.pk,self.inputs,'Explicit human request for fresh reviewed package after cancellation')
        self.advance();new=change.document(self.work,'notice');self.assertNotEqual(old.pk,new.pk);self.review('notice');self.advance()
        job.refresh_from_db();self.assertEqual(job.status,'cancelled');self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),1);self.assertGreater(self.work.budget_used,spent)

    def test_stopped_pending_delivery_exposes_cancel_only_and_settled_restart(self):
        job=self.reserve_notice();change.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db();self.assertEqual(self.work.status,'waiting_effect')
        self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk]);page=self.client.get(url)
        self.assertContains(page,'Cancel original delivery');self.assertNotContains(page,'Retry exact eligible delivery')
        result=self.client.post(url,{'action':'operate_delivery','revision':self.work.revision,'case_revision':rev(self.case),'job':job.pk,'operation':'cancel','reason':'Stop original undispatched effect'})
        self.assertEqual(result.status_code,302);self.work.refresh_from_db();self.assertEqual(self.work.status,'cancelled')
        self.assertContains(self.client.get(url),'Restart settled preparation');head=self.work.source_head_id;spent=self.work.budget_used
        result=self.client.post(url,{'action':'restart','revision':self.work.revision,'case_revision':rev(self.case),'reason':'Fresh explicit preparation instruction after settled stop'})
        self.assertEqual(result.status_code,302);self.work.refresh_from_db();self.assertFalse(self.work.cancel_requested);self.assertNotEqual(self.work.source_head_id,head);self.assertEqual(self.work.budget_used,spent)
        self.advance();self.review('notice');self.advance();self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),1)
