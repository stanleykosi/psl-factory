"""Check that grouped browser staging leaves operator decisions for the walkthrough."""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.finance.models import InvoiceIssue, InvoiceJob, InvoiceReview
from apps.pmo.models import ArchiveCopyPlan, ChangeAuthorization, ChangeDecision, EmergencyAuthorization, EmergencyDecision, EmergencyOutcome, EscalationDecision
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests.railway_batch_walkthrough_seed import (
    PREPARATION, prepare_accounting_intake, prepare_hr_payroll_correction, prepare_invoice_decision_variant,
    prepare_independent_finance_review, prepare_project, prepare_unreadable_invoice,
)


class DesignBatchWalkthroughTests(TestCase):
    def test_uncertain_accounts_sample_reconciles_only_the_original_delivery(self):
        from apps.documents.models import PublicationJob, PublicationReceipt

        actor = get_user_model().objects.create_user('synthetic-batch-accounts-recovery-reader')
        sample = prepare_project(actor, 'accounts_uncertain_receipt')
        job = PublicationJob.objects.get(publication__factory_work_id=sample['work'])
        receipts = PublicationReceipt.objects.filter(publication=job.publication)
        receipt = receipts.get()
        self.assertEqual((job.status, job.attempts), ('unknown', 1))
        self.assertEqual(prepare_project(actor, 'accounts_uncertain_receipt')['work'], sample['work'])
        self.client.force_login(actor)
        recovery = reverse('factory_invoice_recovery', args=[sample['work']])
        self.assertContains(self.client.get(recovery), 'Check original delivery receipts')
        work = FactoryWork.objects.get(pk=sample['work'])
        response = self.client.post(recovery, {'action': 'reconcile', 'revision': work.revision})
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts), ('confirmed', 1))
        self.assertEqual(receipts.get().pk, receipt.pk)
        self.assertEqual(PublicationJob.objects.filter(publication__factory_work=work).count(), 1)

    def test_independent_finance_samples_leave_exact_decisions_for_browser_reviewer(self):
        from apps.workflows import factory_ppe, factory_schedules

        actor = get_user_model().objects.create_user('synthetic-batch-independent-finance-reader')
        for key, workflow, heading in (
            ('asset_review', factory_ppe, 'Calculated schedule decision'),
            ('income_review', factory_schedules, 'Finance schedule decision'),
        ):
            with self.subTest(journey=key):
                sample = prepare_independent_finance_review(actor, key)
                self.assertEqual(prepare_independent_finance_review(actor, key)['work'], sample['work'])
                work = FactoryWork.objects.get(pk=sample['work'])
                self.assertTrue(work.case.synthetic)
                self.assertNotEqual(work.actor_id, actor.pk)
                self.assertFalse(work.actor.has_usable_password())
                schedule = workflow.schedule(work)
                self.assertIsNotNone(schedule, work.finding)
                self.assertFalse(schedule.reviews.exists())
                self.client.force_login(work.actor)
                self.assertNotContains(self.client.get(sample['path']), 'Approve exact schedule')
                self.client.force_login(actor)
                response = self.client.get(sample['path'])
                self.assertContains(response, heading)
                self.assertContains(response, 'Approve exact schedule')
                self.assertNotContains(response, 'Open exact reviewed report')

    def test_invoice_decision_samples_keep_their_actual_scope_and_prior_version(self):
        actor = get_user_model().objects.create_user('synthetic-batch-finance-reader')
        self.client.force_login(actor)
        states = {'invoice_maker': 'Waiting for another Finance reviewer',
                  'invoice_other_reviewer': 'Assigned to another Finance reviewer',
                  'invoice_replaced': 'A newer invoice draft is available'}
        for key, label in states.items():
            with self.subTest(journey=key):
                sample = prepare_invoice_decision_variant(actor, key)
                self.assertEqual(prepare_invoice_decision_variant(actor, key)['work'], sample['work'])
                page = self.client.get(sample['path'])
                self.assertContains(page, label)
                self.assertNotContains(page, 'Claim task')
                self.assertNotContains(page, 'Approve exact packet')
        self.assertFalse(InvoiceReview.objects.exists())
        self.assertFalse(InvoiceJob.objects.exists())

    def test_preparation_reopens_original_even_after_another_report_for_the_same_project(self):
        from apps.workflows import factory_leadership
        from tests.helpers import rev

        actor = get_user_model().objects.create_user('synthetic-batch-report-reviewer')
        original = prepare_project(actor, 'leadership')
        work = FactoryWork.objects.get(pk=original['work'])
        inputs = dict(factory_leadership.source(work, actor)['inputs'])
        inputs['start_at'] = (datetime.fromisoformat(inputs['start_at']) - timedelta(days=1)).isoformat()
        other = factory_leadership.start(actor, work.case_id, 'SAMPLE-LONGER-REPORT', inputs,
                                         'Synthetic report with wider coverage', rev(work.case))
        self.assertNotEqual(work.pk, other.pk)
        self.assertEqual(prepare_project(actor, 'leadership')['work'], work.pk)
        self.assertEqual(FactoryWork.objects.filter(case=work.case, definition=work.definition).count(), 2)

    def test_native_preparations_open_and_preserve_existing_journeys(self):
        from adapters.client_uat import TARGET
        from apps.pmo.models import DeliveryDossier, DeliverySource

        actor = get_user_model().objects.create_user('synthetic-batch-browser-reviewer')
        self.client.force_login(actor)
        for key, (definition, _) in PREPARATION.items():
            with self.subTest(journey=key):
                prepared = prepare_project(actor, key)
                replay = prepare_project(actor, key)
                self.assertFalse(prepared['existing_work_preserved'])
                self.assertTrue(replay['existing_work_preserved'])
                self.assertEqual(prepared['work'], replay['work'])
                work = FactoryWork.objects.get(pk=prepared['work'], definition=definition,
                                               case__synthetic=True, actor=actor)
                self.assertFalse(FactoryProgress.objects.filter(work=work, status='running').exists())
                self.assertEqual(self.client.get(prepared['path']).status_code, 200)
        self.assertFalse(ArchiveCopyPlan.objects.exists())
        self.assertFalse(ChangeAuthorization.objects.exists())
        self.assertFalse(ChangeDecision.objects.exists())
        self.assertFalse(EmergencyAuthorization.objects.exists())
        self.assertFalse(EmergencyDecision.objects.exists())
        self.assertFalse(EmergencyOutcome.objects.exists())
        self.assertFalse(EscalationDecision.objects.exists())
        delivery = DeliveryDossier.objects.get(case__title=PREPARATION['client_testing_wait'][1])
        self.assertFalse(DeliverySource.objects.filter(dossier=delivery, kind=TARGET).exists())
        page = self.client.get(reverse('client_uat', args=[delivery.case_id, delivery.pk]))
        self.assertContains(page, 'Record testing request')
        invoice = FactoryWork.objects.get(case__title=PREPARATION['invoice_release'][1]).invoice
        self.assertIsNotNone(invoice)
        approval = HumanTask.objects.get(case=invoice.case, kind='factory_review', status='open')
        self.assertEqual(approval.context['packet']['recipient_id'], actor.pk)
        self.assertIsNotNone(approval.context['packet'].get('obligation_identity'))
        self.assertFalse(InvoiceReview.objects.filter(invoice=invoice).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=invoice).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice=invoice).exists())

    def test_accounting_intake_samples_remain_held_until_browser_review(self):
        actor = get_user_model().objects.create_user('synthetic-batch-intake-reviewer')
        self.client.force_login(actor)
        for missing in (True, False):
            with self.subTest(missing_units=missing):
                prepared = prepare_accounting_intake(actor, missing_units=missing)
                replay = prepare_accounting_intake(actor, missing_units=missing)
                self.assertEqual(prepared['intake_receipt'], replay['intake_receipt'])
                self.assertTrue(replay['existing_work_preserved'])
                label = 'Confirm file units' if missing else 'Quarantined'
                self.assertContains(self.client.get(prepared['path']), label)
        self.assertFalse(FactoryWork.objects.exists())

    def test_hr_correction_sample_keeps_decision_for_hr_and_hides_rows_from_finance(self):
        from apps.finance import hrfinance
        from apps.finance.models import PayrollHRFollowup

        users = get_user_model().objects
        actor = users.create_user('synthetic-batch-hr-reviewer')
        prepared = prepare_hr_payroll_correction(actor)
        replay = prepare_hr_payroll_correction(actor)
        self.assertTrue(replay['existing_work_preserved'])
        self.assertEqual(prepared['correction'], replay['correction'])
        self.client.force_login(users.get(pk=prepared['finance_preparer']))
        self.assertEqual(self.client.get(prepared['path']).status_code, 403)
        self.client.force_login(actor)
        response = self.client.get(prepared['path'])
        self.assertContains(response, 'Record HR decision')
        self.assertNotContains(response, 'E001')
        link = PayrollHRFollowup.objects.get(pk=prepared['correction'])
        self.assertFalse(hrfinance.correction_disposition(link.record).exists())

    @override_settings(DEBUG=False)
    def test_separate_sample_work_returns_the_same_opaque_page_as_missing_work(self):
        sample = prepare_unreadable_invoice()
        self.assertEqual(prepare_unreadable_invoice()['work'], sample['work'])
        work = FactoryWork.objects.get(pk=sample['work'])
        self.assertFalse(work.actor.has_usable_password())
        self.client.force_login(work.actor)
        self.assertContains(self.client.get(sample['path']), work.invoice.reference)
        other = get_user_model().objects.create_user('synthetic-outside-invoice-reader')
        self.client.force_login(other)
        denied = self.client.get(sample['path'])
        nonexistent = self.client.get(reverse('factory_detail', args=[work.pk + 1000000]))
        self.assertContains(denied, 'Page unavailable', status_code=404)
        self.assertContains(nonexistent, 'Page unavailable', status_code=404)
        self.assertNotContains(denied, work.case.title, status_code=404)
        self.assertNotContains(denied, work.invoice.reference, status_code=404)
        self.assertNotContains(denied, work.invoice.payload['amount'], status_code=404)
