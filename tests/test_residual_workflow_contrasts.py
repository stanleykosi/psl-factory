"""Bounded residual contrasts; synthetic policy, native services, no external provider."""
import copy
import json
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit
from apps.finance import cash, forecast
from apps.finance.models import CashAllocation, CashReversal, InvoiceDelivery, ForecastMatch
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.pmo.models import EscalationDecision, EscalationSignal
from apps.pmo import escalations as native
from apps.workflows import factory_escalation as escalation
from tests.helpers import rev, setup_case
from tests.test_settlement import SettlementTests
from tests.test_project_view import ProjectViewTests
from tests.test_factory_escalation import FactoryEscalationTests
from tests.test_escalations import profile, clocks
from tests.settlement_helpers import draft, issue, receipt, assign, allocate
from tests.billing_helpers import usage, prepare, FIXTURE as USAGE_FIXTURE
from tests.forecast_helpers import fixture, payload, run, actual, match, evidence
from apps.agents.receivables import investigate


class AmbiguousReceiptContrast(SettlementTests):
    def test_two_real_invoice_candidates_require_choice_and_share_reversible_capacity(self):
        first = issue(self.a, self.c, draft(self.a, self.c, self.p), self.e)
        body = json.loads(USAGE_FIXTURE.read_text())['csv'].replace('tx-example-1', 'tx-example-2')
        preparation = prepare(self.a, self.c, self.cov, u=usage(self.a, self.c, self.cov, body))
        second = issue(self.a, self.c, draft(self.a, self.c, preparation, 'SECOND'), self.e)
        r, lot = receipt(self.a, self.c, '40')
        assign(self.a, self.c, r, self.cov, self.e)
        for _ in range(2):
            result = investigate(self.a, self.c.pk, self.snap().pk, rev(self.c)).result
            self.assertEqual({x['issue'] for x in result['matching_alternatives']}, {first.pk, second.pk})
            self.assertTrue(all(x['lot'] == lot.pk and x['human_selection_required'] and x['alternatives_not_combined'] for x in result['matching_alternatives']))
            self.assertFalse(result['allocation_executed'])
            self.assertEqual(CashAllocation.objects.count(), 0)
            self.assertEqual(InvoiceDelivery.objects.count(), 0)
        selected = allocate(self.a, self.c, lot, second, '30', self.e, 'human-second')
        self.assertEqual(cash.open_amount(first), Decimal('32.25'))
        with self.assertRaises(ValidationError):
            allocate(self.a, self.c, lot, first, '11', self.e, 'over-capacity')
        allocate(self.a, self.c, lot, first, '10', self.e, 'human-first')
        self.assertEqual(cash.cash_remaining(lot), 0)
        cash.reverse(self.a, self.c.pk, 'allocation', selected.pk, 'Finance', self.e['cash_correction'].pk, 'Explicit wrong-target reversal', rev(self.c))
        self.assertEqual(cash.cash_remaining(lot), 30)
        self.assertEqual(cash.open_amount(second), Decimal('32.25'))
        self.assertEqual(cash.open_amount(first), Decimal('22.25'))
        with self.assertRaises(ValidationError):
            cash.reverse(self.a, self.c.pk, 'allocation', selected.pk, 'Finance', self.e['cash_correction'].pk, 'No second restoration', rev(self.c))
        self.assertEqual(CashReversal.objects.count(), 1)
        self.assertEqual(CashAllocation.objects.count(), 2)
        self.assertEqual(cash.cash_remaining(lot), 30)


class AmbiguousActualContrast(TestCase):
    def test_two_forecast_targets_share_one_actual_without_automatic_match(self):
        a, c, _ = fixture()
        value = payload(a, c)
        second = copy.deepcopy(value['items'][0])
        second.update(key='receipt-2', source_ref='expected-2')
        value['items'].append(second)
        report = run(a, c, value)
        actual_cash = actual(a, c)
        self.assertEqual(ForecastMatch.objects.count(), 0)
        for key in ['receipt-1', 'receipt-2']:
            self.assertEqual(forecast.matched(report.scenario, key), 0)
        selected = match(a, c, report.scenario, actual_cash, '10', key='receipt-2')
        with self.assertRaisesMessage(ValidationError, 'capacity'):
            match(a, c, report.scenario, actual_cash, '6', key='receipt-1', op='EXCESS')
        match(a, c, report.scenario, actual_cash, '5', key='receipt-1', op='OTHER')
        proof = evidence(a, c, 'forecast_match', 'Explicit mistaken target correction')
        reversal = forecast.unmatch(a, c.pk, selected.pk, proof.pk, 'Restore only selected capacity', rev(c))
        self.assertEqual(forecast.unmatch(a, c.pk, selected.pk, proof.pk, 'Same correction', rev(c)).pk, reversal.pk)
        self.assertEqual(forecast.matched(report.scenario, 'receipt-2'), 0)
        self.assertEqual(forecast.matched(report.scenario, 'receipt-1'), 5)
        match(a, c, report.scenario, actual_cash, '10', key='receipt-1', op='REPLACE')
        with self.assertRaisesMessage(ValidationError, 'capacity'):
            match(a, c, report.scenario, actual_cash, '1', key='receipt-2', op='NO-DOUBLE-RESTORE')
        self.assertEqual(ForecastMatch.objects.count(), 3)
        self.assertEqual(forecast.matched(report.scenario, 'receipt-1'), 15)
        self.assertFalse(Publication.objects.exists())


class PendingOverdueContrast(FactoryEscalationTests):
    def test_overdue_client_threshold_never_bypasses_pending_named_approval(self):
        clocks(self.a, self.c, self.owner)
        self.p = profile(self.a, self.c, self.state, self.e, 'client_dependent', True, timezone.now()-timedelta(hours=25))
        self.r = native.request_escalation(self.a, self.c.pk, self.p.pk, 'escalate', 'Client', self.e.pk, 'Await named human approval', rev(self.c))
        self.w = escalation.start(self.a, self.c.pk, 'P44-PENDING', self.r.pk, self.t.pk, 'Overdue is not authority', rev(self.c))
        for _ in range(3):
            native.scan_profile(self.a, self.c.pk, self.p.pk)
            self.advance()
            report = escalation.report(self.w)
            self.assertTrue(report['timing']['client_24h'])
            self.assertEqual(report['timing']['acknowledgement_status'], 'OVERDUE')
            self.assertEqual(report['stage'], 'decision')
            self.assertIn('pending', report['finding'])
            self.assertIn(self.a.username, escalation.projection(self.a, self.w)['owner_names'])
            self.assertIsNone(escalation.document(self.w))
        self.assertEqual(EscalationSignal.objects.filter(profile=self.p, kind='client_24h').count(), 1)
        self.assertFalse(EscalationDecision.objects.exists())
        for model in [Publication, PublicationJob, PublicationReceipt]:
            self.assertFalse(model.objects.exists())
        self.client.force_login(self.a)
        response = self.client.get(reverse('factory_detail', args=[self.w.pk]))
        self.assertContains(response, 'Client escalation or de-escalation decision')
        self.assertContains(response, 'OVERDUE', msg_prefix='P44-M02 primary work surface must show overdue and pending approval together')


    def test_unconfigured_clock_stays_unknown_on_primary_pending_surface(self):
        self.start(); self.advance(); self.client.force_login(self.a)
        response = self.client.get(reverse('factory_detail', args=[self.w.pk]))
        self.assertContains(response, 'Acknowledgement: UNKNOWN')
        self.assertContains(response, '24-hour threshold: Unknown')
        self.assertContains(response, 'Client escalation or de-escalation decision')
        self.assertFalse(EscalationDecision.objects.exists())
        self.assertFalse(Publication.objects.exists())


class GuessedProjectContrast(ProjectViewTests):
    def test_foreign_project_guessed_html_and_inspect_reveal_no_metadata(self):
        _, other = setup_case(username='foreign-project-owner')
        other.title = 'PRIVATE-FOREIGN-PROJECT-MARKER'
        other.save(update_fields=['title'])
        self.client.force_login(self.b)
        before = Audit.objects.count()
        for params in [{}, {'inspect': '1'}]:
            response = self.client.get(reverse('project_audience', args=[other.pk, 'synthetic_team']), params)
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, other.title, status_code=404)
            self.assertNotContains(response, 'effect_tools', status_code=404)
            self.assertNotContains(response, 'PRIVATE ACTION DESCRIPTION', status_code=404)
        self.assertEqual(Audit.objects.count(), before)


class RestrictedMismatchContrast(TestCase):
    @classmethod
    def setUpTestData(cls):
        from tests.finance_analysis_helpers import fixture as finance_fixture
        from tests.bu_helpers import configure, policy
        from apps.finance import analysis
        from apps.policy.bu_validators import SOURCE, MAPPING, AUTH
        a, c, e, _, _, source, _, recipient = finance_fixture()
        f = {'preparer': a, 'reviewer': a, 'manager': recipient, 'case': c, 'e': e}
        configure(f, catalogue=False)
        from apps.identity.models import Grant
        Grant.objects.get_or_create(case=c, user=recipient, action='case.read')
        value = copy.deepcopy(f['bu_config']['authority']); value['independent_reviewer'] = False
        policy(f, AUTH, value)
        value = copy.deepcopy(f['bu_config']['source'])
        value.update(from_period='2026-10', to_period='2026-10', currency='NGN', company_comparison='finance_allocation_required')
        policy(f, SOURCE, value)
        value = copy.deepcopy(f['bu_config']['mapping'])
        value.update(from_period='2026-10', to_period='2026-10'); value['mappings'][0]['bu'] = 'alpha'
        policy(f, MAPPING, value)
        f['bu_config']['export'].update(period='2026-10', currency='NGN', control_total='195', rows=[{'event_id': 'E1', 'amount': '195', 'tags': ['DIRECT-A']}])
        mapped = analysis.map_source(a, c.pk, source.pk, [], rev(c))
        allocation = analysis.allocate(a, c.pk, mapped.pk, ['direct_cost'], rev(c))
        f['comparison'] = {'run_id': allocation.pk, 'metric': 'direct_cost'}
        cls.f = f

    def mismatch(self):
        from tests.bu_helpers import event
        return event(self.f, comparison=self.f['comparison'])

    def test_restricted_mismatch_retains_both_values_and_never_balances_or_publishes(self):
        from tests.bu_helpers import publish
        from apps.finance.models import BUReport
        f = self.f; work = self.mismatch()
        self.assertEqual(Decimal(work.payload['source_total']), 195)
        self.assertEqual(Decimal(work.payload['finance_company_comparison']['company_total']), 200)
        self.assertFalse(work.payload['finance_company_comparison']['matches'])
        self.assertIn('finance_company_comparison_mismatch', work.metadata['codes'])
        with self.assertRaises(ValidationError): publish(f, work)
        self.assertFalse(BUReport.objects.exists())
        self.client.force_login(f['preparer'])
        response = self.client.get(reverse('bu_inspect', args=[f['case'].pk, 'work', work.pk]))
        self.assertContains(response, '195')
        self.assertContains(response, '200')
        self.assertContains(response, 'company_total')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.client.force_login(f['manager'])
        self.assertEqual(self.client.get(reverse('bu_inspect', args=[f['case'].pk, 'work', work.pk])).status_code, 403)

    def test_source_required_unresolved_difference_is_explicit_in_restricted_inspection(self):
        f = self.f; work = self.mismatch()
        self.client.force_login(f['preparer'])
        response = self.client.get(reverse('bu_inspect', args=[f['case'].pk, 'work', work.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('difference', response.context['value']['finance_company_comparison'], 'F23-E01 requires an explicit unresolved difference, not totals alone')
        self.assertEqual(Decimal(response.context['value']['finance_company_comparison']['difference']), 5)


    def test_private_diagnostics_zero_negative_and_immutable_payload(self):
        from apps.finance import bu
        from apps.finance.models import BUReport
        from tests.bu_helpers import source, event
        from apps.documents.contracts import digest
        f = self.f
        for amount, expected in [('195', '5'), ('200', '0'), ('205', '-5')]:
            supplied = source(f, key='source-'+amount, reference='source-'+amount,
                control_total=amount, rows=[{'event_id': 'E-'+amount, 'amount': amount, 'tags': ['DIRECT-A']}])
            work = event(f, key='compare-'+amount, s=supplied, comparison=f['comparison'])
            before = digest(work.payload)
            for _ in range(2):
                value = bu.read_private(f['preparer'], f['case'].pk, work.pk)
                comparison = value['finance_company_comparison']
                self.assertEqual(Decimal(comparison['difference']), Decimal(expected))
                self.assertEqual(comparison['difference_basis'], 'Company minus BU (supplied comparable totals)')
                self.assertEqual(comparison['difference_status'], 'unresolved' if expected != '0' else 'matching totals; review status unchanged')
            work.refresh_from_db()
            self.assertEqual(digest(work.payload), before)
            self.assertNotIn('difference', work.payload['finance_company_comparison'])
        self.assertFalse(BUReport.objects.exists())

    def test_diagnostic_unknown_and_incomparable_totals_never_become_zero(self):
        from apps.finance.bu import private_comparison_difference
        for bu, company, comparable in [(None, '200', True), ('195', None, True),
            ('195', '200', False), ('NaN', '200', True), ('195', 'Infinity', True)]:
            result = private_comparison_difference(bu, company, comparable)
            self.assertIsNone(result['difference'])
            self.assertEqual(result['difference_status'], 'unknown')

    def test_metadata_reader_sees_no_finance_values_despite_case_access(self):
        from apps.finance.models import BUWork
        from unittest.mock import patch
        from apps.agents.bu import investigate
        f = self.f; self.mismatch()
        self.client.force_login(f['manager'])
        def forbidden(_): raise AssertionError('Private payload read on metadata-only path')
        with patch.object(BUWork, 'payload', new=property(forbidden)):
            response = self.client.get(reverse('bu', args=[f['case'].pk]))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'company_total')
            self.assertNotContains(response, 'Company minus BU')
            self.assertFalse(investigate(f['preparer'], f['case'].pk, rev(f['case'])).result['finance_comparison_values_read'])
