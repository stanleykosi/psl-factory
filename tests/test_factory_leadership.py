"""Recovered P40/P42 factory contract, real native services and synthetic delivery."""
import json
from pathlib import Path
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,transaction,connection
from django.utils import timezone
from django.urls import reverse
from apps.identity.models import Grant
from apps.documents.models import Publication,PublicationReceipt,PublicationJob
from apps.documents.controlled import reserve_publication,publication_requirements
from adapters.publications import PublicationTimeoutAfterAccept
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,active_component
from apps.workflows import factory,factory_leadership as reporting
from apps.workflows.models import FactoryWork,FactoryAttempt,HumanTask
from tests import test_leadership_reporting as native_tests
from tests.document_helpers import artifact
from tests.helpers import rev

class FactoryLeadershipTests(TestCase):
    configure=native_tests.LeadershipReportTests.configure
    save_content=native_tests.LeadershipReportTests.save_content
    def setUp(self):
        native_tests.LeadershipReportTests.setUp(self)
        for action in ['factory.start','factory.read','factory.execute','factory.manage','document.publish','document.operate']:
            Grant.objects.get_or_create(case=self.case,user=self.actor,action=action)
        value=json.loads(Path('fixtures/factory-leadership.json').read_text());value.pop('classification')
        value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk)
        self.policy=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_leadership_execution',value,self.owner.pk,timezone.now())
        transition(self.actor,self.policy.pk,'validated');transition(self.actor,self.policy.pk,'active')
        self.inputs={'start_at':self.start.isoformat(),'end_at':self.end.isoformat(),'template_id':self.template.pk,'content_id':self.content.pk,'kind':self.kind,'audience':'internal','selections':self.selections}
    def start_work(self):
        self.work=reporting.start(self.actor,self.case.pk,'LEADERSHIP-1',self.inputs,'Internal leadership update',rev(self.case));return self.work
    def advance(self):
        factory.run_until_wait(self.work.pk);self.work.refresh_from_db()
    def review(self,verdict='approve'):
        self.work.refresh_from_db();v=reporting.document(self.work);self.assertIsNotNone(v,self.work.finding)
        reporting.review(self.actor,self.work.pk,self.work.revision,rev(self.case),v.pk,verdict,'Exact human themes and selected coverage reviewed');return v
    def tuesday(self):
        self.kind='internal_tuesday';self.configure(self.kind);self.inputs.update(kind=self.kind,template_id=self.template.pk,content_id=self.content.pk)
    def audience(self,value):
        artifact(self.actor,self.case,'OPS.leadership_audience','schema:psl/leadership-audience/v1',value,self.owner)
    def test_tuesday_no_extra_approval_and_exact_receipts(self):
        self.tuesday();transition(self.actor,active_component('OPS.leadership_review_authority',self.case).pk,'revoked')
        self.start_work();self.assertEqual(self.start_work().pk,self.work.pk);self.advance()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        v=reporting.document(self.work);self.assertFalse(v.reviews.exists());self.assertFalse(HumanTask.objects.filter(version=v).exists())
        self.assertIsNone(Publication.objects.get(version=v).review_id);self.assertEqual(len(reporting.verify(self.work,self.actor)['receipt_ids']),1)
    def test_monthly_human_themes_and_exact_role(self):
        artifact(self.actor,self.case,'OPS.leadership_review_authority','schema:psl/leadership-review-authority/v1',{'role':'Head of PMO'},self.owner)
        self.start_work();self.advance();v=reporting.document(self.work);self.assertEqual(HumanTask.objects.get(version=v).required_role,'Head of PMO')
        self.review();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        self.assertIn('performance',v.fields);self.assertIn('critical_incidents',v.fields)
    def test_return_requires_fresh_version_without_budget_reset(self):
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},self.owner)
        self.start_work();self.advance();old=self.review('return');self.advance();spent=self.work.budget_used
        reporting.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.inputs,'Deliberate return response')
        self.advance();self.assertNotEqual(old.pk,reporting.document(self.work).pk);self.assertGreaterEqual(self.work.budget_used,spent)
        self.review();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_missing_narrative_does_useful_investigation(self):
        self.inputs['content_id']=None;self.start_work();self.advance();self.assertIsNone(reporting.document(self.work))
        self.assertTrue(FactoryAttempt.objects.filter(activity__work=self.work,result__investigation__narrative__status='missing').exists())
    def test_unconfigured_role_retains_prepared_document(self):
        artifact(self.actor,self.case,'OPS.leadership_review_authority','schema:psl/leadership-review-authority/v1',{'role':None},self.owner)
        self.start_work();self.advance();v=reporting.document(self.work);self.assertIsNotNone(v);self.assertFalse(HumanTask.objects.filter(version=v).exists());self.assertFalse(Publication.objects.exists())
    def test_unconfigured_membership_holds_only_delivery(self):
        self.tuesday();self.audience({'internal_tuesday:internal':None,'monthly_executive:internal':[self.recipient.pk],'monthly_executive:management':None})
        self.start_work();self.advance();self.assertIsNotNone(reporting.document(self.work));self.assertFalse(HumanTask.objects.exists());self.assertFalse(Publication.objects.exists())
    def test_membership_policy_change_invalidates_without_erasing_receipts(self):
        self.start_work();self.advance();self.review();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        self.audience({'internal_tuesday:internal':[self.recipient.pk],'monthly_executive:internal':None,'monthly_executive:management':None})
        with self.assertRaises(ValidationError):reporting.verify(self.work,self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(finding='Pretend current')
        self.assertEqual(PublicationReceipt.objects.count(),1)
    def test_source_permissions_protect_history_and_ui(self):
        self.start_work();self.advance();Grant.objects.filter(case=self.case,user=self.actor,action='meeting.read').update(active=False)
        with self.assertRaises(PermissionDenied):reporting.source(self.work,self.actor,False)
        self.client.force_login(self.actor);self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,403)
    def test_needs_me_and_read_only_detail(self):
        from apps.workflows.factory_views import presentation
        self.start_work();self.advance();self.assertTrue(presentation(self.actor,self.work)['needs_me']);count=FactoryAttempt.objects.count()
        self.client.force_login(self.actor);self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,200);self.assertEqual(FactoryAttempt.objects.count(),count)
    def test_native_sql_helpers_and_anti_escape(self):
        self.start_work();self.advance();v=self.review();pins,recipients,retention=publication_requirements(self.case,v)
        with connection.cursor() as c:
            c.execute('SELECT psl_leadership_document(%s,%s,%s),psl_leadership_review(%s,%s,%s),psl_leadership_distribution(%s,%s,%s,%s,%s)',[self.work.pk,self.work.source_head_id,v.pk,self.case.pk,v.pk,v.reviews.latest('pk').pk,self.case.pk,v.pk,json.dumps(pins),json.dumps(recipients),retention]);self.assertEqual(c.fetchone(),(True,True,True))
        with self.assertRaises(DatabaseError),transaction.atomic():reserve_publication(self.actor,self.case.pk,v.pk,rev(self.case))
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_role_policy_change_invalidates_current_truth(self):
        self.start_work();self.advance();self.review();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        artifact(self.actor,self.case,'OPS.leadership_review_authority','schema:psl/leadership-review-authority/v1',{'role':'Head of PMO'},self.owner)
        with self.assertRaises(ValidationError):reporting.verify(self.work,self.actor)
        self.assertEqual(PublicationReceipt.objects.count(),1)
    def uncertain(self):
        self.start_work();self.advance();self.review()
        for _ in range(20):
            factory.run_once(self.work.pk,adapter=PublicationTimeoutAfterAccept());self.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=self.work,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=self.work);self.assertEqual(job.status,'unknown',self.work.finding);return job
    def test_uncertain_effect_lookup_only_after_permission_withdrawal(self):
        job=self.uncertain();receipt=PublicationReceipt.objects.get(publication=job.publication)
        Grant.objects.filter(case=self.case,user=self.actor,action='document.publish').update(active=False)
        reporting.reconcile(self.actor,self.work.pk,self.work.revision,adapter=native_tests.LookupOnly());job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.get(publication=job.publication).pk,receipt.pk);self.assertEqual(Publication.objects.count(),1)
    def test_cancel_uncertain_preserves_receipt_and_disallows_restart(self):
        job=self.uncertain();reporting.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        reporting.reconcile(self.actor,self.work.pk,self.work.revision,adapter=native_tests.LookupOnly());self.work.refresh_from_db();self.assertEqual(self.work.status,'followup_needed')
        with self.assertRaises(ValidationError):reporting.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),'No repeat')
    def test_typed_owner_audience_creates_only_draft(self):
        from apps.policy.models import Configuration
        self.start_work();self.client.force_login(self.actor)
        response=self.client.post(reverse('factory_detail',args=[self.work.pk]),{'action':'draft_audience','case_revision':rev(self.case),'purpose':'internal_tuesday:internal','participants':[self.recipient.pk],'evidence':self.owner.pk,'effective_from':timezone.now().isoformat()})
        self.assertEqual(response.status_code,302);policy=Configuration.objects.filter(case=self.case,component='OPS.leadership_audience').latest('pk');self.assertEqual(policy.states.order_by('-pk').first().state,'draft')
    def test_selected_source_successor_invalidates_verified_output(self):
        from apps.pmo.meetings import record_meeting
        self.start_work();self.advance();self.review();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        record_meeting(self.actor,self.case.pk,'STATUS-001','status',timezone.now()-timedelta(minutes=1),'Changed source','New current source',[self.actor.pk],[],self.notes.pk,rev(self.case),self.meeting.meeting_id)
        with self.assertRaises(ValidationError):reporting.verify(self.work,self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(finding='Claim stale output current')
        self.assertEqual(PublicationReceipt.objects.count(),1)
    def test_typed_monthly_source_fields_do_not_collide_with_escalation_theme(self):
        from apps.workflows.factory_leadership_views import InputsForm
        form=InputsForm(self.case,actor=self.actor,initial=self.inputs)
        self.assertIn('source_escalations',form.fields);self.assertIn('escalations',form.fields)
        self.assertNotEqual(type(form.fields['source_escalations']),type(form.fields['escalations']))
    def test_typed_role_configuration_retains_actual_owner_decision_only(self):
        from apps.policy.models import Configuration
        self.start_work();self.client.force_login(self.actor)
        response=self.client.post(reverse('factory_detail',args=[self.work.pk]),{'action':'draft_review_role','case_revision':rev(self.case),'role':'Head of PMO','evidence':self.owner.pk,'effective_from':timezone.now().isoformat()})
        self.assertEqual(response.status_code,302);policy=Configuration.objects.filter(case=self.case,component='OPS.leadership_review_authority').latest('pk');self.assertEqual(policy.states.order_by('-pk').first().state,'draft')
