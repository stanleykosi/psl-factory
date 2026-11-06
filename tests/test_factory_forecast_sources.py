from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from apps.workflows import factory_forecast_sources as bridge
from apps.finance import forecast
from apps.finance.models import ForecastActualVerification, ForecastMatch
from apps.identity.models import Grant
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
