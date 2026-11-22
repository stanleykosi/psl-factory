"""Observe a real draft claim through a read-only second PostgreSQL session."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.utils import timezone

from apps.core.models import Case
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory, factory_progress
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admissions
from tests import railway_finance_live_steps_seed as existing_window
from tests import railway_invoice_processing_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admissions, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admissions, 'ADMISSION_PROFILE', 'sample-reader')
class InvoiceProcessingSeedTests(TransactionTestCase):
    def test_live_native_draft_is_visible_to_exact_reader_and_stops_before_finance_decision(self):
        self.assertEqual(connection.vendor, 'postgresql')
        old = configured()
        origin = old['scopes'][0]['case']
        trial = get_user_model().objects.create_user(seed.TRIAL)
        outsider = get_user_model().objects.create_user('sample-invoice-processing-outsider')
        invitation, token = staff.invite(old['actor'], origin.pk, 'sample-invited-invoice-processing-reviewer',
            'Sample independent invoice reviewer', 'sample-invoice-processing-reviewer@example.invalid',
            ['case.read'], rev(origin), profile_key='sample-reader')
        reviewer = staff.accept(token, 'Synthetic!invoice.processing.836')
        old_grants = set(Grant.objects.filter(user=reviewer).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1_000, reviewer.pk)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        sample = seed.prepare(invitation.pk, reviewer.pk)
        self.assertEqual(seed.prepare(invitation.pk, reviewer.pk), dict(sample, preserved=True))
        work = FactoryWork.objects.get(pk=sample['work'])
        self.assertEqual(set(Grant.objects.filter(user=reviewer).exclude(case=work.case)
                             .values_list('case_id', 'action', 'active')), old_grants)
        self.assertFalse(work.actor.has_usable_password())
        self.client.force_login(trial)
        self.assertNotContains(self.client.get(sample['path']), 'Wait for the current worker observation')
        self.assertFalse(Invoice.objects.filter(case=work.case).exists())

        def read_from_second_connection():
            try:
                running = FactoryWork.objects.get(pk=work.pk)
                self.assertGreater(running.lease_until, timezone.now())
                active = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03',
                                                   phase='started', fence=running.fence)
                self.assertFalse(active.activity.attempts.filter(number=active.number, phase='observed').exists())
                self.assertFalse(Invoice.objects.filter(case=work.case).exists())
                _, value = factory.profile(running)
                state = factory.snapshot(running, value, reader=trial)
                options, _ = factory.eligible(running, value, *state)
                self.assertEqual(factory_progress.current_plan_step(running, state[0]['hash'], options), seed.STEP)
                self.assertIsNone(factory.claim(work.pk))
                reader = Client()
                reader.force_login(trial)
                page = reader.get(sample['path'])
                self.assertEqual(page.context['row']['state'], 'Processing')
                self.assertContains(page, 'Wait for the current worker observation')
                self.assertContains(page, 'A Finance draft has not yet been prepared.')
                self.assertNotContains(page, 'Continue eligible work')
                self.assertNotContains(page, 'Issue and send invoice')
                reader.force_login(outsider)
                self.assertEqual(reader.get(sample['path']).status_code, 404)
            finally:
                connections.close_all()

        def inspect(seconds):
            self.assertEqual(seconds, existing_window.WINDOW_SECONDS)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(read_from_second_connection).result(timeout=30)

        with patch.object(existing_window, 'sleep', side_effect=inspect) as window:
            settled = seed.observe(invitation.pk, reviewer.pk, work.pk)
        window.assert_called_once_with(existing_window.WINDOW_SECONDS)
        work.refresh_from_db()
        invoice = work.invoice
        self.assertEqual(settled['invoice'], invoice.pk)
        self.assertEqual(invoice.preparation.handoff_id, sample['handoff'])
        self.assertEqual(invoice.preparation.handoff.milestone.evidence_id, sample['completion'])
        self.assertNotContains(self.client.get(sample['path']), 'Wait for the current worker observation')
        self.assertContains(self.client.get(sample['decision']), 'NGN 42.00')
        self.assertNotContains(self.client.get(sample['decision']), 'Claim task')
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(sample['decision']), 'Claim task')
        task = HumanTask.objects.get(pk=settled['review_task'], case=work.case)
        self.assertIsNone(task.claimed_by_id)
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(InvoiceReview.objects.filter(invoice=invoice).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=invoice).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice=invoice).exists())
        with self.assertRaisesMessage(RuntimeError, 'Do not replay its worker claim'):
            seed.observe(invitation.pk, reviewer.pk, work.pk)
