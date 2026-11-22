"""Observe one isolated native Assistant claim without contacting a model provider."""

import json
import os
from time import sleep
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.contracts import digest
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from tests import planning_helpers
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD = 'PSL_ASSISTANT_RUNNING_WALKTHROUGH'
TENANT = 'design-assistant-running-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
CONVERSATION_ID = uuid5(NAMESPACE_URL, str(CASE_ID) + '/conversation')
TURN_ID = uuid5(NAMESPACE_URL, str(CONVERSATION_ID) + '/turn')
TITLE = 'SAMPLE Assistant with selected Planning records'
SOURCE_WRITER = 'sample-assistant-running-source'
PREPARED = 'sample.assistant_running_prepared'
MODEL = 'synthetic-assistant-observation'
WINDOW_SECONDS = 40
QUESTION = 'What do these selected Planning and alignment records establish, and can I prepare a Planning draft?'
ANSWER = 'A current Planning packet is available for a draft. The selected alignment meeting was recorded separately. You can review the draft before starting work.'
READ = ('case.read', 'factory.read', 'agent.extract', 'planning.read', 'meeting.read', 'factory.start', 'evidence.add')


def trial_viewer():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and Assistant running fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def selected_records(conversation, data):
    sources, options = assistant.tool_context(conversation)
    required = {'packet': data['packet'], 'meeting': data['meeting']}
    selected = [source for source in sources if source.get('record', {}).get('pk') == required.get(source.get('record', {}).get('field'))
                and 'record' in source]
    if len(selected) != len(required) or 'planning/v1' not in options:
        raise RuntimeError('The original two readable sources and current Planning draft scope are required.')
    return selected


def pinned(viewer, *, lock=False):
    case = Case.objects.get(pk=CASE_ID, tenant=TENANT, kind='project', title=TITLE, synthetic=True)
    queries = AssistantConversation.objects.select_related('case', 'actor')
    if lock:
        queries = queries.select_for_update(of=('self',))
    conversation = queries.get(pk=CONVERSATION_ID, actor=viewer, case=case, persona='tola')
    data = Audit.objects.get(case=case, actor__username=SOURCE_WRITER, action=PREPARED).data
    if (data['viewer'], data['conversation'], data['turn']) != (viewer.pk, str(conversation.pk), str(TURN_ID)):
        raise RuntimeError('Preserve the original scoped Assistant specimen.')
    assistant.check(viewer, conversation)
    return conversation, data


@transaction.atomic
def prepare():
    viewer = trial_viewer()
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying this sample identifier.')
    if created:
        writer = get_user_model().objects.create_user(SOURCE_WRITER)
        Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for user, actions in (
            (writer, dict.fromkeys(ACTIONS)), (viewer, READ),
        ) for action in actions])
        with patch.object(planning_helpers, 'setup_case', return_value=(writer, case)):
            source = planning_helpers.fixture(configured=False, username=SOURCE_WRITER)
        meeting = next(iter(source['meetings'].values()))
        conversation = AssistantConversation.objects.create(pk=CONVERSATION_ID, actor=viewer, case=case, persona='tola')
        data = event(writer, case, PREPARED, viewer=viewer.pk, conversation=str(conversation.pk), turn=str(TURN_ID),
                     packet=source['packet'].pk, meeting=meeting.pk).data
        selected_records(conversation, data)
    conversation, data = pinned(viewer)
    return {**data, 'case': str(case.pk), 'path': reverse('assistant_thread', args=[conversation.pk]), 'preserved': not created}


def observe(conversation_id):
    viewer = trial_viewer()
    if UUID(str(conversation_id)) != CONVERSATION_ID:
        raise RuntimeError('Choose the exact prepared Assistant conversation.')
    with transaction.atomic():
        conversation, data = pinned(viewer, lock=True)
        if conversation.turns.exists():
            raise RuntimeError('Choose the original empty specimen before its first claim.')
        sources = selected_records(conversation, data)
        # Reservation and claim share a transaction so the ordinary queue never sees this sample as queued.
        with patch.dict('os.environ', {'OPENROUTER_MODEL': MODEL}):
            assistant.reserve(viewer, conversation.pk, TURN_ID, QUESTION, [digest(source) for source in sources])
        turn = assistant.claim_turn(TURN_ID)
        if turn is None:
            raise RuntimeError('The native worker must claim this exact turn.')

    def answer(model, department, question, selected, allowed_next, history):
        if (model, department, question) != (MODEL, 'Project management', QUESTION) or history or 'planning/v1' not in allowed_next:
            raise RuntimeError('The original scoped model context is required.')
        if [(item['label'], item['fact']) for item in selected] != [(item['label'], item['fact']) for item in sources]:
            raise RuntimeError('The exact two original sources must reach the answer adapter.')
        print(f'{GUARD}_ACTIVE={turn.pk}', flush=True)
        sleep(WINDOW_SECONDS)
        return {'answer': ANSWER, 'citations': [item['handle'] for item in selected], 'next_work': 'planning/v1'}

    with patch.object(assistant.openrouter, 'answer', side_effect=answer):
        if not assistant.answer_claim(turn, MODEL):
            raise RuntimeError('The exact native Assistant claim no longer exists.')
    result = AssistantTurn.objects.get(pk=TURN_ID, conversation=conversation)
    if (result.status != 'answered' or result.sources != sources or result.next_work != 'planning/v1'
            or result.started_work_id is not None or result.draft_versions.exists()):
        raise RuntimeError('Expected a cited answer awaiting an explicit Planning draft review.')
    return {'turn': str(result.pk), 'conversation': str(conversation.pk), 'started_at': result.started_at.isoformat(),
            'packet': data['packet'], 'meeting': data['meeting'], 'path': reverse('assistant_thread', args=[conversation.pk])}


def run():
    print(GUARD + '=' + json.dumps(prepare()), flush=True)
