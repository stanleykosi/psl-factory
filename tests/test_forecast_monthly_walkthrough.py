from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from adapters.forecast import OPENING_CONTRACT
from apps.core.models import Case
from apps.documents.models import Publication
from apps.finance.models import ForecastReview, ForecastRun
from apps.identity.models import Grant
from apps.workflows import factory_forecast as flow
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_forecast_monthly_seed as seed
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
        response = self.client.post(decision, {'action': 'review', 'work_revision': work.revision,
            'revision': rev(case), 'selected_scenario': sample['scenario'], 'run': run.pk,
            'role': 'Finance', 'verdict': 'return', 'evidence': sample['review_evidence'],
            'reason': 'Supply evidence that reconciles this sample opening.'})
        self.assertRedirects(response, decision, fetch_redirect_response=False)
        self.assertEqual(ForecastReview.objects.get(run=run).actor_id, reviewer.pk)
        self.assertEqual(ForecastReview.objects.get(run=run).verdict, 'return')
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
