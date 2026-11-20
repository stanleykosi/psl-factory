"""Exercise distinct synthetic schedule follow-up cases through their native forms."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.finance import analysis, schedules
from apps.finance.models import FinanceAdjustment, FinanceRun, ScheduleWork
from apps.workflows.models import FactoryWork
from tests import railway_schedule_followup_seed as seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1'}


@patch.dict('os.environ', ENVIRONMENT)
class ScheduleFollowupWalkthroughTests(TestCase):
    def setUp(self):
        self.reviewer = get_user_model().objects.create_user('psl-agent-trial')
        self.client.force_login(self.reviewer)

    def test_export_stops_at_receiving_finance_review_and_maps_only_after_approval(self):
        sample = seed.prepare('receiving-adjustment')
        prior = seed.prepare('receiving-adjustment')
        self.assertTrue(prior['existing_work_preserved'])
        self.assertEqual(prior['adjustment'], sample['adjustment'])
        adjustment = FinanceAdjustment.objects.get(pk=sample['adjustment'])
        self.assertNotEqual(adjustment.actor_id, self.reviewer.pk)
        self.assertFalse(analysis.current_review(adjustment.source.case, 'adjustment', adjustment=adjustment)['valid'])

        path = sample['analysis_path']
        self.assertContains(self.client.get(path), 'Record configured Finance review')
        mapping = {'action': 'map', 'source': sample['finance_source'], 'adjustments': [adjustment.pk]}
        response = self.client.post(path, dict(mapping, revision=rev(adjustment.source.case)))
        self.assertContains(response, 'Selected reporting adjustment needs current configured human review', status_code=200)
        review = {'action': 'review', 'purpose': 'adjustment', 'adjustment': adjustment.pk, 'role': 'Finance',
                  'verdict': 'approve', 'evidence': sample['review_evidence'], 'revision': rev(adjustment.source.case),
                  'note': 'Separately accepted the exact reporting adjustment.'}
        self.assertRedirects(self.client.post(path, review), path, fetch_redirect_response=False)
        decision = adjustment.financereview_set.get()
        self.assertEqual(decision.actor_id, self.reviewer.pk)
        self.assertRedirects(self.client.post(path, dict(mapping, revision=rev(adjustment.source.case))), path,
                             fetch_redirect_response=False)
        result = FinanceRun.objects.get(case_id=sample['case'], kind='mapping', request__adjustment_ids=[adjustment.pk])
        self.assertFalse(result.result['ledger_posted'])

    def test_exact_approval_withdrawal_holds_report_and_restores_the_same_schedule(self):
        sample = seed.prepare('restore-approval')
        work = FactoryWork.objects.get(pk=sample['work'])
        schedule = ScheduleWork.objects.get(pk=sample['schedule'])
        self.assertNotEqual(schedule.actor_id, self.reviewer.pk)
        prior = schedules.approved(schedule)
        path = sample['decision_path']
        self.assertContains(self.client.get(path), 'Withdraw approval')
        self.assertContains(self.client.get(sample['recovery_path']), 'Export reviewed reporting adjustment')
        command = {'action': 'review', 'target': schedule.pk, 'evidence': sample['review_evidence'],
                   'revision': work.revision, 'note': 'Synthetic withdrawal retained for separate restoration.'}
        response = self.client.post(path, dict(command, verdict='revoke', case_revision=rev(work.case)))
        self.assertRedirects(response, path, fetch_redirect_response=False)
        self.assertContains(self.client.get(path), 'Restore exact approval')
        self.assertNotContains(self.client.get(sample['recovery_path']), 'Export reviewed reporting adjustment')
        self.assertEqual(self.client.get(sample['report_path']).status_code, 409)
        with self.assertRaisesMessage(ValidationError, 'Current exact human approval required'):
            schedules.approved(schedule)
        response = self.client.post(path, dict(command, verdict='approve', case_revision=rev(work.case),
                                              note='Restored the same selected original schedule.'))
        self.assertRedirects(response, path, fetch_redirect_response=False)
        current = schedules.approved(schedule)
        self.assertNotEqual(current.pk, prior.pk)
        self.assertEqual(list(schedule.reviews.order_by('pk').values_list('verdict', flat=True)),
                         ['approve', 'revoke', 'approve'])
        self.assertEqual(self.client.get(sample['report_path']).status_code, 200)
