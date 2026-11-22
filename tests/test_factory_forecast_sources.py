from copy import deepcopy
import json
from pathlib import Path
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.workflows import factory, factory_forecast as flow, factory_forecast_sources as bridge
from apps.finance import forecast
from apps.finance.models import ForecastActualVerification, ForecastMatch
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests.billing_helpers import evidence
from tests.forecast_helpers import fixture, scenario, actual, payload
from tests.helpers import rev, setup_case


class ForecastSelectionTests(TestCase):
    def setUp(self):
        self.actor, self.case, self.method = fixture()
        self.scenario = scenario(self.actor, self.case)
        p = self.scenario.payload
        self.value = {'protocol': bridge.PROTOCOL, 'scenario_id': self.scenario.pk,
                      'as_of': p['as_of'], 'months': p['months'],
                      'source_ids': sorted({self.scenario.evidence_id} | {r['evidence_id'] for r in p['openings'] + p['items']}),
                      'template_id': None, 'audience': 'management'}

    def test_exact_selection_and_native_calculation(self):
        r = bridge.prepare(self.actor, self.case.pk, self.value, rev(self.case))
        report = bridge.investigation(self.actor, self.case, self.value, r.pk)
        self.assertTrue(report['calculation_pin']['current'])
        self.assertEqual(report['selection'], self.value)
        self.assertEqual(report['calculation_inventory'], r.manifest)
        self.assertFalse(report['execution_authorized'])
        self.assertEqual(r.result['periods'][0]['closing'], '150')

    def test_explicit_horizon_and_complete_inventory(self):
        for field, value in [('months', list(reversed(self.value['months']))), ('source_ids', self.value['source_ids'][:-1]), ('scenario_id', True), ('template_id', True), ('audience', 'client')]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                bridge.selection(self.actor, self.case, dict(self.value, **{field: value}))
        with self.assertRaises(ValidationError):
            bridge.selection(self.actor, self.case, dict(self.value, inferred_budget=100))

    def test_case_scoped_actuals_remain_native_calculation_inventory(self):
        a = actual(self.actor, self.case, verified=False)
        r = bridge.prepare(self.actor, self.case.pk, self.value, rev(self.case))
        report = bridge.investigation(self.actor, self.case, self.value, r.pk)
        self.assertNotIn(a.evidence_id, report['selection']['source_ids'])
        self.assertIn(a.pk, [row[0] for row in report['calculation_inventory']['actuals']])
        self.assertEqual(r.result['periods'][0]['actual_inflow'], '0')
        self.assertFalse(ForecastActualVerification.objects.exists())
        self.assertFalse(ForecastMatch.objects.exists())

    def test_actual_change_stales_calculation_without_replacing_selection(self):
        r = bridge.prepare(self.actor, self.case.pk, self.value, rev(self.case))
        actual(self.actor, self.case)
        report = bridge.investigation(self.actor, self.case, self.value, r.pk)
        self.assertFalse(report['calculation_pin']['current'])
        self.assertEqual(report['selection'], self.value)
        with self.assertRaises(ValidationError):
            bridge.selected_run(self.actor, self.case, self.value, r.pk)

    def test_no_implicit_latest_scenario_or_run(self):
        scenario(self.actor, self.case)
        with self.assertRaisesMessage(ValidationError, 'explicitly select'):
            bridge.selection(self.actor, self.case, self.value)
        historical, _ = bridge.selection(self.actor, self.case, self.value, current=False)
        self.assertEqual(historical.pk, self.scenario.pk)

    def test_foreign_scenario_and_wrong_run_rejected(self):
        other = scenario(self.actor, self.case, reference='OTHER')
        r = forecast.prepare(self.actor, self.case.pk, other.pk, rev(self.case))
        with self.assertRaises(ValidationError):
            bridge.selected_run(self.actor, self.case, self.value, r.pk)
        actor, case = setup_case(username='foreign')
        with self.assertRaises(ValidationError):
            bridge.selection(actor, case, self.value)

    def test_read_requires_current_finance_permission(self):
        Grant.objects.filter(user=self.actor, case=self.case, action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            bridge.investigation(self.actor, self.case, self.value)

    def test_unknown_opening_is_not_invented(self):
        value = payload(self.actor, self.case)
        value['openings'] = []
        s = scenario(self.actor, self.case, value, reference='UNKNOWN')
        selected = dict(self.value, scenario_id=s.pk, source_ids=sorted({s.evidence_id} | {r['evidence_id'] for r in value['items']}))
        r = bridge.prepare(self.actor, self.case.pk, selected, rev(self.case))
        self.assertIsNone(r.result['periods'][0]['opening'])
        self.assertIsNone(r.result['periods'][0]['closing'])

    def test_work_review_shows_exact_current_months_without_group_or_unscoped_reuse(self):
        value = payload(self.actor, self.case)
        value['openings'] = []
        value['coverage']['inflows'] = 'partial'
        selected_scenario = scenario(self.actor, self.case, value, reference='SAMPLE-UNKNOWN-OPENING')
        selected = dict(self.value, scenario_id=selected_scenario.pk, as_of=value['as_of'], months=value['months'],
                        source_ids=sorted({selected_scenario.evidence_id, *(row['evidence_id'] for row in value['items'])}))
        source = evidence(self.actor, self.case, 'policy_decision', 'Synthetic current cash forecast work.')
        profile = json.loads((Path(__file__).resolve().parent.parent / 'fixtures/factory-forecast.json').read_text(encoding='utf-8'))
        profile.pop('classification')
        profile.update(preparer_id=self.actor.pk, executor_id=self.actor.pk)
        configuration = draft_operator_policy(self.actor, self.case.pk, 'OPS.factory_forecast_execution', profile,
                                              source.pk, timezone.now())
        transition(self.actor, configuration.pk, 'validated')
        transition(self.actor, configuration.pk, 'active')
        work = flow.start(self.actor, self.case.pk, 'forecast-unknown-opening', selected,
                          'Synthetic forecast with missing opening', rev(self.case))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        run = flow.calculation(work, self.actor)
        self.assertIsNotNone(run, work.finding)
        path = reverse('factory_invoice_decision', args=[work.pk])
        self.client.force_login(self.actor)
        response = self.client.get(path)
        self.assertContains(response, 'Cash forecast by month')
        self.assertContains(response, '<td>Unknown</td>', html=True)
        self.assertContains(response, '<td>0</td>', html=True)
        self.assertEqual(response.context['monthly_forecast']['inflows'], 'partial')
        values = response.context['monthly_forecast']['periods']
        self.assertEqual([row['month'] for row in values], value['months'])
        self.assertIsNone(values[0]['opening'])
        self.assertIsNone(values[0]['closing'])
        self.assertIn('no-store', response['Cache-Control'])

        group = flow.start(self.actor, self.case.pk, 'forecast-unknown-group', dict(selected, audience='group'),
                           'Separate synthetic group forecast', rev(self.case))
        factory.run_until_wait(group.pk)
        group.refresh_from_db()
        self.assertIsNotNone(flow.calculation(group, self.actor), group.finding)
        group_response = self.client.get(reverse('factory_invoice_decision', args=[group.pk]))
        self.assertNotContains(group_response, 'Cash forecast by month')
        self.assertIsNone(group_response.context['monthly_forecast'])

        actual(self.actor, self.case)
        stale = self.client.get(path)
        self.assertNotContains(stale, 'Cash forecast by month')
        self.assertIsNone(stale.context['monthly_forecast'])
        Grant.objects.filter(user=self.actor, case=self.case, action='finance.read').update(active=False)
        self.assertIn(self.client.get(path).status_code, (403, 404))
