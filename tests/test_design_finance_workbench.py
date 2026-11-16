from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance import cash
from apps.identity.models import Grant
from tests import settlement_helpers as finance
from tests.helpers import rev, setup_case
from tests.obligation_helpers import issue_identified


class DesignFinanceWorkbenchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, cls.coverage, cls.preparation, cls.evidence = finance.fixture()

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
        self.assertNotContains(self.client.get(url, {'month': '0000-01'}), '72.00000000')
        self.client.force_login(unauthorized)
        self.assertNotContains(self.client.get(url, {'month': date.strftime('%Y-%m')}), '72.00000000')
