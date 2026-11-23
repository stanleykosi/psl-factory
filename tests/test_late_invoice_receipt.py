"""A native worker may resolve or retain an invoice while the operator is waiting."""

from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from adapters.factory_invoices import MockFactoryInvoiceAdapter
from adapters.invoices import InternalInvoiceAdapter
from apps.core.models import Audit
from apps.finance import invoice_delivery
from apps.finance.models import InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values
from apps.workflows import factory, factory_progress
from tests.billing_helpers import policy
from tests.factory_helpers import fixture
from tests.obligation_helpers import factory_approve_identified


class LateInvoiceReceiptTests(TransactionTestCase):
    def waiting_sample(self, *, pause=False, confirm=True):
        f = fixture()
        work, actor = f['work'], f['actor']
        factory.run_until_wait(work.pk)
        factory_approve_identified(f)
        self.client.force_login(actor)
        path = reverse('factory_invoice_recovery', args=[work.pk])

        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        failing = MockFactoryInvoiceAdapter(directory.name, lose_response=True)
        f['late_adapter'] = MockFactoryInvoiceAdapter(directory.name)
        factory.run_once(work.pk, adapter=failing)
        factory.run_once(work.pk, adapter=failing)
        work.refresh_from_db()
        job = InvoiceJob.objects.get(invoice=work.invoice, kind='issue')
        self.assertEqual(job.status, 'unknown')
        self.assertFalse(InvoiceIssue.objects.filter(job=job).exists())
        request = None
        if pause:
            factory_progress.set_progress(actor, work.pk, work.revision, True)
            request = factory_progress.set_progress(actor, work.pk, work.revision, False)
        self.assertContains(self.client.get(path), 'Reconcile original operation')
        self.assertRedirects(self.client.post(path, {'action': 'reconcile', 'revision': work.revision}),
                             path, fetch_redirect_response=False)
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting_effect')
        if not confirm:
            job.refresh_from_db()
            return f, work, job, None, path, request
        self.assertTrue(invoice_delivery.run_once(f['late_adapter'], job_id=job.pk, lookup_only=True))

        job.refresh_from_db()
        self.assertEqual(job.status, 'confirmed')
        receipt = InvoiceIssue.objects.get(job=job)
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting_effect')
        return f, work, job, receipt, path, request

    def test_original_receipt_recovers_same_work_and_retains_background_pause(self):
        f, work, job, receipt, path, request = self.waiting_sample(pause=True)
        reader = get_user_model().objects.create_user('late-invoice-read-only')
        Grant.objects.bulk_create([Grant(user=reader, case=work.case, action=action)
                                   for action in ('case.read', 'finance.read', 'factory.read')])
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(path), 'Check recorded invoice receipt')
        self.assertEqual(self.client.post(path, {'action': 'reconcile', 'revision': work.revision}).status_code, 403)

        self.client.force_login(f['actor'])
        self.assertContains(self.client.get(path), 'Check recorded invoice receipt')
        saved_revision, saved_budget, saved_attempts = work.revision, work.budget_used, job.attempts
        with patch.object(invoice_delivery, 'run_once', side_effect=AssertionError('A recorded receipt needs no dispatch or adapter attempt')):
            response = self.client.post(path, {'action': 'reconcile', 'revision': saved_revision})
            self.assertRedirects(response, path, fetch_redirect_response=False)
            replay = self.client.post(path, {'action': 'reconcile', 'revision': saved_revision})
            self.assertContains(replay, 'work changed')

        work.refresh_from_db()
        job.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual((work.status, work.revision, work.budget_used), ('ready', saved_revision + 1, saved_budget))
        self.assertEqual((request.status, request.requested_by_id), ('paused', f['actor'].pk))
        self.assertEqual(job.attempts, saved_attempts)
        proof = Audit.objects.get(case=work.case, action='factory.invoice_receipt_reconciled')
        self.assertEqual(proof.data, {'work': work.pk, 'job': job.pk, 'receipt': receipt.pk, 'operation': job.operation_key})
        self.assertEqual(InvoiceJob.objects.filter(invoice=job.invoice).count(), 1)
        self.assertFalse(InvoiceDelivery.objects.filter(invoice=job.invoice).exists())

    def test_changed_recipient_cannot_release_work_from_original_receipt(self):
        f, work, job, receipt, path, _ = self.waiting_sample()
        other = get_user_model().objects.create_user('late-invoice-new-destination')
        Grant.objects.create(case=work.case, user=other, action='finance.invoice.receive')
        contract = reference_values(active_component('D08.adapter_contract_ref', work.case))[0]
        policy(f['actor'], work.case, 'D08.adapter_contract_ref', dict(contract, recipient_id=other.pk))
        with patch.object(invoice_delivery, 'run_once', side_effect=AssertionError('Changed scope cannot dispatch from recovery')):
            response = self.client.post(path, {'action': 'reconcile', 'revision': work.revision})
        self.assertContains(response, 'fresh exact-packet review required')
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting_effect')
        self.assertEqual(InvoiceIssue.objects.get(job=job).pk, receipt.pk)
        self.assertEqual(InvoiceJob.objects.filter(invoice=job.invoice).count(), 1)
        self.assertFalse(Audit.objects.filter(case=work.case, action='factory.invoice_receipt_reconciled').exists())

    def test_leased_and_held_original_job_keep_work_waiting(self):
        f, work, job, _, path, _ = self.waiting_sample(confirm=False)

        def lease_first(adapter, *, case_id, job_id, lookup_only):
            self.assertEqual((case_id, job_id, lookup_only), (work.case_id, job.pk, True))
            self.assertIsNotNone(invoice_delivery.claim(case_id=case_id, job_id=job_id, lookup_only=True))
            return False

        with patch.object(invoice_delivery, 'run_once', side_effect=lease_first):
            self.assertRedirects(self.client.post(path, {'action': 'reconcile', 'revision': work.revision}),
                                 path, fetch_redirect_response=False)
        work.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual((work.status, job.status), ('waiting_effect', 'leased'))
        self.assertIn('checking the original operation', work.finding)
        invoice_delivery.finish(job.pk, job.fence, 'unknown')

        class ConflictingReceipt(InternalInvoiceAdapter):
            def lookup(self, job):
                raise ValidationError('Synthetic conflicting receipt evidence')

            def deliver(self, pk, fence):
                raise AssertionError('Invoice receipt reconciliation cannot dispatch')

        with override_settings(FACTORY_ADAPTERS={str(f['case'].pk): ConflictingReceipt()}):
            self.assertRedirects(self.client.post(path, {'action': 'reconcile', 'revision': work.revision}),
                                 path, fetch_redirect_response=False)
        work.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual((work.status, job.status), ('waiting_effect', 'held'))
        self.assertIn('needs authorised Finance recovery', work.finding)
        self.assertFalse(InvoiceIssue.objects.filter(job=job).exists())

    def test_lookup_keeps_receipt_without_overwriting_concurrent_cancel(self):
        f, work, job, _, path, _ = self.waiting_sample(confirm=False)
        run_once = invoice_delivery.run_once
        expected = work.revision

        def accept_and_cancel():
            close_old_connections()
            try:
                confirmed = run_once(f['late_adapter'], case_id=work.case_id, job_id=job.pk, lookup_only=True)
                factory.manage(f['actor'], work.pk, expected, 'cancel')
                return confirmed
            finally:
                close_old_connections()

        def overlap(*args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(accept_and_cancel).result(timeout=20)

        with patch.object(invoice_delivery, 'run_once', side_effect=overlap):
            response = self.client.post(path, {'action': 'reconcile', 'revision': expected})
        self.assertContains(response, 'work changed while checking the original receipt')
        work.refresh_from_db()
        job.refresh_from_db()
        self.assertTrue(work.cancel_requested)
        self.assertEqual((work.revision, work.status, job.status), (expected + 1, 'waiting_effect', 'confirmed'))
        self.assertTrue(InvoiceIssue.objects.filter(job=job).exists())
        self.assertFalse(InvoiceDelivery.objects.filter(invoice=job.invoice).exists())

    def test_lookup_that_confirms_while_destination_changes_records_receipt_but_keeps_work_waiting(self):
        f, work, job, _, path, _ = self.waiting_sample(confirm=False)
        other = get_user_model().objects.create_user('invoice-destination-during-lookup')
        Grant.objects.create(case=work.case, user=other, action='finance.invoice.receive')
        contract = reference_values(active_component('D08.adapter_contract_ref', work.case))[0]
        run_once = invoice_delivery.run_once

        def settle_before_scope_check(*args, **kwargs):
            confirmed = run_once(f['late_adapter'], case_id=work.case_id, job_id=job.pk, lookup_only=True)
            policy(f['actor'], work.case, 'D08.adapter_contract_ref', dict(contract, recipient_id=other.pk))
            return confirmed

        with patch.object(invoice_delivery, 'run_once', side_effect=settle_before_scope_check):
            self.assertRedirects(self.client.post(path, {'action': 'reconcile', 'revision': work.revision}),
                                 path, fetch_redirect_response=False)
        work.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual((work.status, job.status), ('waiting_effect', 'confirmed'))
        self.assertIn('verify the original receipt and current scope', work.finding)
        self.assertTrue(InvoiceIssue.objects.filter(job=job).exists())
        self.assertEqual(InvoiceJob.objects.filter(invoice=job.invoice).count(), 1)
        self.assertFalse(Audit.objects.filter(case=work.case, action='factory.invoice_receipt_reconciled').exists())
