from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_assistant_running_seed as seed
from tests.helpers import rev, setup_case


ENVIRONMENT = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'}
RUNNING = 'Checking your project records for this answer.'


@patch.dict('os.environ', ENVIRONMENT)
class AssistantRunningWalkthroughSeedTests(TestCase):
    def test_exact_native_claim_keeps_other_turns_and_links_only_human_started_draft(self):
        self.assertEqual(connection.vendor, 'postgresql')
        viewer = get_user_model().objects.create_user('psl-agent-trial')
        other, other_case = setup_case(username='sample-assistant-independent')
        original = AssistantConversation.objects.create(actor=other, case=other_case, persona='tola')
        with patch.dict('os.environ', {'OPENROUTER_MODEL': seed.MODEL}):
            older = assistant.reserve(other, original.pk, uuid4(), 'Check separate project')
        delayed = AssistantTurn.objects.create(conversation=original, question='Earlier separate claim', status='running',
                                               started_at=timezone.now() - timedelta(minutes=6))
        with patch.dict('os.environ', {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'Assistant running fixture guard'):
                seed.prepare()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        data = seed.prepare()
        self.assertEqual(seed.prepare(), data | {'preserved': True})
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(data['path']), RUNNING)

        def read_live(seconds):
            self.assertEqual(seconds, seed.WINDOW_SECONDS)
            active = AssistantTurn.objects.get(pk=data['turn'])
            self.assertEqual(active.status, 'running')
            self.assertIsNotNone(active.started_at)
            self.assertEqual((active.answer, active.sources, active.next_work), ('', [], ''))
            page = self.client.get(data['path'])
            self.assertContains(page, RUNNING)
            self.assertContains(page, 'Started <time')
            self.assertContains(page, 'data-assistant-wait')
            self.assertNotContains(page, 'Records checked')
            self.assertNotContains(page, 'Edit draft')
            self.assertFalse(FactoryWork.objects.filter(case_id=data['case']).exists())
            self.client.force_login(other)
            self.assertEqual(self.client.get(data['path']).status_code, 404)
            self.client.force_login(viewer)

        with (patch.object(seed, 'sleep', side_effect=read_live) as live, redirect_stdout(StringIO()),
              patch.dict('os.environ', {'OPENROUTER_API_KEY': ''})):
            result = seed.observe(data['conversation'])
        live.assert_called_once_with(seed.WINDOW_SECONDS)
        self.assertEqual(result['turn'], data['turn'])
        older.refresh_from_db()
        delayed.refresh_from_db()
        self.assertEqual((older.status, delayed.status), ('queued', 'running'))
        turn = AssistantTurn.objects.get(pk=data['turn'])
        self.assertEqual({item['record']['field']: item['record']['pk'] for item in turn.sources},
                         {'packet': data['packet'], 'meeting': data['meeting']})
        self.assertFalse(turn.draft_versions.exists())
        answered = self.client.get(data['path'])
        self.assertContains(answered, seed.ANSWER)
        self.assertContains(answered, 'Records checked')
        self.assertContains(answered, 'Edit draft')
        self.assertNotContains(answered, RUNNING)
        self.assertNotContains(answered, 'Open the work item')
        intake = answered.context['turns'][0].next_url
        form = self.client.get(intake).context['form']
        self.assertEqual(form.initial['packet'], data['packet'])
        values = {'definition': 'planning/v1', 'key': data['turn'], 'assistant_turn': data['turn'], 'case': data['case'],
                  'packet': data['packet'], 'reference': 'SAMPLE ASSISTANT PLANNING DRAFT', 'revision': rev(turn.conversation.case)}
        self.assertRedirects(self.client.post(intake, values | {'action': 'save_draft'}), intake, fetch_redirect_response=False)
        self.assertContains(self.client.get(data['path']), 'SAMPLE ASSISTANT PLANNING DRAFT · Draft 1')
        self.assertFalse(FactoryWork.objects.filter(case_id=data['case']).exists())
        started = self.client.post(intake, values | {'draft_version': 1})
        self.assertEqual(started.status_code, 302)
        turn.refresh_from_db()
        self.assertEqual(turn.started_draft.number, 1)
        self.assertEqual(turn.started_work.request['packet'], data['packet'])
        self.assertFalse(FactoryProgress.objects.filter(work=turn.started_work).exists())
        self.assertContains(self.client.get(data['path']), 'Open the work item')
        with self.assertRaisesMessage(RuntimeError, 'original empty specimen'):
            seed.observe(data['conversation'])

    def test_source_scope_changed_during_exact_claim_holds_without_citation_or_draft(self):
        viewer = get_user_model().objects.create_user('psl-agent-trial')
        data = seed.prepare()

        def withdraw_source(seconds):
            Grant.objects.filter(case_id=data['case'], user=viewer, action='meeting.read').update(active=False)

        with patch.object(seed, 'sleep', side_effect=withdraw_source), redirect_stdout(StringIO()):
            with self.assertRaisesMessage(RuntimeError, 'Expected a cited answer'):
                seed.observe(data['conversation'])
        turn = AssistantTurn.objects.get(pk=data['turn'])
        self.assertEqual((turn.status, turn.sources, turn.next_work), ('held', [], ''))
        self.client.force_login(viewer)
        self.assertContains(self.client.get(data['path']), 'An answer could not be completed')
        self.assertNotContains(self.client.get(data['path']), 'Edit draft')
