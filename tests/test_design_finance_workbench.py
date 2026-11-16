from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance import cash, receivables
from apps.finance.models import ReceivableSnapshot
from apps.identity.models import Grant
from apps.policy.services import active_component, transition
from tests import settlement_helpers as finance
from tests.billing_helpers import stage_policy
from tests.helpers import rev, setup_case, signed
from tests.obligation_helpers import issue_identified


class DesignFinanceWorkbenchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, cls.coverage, cls.preparation, cls.evidence = finance.fixture()

    def test_project_money_displays_exact_signed_stages_and_unconfigured_terms(self):
        proof = signed(self.actor, self.case)['signature']
        stage_policy(self.actor, self.case, self.coverage, proof)
        self.client.force_login(self.actor)
        url = reverse('design_project_tab', args=[self.case.pk, 'money'])
        page = self.client.get(url, {'figure': 'signed_sow'})
        self.assertContains(page, 'Signed agreement · recorded signature')
        self.assertContains(page, 'Due 2026-11-01')
        self.assertContains(page, 'Due date unknown')
        self.assertEqual(page.context['money']['selected']['amount'], '30.00')
        self.assertEqual(self.client.get(url, {'figure': 'uat'}).status_code, 404)
        rule = active_component('D12.stage_terms', self.case)
        transition(self.actor, rule.pk, 'revoked')
        missing = self.client.get(url)
        self.assertContains(missing, 'Signed agreement')
        self.assertContains(missing, 'User acceptance testing')
        self.assertIsNone(missing.context['money']['rows'][0]['amount'])

    def test_project_money_separates_invoice_and_payment_and_resolves_exact_figure(self):
        self.client.force_login(self.actor)
        url = reverse('design_project_tab', args=[self.case.pk, 'money'])
        invoice = finance.draft(self.actor, self.case, self.preparation)
        figure = {'figure': f'invoice-{invoice.pk}'}
        page = self.client.get(url, figure)
        self.assertContains(page, 'Where NGN')
        self.assertContains(page, 'Recorded billing preparation')
        self.assertContains(page, 'Unknown')
        self.assertNotContains(page, 'Applied NGN')
        issue = issue_identified(self.actor, self.case, invoice, self.evidence)
        receipt, lot = finance.receipt(self.actor, self.case)
        finance.assign(self.actor, self.case, receipt, self.coverage, self.evidence)
        finance.allocate(self.actor, self.case, lot, issue, '25.00', self.evidence)
        page = self.client.get(url, figure)
        [line] = page.context['money']['selected']['invoices']
        self.assertEqual(line['paid'], Decimal('25.00'))
        self.assertEqual(line['owed'], invoice.amount - Decimal('25.00'))
        self.assertContains(page, 'Applied receipt tx-cash-1')
        self.assertEqual(self.client.get(url, {'figure': 'invoice-900000000'}).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action='finance.read').update(active=False)
        self.assertEqual(self.client.get(url, figure).status_code, 403)

    def test_client_details_show_captured_coverage_and_only_verified_invoice_amounts(self):
        self.client.force_login(self.actor)
        url = reverse('design_client_project', args=[self.case.pk])
        invoice = finance.draft(self.actor, self.case, self.preparation)
        page = self.client.get(url)
        self.assertNotContains(page, 'Design client project')
        self.assertContains(page, 'Billing coverage')
        self.assertContains(page, self.coverage.contract)
        self.assertContains(page, 'Amounts are unknown')

        issue = issue_identified(self.actor, self.case, invoice, self.evidence)
        receipt, lot = finance.receipt(self.actor, self.case)
        finance.assign(self.actor, self.case, receipt, self.coverage, self.evidence)
        finance.allocate(self.actor, self.case, lot, issue, '25.00', self.evidence)
        page = self.client.get(url)
        self.assertContains(page, 'Applied receipts')
        [group] = page.context['billing']['amounts']
        self.assertEqual(group['invoiced'], invoice.amount)
        self.assertEqual(group['applied'], Decimal('25.00'))
        self.assertEqual(group['owed'], invoice.amount - Decimal('25.00'))

        cash.reverse(self.actor, self.case.pk, 'lot', lot.pk, 'Finance', self.evidence['cash_correction'].pk,
                     'Synthetic reversal', rev(self.case))
        [group] = self.client.get(url).context['billing']['amounts']
        self.assertEqual(group['owed'], invoice.amount)
        Grant.objects.filter(case=self.case, user=self.actor, action='finance.read').update(active=False)
        self.assertNotContains(self.client.get(url), self.coverage.contract)

    def test_company_month_uses_verified_receipt_dates_and_current_grants(self):
        self.client.force_login(self.actor)
        date = timezone.localtime().replace(day=15, hour=12, minute=0, second=0, microsecond=0) - timedelta(days=32)
        finance.receipt(self.actor, self.case, amount='72.00', received_at=date.isoformat())
        finance.receipt(self.actor, self.case, amount='99.00', received_at=date.isoformat(), verify=False, ref='unproven')
        url = reverse('design_company_month_end')
        unauthorized, _ = setup_case(username='outside-month-end')
        page = self.client.get(url, {'month': date.strftime('%Y-%m')})
        self.assertContains(page, 'Verified cash received')
        [report] = page.context['report']
        self.assertEqual(report['cash'], [('NGN', 'gross_including_tax', Decimal('72.00'))])
        self.assertEqual(page.context['coverage'], {'workspaces': 1, 'reviewed': 0, 'captured': 0, 'cash': 1})
        self.assertNotContains(self.client.get(url, {'month': '0000-01'}), '72.00000000')
        self.client.force_login(unauthorized)
        self.assertNotContains(self.client.get(url, {'month': date.strftime('%Y-%m')}), '72.00000000')

    def test_capture_shows_exact_reconciliation_and_holds_unauthorised_or_stale_writes(self):
        self.client.force_login(self.actor)
        month = timezone.localdate().strftime('%Y-%m')
        url = reverse('design_project_tab', args=[self.case.pk, 'month-end'])
        capture = reverse('design_capture_month_end_receivables', args=[self.case.pk])
        invoice = finance.draft(self.actor, self.case, self.preparation)
        issue = issue_identified(self.actor, self.case, invoice, self.evidence)
        receipt, lot = finance.receipt(self.actor, self.case)
        finance.assign(self.actor, self.case, receipt, self.coverage, self.evidence)
        finance.allocate(self.actor, self.case, lot, issue, '25.00', self.evidence)
        finance.receipt(self.actor, self.case, verify=False, ref='reported-only')
        transition(self.actor, active_component('D14.allocation_rule_ref', self.case).pk, 'revoked')
        self.assertContains(self.client.get(url), 'No receivables capture in this month')
        self.assertEqual(self.client.get(capture).status_code, 405)
        data = {'month': month, 'revision': rev(self.case), 'return_to': 'workspace'}
        self.assertRedirects(self.client.post(capture, data), url + '?month=' + month)
        row = ReceivableSnapshot.objects.get(case=self.case)
        page = self.client.get(url)
        self.assertContains(page, 'Captured on the selected date')
        self.assertContains(page, 'Reported cash awaiting verification')
        self.assertContains(page, reverse('finance_corrections', args=[self.case.pk]))
        [group] = page.context['close']['receivables']['groups']
        self.assertEqual(Decimal(group['receivable']), invoice.amount - Decimal('25.00'))
        self.assertEqual(Decimal(group['unallocated_cash']), Decimal('25.00'))
        self.assertIsNone(group['overdue'])
        self.client.post(capture, data)
        self.assertEqual(ReceivableSnapshot.objects.filter(case=self.case).count(), 1)

        Grant.objects.filter(case=self.case, user=self.actor, action__in=['finance.receivables', 'payroll.read']).update(active=False)
        page = self.client.get(url)
        self.assertContains(page, 'Capture ' + str(row.pk))
        self.assertNotContains(page, 'Capture today’s receivables')
        self.assertNotContains(page, 'Restricted payroll and staff costs')
        self.assertEqual(self.client.post(capture, dict(data, revision=rev(self.case))).status_code, 403)
        other, _ = setup_case(username='outside-captured-close')
        self.client.force_login(other)
        self.assertEqual(self.client.post(capture, data).status_code, 404)
        self.assertNotContains(self.client.get(reverse('design_company_month_end')), 'Capture ' + str(row.pk))

    def test_month_end_preserves_actual_earlier_and_exact_captures(self):
        self.client.force_login(self.actor)
        today = timezone.localdate()
        last = today.replace(day=1) - timedelta(days=1)
        month = last.strftime('%Y-%m')
        url = reverse('design_company_month_end')
        invoice = finance.draft(self.actor, self.case, self.preparation)
        issue = issue_identified(self.actor, self.case, invoice, self.evidence)
        with patch('apps.finance.receivables.timezone.localdate', return_value=last - timedelta(days=2)):
            earlier = receivables.snapshot(self.actor, self.case.pk, timezone.localdate(), rev(self.case))
        page = self.client.get(url, {'month': month})
        self.assertContains(page, 'Earlier capture in this month')
        self.assertContains(page, 'Capture ' + str(earlier.pk))
        self.assertNotContains(page, 'Capture today’s receivables')
        self.client.post(reverse('design_capture_month_end_receivables', args=[self.case.pk]), {'month': month, 'revision': rev(self.case)})
        self.assertEqual(ReceivableSnapshot.objects.filter(case=self.case).count(), 1)
        with patch('apps.finance.receivables.timezone.localdate', return_value=last):
            exact = receivables.snapshot(self.actor, self.case.pk, last, rev(self.case))
        receipt, lot = finance.receipt(self.actor, self.case)
        finance.assign(self.actor, self.case, receipt, self.coverage, self.evidence)
        finance.allocate(self.actor, self.case, lot, issue, '25.00', self.evidence)
        page = self.client.get(url, {'month': month})
        self.assertContains(page, 'Captured on the selected date')
        [entry] = page.context['report']
        self.assertEqual(page.context['coverage']['captured'], 1)
        self.assertEqual(entry['receivables']['pk'], exact.pk)
        self.assertEqual(Decimal(entry['receivables']['groups'][0]['receivable']), invoice.amount)
        future = date(today.year + 1, 1, 1)
        self.assertContains(self.client.get(url, {'month': future.strftime('%Y-%m')}), 'Future month')
