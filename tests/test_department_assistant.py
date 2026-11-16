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

    def test_conversation_replays_the_same_two_selected_records_and_hides_revoked_sources(self):
        self.client.force_login(self.actor)
        conversation = self.start('tola')
        url = reverse('assistant_thread', args=[conversation.pk])
        sources, _ = assistant.tool_context(conversation)
        selected = [item for item in sources if item['label'] in ['Workspace', 'Commercial requirements']]
        self.assertEqual(len(selected), 2)
        focus = [digest(item) for item in selected]
        message = {'key': uuid4(), 'question': 'Use both selected sources', 'focus': focus}
        self.assertRedirects(self.client.post(url, message), url)
        self.assertRedirects(self.client.post(url, dict(message, focus=focus[::-1])), url)
        self.assertEqual(conversation.turns.count(), 1)
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'A synthetic answer using both sources.', 'citations': ['S1', 'S2'], 'next_work': '',
        }) as model:
            self.assertTrue(assistant.worker_once())
            self.assertEqual([item['label'] for item in model.call_args.args[3]], [item['label'] for item in selected])
        self.assertContains(self.client.get(url), 'A synthetic answer using both sources.')
        Grant.objects.filter(case=self.case, user=self.actor, action='commercial.read').update(active=False)
        self.assertNotContains(self.client.get(url), 'A synthetic answer using both sources.')

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

    def test_commercial_draft_pins_requirements_and_replays_the_native_start(self):
        from apps.pmo import commercial_intake
        from tests.helpers import rev

        self.client.force_login(self.actor)
        conversation = self.start('tola')
        source = next(item for item in assistant.tool_context(conversation)[0] if item['label'] == 'Commercial requirements')
        key = uuid4()
        assistant.reserve(self.actor, conversation.pk, key, 'Prepare commercial work', digest(source))
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'The requirements are available.', 'citations': ['S1'], 'next_work': 'commercial/v1',
        }):
            self.assertTrue(assistant.worker_once())
        thread = self.client.get(reverse('assistant_thread', args=[conversation.pk]))
        intake = thread.context['turns'][0].next_url
        form = self.client.get(intake)
        self.assertEqual(form.context['form'].initial['requirements'], source['record']['pk'])
        data = {'definition': 'commercial/v1', 'assistant_turn': key, 'key': key, 'case': self.case.pk,
                'revision': rev(self.case), 'requirements': source['record']['pk'], 'reference': 'New proposal'}
        self.assertRedirects(self.client.post(intake, dict(data, action='save_draft')), intake,
                             fetch_redirect_response=False)
        self.assertContains(self.client.post(intake, dict(data, draft_version=1, reference='Unsaved edit')),
                            'Save your current draft')
        confirmed = dict(data, draft_version=1, background='on')
        start = self.client.post(intake, confirmed)
        self.assertEqual(start.status_code, 302)
        self.assertEqual(self.client.post(intake, confirmed).url, start.url)
        turn = AssistantTurn.objects.get(pk=key)
        self.assertEqual(turn.started_draft.number, 1)
        native = commercial_intake.latest(self.case)
        self.assertEqual(turn.started_work.request['intake'], native.pk)
        self.assertIsNone(commercial_intake.read(self.actor, self.case, native)['sow'])

    def test_bid_draft_preserves_edited_requirement_rows_until_confirmation(self):
        from apps.workflows.factory_rfp import inputs
        from tests.factory_rfp_helpers import configured
        from tests.helpers import rev

        fixture = configured()
        actor, case = fixture['actor'], fixture['case']
        self.client.force_login(actor)
        conversation = AssistantConversation.objects.create(actor=actor, case=case, persona='tola')
        source = next(item for item in assistant.tool_context(conversation)[0] if item['label'] == 'Received bid request')
        key = uuid4()
        assistant.reserve(actor, conversation.pk, key, 'Draft a bid response', digest(source))
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'The received bid request is available.', 'citations': ['S1'], 'next_work': 'rfp-response/v1',
        }):
            self.assertTrue(assistant.worker_once())
        intake = self.client.get(reverse('assistant_thread', args=[conversation.pk])).context['turns'][0].next_url
        proposed = fixture['payload']
        fields = {'definition': 'rfp-response/v1', 'case': case.pk, 'assistant_turn': key, 'key': key,
                  'reference': 'Bid draft', 'revision': rev(case), **proposed['sources'],
                  'response_evidence': proposed['response_evidence'], 'public_terms': proposed['public_terms'],
                  'lessons': proposed['lessons'], 'requirements-TOTAL_FORMS': 1, 'requirements-INITIAL_FORMS': 0,
                  **{'requirements-0-' + field: value for field, value in proposed['matrix'][0].items()}}
        self.assertRedirects(self.client.post(intake, dict(fields, action='save_draft')), intake, fetch_redirect_response=False)
        self.assertContains(self.client.get(intake), 'Cited coverage')
        edited = dict(fields, draft_version=1, **{'requirements-0-response': 'Reviewed requirement response'})
        self.assertContains(self.client.post(intake, edited), 'Save your current draft')
        self.assertRedirects(self.client.post(intake, dict(edited, action='save_draft')), intake, fetch_redirect_response=False)
        start = self.client.post(intake, dict(edited, draft_version=2))
        self.assertEqual(start.status_code, 302)
        turn = AssistantTurn.objects.get(pk=key)
        self.assertEqual(turn.started_draft.number, 2)
        self.assertEqual(inputs(turn.started_work)['matrix'][0]['response'], 'Reviewed requirement response')

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
