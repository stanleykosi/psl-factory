from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse

from apps.core.models import Audit, Case, Evidence
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.pmo.models import MinutesReportBinding
from apps.workflows import factory_reporting as weekly
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork, HumanTask
from tests import railway_weekly_live_drafting_seed as seed
from tests.helpers import rev


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.prior.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                           seed.GUARD: '1', 'PGDATABASE': 'isolated-preview'})
class WeeklyLiveDraftingSeedTests(TransactionTestCase):
    def test_committed_assembly_claim_shows_current_scoped_sources_then_waits_for_independent_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user('psl-agent-trial')
        prior = Case.objects.create(pk=uuid5(NAMESPACE_URL, 'sample-existing-weekly-return'),
                                   tenant=seed.prior.TENANT, title=seed.prior.TITLE, kind='project', synthetic=True)
        original_revision = rev(prior)
        original_grant = Grant.objects.create(case=prior, user=trial, action='case.read')
        with patch.dict('os.environ', {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'weekly live drafting fixture guard'):
                seed.prepare()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        sample = seed.prepare()
        self.assertEqual(seed.prepare(), sample | {'preserved': True})
        work = FactoryWork.objects.get(pk=sample['work'])
        self.assertEqual((work.plan_revision, work.fence), (1, 1))
        self.assertEqual(set(Grant.objects.filter(case=work.case, user=trial).values_list('action', flat=True)),
                         set(seed.prior.READ))
        with self.assertRaises(FactoryWork.DoesNotExist):
            seed.observe(work.pk + 1)
        self.assertFalse(Audit.objects.filter(case=work.case, action=seed.OBSERVATION).exists())
        self.assertFalse(weekly.document(work))
        self.client.force_login(trial)
        label = 'Assembling the weekly report'
        review_path = reverse('factory_invoice_decision', args=[work.pk])
        self.assertNotContains(self.client.get(sample['path']), label)
        self.assertNotContains(self.client.get(sample['path']), 'Continue eligible work')

        def inspect_claim(seconds):
            self.assertEqual(seconds, seed.WINDOW)
            self.assertFalse(connection.in_atomic_block)
            work.refresh_from_db()
            claim = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03',
                                               phase='started', fence=work.fence)
            self.assertFalse(claim.activity.attempts.filter(number=claim.number, phase='observed').exists())
            active = self.client.get(sample['path'])
            self.assertContains(active, label)
            self.assertContains(active, 'Selected week')
            self.assertContains(active, '4 meetings')
            self.assertContains(active, seed.TEMPLATE)
            self.assertContains(active, 'Using the four supplied sections with their cited records.')
            self.assertContains(active, 'data-work-watch')
            self.assertNotContains(active, 'Approve exact report')
            self.assertEqual(active.context['row']['reporting']['progress']['started_at'], claim.created_at)
            self.assertNotContains(self.client.get(review_path), label)
            self.assertFalse(weekly.document(work))
            self.assertFalse(Publication.objects.filter(factory_work=work).exists())
            visibility = Grant.objects.filter(case=work.case, user=trial, action='meeting.read')
            visibility.update(active=False)
            self.assertEqual(self.client.get(sample['path']).status_code, 403)
            visibility.update(active=True)

        with patch.object(seed, 'sleep', side_effect=inspect_claim) as live:
            result = seed.observe(work.pk)
        live.assert_called_once_with(seed.WINDOW)
        work.refresh_from_db()
        report = weekly.document(work)
        self.assertEqual(result['report'], report.pk)
        self.assertEqual((report.audience, report.created_by.username), ('client', seed.MAKER))
        binding = MinutesReportBinding.objects.get(version=report)
        self.assertEqual((binding.report.start_at.isoformat(), binding.report.end_at.isoformat()),
                         (sample['inputs']['start_at'], sample['inputs']['end_at']))
        citation_ids = {pk for item in sample['sections'].values() for pk in item['evidence_ids']}
        self.assertEqual(set(Evidence.objects.filter(case=work.case, pk__in=citation_ids).values_list('pk', flat=True)),
                         citation_ids)
        self.assertEqual({key: report.fields[key]['text'] for key in sample['sections']},
                         {key: item['text'] for key, item in sample['sections'].items()})
        review = HumanTask.objects.get(pk=result['review'], version=report, status='open', required_role='PMO Lead')
        self.assertIsNone(review.claimed_by)
        self.assertFalse(report.reviews.exists())
        self.assertEqual(FactoryAttempt.objects.filter(activity__work=work, activity__kind=seed.STEP, phase='observed').count(), 1)
        settled = self.client.get(sample['path'])
        self.assertNotContains(settled, label)
        self.assertContains(settled, 'Weekly client report')
        self.assertContains(settled, 'No receipt recorded for this exact report.')
        self.assertNotContains(self.client.get(review_path), 'Approve exact report')
        self.client.force_login(get_user_model().objects.get(pk=sample['reviewer']))
        self.assertContains(self.client.get(review_path), 'Approve exact report')
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__factory_work=work).exists())
        with self.assertRaisesMessage(RuntimeError, 'fresh weekly specimen'):
            seed.observe(work.pk)
        original = (work.revision, work.fence, report.pk, review.pk)
        directed = seed.prepare('directed')
        self.assertEqual(directed['case'], str(seed.specimen('directed').case_id))
        self.assertNotEqual(directed['case'], sample['case'])
        self.assertNotEqual(directed['source'], sample['source'])
        self.assertEqual(seed.prepare('directed'), directed | {'preserved': True})
        with self.assertRaises(FactoryWork.DoesNotExist):
            seed.observe(work.pk, 'directed')
        with self.assertRaises(FactoryWork.DoesNotExist):
            seed.observe(directed['work'])
        self.client.force_login(trial)
        with patch.object(seed, 'sleep', side_effect=lambda _: self.assertContains(self.client.get(directed['path']), label)):
            directed_result = seed.observe(directed['work'], 'directed')
        self.assertNotEqual(directed_result['report'], report.pk)
        self.assertFalse(Publication.objects.filter(factory_work_id=directed['work']).exists())
        work.refresh_from_db()
        self.assertEqual((work.revision, work.fence, weekly.document(work).pk,
                          HumanTask.objects.get(version=report, status='open').pk), original)
        self.assertEqual(rev(prior), original_revision)
        self.assertEqual(list(Grant.objects.filter(case=prior).values_list('pk', flat=True)), [original_grant.pk])
        self.assertFalse(Audit.objects.filter(case=prior).exists())
