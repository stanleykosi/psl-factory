"""Native restricted payroll factory integration; requires accepted payroll schema."""
import json,os
from pathlib import Path
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError,connection
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.finance import payroll as native
from apps.finance.payroll_models import PayrollPublication,PayrollReportReceipt
from apps.workflows import factory,factory_payroll as payroll
from apps.workflows.models import FactoryWork,FactoryAttempt
from tests.payroll_helpers import fixture,approve,capture
from tests.helpers import rev

class FactoryPayrollTests(TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('PSL_PAYROLL_DIAGNOSTIC_GUARD')=='1':
            from tests.payroll_diagnostic_schema import SQL
            with connection.cursor() as cursor:cursor.execute(SQL)
        super().setUpClass()
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.environ.get('PSL_PAYROLL_DIAGNOSTIC_GUARD')=='1':
            from tests.payroll_diagnostic_schema import PREVIOUS
            with connection.cursor() as cursor:cursor.execute(PREVIOUS)

    @classmethod
    def setUpTestData(cls):
        cls.f=fixture();f=cls.f
        value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
        p=draft_operator_policy(f['owner'],f['case'].pk,'OPS.factory_payroll_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(f['owner'],p.pk,'validated');transition(f['owner'],p.pk,'active')
        Grant.objects.create(case=f['case'],user=f['manager'],action='factory.read')
    def rowsets(self):
        tables=[name for name in connection.introspection.table_names() if name.startswith(('core_','finance_','workflows_','agents_','policy_','pmo_','documents_','identity_'))]
        result={}
        with connection.cursor() as cursor:
            for name in tables:
                cursor.execute("SELECT count(*), md5(COALESCE(string_agg(row_to_json(t)::text, chr(10) ORDER BY row_to_json(t)::text),'')) FROM "+connection.ops.quote_name(name)+' t')
                result[name]=cursor.fetchone()
        return result
    def start(self,hr=True):
        f=self.f;self.inputs={'input_ids':[i.pk for i in f['inputs']],'hr_snapshot_id':f['hr'].pk if hr else None}
        self.work=payroll.start(f['preparer'],f['case'].pk,'PAYROLL-1',f['request'].pk,self.inputs,'September staff-cost work',rev(f['case']));return self.work
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def pipeline(self):
        f=self.f;self.start();self.advance();self.assertEqual(payroll.report(self.work)['stage'],'input_review')
        for i in f['inputs']:approve(f,i)
        for stage in ['combine','match','aggregate']:
            self.advance();r=payroll.run(self.work,stage);self.assertIsNotNone(r,self.work.finding);approve(f,r)
        self.advance();self.assertEqual(payroll.report(self.work)['stage'],'publish');self.assertFalse(PayrollPublication.objects.exists())
        p=payroll.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'publish',{})
        self.advance();self.assertNotEqual(self.work.status,'verified');return p
    def test_complete_native_path_requires_reviews_human_publication_and_actual_recipient_receipt(self):
        f=self.f;p=self.pipeline();self.assertFalse(PayrollReportReceipt.objects.exists())
        payroll.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding);result=payroll.verify(self.work)
        self.assertEqual(result['publication'],p.pk);self.assertEqual(len(result['receipt_ids']),1);self.assertFalse(result['hr_written'])
        self.assertEqual(native.read_publication(f['manager'],p.pk)['by_bu'],{'BU-A':'250.00'});self.assertEqual(connection.vendor,'postgresql')
        text=json.dumps(list(FactoryAttempt.objects.filter(activity__work=self.work).values('observation','result')))
        for secret in ['E001','E002','employee_id','effective_from','BASIC']:self.assertNotIn(secret,text)
    def test_exact_sources_idempotency_and_database_verified_guard(self):
        f=self.f;self.start()
        self.assertEqual(payroll.start(f['preparer'],f['case'].pk,'OTHER',f['request'].pk,self.inputs,'Same native request').pk,self.work.pk)
        with self.assertRaises(ValidationError):payroll.start(f['preparer'],f['case'].pk,'PAYROLL-2',f['request'].pk,dict(self.inputs,input_ids=[f['inputs'][0].pk]*2),'Wrong two inputs')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_private_source_access_is_not_conferred_by_factory_read(self):
        f=self.f;self.start();Grant.objects.filter(case=f['case'],user=f['preparer'],action='payroll.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):payroll.source(self.work,f['preparer'])
        self.client.force_login(f['preparer']);self.assertIn(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,[403,404])
    def test_minimal_hr_selection_required_without_guessed_matching(self):
        f=self.f;self.start(hr=False)
        for i in f['inputs']:approve(f,i)
        self.advance();approve(f,payroll.run(self.work,'combine'));self.advance()
        self.assertIsNone(payroll.run(self.work,'match'));self.assertIn('HR',self.work.finding)
    def test_source_owned_replacement_preserves_history_and_budget(self):
        f=self.f;self.start();self.advance();old=self.work.source_head_id;spent=self.work.budget_used
        new=capture(f,0,'replacement',source_version='A-v2')
        inputs=dict(self.inputs,input_ids=[new.pk,f['inputs'][1].pk])
        payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,inputs,'Source owner supplied corrected version')
        self.work.refresh_from_db();self.assertNotEqual(self.work.source_head_id,old);self.assertEqual(self.work.budget_used,spent);self.assertTrue(self.work.activities.exists())
        with self.assertRaises(ValidationError):payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,inputs,'Unchanged retry not a replacement')
    def test_recipient_console_is_aggregate_only_and_get_preserves_revision(self):
        f=self.f;p=self.pipeline();self.client.force_login(f['manager']);url=reverse('factory_detail',args=[self.work.pk]);before=self.work.revision
        response=self.client.get(url);self.assertContains(response,'Acknowledge receipt as myself');self.assertNotContains(response,'Inspect restricted payroll input')
        self.work.refresh_from_db();self.assertEqual(self.work.revision,before)
        self.assertEqual(self.client.post(url,{'action':'receive','revision':before,'case_revision':rev(f['case']),'publication_id':p.pk}).status_code,302)
        self.assertEqual(PayrollReportReceipt.objects.get(publication=p).actor_id,f['manager'].pk)
    def test_preparer_cannot_impersonate_recipient(self):
        f=self.f;p=self.pipeline()
        with self.assertRaises(PermissionDenied):payroll.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.assertFalse(PayrollReportReceipt.objects.exists())
    def test_current_review_revocation_invalidates_verification(self):
        f=self.f;p=self.pipeline();native.receive_report(f['manager'],f['case'].pk,p.pk,rev(f['case']));self.advance();self.assertEqual(self.work.status,'verified')
        approve(f,payroll.run(self.work,'aggregate'),'revoke-aggregate','revoke')
        with self.assertRaises(ValidationError):payroll.verify(self.work)
        self.assertEqual(PayrollReportReceipt.objects.filter(publication=p).count(),1)
    def test_cancel_after_publication_retains_native_effect_and_receipt_route(self):
        f=self.f;p=self.pipeline();factory.manage(f['preparer'],self.work.pk,self.work.revision,'cancel');self.work.refresh_from_db()
        self.assertEqual(self.work.status,'followup_needed');self.assertTrue(PayrollPublication.objects.filter(pk=p.pk).exists())
        self.assertFalse(PayrollReportReceipt.objects.exists())
    def test_returned_work_rebuilds_without_erasing_prior_native_result(self):
        f=self.f;self.start()
        for i in f['inputs']:approve(f,i)
        self.advance();old=payroll.run(self.work,'combine');approve(f,old,'return-first-combine','return');spent=self.work.budget_used
        payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,self.inputs,'Reviewer returned the exact working result for controlled preparation')
        self.work.refresh_from_db();self.assertEqual(self.work.budget_used,spent);self.advance();new=payroll.run(self.work,'combine')
        self.assertNotEqual(new.pk,old.pk);self.assertTrue(old.reviews.filter(verdict='return').exists());self.assertFalse(PayrollPublication.objects.exists())
    def test_preparer_console_and_profile_are_available_without_get_mutation(self):
        f=self.f;self.start();self.client.force_login(f['preparer']);before=self.work.revision
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertContains(response,'Continue permitted agent work');self.assertContains(response,'Exactly two accepted provider versions')
        self.work.refresh_from_db();self.assertEqual(self.work.revision,before)
    def test_foreign_native_review_subject_is_not_a_work_decision(self):
        f=self.f;self.start()
        with self.assertRaises(ValidationError):payroll.human_action(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),'review',{'kind':'input','subject_id':999999,'verdict':'approve','operation_key':'foreign-review','evidence_id':f['e']['payroll_review'].pk})

    def test_observation_and_get_preserve_all_native_rows_revisions_attempts_and_audit(self):
        f=self.f;p=self.pipeline();self.client.force_login(f['preparer']);before=self.rowsets()
        _,profile=factory.profile(self.work)
        state,*_=payroll.snapshot(self.work,profile,reader=f['preparer'])
        self.assertEqual(state['native']['stage'],'receipt')
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertEqual(response.status_code,200)
        self.assertEqual(self.rowsets(),before)
        self.client.force_login(f['manager']);before=self.rowsets()
        self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,200)
        self.assertEqual(self.rowsets(),before)
