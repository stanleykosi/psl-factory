"""Narrow C03-C08 proof contrasts; synthetic policies, no held calculation pipeline.

No broad test inheritance. C06's editable-link premise is not a native input.
C08 intentionally asserts the missing bounded owner-hold contract.
"""
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from django.test import TestCase
from django.db import connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.services import add_evidence
from apps.core.models import Evidence, Audit
from tests.helpers import setup_case, rev


def effects():
    """Exact rows, not just counters, across existing ledger/payment/effect tables."""
    prefixes = ('finance_ledger', 'finance_invoice', 'finance_cash', 'finance_payment')
    names = {'pmo_milestone', 'workflows_outbox', 'finance_handoff', 'finance_financialimport'}
    with connection.cursor() as cursor:
        tables = sorted(t for t in connection.introspection.table_names(cursor)
                        if t in names or t.startswith(prefixes))
        result = {}
        for table in tables:
            cursor.execute('SELECT row_to_json(t)::text FROM ' + connection.ops.quote_name(table) + ' t ORDER BY id')
            result[table] = [row[0] for row in cursor.fetchall()]
    return result


class FinanceClauseBoundariesTests(TestCase):
    def test_C03_adjustment_successor_stales_mapping_without_ledger_effects(self):
        from tests.finance_analysis_helpers import fixture
        from apps.finance import analysis
        a, c, e, _, _, source, _, _ = fixture()
        before = effects()
        adjustment = analysis.adjustment(a, c.pk, source.pk, 'ADJ-CLAUSE', 'additive',
            [{'account': 'sales', 'amount': '25'}], e['finance_adjustment'].pk, 'Synthetic report only', rev(c))
        analysis.review(a, c.pk, 'adjustment', adjustment.pk, 'Finance', 'approve',
                        e['finance_review'].pk, 'Exact review', rev(c))
        mapped = analysis.map_source(a, c.pk, source.pk, [adjustment.pk], rev(c))
        original = deepcopy(mapped.result)
        successor = analysis.adjustment(a, c.pk, source.pk, 'ADJ-CLAUSE', 'additive',
            [{'account': 'sales', 'amount': '30'}], e['finance_adjustment'].pk, 'Corrected report only', rev(c))
        self.assertNotEqual(successor.pk, adjustment.pk)
        with self.assertRaises(ValidationError):
            analysis.ensure_current(mapped)
        mapped.refresh_from_db()
        self.assertEqual(mapped.result, original)
        self.assertEqual(effects(), before)

    def test_C03_event_aggregate_once_without_ledger_effects(self):
        from tests.bu_helpers import fixture, event, publish
        from apps.finance import bu
        from apps.finance.models import BUEventClaim
        f = fixture()
        before = effects()
        work = event(f)
        publication = publish(f, work)
        result = bu.read_report(f['manager'], publication.pk)
        self.assertEqual(work.payload['by_bu'], {'BU-A': '100.00'})
        self.assertTrue(work.payload['conserved'])
        self.assertEqual(result['company_source_total'], '100')
        self.assertEqual(BUEventClaim.objects.count(), 1)
        self.assertEqual(effects(), before)

    def test_C04_selected_price_without_tax_rule_stays_unknown(self):
        from tests.billing_helpers import coverage, usage, prepare, policy, FIXTURE
        a, c = setup_case()
        cov = coverage(a, c)
        rule = dict(json.loads(FIXTURE.read_text())['rule'], coverage_id=cov.pk)
        policy(a, c, 'D08.effective_price_rule_refs', [rule])
        u = usage(a, c, cov)
        before = effects()
        p = prepare(a, c, cov, u=u)
        self.assertEqual(p.result['status'], 'held')
        self.assertEqual(p.result['findings'], ['D08.tax_tier_rounding_rules: MISSING'])
        line = p.result['lines'][0]
        self.assertEqual(line['rule'], rule['key'])
        self.assertEqual(line['rate'], rule['rate'])
        for key in ['net', 'tax', 'total', 'raw_net']:
            self.assertIsNone(line[key])
        self.assertIsNone(p.result['total'])
        with self.assertRaisesMessage(ValidationError, 'Overlapping effective price rules'):
            policy(a, c, 'D08.effective_price_rule_refs', [rule, dict(rule, key='overlap')])
        self.assertEqual(effects(), before)

    def test_C05_select_one_of_two_native_receivables_with_omitted_coverage(self):
        from tests.settlement_helpers import fixture, draft
        from tests.obligation_helpers import issue_identified as issue
        from tests.billing_helpers import usage, prepare, FIXTURE
        from tests.forecast_helpers import configure, payload, scenario
        from apps.finance import forecast
        a, c, cov, preparation, evidence = fixture()
        first = issue(a, c, draft(a, c, preparation, 'INV-SELECTED'), evidence)
        body = json.loads(FIXTURE.read_text())['csv'].replace('tx-example-1', 'tx-omitted').replace(',12\n', ',24\n')
        second_preparation = prepare(a, c, cov, u=usage(a, c, cov, body))
        second = issue(a, c, draft(a, c, second_preparation, 'INV-OMITTED'), evidence)
        configure(a, c)
        value = payload(a, c)
        value['items'] = [dict(value['items'][0], kind='receivable', issue_id=first.pk,
                               amount=str(first.invoice.amount), source_ref='selected-native-invoice')]
        selected = scenario(a, c, value)
        before = effects()
        result = forecast.prepare(a, c.pk, selected.pk, rev(c)).result
        self.assertEqual(Decimal(result['periods'][0]['inflow']), Decimal('32.25'))
        self.assertEqual([row['issue'] for row in result['omitted_receivables']], [second.pk])
        self.assertEqual(Decimal(result['omitted_receivables'][0]['open']), Decimal('64.50'))
        self.assertIn('Captured receivables omitted from selected scenario', result['findings'])
        self.assertFalse(result['full_business_cash_forecast'])
        self.assertEqual(effects(), before)

    def test_C06_generated_chain_is_immutable_and_unknown_propagates(self):
        from django.db import transaction, DatabaseError
        from tests.forecast_helpers import fixture, payload, scenario
        from apps.finance import forecast
        from apps.finance.models import ForecastRun
        a, c, method = fixture()
        value = payload(a, c)
        selected = scenario(a, c, value)
        run = forecast.prepare(a, c.pk, selected.pk, rev(c))
        self.assertEqual(method['implementation'], 'monthly_cash_chain_v1')
        self.assertEqual(run.result['periods'][1]['opening'], run.result['periods'][0]['closing'])
        original = deepcopy(run.result)
        corrupt = deepcopy(original)
        corrupt['periods'][1]['opening'] = '999'
        with self.assertRaises(DatabaseError), transaction.atomic():
            ForecastRun.objects.filter(pk=run.pk).update(result=corrupt)
        run.refresh_from_db()
        self.assertEqual(run.result, original)
        value['items'][0]['amount'] = None
        unknown = scenario(a, c, value, reference='UNKNOWN-CHAIN')
        result = forecast.prepare(a, c.pk, unknown.pk, rev(c)).result
        self.assertIsNone(result['periods'][0]['closing'])
        self.assertIsNone(result['periods'][1]['opening'])
        self.assertIsNone(result['periods'][1]['closing'])
        self.assertIn('Projected balance is unknown; missing input is not zero', result['findings'])
        # This is a generated-chain safeguard, NOT the unimplemented external
        # workbook-reference inspection or real Finance oracle acceptance.

    def test_C07_dated_estimate_and_cash_without_completed_milestone_has_no_effects(self):
        from apps.finance import recognition
        from apps.pmo.models import Milestone
        from apps.workflows.models import Outbox
        a, c = setup_case()
        estimate = add_evidence(a, c.pk, 'progress_estimate', 'Dated estimate: 50 percent, not acceptance', 'synthetic:clause')
        cash = add_evidence(a, c.pk, 'cash_report', 'Cash reported: 20 TEST, not verified or completion', 'synthetic:clause')
        value = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/recognition-review.json').read_text())['packet']
        value.update(as_of=timezone.localdate().isoformat(), milestone_ids=[], facts=[
            {'category': 'estimate', 'evidence_id': estimate.pk, 'description': '50 percent estimate'},
            {'category': 'cash', 'evidence_id': cash.pk, 'description': '20 TEST reported cash'}])
        before = effects()
        packet = recognition.prepare(a, c.pk, 'estimate-cash-only', value, estimate.pk, rev(c))
        self.assertEqual(packet.payload['facts'], value['facts'])
        self.assertEqual(packet.payload['as_of'], value['as_of'])
        self.assertEqual(packet.manifest['milestones'], {})
        self.assertFalse(Milestone.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        position = recognition.position(packet)
        self.assertIsNone(position['recognised_amount'])
        self.assertFalse(position['accounting_posted'])
        self.assertEqual(position['records'], [])
        self.assertEqual(Evidence.objects.get(pk=estimate.pk).body, estimate.body)
        self.assertEqual(Evidence.objects.get(pk=cash.pk).body, cash.body)
        self.assertIn('Acceptance evidence missing', recognition.findings(packet))
        self.assertEqual(effects(), before)

    def test_C08_rejected_hr_scope_exposes_bounded_owner_hold_without_secret(self):
        from tests.hrfinance_helpers import fixture, body
        from apps.finance import hrfinance
        from apps.finance.models import HRReadSnapshot
        from apps.agents.hrfinance import investigate
        f = fixture()
        raw = json.loads(body(f))
        raw['rows'][0]['medical'] = 'FORBIDDEN-CLAUSE-SENTINEL'
        snapshot = hrfinance.capture(f['hr'], f['case'].pk, f['contract'].pk,
            'scope-clause', json.dumps(raw), rev(f['case']))
        self.assertEqual(snapshot.status, 'rejected')
        self.assertEqual(snapshot.payload, {})
        result = investigate(f['hr'], f['case'].pk, rev(f['case'])).result
        safe = result['findings'][0]['contracts'][0]['snapshots'][0]
        self.assertEqual(safe['exception_codes'], ['out_of_contract_fields'])
        self.assertNotIn('FORBIDDEN-CLAUSE-SENTINEL', json.dumps(result))
        self.assertFalse(Evidence.objects.filter(body__contains='FORBIDDEN-CLAUSE-SENTINEL').exists())
        self.assertNotIn('FORBIDDEN-CLAUSE-SENTINEL', json.dumps(list(Audit.objects.values_list('data', flat=True))))
        self.assertNotIn('FORBIDDEN-CLAUSE-SENTINEL', json.dumps(list(HRReadSnapshot.objects.values_list('payload', flat=True))))
        # Desired bounded contract, intentionally not silently satisfied by generic held status.
        self.assertEqual(safe.get('scope_exception'), {'status': 'held', 'reason': 'scope_exception_owner_unconfigured'})

    def test_C08_scope_question_preserves_capture_history_and_has_no_outbound_effect(self):
        from unittest.mock import patch
        from tests.hrfinance_helpers import fixture, body
        from apps.finance import hrfinance
        from apps.finance.models import HRReadSnapshot, HRHandoffRecord, HRDisclosure
        from apps.agents.hrfinance import investigate
        f = fixture()
        raw = json.loads(body(f))
        raw['rows'][0]['disciplinary'] = 'NEVER-RETAIN-SCOPE-SECRET'
        s = hrfinance.capture(f['hr'], f['case'].pk, f['contract'].pk,
                              'disciplinary-scope', json.dumps(raw), rev(f['case']))
        before = effects()
        history = {model.__name__: list(model.objects.order_by('pk').values())
                   for model in [HRReadSnapshot, HRHandoffRecord, HRDisclosure]}
        def forbidden(_):
            raise AssertionError('Scope investigation read snapshot payload')
        with patch.object(HRReadSnapshot, 'payload', property(forbidden)):
            result = investigate(f['hr'], f['case'].pk, rev(f['case'])).result
        finding = result['findings'][0]
        questions = finding['questions']
        self.assertEqual(sum('scope-exception owner/action route' in q for q in questions), 1)
        self.assertTrue(any('Forbidden fields remain rejected and discarded' in q for q in questions))
        self.assertTrue(any('no notification was sent' in q for q in questions))
        self.assertFalse(result['disclosure_approved'])
        self.assertFalse(result['hr_source_written'])
        self.assertFalse(result['private_rows_read'])
        self.assertEqual(effects(), before)
        self.assertEqual(history, {model.__name__: list(model.objects.order_by('pk').values())
                                  for model in [HRReadSnapshot, HRHandoffRecord, HRDisclosure]})
        self.assertNotIn('NEVER-RETAIN-SCOPE-SECRET', json.dumps(result))
        self.assertFalse(Evidence.objects.filter(body__contains='NEVER-RETAIN-SCOPE-SECRET').exists())
        self.assertNotIn('NEVER-RETAIN-SCOPE-SECRET', json.dumps(list(Audit.objects.values_list('data', flat=True))))
        s.refresh_from_db()
        self.assertEqual((s.status, s.payload), ('rejected', {}))
        self.assertEqual(s.manifest['findings'], ['out_of_contract_fields'])

    def test_C08_scope_investigation_requires_current_case_and_hr_read_grants(self):
        from tests.hrfinance_helpers import fixture, body
        from apps.finance import hrfinance
        from apps.agents.hrfinance import investigate
        from apps.agents.models import AgentRun
        from apps.identity.models import Grant
        from django.core.exceptions import PermissionDenied
        f = fixture()
        raw = json.loads(body(f))
        raw['rows'][0]['medical'] = 'NO-READ-GRANT-SECRET'
        hrfinance.capture(f['hr'], f['case'].pk, f['contract'].pk,
                          'scope-grants', json.dumps(raw), rev(f['case']))
        for action in ['case.read', 'hrfinance.read', 'agent.hrfinance']:
            with self.subTest(action=action):
                grants = Grant.objects.filter(case=f['case'], user=f['hr'], action=action)
                self.assertTrue(grants.exists())
                grants.update(active=False)
                before = (AgentRun.objects.count(), Evidence.objects.count(), Audit.objects.count(), effects())
                with self.assertRaises(PermissionDenied):
                    investigate(f['hr'], f['case'].pk, rev(f['case']))
                self.assertEqual(before, (AgentRun.objects.count(), Evidence.objects.count(), Audit.objects.count(), effects()))
                grants.update(active=True)

    def test_C08_scope_hold_is_not_added_to_accepted_or_unrelated_rejected_snapshot(self):
        from tests.hrfinance_helpers import fixture, capture
        from apps.agents.hrfinance import investigate
        f = fixture()
        accepted = capture(f)
        unrelated = capture(f, 'unrelated-rejection', source_version=None)
        self.assertEqual(accepted.status, 'accepted')
        self.assertEqual(unrelated.status, 'rejected')
        self.assertNotIn('out_of_contract_fields', unrelated.manifest['findings'])
        finding = investigate(f['hr'], f['case'].pk, rev(f['case'])).result['findings'][0]
        self.assertTrue(all('scope_exception' not in row for row in finding['contracts'][0]['snapshots']))
        self.assertFalse(any('scope-exception owner/action route' in q for q in finding['questions']))
