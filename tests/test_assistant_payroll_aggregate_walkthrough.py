from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.core.models import Case
from apps.finance.payroll_models import PayrollPublication, PayrollReportReceipt
from apps.finance.payroll_question_models import PayrollReportQuestion
from apps.identity.models import Grant
from tests import railway_assistant_payroll_aggregate_seed as seed
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
class AssistantPayrollAggregateWalkthroughTests(TestCase):
    def test_fixture_preserves_one_received_report_and_leaves_the_assistant_empty(self):
        trial = get_user_model().objects.create_user('psl-agent-trial')
        separate = Case.objects.create(tenant='fixture-unchanged', title='Unrelated test case', kind='project', synthetic=True)
        Grant.objects.create(case=separate, user=trial, action='case.read')
        grants = Grant.objects.filter(user=trial)
        original_grants = set(grants.values_list('case_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())

        with patch('adapters.openrouter.answer') as provider:
            sample = seed.prepare()
            self.assertEqual(seed.prepare(), dict(sample, preserved=True))
            case = Case.objects.get(pk=sample['case'], synthetic=True)
            self.assertEqual(set(grants.exclude(case=case).values_list('case_id', 'action', 'active')), original_grants)
            self.assertEqual(set(grants.filter(case=case, active=True).values_list('action', flat=True)),
                             set(seed.RECIPIENT_ACTIONS))
            self.assertFalse(AssistantConversation.objects.filter(case=case).exists())
            self.assertFalse(PayrollReportQuestion.objects.filter(case=case).exists())
            report = PayrollPublication.objects.get(request__case=case)
            self.assertEqual(report.pk, sample['report'])
            self.assertNotEqual(report.actor_id, trial.pk)
            receipt = PayrollReportReceipt.objects.get(publication=report, actor=trial)
            self.assertEqual(receipt.pk, sample['receipt'])
            self.assertEqual(report.payload['disclosure'], 'aggregate_only')

            self.client.force_login(trial)
            start = self.client.get(sample['assistant_path'])
            self.assertEqual(start.context['form'].initial['workspace'], case.pk)
            key = uuid4()
            thread = reverse('assistant_thread', args=[key])
            self.assertRedirects(self.client.post(sample['assistant_path'], {'workspace': case.pk, 'key': key}), thread)
            page = self.client.get(thread)
            self.assertContains(page, 'Ask about your staff-cost report')
            self.assertContains(page, f'Reviewed staff-cost report {report.pk}')
            self.assertNotContains(page, 'PRIVATE-ZAINAB-SAMPLE-001')
            self.assertNotContains(page, sample['total'])
            self.assertFalse(AssistantTurn.objects.filter(conversation_id=key).exists())
            local_report = self.client.get(sample['report_path'])
            self.assertContains(local_report, sample['total'])
            self.assertNotContains(local_report, 'PRIVATE-ZAINAB-SAMPLE-001')
            self.assertContains(local_report, 'Ask HR a question')

            Grant.objects.filter(case=case, user_id=sample['publisher'], action='payroll.publish').update(active=False)
            with self.assertRaises(RuntimeError):
                seed.prepare()
            conversation = AssistantConversation.objects.get(pk=key)
            self.assertEqual(assistant.tool_context(conversation), ([], []))
            self.assertEqual(PayrollReportReceipt.objects.get(publication=report, actor=trial).pk, receipt.pk)
            self.assertFalse(AssistantTurn.objects.filter(conversation_id=key).exists())
            provider.assert_not_called()
