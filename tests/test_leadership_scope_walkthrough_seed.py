"""The native browser setup reaches an unapproved scoped monthly report."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import leadership_project_scope as coverage
from apps.workflows import factory_leadership as flow, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests import railway_leadership_scope_seed as seed
from tests.helpers import rev


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                           seed.GUARD: '1', 'PGDATABASE': 'synthetic-preview'})
class LeadershipScopeWalkthroughSeedTests(TestCase):
    def test_existing_trial_starts_only_the_two_project_sample_and_stops_before_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        operator = get_user_model().objects.create_user('psl-agent-trial')
        other = Case.objects.create(title='Preserved earlier leadership workspace', tenant='older-test', synthetic=True,
                                    kind='project')
        Grant.objects.create(case=other, user=operator, action='case.read')
        other_revision = rev(other)
        with patch.dict('os.environ', {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'leadership sample guard'):
                seed.prepare()
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare()
        self.assertEqual(seed.prepare(), sample | {'preserved': True})
        self.assertEqual(rev(other), other_revision)
        self.assertEqual(set(Grant.objects.filter(case=other, user=operator).values_list('action', flat=True)), {'case.read'})
        self.assertFalse(Audit.objects.filter(case=other).exists())
        self.assertIsNone(sample['existing_work'])
        home = Case.objects.get(pk=sample['home'])
        self.assertFalse(FactoryWork.objects.filter(case=home).exists())

        self.client.force_login(operator)
        page = self.client.get(sample['path'])
        self.assertContains(page, 'All projects I can report on')
        self.assertContains(page, seed.TEMPLATE)
        response = self.client.post(reverse('factory_create'), {'definition': flow.DEFINITION, 'case': home.pk,
            'scope': coverage.MODE, 'kind': seed.KIND, 'key': 'SAMPLE-LEADERSHIP-WALKTHROUGH',
            'reference': sample['reference'], 'revision': rev(home), 'background': 'on', 'audience': 'internal',
            'start_at': sample['start'], 'end_at': sample['end'], 'template_id': sample['template'], 'domains': sample['areas']})
        work = FactoryWork.objects.get(case=home, actor=operator, definition=flow.DEFINITION)
        target = reverse('factory_detail', args=[work.pk])
        self.assertRedirects(response, target, fetch_redirect_response=False)
        progress = FactoryProgress.objects.get(work=work, requested_by=operator)
        self.assertEqual(progress.status, 'queued')
        for _ in range(16):
            self.assertEqual(factory_progress.run_once(), progress.pk)
            progress.refresh_from_db()
            if progress.status == 'waiting':
                break
        self.assertEqual(progress.status, 'waiting')

        work.refresh_from_db()
        report = flow.document(work)
        self.assertIsNotNone(report, work.finding)
        self.assertEqual(report.audience, 'internal')
        self.assertNotEqual(report.created_by_id, operator.pk)
        task = HumanTask.objects.get(case=home, version=report, status='open')
        self.assertEqual(task.required_role, 'PMO Lead')
        self.assertFalse(report.reviews.exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        manifest = flow.source(work, operator)['manifest']['project_scope']
        self.assertEqual(manifest['record_counts'], {'meetings': 2})
        self.assertEqual({row['case'] for row in manifest['projects']}, {sample['home'], sample['contributor']})
        visible = self.client.get(target)
        self.assertContains(visible, '2 projects were checked')
        self.assertContains(visible, seed.SECOND_TITLE)
        self.assertNotContains(visible, 'Approve exact report')
        self.client.force_login(get_user_model().objects.get(pk=sample['reviewer']))
        self.assertContains(self.client.get(reverse('factory_invoice_decision', args=[work.pk])), 'Approve exact report')
        self.assertEqual(seed.prepare(), sample | {'preserved': True, 'existing_work': work.pk})
        self.assertFalse(report.reviews.exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
