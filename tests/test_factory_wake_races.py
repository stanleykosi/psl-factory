"""Exercise native progression while a source wake or pause reaches its final write."""
from datetime import timedelta

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from apps.workflows import factory_progress
from apps.workflows.models import HumanTask
from tests.billing_helpers import evidence
from tests.factory_helpers import fixture


class FactoryWakeRaceTests(TransactionTestCase):
    def waiting(self):
        data = fixture(missing=True)
        work, actor = data['work'], data['actor']
        job = factory_progress.set_progress(actor, work.pk, work.revision, True)
        self.drain(job)
        self.assertEqual(job.status, 'waiting')
        job.available_at = timezone.now() - timedelta(seconds=1)
        job.save(update_fields=['available_at'])
        return work, actor, job

    def drain(self, job):
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), job.pk)
            job.refresh_from_db()
            if job.status != 'queued':
                return
        self.fail('The synthetic workflow exceeded its bounded progression steps.')

    def test_source_wake_during_final_write_is_preserved_and_processed(self):
        work, actor, job = self.waiting()
        fired = False

        def incoming_source(execute, sql, params, many, context):
            nonlocal fired
            where = sql.partition('WHERE')[2]
            if not fired and sql.startswith('UPDATE "workflows_factoryprogress"') and '"token" =' in where:
                fired = True
                evidence(actor, work.case, 'factory_information', 'SAMPLE evidence received while the worker finishes.')
                factory_progress.wake_waiting(work.pk)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(incoming_source):
            self.assertEqual(factory_progress.run_once(), job.pk)
        self.assertTrue(fired)
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.observation, '')
        self.drain(job)
        self.assertTrue(HumanTask.objects.filter(case=work.case, kind='factory_review', status='open').exists())

    def test_human_pause_during_final_write_keeps_the_request_paused(self):
        work, actor, job = self.waiting()
        fired = False

        def incoming_pause(execute, sql, params, many, context):
            nonlocal fired
            where = sql.partition('WHERE')[2]
            if not fired and sql.startswith('UPDATE "workflows_factoryprogress"') and '"token" =' in where:
                fired = True
                work.refresh_from_db()
                factory_progress.set_progress(actor, work.pk, work.revision, False)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(incoming_pause):
            self.assertEqual(factory_progress.run_once(), job.pk)
        self.assertTrue(fired)
        job.refresh_from_db()
        self.assertEqual(job.status, 'paused')
        self.assertIsNone(factory_progress.run_once())
