"""Use the existing Tola worker with only the selected bid source metadata."""
import os
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.core.models import Audit
from apps.core.services import event
from apps.documents.contracts import digest
from apps.identity.services import require


REQUESTED = 'factory.rfp_estimate_model_requested'


def available(actor, work):
    # Web reserves the turn. Only the background worker needs the provider credential.
    return bool(os.getenv('OPENROUTER_MODEL')
                and assistant.cases_for(actor, 'tola').filter(pk=work.case_id).exists())


def latest(actor, work, scope):
    command = Audit.objects.filter(case=work.case, actor=actor, action=REQUESTED, data__scope=scope).order_by('-pk').first()
    return (AssistantTurn.objects.filter(pk=command.data['turn'], conversation__actor=actor,
                                         conversation__case=work.case, conversation__persona='tola')
            .select_related('conversation__case', 'conversation__actor').first()) if command else None


@transaction.atomic
def request(actor, work_id, expected):
    from . import rfp_estimate_requests as estimate

    work = estimate.lock_work(actor, work_id, expected, 'prepare')
    require(actor, work.case, 'agent.rfp')
    _, scope = estimate.scope(actor, work)
    if not available(actor, work):
        raise PermissionDenied('Tola is available when this workspace has approved model access.')
    original = latest(actor, work, scope)
    if original and original.status in ('queued', 'running', 'answered'):
        return original
    if estimate.current_draft(actor, work, scope) is None:
        estimate.prepare(actor, work_id, expected)
    conversation = AssistantConversation.objects.create(actor=actor, case=work.case, persona='tola')
    sources, _ = assistant.tool_context(conversation)
    selected = [digest(item) for item in sources if item.get('record') == {'field': 'rfp_intake', 'pk': scope['intake']}]
    if len(selected) != 1:
        raise ValidationError('The exact received bid reference is unavailable for model drafting.')
    turn = assistant.reserve(actor, conversation.pk, uuid4(),
        'Write a short message asking Security for an effort estimate for the selected received bid. '
        'Ask for scope, assumptions and exclusions. Cite the selected bid and leave costs, recipients and dates for human review.',
        selected)
    event(actor, work.case, REQUESTED, work=work.pk, turn=str(turn.pk), scope=scope)
    return turn


def checked_answer(actor, work, scope, expected=None):
    turn = latest(actor, work, scope)
    if (turn is None or (expected is not None and turn.pk != expected) or turn.status != 'answered' or not turn.sources
            or {item.get('record', {}).get('pk') for item in turn.sources if item.get('record', {}).get('field') == 'rfp_intake'}
            != {scope['intake']}):
        raise ValidationError('A cited Tola draft for this exact bid is required.')
    assistant.check(actor, turn.conversation)
    context, _ = assistant.turn_context(turn, pending=False)
    if digest(context) != turn.context_hash:
        raise ValidationError('The model draft needs a fresh check of its selected bid.')
    return turn
