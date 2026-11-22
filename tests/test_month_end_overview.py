"""Month-end shows a bounded authorized work read and separate known cash totals."""

import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.finance import cash
from apps.finance.month_end import cash_in_month
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values
from apps.workflows import factory
from tests import factory_helpers, settlement_helpers
from tests.billing_helpers import evidence, policy
from tests.helpers import rev


class MonthEndOverviewTests(TestCase):
    def test_api_capture_current_as_of_and_read_company_close(self):
        actor, case, *_ = settlement_helpers.fixture()
        self.client.force_login(actor)
        month = timezone.localdate().strftime('%Y-%m')
        initial = self.client.get('/api/v1/month-end', {'month': month}).json()
        self.assertEqual(initial['workspaces'][0]['workspace']['case_id'], str(case.pk))
        url = f'/api/v1/projects/{case.pk}/month-end/receivables'
        body = {'month': month, 'revision': rev(case)}
        recorded = self.client.post(url, body, content_type='application/json')
        self.assertEqual(recorded.status_code, 201, recorded.content)
        display = self.client.get(f'/api/v1/projects/{case.pk}/month-end', {'month': month}).json()
        self.assertEqual(display['receivables']['snapshot_id'], recorded.json()['id'])
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 409)
        Grant.objects.filter(case=case, user=actor, action='finance.read').update(active=False)
        self.assertEqual(self.client.get('/api/v1/month-end', {'month': month}).json()['workspaces'], [])

    def test_current_leased_and_waiting_work_links_feed_bounded_counts(self):
        first = factory_helpers.fixture(username='month-close-operator')
        other = factory_helpers.fixture(username='month-close-other-operator')
        actor, work = first['actor'], first['work']
        factory.run_until_wait(work.pk)
        self.client.force_login(actor)
        waiting_url = reverse('factory_detail', args=[work.pk])
        other_url = reverse('factory_detail', args=[other['work'].pk])
        close_url = reverse('design_company_month_end')
        month = timezone.localdate().strftime('%Y-%m')

        self.assertIsNotNone(factory.claim(work.pk))
        read_count = Audit.objects.count()
        overview = self.client.get(close_url, {'month': month})
        self.assertContains(overview, 'Month-end checklist')
        self.assertContains(overview, 'Processing')
        self.assertContains(overview, waiting_url)
        self.assertNotContains(overview, other_url)
        self.assertEqual(overview.context['overview']['counts'], {'done': 0, 'waiting': 0, 'in_progress': 1, 'stopped': 0})
        self.assertEqual(Audit.objects.count(), read_count)

        Grant.objects.bulk_create([Grant(case=other['case'], user=actor, action=action)
                                   for action in ('case.read', 'finance.read', 'factory.read')])
        expanded = self.client.get(close_url, {'month': month})
        self.assertContains(expanded, other_url)
        self.assertEqual(expanded.context['overview']['counts']['waiting'], 1)
        with patch('apps.finance.month_end.WORK_LIMIT', 1):
            limited = self.client.get(close_url, {'month': month})
        self.assertEqual(len(limited.context['overview']['work']), 1)
        self.assertEqual(sum(limited.context['overview']['counts'].values()), 1)
        self.assertContains(limited, 'Showing 1 work item.')

        previous = timezone.localdate().replace(day=1) - timedelta(days=1)
        other_month = self.client.get(close_url, {'month': previous.strftime('%Y-%m')})
        self.assertNotContains(other_month, waiting_url)
        self.assertNotContains(other_month, other_url)
        Grant.objects.filter(case=first['case'], user=actor, action='factory.read').update(active=False)
        workspace = self.client.get(reverse('design_project_tab', args=[first['case'].pk, 'month-end']), {'month': month})
        self.assertNotContains(workspace, waiting_url)
        self.assertEqual(workspace.context['overview']['work'], [])

    def test_known_verified_cash_keeps_currency_basis_and_unknown_coverage(self):
        actor, case, _, _, _ = settlement_helpers.fixture()
        self.client.force_login(actor)
        at = timezone.now() - timedelta(minutes=5)
        month = timezone.localtime(at).strftime('%Y-%m')
        settlement_helpers.receipt(actor, case, amount='72.00', ref='month-gross-ngn', received_at=at.isoformat())
        settlement_helpers.receipt(actor, case, amount='777.00', ref='month-reported-only', received_at=at.isoformat(), verify=False)
        source = reference_values(active_component('D14.receipt_verification_source_ref', case))[0]

        def verified(ref, amount, currency):
            policy(actor, case, 'D14.receipt_verification_source_ref', dict(source, currency=currency))
            value = {'source': source['source'], 'transaction_ref': ref, 'customer': 'sample-client',
                     'amount': amount, 'currency': currency, 'amount_basis': source['amount_basis'], 'received_at': at.isoformat()}
            report = evidence(actor, case, 'cash_report', json.dumps(value))
            receipt = cash.report(actor, case.pk, report.pk, rev(case))
            proof = evidence(actor, case, 'cash_verification', json.dumps(value))
            cash.verify(actor, case.pk, receipt.pk, 'Finance', proof.pk, rev(case))

        verified('month-gross-usd', '9.00', 'USD')
        page = self.client.get(reverse('design_company_month_end'), {'month': month})
        groups = page.context['overview']['cash']['groups']
        self.assertEqual({(group['currency'], group['basis'], group['amount']) for group in groups},
                         {('NGN', 'gross_including_tax', Decimal('72.00')), ('USD', 'gross_including_tax', Decimal('9.00'))})
        # The native verification contract admits gross receipts only. Test the
        # aggregation boundary separately to ensure supplied bases stay distinct.
        recorded = page.context['report'][0]
        by_basis = cash_in_month([dict(recorded, cash=[*recorded['cash'], ('NGN', 'net_excluding_tax', Decimal('11.00'))])])
        self.assertCountEqual([(row['basis'], row['amount']) for row in by_basis['groups'] if row['currency'] == 'NGN'],
                              [('gross_including_tax', Decimal('72.00')), ('net_excluding_tax', Decimal('11.00'))])
        self.assertContains(page, 'NGN 72.00')
        self.assertContains(page, 'USD 9.00')
        self.assertContains(page, 'Remaining cash coverage is')
        self.assertContains(page, 'Unknown')
        self.assertNotContains(page, '777.00')

        other = Case.objects.create(tenant='separate-close-organization', kind='project',
                                    title='SAMPLE separate Finance workspace', synthetic=True)
        Grant.objects.bulk_create([Grant(case=other, user=actor, action=action) for action in dict.fromkeys(ACTIONS)])
        settlement_helpers.configured(actor, other)
        settlement_helpers.receipt(actor, other, amount='72.00', ref='month-gross-ngn', received_at=at.isoformat())
        mixed = self.client.get(reverse('design_company_month_end'), {'month': month})
        gross_ngn = [group for group in mixed.context['overview']['cash']['groups']
                     if (group['currency'], group['basis']) == ('NGN', 'gross_including_tax')]
        self.assertCountEqual([(group['workspace_id'], group['amount']) for group in gross_ngn],
                              [(str(case.pk), Decimal('72.00')), (str(other.pk), Decimal('72.00'))])
