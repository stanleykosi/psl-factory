from datetime import timedelta
from tempfile import TemporaryDirectory
from threading import Event, Thread

from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from adapters.factory_invoices import MockFactoryInvoiceAdapter
from apps.finance import invoice_delivery
from apps.finance.models import InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.models import Grant
from apps.workflows import factory_progress
from apps.workflows.models import FactoryWork, HumanTask
from tests.billing_helpers import evidence
from tests.factory_helpers import fixture
from tests.obligation_helpers import factory_approve_identified


class FactoryProgressTests(TransactionTestCase):
    def test_background_refresh_marks_only_active_or_woken_work_and_preserves_posted_errors(self):
        data=fixture(missing=True)
        work,actor=data['work'],data['actor']
        job=factory_progress.set_progress(actor,work.pk,work.revision,True)
        self.client.force_login(actor)
        url=reverse('factory_detail',args=[work.pk])
        page=self.client.get(url)
        self.assertContains(page,'data-work-watch')
        self.assertContains(page,'work-progress.js')
        page=self.client.post(url,{'action':'unknown-action','revision':work.revision})
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'data-preserve-form="true"')
        self.assertEqual(self.drain(job),'waiting')
        self.assertNotContains(self.client.get(url),'data-work-watch')
        factory_progress.wake_waiting(work.pk)
        self.assertContains(self.client.get(url),'data-work-watch')
        work.refresh_from_db()
        factory_progress.set_progress(actor,work.pk,work.revision,False)
        self.assertNotContains(self.client.get(url),'data-work-watch')

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

    def test_explicit_invoice_release_rechecks_sources_and_queues_the_original_work(self):
        from unittest.mock import patch

        from apps.workflows import factory
        from apps.workflows.models import FactoryProgress

        data = fixture()
        work, actor = data['work'], data['actor']
        factory.run_until_wait(work.pk)
        self.client.force_login(actor)
        url = reverse('factory_detail', args=[work.pk])
        self.assertNotContains(self.client.get(url), 'Issue and send invoice')
        factory_approve_identified(data)
        work.refresh_from_db()
        self.assertContains(self.client.get(url), 'Issue and send invoice')
        request = {'action': 'release_invoice', 'revision': work.revision}

        later = timezone.now() + timedelta(days=2)
        with patch.object(timezone, 'now', return_value=later):
            self.assertContains(self.client.post(url, request), 'The invoice is not ready to issue.')
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=work.invoice).exists())

        self.assertEqual(self.client.post(url, request).status_code, 302)
        self.assertEqual(self.client.post(url, request).status_code, 302)
        job = FactoryProgress.objects.get(work=work)
        self.assertEqual(job.status, 'queued')
        self.assertFalse(InvoiceIssue.objects.filter(invoice=work.invoice).exists())
        with TemporaryDirectory() as path, override_settings(FACTORY_ADAPTERS={str(work.case_id): MockFactoryInvoiceAdapter(path)}):
            self.assertEqual(self.drain(job), 'finished')
        self.assertEqual(InvoiceIssue.objects.filter(invoice=work.invoice).count(), 1)
        self.assertEqual(InvoiceDelivery.objects.filter(invoice=work.invoice).count(), 1)
        self.assertNotContains(self.client.get(url), 'Issue and send invoice')

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
            self.client.force_login(actor)
            url = reverse('factory_invoice_recovery', args=[work.pk])
            self.assertContains(self.client.get(url), 'Recover the original operation')
            work.refresh_from_db()
            self.assertRedirects(self.client.post(url, {'action': 'reconcile', 'revision': work.revision}), url,
                                 fetch_redirect_response=False)
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

    def test_intake_does_not_block_on_work_owned_by_another_transaction(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = fixture()
        actor, work = data['actor'], data['work']
        locked, release = Event(), Event()

        def own_work():
            try:
                with transaction.atomic():
                    FactoryWork.objects.select_for_update().get(pk=work.pk)
                    locked.set()
                    release.wait(timeout=15)
            finally:
                connections.close_all()

        worker = Thread(target=own_work)
        worker.start()
        try:
            self.assertTrue(locked.wait(timeout=5))
            with self.assertRaisesMessage(ValidationError, 'busy or unavailable'):
                factory_progress.set_progress(actor, work.pk, work.revision, True, initial=True)
        finally:
            release.set()
            worker.join(timeout=15)
        requested = factory_progress.set_progress(actor, work.pk, work.revision, True)
        self.assertEqual(requested.status, 'queued')
