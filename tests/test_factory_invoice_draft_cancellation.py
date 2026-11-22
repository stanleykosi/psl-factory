from concurrent.futures import ThreadPoolExecutor
from datetime import date
from queue import Queue
from threading import Event
from time import monotonic

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.models import Audit
from apps.finance import invoices
from apps.finance.models import Invoice, InvoiceDelivery, InvoiceIssue, InvoiceJob, InvoiceReview, UsageIntakeAcceptance
from apps.identity.models import Grant
from apps.workflows import factory
from apps.workflows.factory_invoice_cancellation import DraftStop
from apps.workflows.models import HumanTask, TaskEvent
from tests.billing_helpers import prepare
from tests.helpers import rev
from tests.obligation_helpers import factory_approve_identified, issue_identified
from tests.test_factory_invoice_intake import prepared, start


class InvoiceDraftCancellationTests(TestCase):
    reason = 'This duplicate can be stopped before sending.'

    def setUp(self):
        self.fixture = prepared()
        self.actor, self.case = self.fixture['actor'], self.fixture['case']
        self.actor.first_name = 'Sample'
        self.actor.last_name = 'Finance reviewer'
        self.actor.save(update_fields=['first_name', 'last_name'])
        self.work = start(self.fixture)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.draft = self.work.invoice
        self.path = reverse('factory_invoice_recovery', args=[self.work.pk])
        self.client.force_login(self.actor)

    def stop(self, **override):
        values = {'action': 'stop_invoice_draft', 'revision': self.work.revision,
                  'case_revision': rev(self.case), 'reason': self.reason}
        return self.client.post(self.path, {**values, **override})

    def issue(self, preparation, reference):
        invoice = invoices.draft(self.actor, self.case.pk, preparation.pk, reference,
                                 date(2026, 11, 20), rev(self.case))
        issue = issue_identified(self.actor, self.case, invoice, {'invoice_review': self.fixture['proof']})
        return invoice, issue

    def test_same_obligation_issued_invoice_is_linked_with_exact_cancellation_history(self):
        invoice, issue = self.issue(self.fixture['prep'], 'VALID-ISSUED-INVOICE')
        work_request = self.work.request
        issued = list(InvoiceIssue.objects.values())
        self.assertContains(self.client.get(self.path), 'Stop this invoice draft')
        self.assertContains(self.client.get(self.path), 'VALID-ISSUED-INVOICE')

        api = f'/api/v1/work/{self.work.pk}/invoice-draft-stop'
        controls = self.client.get(api).json()
        self.assertEqual(controls['existing_issue']['id'], invoice.pk)
        body = {'expected_revision': controls['revision'], 'case_revision': controls['case_revision'],
                'reason': self.reason, 'existing_invoice_id': invoice.pk}
        response = self.client.post(api, body, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.client.post(api, body, content_type='application/json').status_code, 409)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'cancelled')
        self.assertEqual(self.work.request, work_request)
        self.assertEqual(self.work.invoice_id, self.draft.pk)
        event = invoices.draft_stop_history(self.draft).get()
        self.assertEqual(event.actor_id, self.actor.pk)
        self.assertEqual(event.data['existing_issue'], issue.pk)
        self.assertEqual(event.data['reason'], self.reason)
        self.assertFalse(HumanTask.objects.filter(factory_key__startswith=f'factory:{self.work.pk}:', status='open').exists())
        self.assertTrue(TaskEvent.objects.filter(task__factory_key__startswith=f'factory:{self.work.pk}:',
                                                 action='factory.wait_cancelled').exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=self.draft).exists())
        self.assertFalse(InvoiceDelivery.objects.filter(invoice=self.draft).exists())
        self.assertEqual(list(InvoiceIssue.objects.values()), issued)
        self.assertEqual(Invoice.objects.filter(case=self.case).count(), 2)

        page = self.client.get(self.path)
        self.assertContains(page, self.reason)
        self.assertContains(page, 'Sample Finance reviewer')
        self.assertContains(page, 'Never sent')
        self.assertContains(page, 'Open VALID-ISSUED-INVOICE')
        self.assertNotContains(page, 'Review the current invoice draft')
        exact = self.client.get(self.path, {'existing_invoice': invoice.pk})
        self.assertContains(exact, 'Recorded issued invoice for this billing obligation.')
        wrong = self.client.get(self.path, {'existing_invoice': self.draft.pk})
        self.assertNotContains(wrong, 'Recorded issued invoice for this billing obligation.')
        self.assertEqual(invoices.draft_stop_history(self.draft).count(), 1)
        recorded = self.client.get(api).json()
        self.assertFalse(recorded['can_stop'])
        self.assertEqual(recorded['recorded_stop']['existing_issue']['id'], invoice.pk)

    def test_stale_blank_unissued_and_unrelated_links_cannot_stop_draft(self):
        later_draft = invoices.draft(self.actor, self.case.pk, self.fixture['prep'].pk,
                                     'UNISSUED-ALTERNATIVE', date(2026, 11, 20), rev(self.case))
        accepted = UsageIntakeAcceptance.objects.get(source_id=self.fixture['receipt'].source_id)
        unrelated = accepted.partitions.exclude(coverage=self.fixture['coverage']).get()
        preparation = prepare(self.actor, self.case, unrelated.coverage, u=unrelated)
        wrong, _ = self.issue(preparation, 'OTHER-ISSUED-OBLIGATION')

        self.assertContains(self.stop(case_revision=rev(self.case) - 1), 'Stale revision')
        self.assertContains(self.stop(revision=self.work.revision - 1), 'work changed')
        self.assertContains(self.stop(reason='  '), 'Enter a reason')
        self.assertContains(self.stop(existing_invoice=later_draft.pk), 'Choose the recorded issued invoice')
        self.assertContains(self.stop(existing_invoice=wrong.pk), 'Choose the recorded issued invoice')
        self.assertNotContains(self.client.get(self.path), 'OTHER-ISSUED-OBLIGATION')

        reader = get_user_model().objects.create_user(username='invoice-cancel-read-only')
        for action in ('case.read', 'factory.read', 'finance.read'):
            Grant.objects.create(user=reader, case=self.case, action=action)
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(self.path), 'Stop this invoice draft')
        self.assertEqual(self.stop().status_code, 403)

        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'waiting')
        self.assertFalse(invoices.draft_stop_history(self.draft).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=self.draft).exists())

    def test_unlinked_stop_fences_even_an_approved_draft_and_retains_decision(self):
        review = factory_approve_identified(self.fixture)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'ready')
        self.assertRedirects(self.stop(), self.path)
        self.assertContains(self.client.get(self.path), 'Never sent')
        self.assertNotContains(self.client.get(self.path), 'Existing issued invoice')
        with self.assertRaisesMessage(ValidationError, 'This exact invoice draft was cancelled before issuance'):
            invoices.reserve(self.actor, self.case.pk, self.draft.pk, 'issue', 'Finance', rev(self.case))
        self.assertTrue(InvoiceReview.objects.filter(pk=review.pk).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=self.draft).exists())

    def test_exact_reserved_operation_stays_with_original_recovery(self):
        factory_approve_identified(self.fixture)
        self.work.refresh_from_db()
        job = invoices.reserve(self.actor, self.case.pk, self.draft.pk, 'issue', 'Finance', rev(self.case),
                               factory_work_id=self.work.pk)
        page = self.client.get(self.path)
        self.assertNotContains(page, 'Stop this invoice draft')
        self.assertContains(self.stop(), 'check its original operations')
        self.work.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')
        self.assertFalse(self.work.cancel_requested)
        self.assertFalse(invoices.draft_stop_history(self.draft).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice=self.draft).exists())

    def test_database_rejects_unstopped_audit_and_effects_for_exact_stopped_draft(self):
        issue_invoice, issue = self.issue(self.fixture['prep'], 'PRIOR-EXACT-ISSUE')
        data = {'schema': invoices.DRAFT_STOP_SCHEMA, 'work': self.work.pk,
                'invoice': self.draft.pk, 'invoice_sha256': self.draft.sha256, 'reason': self.reason,
                'existing_invoice': issue_invoice.pk, 'existing_issue': issue.pk}
        with self.assertRaisesMessage(DatabaseError, 'Exact stopped invoice draft'), transaction.atomic():
            Audit.objects.create(case=self.case, actor=self.actor, action='factory.cancel', data=data)

        self.assertRedirects(self.stop(existing_invoice=issue_invoice.pk), self.path)
        with self.assertRaisesMessage(DatabaseError, 'Exact stopped invoice draft'), transaction.atomic():
            Audit.objects.create(case=self.case, actor=self.actor, action='factory.cancel', data=data)
        with self.assertRaisesMessage(DatabaseError, 'Exact invoice draft was cancelled'), transaction.atomic():
            InvoiceDelivery.objects.create(invoice=self.draft, job=issue.job, recipient=self.actor,
                                           payload=self.draft.payload, sha256=self.draft.sha256)
        self.assertEqual(invoices.draft_stop_history(self.draft).count(), 1)
        self.assertEqual(InvoiceIssue.objects.get(pk=issue.pk).invoice_id, issue_invoice.pk)


class InvoiceDraftCancellationConcurrencyTests(TransactionTestCase):
    def test_competing_database_reservation_waits_and_cannot_cross_original_stop(self):
        fixture = prepared()
        actor, case = fixture['actor'], fixture['case']
        work = start(fixture)
        factory.run_until_wait(work.pk)
        factory_approve_identified(fixture)
        work.refresh_from_db()
        draft = work.invoice
        with transaction.atomic():
            _, intent, pending = invoices.guard_reserve(actor, case, draft.pk, 'issue', 'Finance', work.pk)
        self.assertIsNone(pending)
        command = DraftStop(rev(case), 'The duplicate must stay unsent.', None)
        written, commit = Event(), Event()
        backend = Queue()

        def stop():
            close_old_connections()
            try:
                with transaction.atomic():
                    factory.manage(actor, work.pk, work.revision, 'cancel', draft_stop=command)
                    written.set()
                    if not commit.wait(15):
                        raise RuntimeError('Timed out waiting to finish the exact cancellation transaction.')
            finally:
                close_old_connections()

        def reserve():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    backend.put(cursor.fetchone()[0])
                return InvoiceJob.objects.create(
                    invoice=draft, kind='issue', actor=actor, intent=intent,
                    operation_key=f'invoice:{draft.pk}:issue:g1',
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            stopped = pool.submit(stop)
            try:
                self.assertTrue(written.wait(10))
                reserved = pool.submit(reserve)
                pid = backend.get(timeout=5)
                expires = monotonic() + 5
                with connection.cursor() as cursor:
                    while monotonic() < expires:
                        cursor.execute('SELECT cardinality(pg_blocking_pids(%s))', [pid])
                        if cursor.fetchone()[0]:
                            break
                        Event().wait(.05)
                    else:
                        self.fail('The competing reservation did not wait for the draft stop.')
            finally:
                commit.set()
            stopped.result(timeout=10)
            with self.assertRaisesMessage(DatabaseError, 'Exact invoice draft was cancelled'):
                reserved.result(timeout=10)

        self.assertEqual(invoices.draft_stop_history(draft).count(), 1)
        self.assertFalse(InvoiceJob.objects.filter(invoice=draft).exists())
