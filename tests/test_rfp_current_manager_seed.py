from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Case
from apps.documents.models import Publication
from apps.pmo import rfp_followup, rfp_messages
from apps.pmo.models import RFPFollowupDispatch, RFPFollowupReceipt, RFPSubmission
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.railway_rfp_current_manager_seed import prepare


class CurrentManagerWalkthroughTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(username='sample-bid-current-manager-recorder')
        cls.samples = {scenario: prepare(cls.manager, scenario) for scenario in ('reminder', 'message')}

    def outcome(self, sample, at, *, remind_at=None):
        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        command = {'action': 'outcome', 'target': sample['submission'], 'revision': work.revision,
            'case_revision': work.case.revision, 'verdict': 'unknown', 'role': 'Client',
            'observed_at': at.isoformat(), 'note': 'No reply to this exact fictional submission.'}
        if remind_at is not None:
            command['remind_at'] = remind_at.isoformat()
        return self.client.post(sample['path'], command)

    def test_prepares_two_distinct_approved_portal_receipts_without_customer_effects(self):
        self.assertEqual(connection.vendor, 'postgresql')
        for scenario, sample in self.samples.items():
            self.assertFalse(sample['preserved'])
            self.assertNotEqual(sample['maker'], self.manager.pk)
            self.assertEqual(sample['manager'], self.manager.pk)
            self.assertEqual(sample['outcomes'], [])
            self.assertEqual(sample['followups'], [])
            submission = RFPSubmission.objects.get(pk=sample['submission'])
            self.assertEqual(submission.actor_id, sample['maker'])
            self.assertEqual(submission.portal_receipt.reference, sample['portal_reference'])
            self.assertFalse(Publication.objects.filter(version_id=submission.version_id).exists())
            again = prepare(self.manager, scenario)
            self.assertEqual(again, {**sample, 'preserved': True})
        self.assertNotEqual(self.samples['reminder']['case'], self.samples['message']['case'])

    def test_current_manager_changes_exact_reminder_and_old_manager_sees_none(self):
        sample = self.samples['reminder']
        observed = timezone.now()
        original_at = observed + timedelta(minutes=2)
        revised_at = observed + timedelta(minutes=5)
        previous = get_user_model().objects.get(pk=sample['maker'])
        self.client.force_login(previous)
        self.assertNotContains(self.client.get(sample['path']), 'Record evidenced outcome')
        self.assertEqual(self.outcome(sample, observed, remind_at=original_at).status_code, 403)

        self.client.force_login(self.manager)
        self.assertContains(self.client.get(sample['path']), 'Record evidenced outcome')
        self.assertEqual(self.outcome(sample, observed, remind_at=original_at).status_code, 302)
        self.assertEqual(self.outcome(sample, observed, remind_at=revised_at).status_code, 302)
        submission = RFPSubmission.objects.get(pk=sample['submission'])
        self.assertEqual(list(submission.outcomes.order_by('pk').values_list('actor_id', 'remind_at')),
                         [(self.manager.pk, original_at), (self.manager.pk, revised_at)])

        def alerts():
            page = self.client.get(sample['alerts'], {'q': sample['reference']})
            self.assertEqual(page.status_code, 200)
            return {(row['label'], row['subject'], row['detail']) for row in page.context['rows']}

        reminder = ('Bid follow-up due', sample['reference'], timezone.localtime(revised_at).strftime('%d %b %Y %H:%M:%S %Z'))
        with patch('apps.pmo.rfp_followup.timezone.now', return_value=original_at):
            early = alerts()
            self.assertIn(('Assigned RFP coordination', Case.objects.get(pk=sample['case']).title, sample['reference']), early)
            self.assertFalse(any(label == 'Bid follow-up due' for label, _, _ in early))
        with patch('apps.pmo.rfp_followup.timezone.now', return_value=revised_at):
            self.assertIn(reminder, alerts())
            self.client.force_login(previous)
            self.assertFalse(any(label == 'Bid follow-up due' for label, _, _ in alerts()))
        self.assertFalse(RFPFollowupDispatch.objects.filter(outcome__submission=submission).exists())
        self.assertEqual(len(prepare(self.manager, 'reminder')['outcomes']), 2)

    def test_only_the_current_manager_completes_a_reviewed_sample_mailbox_delivery(self):
        sample = self.samples['message']
        case = Case.objects.get(pk=sample['case'])
        self.client.force_login(self.manager)
        self.assertEqual(self.outcome(sample, timezone.now()).status_code, 302)
        outcome = RFPSubmission.objects.get(pk=sample['submission']).outcomes.get()

        def action(action_name, **fields):
            return self.client.post(sample['path'], {'action': action_name, 'target': outcome.pk,
                'case_revision': rev(case), **fields})

        previous = get_user_model().objects.get(pk=sample['maker'])
        self.client.force_login(previous)
        self.assertNotContains(self.client.get(sample['path']), 'Prepare a follow-up draft')
        self.assertEqual(action('followup_draft').status_code, 403)
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(sample['path']), 'Prepare a follow-up draft')
        self.assertEqual(action('followup_draft').status_code, 302)
        run = rfp_followup.latest_run(self.manager, case, outcome)
        wording = 'SAMPLE, could you share an update on this fictional bid?'
        self.assertEqual(action('followup_review', run=run.pk, reviewed=0, text=wording).status_code, 302)
        review = rfp_followup.reviews(case, run).get()
        self.assertEqual(action('followup_send', reviewed=review.pk, route='customer_followup').status_code, 302)
        dispatch = RFPFollowupDispatch.objects.get(outcome=outcome)
        self.assertEqual((dispatch.actor_id, dispatch.route['mode'], dispatch.payload['recipient']),
                         (self.manager.pk, 'synthetic_mailbox', 'procurement@example.invalid'))
        self.assertEqual(dispatch.payload['body'], wording)
        self.assertTrue(rfp_messages.run_once(dispatch.pk))
        self.assertFalse(rfp_messages.run_once(dispatch.pk))
        self.assertEqual(RFPFollowupReceipt.objects.filter(dispatch=dispatch, delivered=True).count(), 1)
        page = self.client.get(sample['path'])
        self.assertContains(page, 'Delivery verified')
        self.assertContains(page, wording)
        self.assertNotContains(page, 'Release reviewed follow-up')
        self.assertEqual(prepare(self.manager, 'message')['followups'], [dispatch.pk])
