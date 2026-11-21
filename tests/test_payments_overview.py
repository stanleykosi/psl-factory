from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.models import Case
from apps.finance import invoice_delivery, invoices
from apps.finance.models import Invoice, InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.models import Grant
from apps.policy.services import active_component, transition
from tests import correction_helpers, settlement_helpers
from tests.helpers import rev
from tests.obligation_helpers import identified
from tests.railway_signed_milestone_payment_seed import PART_PAYMENT, REFERENCE, SIGNED_AMOUNT, TRIAL, prepare
from tests.test_fixed_contract_bridge import FixedContractFixture


class PaymentsOverviewTests(TestCase):
    def test_trial_reads_exact_part_payment_and_only_current_reviewed_ageing(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user(TRIAL)
        prepared = prepare()
        invoice = Invoice.objects.get(pk=prepared['invoice'])
        owner = get_user_model().objects.get(pk=prepared['preparer'])
        Grant.objects.bulk_create([Grant(case=invoice.case, user=trial, action=action)
                                   for action in ('finance.reminder.read', 'finance.cash.record', 'evidence.add')])
        self.client.force_login(trial)
        url = reverse('design_payments')
        query = {'q': REFERENCE, 'state': 'part-paid'}
        after_due = invoice.due_date + timedelta(days=3)
        with patch('apps.finance.payments_overview.timezone.localdate', return_value=after_due):
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(url, query)
            self.assertLess(len(captured), 130)
        self.assertContains(response, 'Bank data through')
        self.assertContains(response, 'Total received this month')
        self.assertContains(response, '3 days')
        self.assertContains(response, 'Record a payment received')
        [row] = response.context['rows']
        self.assertEqual((row['face'], row['paid'], row['owed']), (SIGNED_AMOUNT, PART_PAYMENT, Decimal('22.50')))
        self.assertEqual(row['state'], 'Part paid')
        self.assertEqual(row['reminder'], reverse('design_payment_reminder', args=[invoice.case_id, prepared['issue']]))
        self.assertEqual(row['record_payment'], reverse('finance_record_payment', args=[invoice.case_id, prepared['issue']]))
        self.assertTrue(row['records'].endswith(f'#invoice-{invoice.pk}'))
        table = self.client.get(reverse('finance_settlement', args=[invoice.case_id]))
        self.assertContains(table, f'id="invoice-{invoice.pk}"')
        self.assertContains(table, 'id="record-payment"')
        selected = active_component('D14.allocation_rule_ref', invoice.case)
        transition(owner, selected.pk, 'revoked')
        after = self.client.get(url, query)
        self.assertIsNone(after.context['rows'][0]['age_days'])
        self.assertEqual(after.context['rows'][0]['owed'], Decimal('22.50'))
        self.assertFalse(InvoiceDelivery.objects.filter(invoice=invoice).exists())

    def test_ungranted_workspace_and_unconfirmed_issue_are_distinguished(self):
        owner, case, _, preparation, proofs = settlement_helpers.fixture()
        invoice = settlement_helpers.draft(owner, case, preparation, 'SAMPLE-AWAITING-PAYMENT-PROOF')
        identified(owner, case, invoice)
        settlement_helpers.approve(owner, case, invoice, proofs)
        job = invoices.reserve(owner, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
        _, fence = invoice_delivery.claim(case_id=case.pk, job_id=job.pk)
        invoice_delivery.finish(job.pk, fence, 'unknown')
        url = reverse('design_payments')
        stranger = get_user_model().objects.create_user('no-finance-reader')
        Grant.objects.create(case=case, user=stranger, action='case.read')
        self.client.force_login(stranger)
        self.assertNotContains(self.client.get(url), invoice.reference, status_code=403)
        visible = Case.objects.create(title='SAMPLE other visible Finance workspace', tenant=case.tenant, kind='project', synthetic=True)
        Grant.objects.bulk_create(Grant(case=visible, user=stranger, action=action) for action in ('case.read', 'finance.read'))
        inaccessible = self.client.get(url, {'q': invoice.reference})
        self.assertContains(inaccessible, 'No available invoice records match this search.')
        self.assertEqual(inaccessible.context['search'], invoice.reference)
        self.assertEqual(inaccessible.context['rows'], [])
        self.assertEqual(inaccessible.context['totals'], [])
        self.assertIsNone(inaccessible.context['next_url'])
        self.assertNotContains(inaccessible, reverse('finance_settlement', args=[case.pk]))
        self.client.force_login(owner)
        uncertain = self.client.get(url, {'state': 'unknown'})
        self.assertContains(uncertain, invoice.reference)
        self.assertContains(uncertain, 'The invoice issue is still being verified.')
        [row] = uncertain.context['rows']
        for key in ('face', 'paid', 'owed', 'age_days'):
            self.assertIsNone(row[key])
        self.assertIsNone(uncertain.context['totals'][0]['owed'])
        self.assertNotContains(self.client.get(url, {'state': 'issued'}), invoice.reference)
        self.assertFalse(InvoiceIssue.objects.filter(invoice=invoice).exists())
        self.assertEqual(InvoiceJob.objects.get(pk=job.pk).status, 'unknown')

    def test_only_accepted_corrections_change_the_recorded_face(self):
        owner, case, coverage, issue, proofs = correction_helpers.fixture(identity=True)
        corrected = correction_helpers.note(owner, case, issue, proofs, amount='5.00')
        correction_helpers.apply(owner, case, corrected, proofs)
        receipt, lot = settlement_helpers.receipt(owner, case)
        settlement_helpers.assign(owner, case, receipt, coverage, proofs)
        settlement_helpers.allocate(owner, case, lot, issue, '20.00', proofs)
        self.client.force_login(owner)
        row = self.client.get(reverse('design_payments')).context['rows'][0]
        self.assertEqual((row['face'], row['paid'], row['owed']),
                         (issue.invoice.amount - Decimal('5'), Decimal('20'), issue.invoice.amount - Decimal('25')))


class FixedPaymentOverviewTests(FixedContractFixture, TestCase):
    def test_fixed_invoice_needs_existing_exact_source_access_to_discover_or_search(self):
        _, _, preparation = self.prepared()
        invoice, _ = self.issued(preparation, identity=True)
        reader = get_user_model().objects.create_user('payment-fixed-case-reader')
        Grant.objects.bulk_create([Grant(user=reader, case=self.c, action=action)
                                   for action in ('case.read', 'finance.read')])
        url = reverse('design_payments')
        self.client.force_login(reader)
        missing = self.client.get(url, {'q': invoice.reference})
        self.assertEqual(missing.context['rows'], [])
        self.assertEqual(missing.context['totals'], [])
        self.assertIsNone(missing.context['next_url'])
        self.client.force_login(self.a)
        page = self.client.get(url, {'q': invoice.reference})
        self.assertContains(page, invoice.reference)
        self.assertEqual(page.context['rows'][0]['face'], invoice.amount)
