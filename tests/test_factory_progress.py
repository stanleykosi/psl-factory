from datetime import timedelta
from tempfile import TemporaryDirectory

from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from adapters.factory_invoices import MockFactoryInvoiceAdapter
from apps.finance import invoice_delivery
from apps.finance.models import InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.models import Grant
from apps.workflows import factory_progress
from apps.workflows.models import HumanTask
from tests.billing_helpers import evidence
from tests.factory_helpers import fixture
from tests.obligation_helpers import factory_approve_identified


class FactoryProgressTests(TransactionTestCase):
    def drain(self, job):
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), job.pk)
            job.refresh_from_db()
            if job.status != 'queued':
                return job.status
        self.fail('Work did not reach a stop within the fixture budget')

    def wake(self, job):
        job.available_at = timezone.now() - timedelta(seconds=1)
        job.save(update_fields=['available_at'])

    def test_background_waits_without_spending_and_resumes_to_native_receipts(self):
        data = fixture(missing=True)
        work, actor = data['work'], data['actor']
        job = factory_progress.set_progress(actor, work.pk, work.revision, True)
        self.assertEqual(self.drain(job), 'waiting')
        self.assertTrue(HumanTask.objects.filter(case=work.case, kind='factory_information', status='open').exists())
        work.refresh_from_db()
        used = work.budget_used
        self.wake(job)
        self.assertEqual(self.drain(job), 'waiting')
        work.refresh_from_db()
        self.assertEqual(work.budget_used, used)
        evidence(actor, work.case, 'factory_information', 'Synthetic evidence supplied for the background trial')
        self.wake(job)
        self.assertEqual(self.drain(job), 'waiting')
        self.assertFalse(InvoiceIssue.objects.exists())
        factory_approve_identified(data)
        self.wake(job)
        with TemporaryDirectory() as path, override_settings(FACTORY_ADAPTERS={str(work.case_id): MockFactoryInvoiceAdapter(path)}):
            self.assertEqual(self.drain(job), 'finished')
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(InvoiceIssue.objects.filter(invoice=work.invoice).count(), 1)
        self.assertEqual(InvoiceDelivery.objects.filter(invoice=work.invoice).count(), 1)

    def test_uncertain_send_stops_until_native_recovery(self):
        data = fixture()
        work, actor = data['work'], data['actor']
        job = factory_progress.set_progress(actor, work.pk, work.revision, True)
        self.assertEqual(self.drain(job), 'waiting')
        factory_approve_identified(data)
        self.wake(job)
        with TemporaryDirectory() as path, override_settings(FACTORY_ADAPTERS={str(work.case_id): MockFactoryInvoiceAdapter(path, lose_response=True)}):
            self.assertEqual(self.drain(job), 'held')
            issue = InvoiceJob.objects.get(kind='issue')
            self.assertEqual(issue.status, 'unknown')
            self.assertTrue(invoice_delivery.run_once(job_id=issue.pk))
            issue.refresh_from_db()
            self.assertEqual(issue.status, 'unknown')
            self.assertFalse(InvoiceIssue.objects.exists())
            self.assertTrue(invoice_delivery.run_once(MockFactoryInvoiceAdapter(path), job_id=issue.pk))
            self.assertEqual(InvoiceIssue.objects.count(), 1)
        self.assertIsNone(factory_progress.run_once())
        self.assertEqual(InvoiceJob.objects.count(), 1)

    def test_paused_and_revoked_requests_do_not_advance(self):
        data = fixture()
        work, actor = data['work'], data['actor']
        self.client.force_login(actor)
        url = reverse('factory_background', args=[work.pk])
        payload = {'revision': work.revision, 'action': 'continue'}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        job = work.background_progress
        factory_progress.set_progress(actor, work.pk, work.revision, False)
        self.assertIsNone(factory_progress.run_once())
        factory_progress.set_progress(actor, work.pk, work.revision, True, initial=True)
        job.refresh_from_db()
        self.assertEqual(job.status, 'paused')
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        Grant.objects.filter(user=actor, case=work.case, action='factory.execute').update(active=False)
        self.assertEqual(self.drain(job), 'held')
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.assertFalse(work.activities.exists())
