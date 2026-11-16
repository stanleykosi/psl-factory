import os
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.documents.contracts import digest
from apps.identity.models import Grant
from tests.factory_helpers import fixture
from tests.helpers import setup_case


@patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
class DepartmentAssistantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        data = fixture(username='department-assistant')
        cls.actor, cls.case = data['actor'], data['case']
        cls.work = data['work']
        cls.other, cls.other_case = setup_case(username='other-assistant')

    def start(self, persona):
        key = uuid4()
        url = reverse('assistant_start', args=[persona])
        response = self.client.post(url, {'workspace': self.case.pk, 'key': key})
        self.assertRedirects(response, reverse('assistant_thread', args=[key]), fetch_redirect_response=False)
        return AssistantConversation.objects.get(pk=key)

    def test_authorized_finance_answer_links_to_native_intake_and_replays(self):
        self.client.force_login(self.actor)
        conversation = self.start('chidi')
        url = reverse('assistant_thread', args=[conversation.pk])
        key = uuid4()
        message = {'key': key, 'question': 'Can I prepare an invoice for the milestone?'}
        for _ in range(2):
            self.assertRedirects(self.client.post(url, message), url, fetch_redirect_response=False)
        self.assertEqual(conversation.turns.count(), 1)
        self.assertContains(self.client.get(url), 'Question queued')
        reply = {'answer': 'Finance has a milestone handoff. Choose the exact source for invoice preparation.',
                 'citations': ['S2'], 'next_work': 'pmo-finance/v1'}
        with patch('adapters.openrouter.answer', return_value=reply) as model:
            self.assertTrue(assistant.worker_once())
            self.assertFalse(assistant.worker_once())
            model.assert_called_once()
            self.assertIn('pmo-finance/v1', model.call_args.args[4])
        turn = AssistantTurn.objects.get(pk=key)
        self.assertEqual(turn.status, 'answered')
        response = self.client.get(url)
        self.assertContains(response, 'Records checked')
        self.assertContains(response, 'Edit draft')
        next_url = response.context['turns'][0].next_url
        intake = self.client.get(next_url)
        self.assertContains(intake, 'Invoice reference')
        self.assertEqual(intake.context['form'].initial['handoff'], self.work.request['handoff'])
        self.case.refresh_from_db()
        fields = {'key': key, 'assistant_turn': key, 'case': self.case.pk, 'revision': self.case.revision,
                  'reference': self.work.request['reference'], 'mode': 'completion',
                  'coverage': self.work.request['coverage'], 'handoff': self.work.request['handoff']}
        first = dict(fields, reference='DRAFT-ONE', action='save_draft')
        self.assertRedirects(self.client.post(next_url, first), next_url, fetch_redirect_response=False)
        self.assertContains(self.client.get(next_url), 'DRAFT-ONE')
        second = dict(fields, draft_version=1, action='save_draft')
        for _ in range(2):
            self.assertRedirects(self.client.post(next_url, second), next_url, fetch_redirect_response=False)
        self.assertEqual(list(turn.draft_versions.order_by('number').values_list('number', flat=True)), [1, 2])
        self.assertContains(self.client.post(next_url, dict(first, reference='STALE-DRAFT')),
                            'A newer draft is available')
        self.assertContains(self.client.post(next_url, dict(fields, draft_version=2, reference='UNSAVED')),
                            'Save your current draft')
        fields.update(draft_version=2, background='on')
        for _ in range(2):
            self.assertRedirects(self.client.post(next_url, fields), reverse('factory_detail', args=[self.work.pk]),
                                 fetch_redirect_response=False)
        turn.refresh_from_db()
        self.assertEqual(turn.started_work_id, self.work.pk)
        self.assertEqual(turn.started_draft.number, 2)
        self.assertEqual(self.work.background_progress.status, 'queued')
        self.assertContains(self.client.get(url), 'Open the work item')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_personas_check_current_scope_and_hold_invalid_provider_output(self):
        self.client.force_login(self.actor)
        for persona in ('tola', 'zainab'):
            conversation = self.start(persona)
            key = uuid4()
            assistant.reserve(self.actor, conversation.pk, key, 'Which records are available to me?')
            with patch('adapters.openrouter.answer', return_value={
                'answer': 'Invalid reference', 'citations': ['S999'], 'next_work': '',
            }):
                self.assertTrue(assistant.worker_once())
            self.assertEqual(AssistantTurn.objects.get(pk=key).status, 'held')
        finance = self.start('chidi')
        key = uuid4()
        assistant.reserve(self.actor, finance.pk, key, 'What can I see?')
        Grant.objects.filter(case=self.case, user=self.actor, action='finance.read').update(active=False)
        with patch('adapters.openrouter.answer') as model:
            self.assertTrue(assistant.worker_once())
            model.assert_not_called()
        self.assertEqual(AssistantTurn.objects.get(pk=key).status, 'held')
        self.assertEqual(self.client.get(reverse('assistant_thread', args=[finance.pk])).status_code, 404)

    def test_department_transfer_is_confirmed_and_uses_its_own_sources(self):
        self.client.force_login(self.actor)
        conversation = self.start('tola')
        key = uuid4()
        question = 'Which milestone can Finance invoice?'
        assistant.reserve(self.actor, conversation.pk, key, question)
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'Ask Finance for the milestone handoff.', 'citations': ['S1'], 'next_work': 'assistant:chidi',
        }):
            self.assertTrue(assistant.worker_once())
        transfer_url = reverse('assistant_transfer', args=[key, 'chidi'])
        self.assertContains(self.client.get(reverse('assistant_thread', args=[conversation.pk])), 'Ask Chidi instead')
        self.assertEqual(self.client.get(transfer_url).status_code, 405)
        outcome = self.client.post(transfer_url)
        self.assertEqual(self.client.post(transfer_url).url, outcome.url)
        target = AssistantConversation.objects.get(persona='chidi')
        self.assertEqual(target.turns.get().question, question)
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'Finance has a milestone handoff.', 'citations': ['S2'], 'next_work': 'pmo-finance/v1',
        }) as model:
            self.assertTrue(assistant.worker_once())
            self.assertEqual(model.call_args.args[1], 'Finance')
            self.assertEqual(model.call_args.args[5], [])
        self.assertEqual(target.turns.get().status, 'answered')

    def test_focused_question_transmits_only_selected_current_record(self):
        self.client.force_login(self.actor)
        conversation = self.start('chidi')
        sources, _ = assistant.tool_context(conversation)
        handoff = next(source for source in sources if source.get('record', {}).get('field') == 'handoff')
        url = reverse('assistant_thread', args=[conversation.pk])
        key = uuid4()
        data = {'question': 'What does this source prove?', 'key': key, 'focus': digest(handoff)}
        self.assertContains(self.client.post(url, dict(data, focus='f' * 64)), 'Select a valid choice')
        self.assertRedirects(self.client.post(url, data), url, fetch_redirect_response=False)
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'The selected completion was received.', 'citations': ['S1'], 'next_work': '',
        }) as model:
            self.assertTrue(assistant.worker_once())
            self.assertEqual(len(model.call_args.args[3]), 1)
            self.assertEqual(model.call_args.args[3][0]['label'], 'Milestone handoff')
        self.assertEqual(AssistantTurn.objects.get(pk=key).sources, [handoff])

    def test_confirmation_cannot_link_a_different_existing_planning_request(self):
        from tests.test_factory_planning import setup

        planning = setup(configured=False, department_configured=False)
        actor, case, packet, work = (planning[key] for key in ('a', 'c', 'packet', 'work'))
        self.client.force_login(actor)
        conversation = AssistantConversation.objects.create(actor=actor, case=case, persona='tola')
        source = next(item for item in assistant.tool_context(conversation)[0] if item.get('record'))
        key = uuid4()
        assistant.reserve(actor, conversation.pk, key, 'Prepare Planning', digest(source))
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'The selected packet is available.', 'citations': ['S1'], 'next_work': 'planning/v1',
        }):
            self.assertTrue(assistant.worker_once())
        thread = self.client.get(reverse('assistant_thread', args=[conversation.pk]))
        intake = thread.context['turns'][0].next_url
        case.refresh_from_db()
        data = {'definition': 'planning/v1', 'key': key, 'assistant_turn': key, 'case': case.pk, 'packet': packet.pk,
                'reference': 'DIFFERENT-PLAN', 'revision': case.revision}
        self.assertContains(self.client.post(intake, data), 'Planning work already exists with different intake details')
        turn = AssistantTurn.objects.get(pk=key)
        self.assertIsNone(turn.started_work_id)
        self.assertFalse(turn.draft_versions.exists())
        self.assertRedirects(self.client.post(intake, dict(data, reference=work.request['reference'])),
                             reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
