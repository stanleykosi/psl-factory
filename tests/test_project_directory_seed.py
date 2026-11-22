import json
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.models import Audit, Case
from apps.identity.models import Grant
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_project_directory_seed as seed


class ProjectDirectoryWalkthroughSeedTests(TestCase):
    def test_trial_rows_use_exact_current_source_facts_with_independent_visibility(self):
        self.assertEqual(connection.vendor, 'postgresql')
        viewer = get_user_model().objects.create_user('psl-agent-trial')
        environment = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                       'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'}
        with patch.dict('os.environ', environment | {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'project directory fixture guard'):
                seed.run()
        self.assertFalse(Case.objects.filter(pk__in=seed.CASE_IDS.values()).exists())
        output = StringIO()
        with patch.dict('os.environ', environment), redirect_stdout(output):
            seed.run()
        prefix, value = output.getvalue().strip().split('=', 1)
        sample = json.loads(value)
        self.assertEqual(prefix, seed.GUARD)
        self.assertNotEqual(sample['release']['manager'], viewer.pk)
        review = HumanTask.objects.get(pk=sample['review']['review'], version_id=sample['review']['report'])
        self.assertEqual((review.status, review.required_role), ('open', 'PMO Lead'))
        self.assertNotEqual(review.version.created_by_id, viewer.pk)

        self.client.force_login(viewer)
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(sample['path'])
        self.assertLessEqual(len(queries), 560)
        self.assertContains(page, seed.MANAGER)
        self.assertContains(page, seed.MILESTONE)
        self.assertContains(page, 'Needs a person')
        self.assertContains(page, 'Stopped')
        self.assertContains(page, '<span class="project-directory-label" aria-hidden="true">Project manager</span>', html=True)
        self.assertNotContains(page, '42.50')
        from apps.core.project_list import _counts

        release_work = FactoryWork.objects.select_related('case', 'source_head').get(pk=sample['release']['work'])
        with CaptureQueriesContext(connection) as release_queries:
            self.assertEqual(_counts(viewer, [release_work], False), (0, 1))
        self.assertLessEqual(len(release_queries), 24)
        project_rows = {str(row['case'].pk): row for row in page.context['project_rows']}
        release = project_rows[sample['release']['case']]
        self.assertEqual((release['manager'], release['lifecycle'], release['phase'], release['state']),
                         (seed.MANAGER, 'Active', 'Release', 'Setup needed'))
        self.assertEqual(release['milestone'], {'name': seed.MILESTONE, 'due': date.fromisoformat(sample['release']['due'])})
        self.assertEqual((release['reviews'], release['exceptions']), (0, 1))
        pending = project_rows[sample['review']['case']]
        self.assertEqual((pending['reviews'], pending['exceptions']), (1, 0))
        unprovided = project_rows[sample['unprovided']['case']]
        self.assertIsNone(unprovided['manager'])
        self.assertIsNone(unprovided['milestone'])
        self.assertEqual((unprovided['reviews'], unprovided['exceptions']), (0, 0))
        self.assertContains(page, sample['release']['journey'])
        self.assertContains(self.client.get(sample['release']['journey']), sample['release']['title'])
        self.assertContains(self.client.get(sample['active']), sample['release']['title'])

        Grant.objects.filter(case_id=sample['release']['case'], user=viewer, action__in=('engagement.read', 'finance.read')).update(active=False)
        Grant.objects.filter(case_id=sample['review']['case'], user=viewer, action='report.read').update(active=False)
        restricted = self.client.get(sample['path'])
        self.assertNotContains(restricted, seed.MANAGER)
        self.assertNotContains(restricted, seed.MILESTONE)
        records = {str(row['case'].pk): row for row in restricted.context['project_rows']}
        self.assertEqual(records[sample['review']['case']]['reviews'], 0)
        self.assertContains(restricted, sample['review']['title'])
        self.assertEqual(FactoryWork.objects.get(pk=sample['release']['work']).status, 'configuration_needed')
        review.refresh_from_db()
        self.assertEqual(review.status, 'open')
        self.assertEqual(Audit.objects.filter(case_id__in=seed.CASE_IDS.values(), action=seed.MARKER).count(), 3)
        rerun = seed.prepare(viewer)
        for scenario in seed.TITLES:
            self.assertEqual(rerun[scenario], sample[scenario] | {'preserved': True})
