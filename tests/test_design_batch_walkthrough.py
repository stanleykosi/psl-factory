"""Check that grouped browser staging leaves operator decisions for the walkthrough."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.finance.models import InvoiceIssue, InvoiceJob, InvoiceReview
from apps.pmo.models import ArchiveCopyPlan, ChangeAuthorization, EmergencyAuthorization, EmergencyDecision, EmergencyOutcome, EscalationDecision
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests.railway_batch_walkthrough_seed import PREPARATION, prepare_accounting_intake, prepare_hr_payroll_correction, prepare_project


class DesignBatchWalkthroughTests(TestCase):
    def test_native_preparations_open_and_preserve_existing_journeys(self):
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
        self.assertFalse(EmergencyAuthorization.objects.exists())
        self.assertFalse(EmergencyDecision.objects.exists())
        self.assertFalse(EmergencyOutcome.objects.exists())
        self.assertFalse(EscalationDecision.objects.exists())
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
