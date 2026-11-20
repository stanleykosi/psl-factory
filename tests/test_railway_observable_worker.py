from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.workflows import factory
from apps.workflows.models import FactoryWork
from tests import railway_observable_worker as worker
from tests.railway_batch_walkthrough_seed import OBSERVABLE_PREPARATION, prepare_project


class ObservableWorkerTests(TestCase):
    def test_only_the_explicit_acceptance_worker_can_wait_for_browser_observation(self):
        names = {'RAILWAY_PROJECT_ID': worker.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                 'PSL_ACCEPTANCE_OBSERVABLE_WORKER': '1'}
        with patch.dict('os.environ', {**names, 'RAILWAY_ENVIRONMENT_NAME': 'production'}):
            with self.assertRaises(RuntimeError):
                worker.work_progress()
        with patch.dict('os.environ', names):
            worker.require_acceptance()

    def test_new_named_samples_replay_and_only_show_live_claim_for_exact_operation(self):
        actor = get_user_model().objects.create_user('synthetic-observable-progress-reviewer')
        self.client.force_login(actor)
        for key in OBSERVABLE_PREPARATION:
            with self.subTest(sample=key):
                sample = prepare_project(actor, key)
                self.assertEqual(prepare_project(actor, key)['work'], sample['work'])
                work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
                self.assertEqual(worker.sample_key(work), key)
                if key == 'archive_observable':
                    continue
                label = 'Investigating the asset register and supporting records.'
                if key == 'assets_observable':
                    self.assertNotContains(self.client.get(sample['path']), label)
                    with patch.object(worker, 'sleep', side_effect=lambda _: self.assertContains(
                            self.client.get(sample['path']), label)) as observing:
                        self.assertTrue(factory.run_once(work.pk, provider=worker.ObservableCoordinator({'ACT04'})))
                    observing.assert_called_once_with(worker.WINDOW_SECONDS)
                    self.assertNotContains(self.client.get(sample['path']), label)
        regular = prepare_project(actor, 'assets_live')
        self.assertIsNone(worker.sample_key(FactoryWork.objects.select_related('case').get(pk=regular['work'])))

    def test_report_samples_stop_before_the_exact_draft_and_original_publication(self):
        from apps.documents.models import PublicationJob
        from apps.workflows import factory_accounting

        actor = get_user_model().objects.create_user('synthetic-report-observation-reviewer')
        for key, step in [('accounts_draft_observable', 'ACT09'), ('accounts_publish_observable', 'ACT11')]:
            with self.subTest(sample=key):
                sample = prepare_project(actor, key)
                work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
                _, value = factory.profile(work)
                state, latest, missing, stale, tasks, jobs = factory_accounting.snapshot(work, value)
                options, _ = factory_accounting.eligible(work, value, state, latest, missing, stale, tasks, jobs)
                self.assertEqual(options, [step])
                self.assertTrue(state['formula'])
                self.assertEqual(bool(state['document']), step == 'ACT11')
                self.assertFalse(PublicationJob.objects.filter(publication__factory_work=work).exists())
                self.assertEqual(prepare_project(actor, key)['work'], work.pk)
