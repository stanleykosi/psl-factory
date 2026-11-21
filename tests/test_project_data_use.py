from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.agents import assistant, assistant_access
from apps.core.services import add_evidence
from apps.policy.services import transition
from tests.helpers import activate, setup_case


class ProjectAssistantAccessTests(TestCase):
    @patch.dict('os.environ', {'OPENROUTER_MODEL': 'reviewed-test-model'})
    def test_payroll_totals_do_not_authorise_model_use_of_payroll_report_metadata(self):
        from apps.identity.models import Grant
        actor, case = setup_case(username='local-payroll-disclosure', synthetic=False)
        Grant.objects.get_or_create(user=actor, case=case, action='agent.extract')
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Approved record categories', 'isolated-test')
        chat = assistant.AssistantConversation.objects.create(actor=actor, case=case, persona='zainab')
        rule = {'personas':['zainab'], 'provider':'openrouter', 'model':'reviewed-test-model',
                'sources':['meeting'], 'send_user_question':True}
        activate(actor, case, assistant_access.CHAT, rule, proof)
        self.assertEqual(assistant.payroll_questions_for(chat), (assistant.TOTALS_QUESTION,))
        activate(actor, case, assistant_access.CHAT, dict(rule, sources=['payroll_report']), proof)
        self.assertIn(assistant.PAYROLL_REPORT_QUESTIONS[0], assistant.payroll_questions_for(chat))

    @patch.dict('os.environ', {'OPENROUTER_MODEL': 'reviewed-test-model'})
    def test_restricted_project_and_model_need_a_current_project_decision(self):
        actor, case = setup_case(username='project-use-check', synthetic=False)
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Test owner decision', 'isolated-test')
        self.assertFalse(assistant.cases_for(actor, 'tola').filter(pk=case.pk).exists())
        value = {'personas':['tola'], 'provider':'openrouter', 'model':'reviewed-test-model',
                 'sources':['meeting'], 'send_user_question':True}
        config = activate(actor, case, assistant_access.CHAT, value, proof)
        self.assertTrue(assistant.cases_for(actor, 'tola').filter(pk=case.pk).exists())
        chat = assistant.AssistantConversation.objects.create(actor=actor, case=case, persona='tola')
        rows = [{'record':{'field':field}} for field in ['meeting', 'payroll_report']]
        self.assertEqual(assistant_access.project_sources(chat, rows), [dict(rows[0], permission_version=config.pk)])
        self.client.force_login(actor)
        self.assertContains(self.client.get(reverse('project_data_use', args=[case.pk]) + '?rule=' + assistant_access.CHAT),
                            'Exact approved OpenRouter model')
        transition(actor, config.pk, 'revoked')
        self.assertFalse(assistant.cases_for(actor, 'tola').filter(pk=case.pk).exists())
