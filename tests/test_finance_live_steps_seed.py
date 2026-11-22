from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.finance.models import LedgerLineage
from apps.identity.models import Grant
from apps.workflows import factory_ppe
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests import railway_finance_live_steps_seed as seed


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_FINANCE_LIVE_STEP_FIXTURE': '1'})
class FinanceLiveStepSeedTests(TestCase):
    def test_new_steps_expose_exact_worker_claims_to_trial_reader_only(self):
        trial = get_user_model().objects.create_user('psl-agent-trial')
        self.client.force_login(trial)
        for station, label in (
                ('asset-calculation', 'Calculating the asset schedule.'),
                ('ledger-investigation', 'Investigating the supplied ledger reference.')):
            with self.subTest(station=station):
                sample = seed.prepare(station)
                work = FactoryWork.objects.get(pk=sample['work'])
                self.assertEqual(seed.prepare(station), dict(sample, preserved=True))
                self.assertNotEqual(work.actor_id, trial.pk)
                self.assertFalse(Grant.objects.filter(case=work.case, user=trial, action='factory.execute').exists())
                self.assertNotContains(self.client.get(sample['path']), label)

                def inspect_claim(seconds):
                    self.assertEqual(seconds, seed.WINDOW_SECONDS)
                    work.refresh_from_db()
                    claim = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03',
                                                       phase='started', fence=work.fence)
                    self.assertFalse(claim.activity.attempts.filter(number=claim.number, phase='observed').exists())
                    self.assertContains(self.client.get(sample['path']), label)
                    self.assertNotContains(self.client.get(reverse('factory_invoice_decision', args=[work.pk])), label)

                with patch.object(seed, 'sleep', side_effect=inspect_claim) as window:
                    result = seed.observe(station, work.pk)
                window.assert_called_once_with(seed.WINDOW_SECONDS)
                self.assertEqual(result['step'], sample['step'])
                self.assertNotContains(self.client.get(sample['path']), label)
                self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
                with self.assertRaisesMessage(RuntimeError, 'fresh synthetic sample'):
                    seed.observe(station, work.pk)
                work.refresh_from_db()
                if station == 'asset-calculation':
                    schedule = factory_ppe.schedule(work)
                    self.assertIsNotNone(schedule)
                    self.assertFalse(schedule.reviews.filter(authority__purpose='schedule').exists())
                else:
                    self.assertFalse(LedgerLineage.objects.filter(case=work.case).exists())
