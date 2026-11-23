from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from adapters.forecast import OPENING_CONTRACT
from apps.core.models import Case
from apps.documents.models import Publication
from apps.finance import forecast
from apps.finance.models import ForecastReview, ForecastRun
from apps.identity.models import Grant
from apps.workflows import factory_forecast as flow
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import forecast_helpers, railway_forecast_monthly_seed as seed
from tests.billing_helpers import evidence
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
class ForecastMonthlyWalkthroughTests(TestCase):
    def test_fresh_private_review_preserves_unreconciled_opening_and_known_zero(self):
        self.enterContext(patch.object(timezone, 'localdate', return_value=timezone.localdate()))
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        other = Case.objects.create(tenant='unrelated-test', title='Unrelated test case', kind='project', synthetic=True)
        Grant.objects.create(case=other, user=reviewer, action='case.read')
        scope = Grant.objects.filter(user=reviewer)
        existing = set(scope.values_list('case_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())

        sample = seed.prepare()
        case = Case.objects.get(pk=sample['case'], synthetic=True)
        work = FactoryWork.objects.get(pk=sample['work'], case=case)
        run = ForecastRun.objects.get(pk=sample['run'], case=case)
        self.assertEqual(seed.prepare(), dict(sample, preserved=True))
        self.assertEqual(set(scope.exclude(case=case).values_list('case_id', 'action', 'active')), existing)
        self.assertEqual(set(scope.filter(case=case, active=True).values_list('action', flat=True)), set(seed.REVIEWER_ACTIONS))
        self.assertNotEqual(run.actor_id, reviewer.pk)
        self.assertFalse(ForecastReview.objects.filter(run=run).exists())
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        scenario, selection = flow.source(work, reviewer)
        self.assertEqual(selection['source_ids'], sample['source_ids'])
        opening, = scenario.payload['openings']
        self.assertEqual((opening['contract'], opening['evidence_id'], opening['boundary']['status']),
                         (OPENING_CONTRACT, sample['opening'], 'unreconciled'))
        self.assertEqual(opening['amount'], '100')
        self.assertFalse(run.result['opening_provenance'][0]['eligible'])

        self.client.force_login(reviewer)
        decision = sample['decision_path']
        view = self.client.get(decision)
        self.assertContains(view, 'Cash forecast by month')
        self.assertIsNone(view.context['management_decision'])
        self.assertContains(view, '<td>Unknown</td>', html=True)
        self.assertContains(view, '<td>0</td>', html=True)
        current = view.context['monthly_forecast']
        self.assertEqual((current['account_count'], current['inflows'], current['outflows']), (1, 'partial', 'complete'))
        first, second = current['periods']
        self.assertEqual([first['month'], second['month']], sample['months'])
        self.assertEqual((first['opening'], first['inflow'], first['outflow'], first['closing']), (None, '50', '0', None))
        self.assertEqual(second['outflow'], '20')
        self.assertContains(self.client.get(sample['source_path']), 'Unresolved boundary; opening unknown')

        other_actor = get_user_model().objects.create_user('monthly-forecast-unscoped-reader')
        Grant.objects.create(case=case, user=other_actor, action='case.read')
        self.client.force_login(other_actor)
        self.assertIn(self.client.get(decision).status_code, (403, 404))
        self.client.force_login(reviewer)
        reason = 'Supply evidence that reconciles this sample opening.'
        response = self.client.post(decision, {'action': 'review', 'work_revision': work.revision,
            'revision': rev(case), 'selected_scenario': sample['scenario'], 'run': run.pk,
            'role': 'Finance', 'verdict': 'return', 'evidence': sample['review_evidence'],
            'reason': reason})
        self.assertRedirects(response, decision, fetch_redirect_response=False)
        review = ForecastReview.objects.get(run=run)
        self.assertEqual((review.actor_id, review.verdict), (reviewer.pk, 'return'))

        maker = run.actor
        unrelated_reason = 'A different-scoped calculation with a confidential reason.'
        unrelated = forecast_helpers.scenario(maker, case, reference='OTHER-SYNTHETIC-SCENARIO')
        unrelated_run = forecast.prepare(maker, case.pk, unrelated.pk, rev(case))
        unrelated_proof = evidence(maker, case, 'forecast_review', 'Independent test proof for the other scenario.')
        forecast.review(reviewer, case.pk, unrelated_run.pk, 'Finance', 'return', unrelated_proof.pk,
                        unrelated_reason, rev(case))

        with CaptureQueriesContext(connection) as visible_queries:
            returned = self.client.get(decision)
        self.assertContains(returned, 'Returned for correction')
        self.assertContains(returned, 'Prepare a corrected calculation for fresh Finance review.')
        self.assertContains(returned, reason)
        self.assertNotContains(returned, unrelated_reason)
        self.assertNotContains(returned, 'Await native readiness and exact human forecast review')
        self.assertEqual(returned.context['management_decision']['id'], review.pk)
        self.assertEqual(returned.context['management_decision']['run'], run.pk)
        self.assertEqual(sum('"finance_forecastreview"."reason"' in q['sql'] for q in visible_queries), 1)

        def assert_reason_held(actor):
            self.client.force_login(actor)
            with CaptureQueriesContext(connection) as queries:
                page = self.client.get(decision)
            self.assertEqual(page.status_code, 200)
            self.assertIsNone(page.context['management_decision'])
            self.assertNotContains(page, reason)
            self.assertNotContains(page, unrelated_reason)
            self.assertFalse(any('"finance_forecastreview"."reason"' in q['sql'] for q in queries))

        for action in set(seed.REVIEWER_ACTIONS) - {'case.read'}:
            Grant.objects.create(case=case, user=other_actor, action=action)
        assert_reason_held(other_actor)

        Grant.objects.create(case=case, user=maker, action='factory.manage')
        self.client.force_login(maker)
        self.assertContains(self.client.get(decision), reason)
        reviewer_grant = scope.filter(case=case, action='finance.forecast.review')
        reviewer_grant.update(active=False)
        assert_reason_held(maker)
        reviewer_grant.update(active=True)

        successor = forecast_helpers.scenario(maker, case, reference=scenario.reference)
        self.assertGreater(successor.number, scenario.number)
        assert_reason_held(reviewer)
        self.assertEqual(ForecastReview.objects.get(pk=review.pk).reason, reason)
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
