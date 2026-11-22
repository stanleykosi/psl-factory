"""The native Commercial route preserves an independently recorded portal and outcome."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Case
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo.models import Baseline, RFPDisposition, RFPOutcome, RFPPortalReceipt, RFPSubmission
from apps.workflows import factory_progress, factory_rfp
from apps.workflows.models import FactoryProgress, FactoryWork
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PORTAL_REFERENCE, RECORDER_ACTIONS, prepare


class IndependentCommercialRecordingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.recorder = users.create_user(username='sample-independent-bid-recorder')
        cls.reader = users.create_user(username='sample-independent-bid-reader')
        cls.sample = prepare(cls.recorder)
        cls.case = Case.objects.get(pk=cls.sample['case'])
        Grant.objects.bulk_create([Grant(case=cls.case, user=cls.reader, action=action)
                                   for action in sorted(RECORDER_ACTIONS)])

    def portal_command(self, key):
        return {'action': 'portal_receipt', 'target': self.sample['version'], 'case_revision': rev(self.case),
            'evidence': self.sample['sources'][key], 'note': 'Checked the exact fictional portal pack and receipt.'}

    def outcome_command(self, submission, role='Client'):
        work = FactoryWork.objects.get(pk=self.sample['work'])
        return {'action': 'outcome', 'target': submission.pk, 'revision': work.revision, 'case_revision': rev(self.case),
            'verdict': 'won', 'role': role, 'observed_at': timezone.now().isoformat(),
            'evidence': self.sample['sources']['award'], 'note': 'Observed fictional award for the exact received pack.'}

    def test_original_maker_independent_portal_recorder_and_verified_route(self):
        self.assertEqual(connection.vendor, 'postgresql')
        work = FactoryWork.objects.get(pk=self.sample['work'])
        maker = work.actor
        self.assertNotEqual(maker.pk, self.recorder.pk)
        self.assertEqual(set(Grant.objects.filter(case=self.case, user=self.recorder, active=True)
                             .values_list('action', flat=True)), RECORDER_ACTIONS)
        self.assertFalse(self.recorder.has_usable_password())
        self.assertFalse(Grant.objects.filter(user=self.recorder).exclude(case=self.case).exists())
        self.assertFalse(RFPSubmission.objects.filter(version_id=self.sample['version']).exists())

        factory_progress.run_once()
        progress = FactoryProgress.objects.get(work=work)
        self.assertEqual(progress.requested_by_id, maker.pk)
        self.assertEqual(progress.status, 'waiting')

        url = self.sample['path']
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(url, self.portal_command('portal')).status_code, 403)
        self.assertFalse(RFPPortalReceipt.objects.filter(submission__version_id=self.sample['version']).exists())
        self.client.force_login(self.recorder)
        self.assertContains(self.client.get(url), 'Record original client portal receipt')
        self.assertContains(self.client.post(url, self.portal_command('wrong_portal')),
                            'matching the exact approved pack')
        self.assertFalse(RFPPortalReceipt.objects.filter(submission__version_id=self.sample['version']).exists())
        self.assertEqual(self.client.post(url, self.portal_command('portal')).status_code, 302)
        submission = RFPSubmission.objects.get(version_id=self.sample['version'])
        receipt = submission.portal_receipt
        self.assertEqual((receipt.actor_id, receipt.review.actor_id), (self.recorder.pk, maker.pk))
        self.assertEqual(receipt.evidence_id, self.sample['sources']['portal'])
        self.assertEqual(receipt.reference, PORTAL_REFERENCE)
        self.assertEqual(submission.response.actor_id, maker.pk)
        self.assertEqual(submission.actor_id, self.recorder.pk)
        self.assertContains(self.client.get(url), PORTAL_REFERENCE)

        self.client.force_login(maker)
        self.assertNotContains(self.client.get(url), 'Record evidenced outcome')
        self.assertEqual(self.client.post(url, self.outcome_command(submission)).status_code, 403)
        self.assertFalse(submission.outcomes.exists())
        self.client.force_login(self.recorder)
        self.assertEqual(self.client.post(url, self.outcome_command(submission, role='PM')).status_code, 403)
        self.assertEqual(self.client.post(url, self.outcome_command(submission)).status_code, 302)
        outcome = RFPOutcome.objects.get(submission=submission)
        self.assertEqual((outcome.actor_id, outcome.role), (self.recorder.pk, 'Client'))
        self.assertIsNone(outcome.award_amount)
        progress.refresh_from_db()
        self.assertLessEqual(progress.available_at, timezone.now())
        for _ in range(5):
            if not factory_progress.run_once():
                break
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(factory_rfp.verify(work)['portal_receipt'], receipt.pk)
        disposition = RFPDisposition.objects.get(outcome=outcome)
        self.assertEqual((disposition.kind, disposition.actor_id), ('route_a', maker.pk))
        self.assertFalse(Publication.objects.filter(version=submission.version).exists())
        self.assertFalse(Baseline.objects.filter(case=self.case).exists())
        self.assertTrue(prepare(self.recorder)['existing_work_preserved'])
        self.assertEqual(RFPPortalReceipt.objects.filter(submission__version_id=self.sample['version']).count(), 1)
