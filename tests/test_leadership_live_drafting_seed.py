from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.workflows import factory_leadership as flow
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork, HumanTask
from tests import railway_leadership_live_drafting_seed as seed
from tests.helpers import rev


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.scoped.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                           seed.GUARD: '1', 'PGDATABASE': 'synthetic-preview'})
class LeadershipLiveDraftingSeedTests(TestCase):
    def test_reader_sees_exact_live_lease_then_native_draft_waits_for_separate_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user('psl-agent-trial')
        previous = Case.objects.create(pk=seed.scoped.HOME_ID, tenant=seed.scoped.TENANT, title=seed.scoped.HOME_TITLE,
                                       kind='project', synthetic=True)
        original_revision = rev(previous)
        original_grant = Grant.objects.create(case=previous, user=trial, action='case.read')
        with patch.dict('os.environ', {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'live leadership drafting fixture guard'):
                seed.prepare()
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
        sample = seed.prepare()
        self.assertEqual(seed.prepare(), sample | {'preserved': True})
        work = FactoryWork.objects.get(pk=sample['work'])
        case = work.case
        self.assertEqual((work.plan_revision, work.fence), (1, 1))
        self.assertFalse(flow.document(work))
        self.assertEqual(set(Grant.objects.filter(case=case, user=trial).values_list('action', flat=True)),
                         {'case.read', 'report.read', 'meeting.read', 'factory.read'})
        self.client.force_login(trial)
        label = 'Drafting the leadership report from the selected sources.'
        self.assertNotContains(self.client.get(sample['path']), label)
        self.assertNotContains(self.client.get(sample['path']), 'Continue eligible work')

        def inspect_claim(seconds):
            self.assertEqual(seconds, seed.WINDOW_SECONDS)
            work.refresh_from_db()
            claim = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03',
                                               phase='started', fence=work.fence)
            self.assertFalse(claim.activity.attempts.filter(number=claim.number, phase='observed').exists())
            active = self.client.get(sample['path'])
            self.assertContains(active, label)
            self.assertContains(active, '2 projects were checked')
            self.assertNotContains(active, 'Approve exact report')
            self.assertNotContains(self.client.get(reverse('factory_invoice_decision', args=[work.pk])), label)
            self.assertIsNone(flow.document(work))
            self.assertFalse(Publication.objects.filter(factory_work=work).exists())

        with patch.object(seed, 'sleep', side_effect=inspect_claim) as live:
            result = seed.observe(work.pk)
        live.assert_called_once_with(seed.WINDOW_SECONDS)
        work.refresh_from_db()
        report = flow.document(work)
        self.assertEqual(result['report'], report.pk)
        self.assertEqual(report.audience, 'internal')
        self.assertEqual(report.created_by.username, seed.SPONSOR)
        task = HumanTask.objects.get(pk=result['review'], version=report, status='open', required_role='PMO Lead')
        self.assertIsNone(task.claimed_by)
        self.assertFalse(report.reviews.exists())
        after = self.client.get(sample['path'])
        self.assertNotContains(after, label)
        self.assertNotContains(after, 'Approve exact report')
        reviewer = get_user_model().objects.get(username=seed.REVIEWER)
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(reverse('factory_invoice_decision', args=[work.pk])), 'Approve exact report')
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__factory_work=work).exists())
        with self.assertRaisesMessage(RuntimeError, 'fresh specimen'):
            seed.observe(work.pk)
        self.assertEqual(Audit.objects.filter(case=case, action=seed.OBSERVATION).count(), 1)
        self.assertEqual(seed.prepare(), sample | {'preserved': True})
        self.assertEqual(rev(previous), original_revision)
        self.assertEqual(list(Grant.objects.filter(case=previous).values_list('pk', flat=True)), [original_grant.pk])
        self.assertFalse(Audit.objects.filter(case=previous).exists())
