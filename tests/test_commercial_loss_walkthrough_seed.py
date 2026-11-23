"""The synthetic preparation stops before making the browser's loss decisions."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Case
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp_loss
from apps.pmo.models import ActionItem, RFPDisposition, RFPFollowupDispatch, RFPOutcome, RFPSubmission
from apps.policy.models import Configuration
from apps.policy.rfp_loss_validators import COMPONENT
from apps.policy.services import reference_values
from apps.workflows import factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests.helpers import rev
from tests.railway_commercial_loss_seed import DEBRIEF_REFERENCE, LESSON, RECORDER_ACTIONS, prepare


class CommercialLossWalkthroughSeedTests(TestCase):
    def test_pending_fixture_keeps_exact_sources_then_uses_only_native_human_actions(self):
        self.assertEqual(connection.vendor, 'postgresql')
        recorder = get_user_model().objects.create_user(username='sample-loss-browser-recorder')
        sample = prepare(recorder)
        case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'])
        submission = RFPSubmission.objects.get(pk=sample['submission'])
        pending = RFPOutcome.objects.get(submission=submission)
        self.assertEqual((pending.pk, pending.result, pending.actor_id), (sample['initial_pending'], 'pending', recorder.pk))
        self.assertEqual(submission.portal_receipt.pk, sample['receipt'])
        self.assertEqual(submission.response.actor_id, sample['maker'])
        self.assertEqual(set(Grant.objects.filter(case=case, user=recorder, active=True).values_list('action', flat=True)),
                         RECORDER_ACTIONS)
        self.assertFalse(Configuration.objects.filter(case=case, component=COMPONENT).exists())
        self.assertFalse(RFPDisposition.objects.filter(rfp__case=case).exists())
        debrief = rfp_loss.current_debriefs(recorder, case).get(pk=sample['debrief'])
        self.assertEqual((debrief.meeting.reference, debrief.evidence_id), (DEBRIEF_REFERENCE, sample['sources']['debrief']))
        self.assertEqual(FactoryProgress.objects.get(work=work).requested_by_id, sample['maker'])

        self.client.force_login(recorder)
        self.assertContains(self.client.get(sample['path']), 'Customer decision pending')
        self.assertNotContains(self.client.get(sample['path'], {'outcome': 'lost'}), 'name="loss_reason"')
        settings_url = sample['settings'].split('#', 1)[0]
        self.assertEqual(self.client.post(settings_url, {'action': 'draft_loss_catalog', 'loss-revision': rev(case),
            'loss-base': 0, 'loss-evidence': sample['sources']['catalog'], 'loss-names': '\n'.join(sample['reason_names'])}).status_code, 302)
        catalog = Configuration.objects.get(case=case, component=COMPONENT)
        for action in ['validated', 'active']:
            self.assertEqual(self.client.post(settings_url, {'action': action, 'configuration': catalog.pk}).status_code, 302)
        reason = reference_values(catalog)[0]['reasons'][0]
        work.refresh_from_db()
        self.assertEqual(self.client.post(sample['path'], {'action': 'outcome', 'revision': work.revision,
            'case_revision': rev(case), 'target': submission.pk, 'verdict': 'lost', 'role': 'Client',
            'observed_at': timezone.now().isoformat(), 'evidence': sample['sources']['loss'],
            'note': 'Recorded the exact fictional customer response.', 'loss_reason': reason['key'],
            'loss_catalog': catalog.pk, 'debrief_version': sample['debrief']}).status_code, 302)
        for _ in range(6):
            if not factory_progress.run_once():
                break
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        archive = RFPDisposition.objects.get(rfp__case=case)
        self.assertEqual((archive.kind, archive.lessons_id), ('loss_archive', sample['sources']['lessons']))
        self.assertEqual(archive.outcome.debrief_version_id, sample['debrief'])
        result = self.client.get(sample['path'])
        self.assertContains(result, LESSON)
        self.assertContains(result, 'Recorded debrief proof')
        self.assertTrue(prepare(recorder)['existing_work_preserved'])
        self.assertEqual(RFPOutcome.objects.filter(submission=submission).count(), 2)
        self.assertFalse(ActionItem.objects.filter(case=case).exists())
        self.assertFalse(RFPFollowupDispatch.objects.filter(outcome__submission=submission).exists())
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())
