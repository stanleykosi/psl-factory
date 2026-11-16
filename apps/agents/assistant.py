"""Department assistant backed by saved requests and scoped native readers."""
import os
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from adapters import openrouter
from apps.core.workbench import granted
from apps.documents.contracts import digest

from .assistant_models import AssistantConversation, AssistantTurn


PERSONAS = {
    'tola': ('Tola', 'Project management', 'factory.read'),
    'chidi': ('Chidi', 'Finance', 'finance.read'),
    'zainab': ('Zainab', 'HR', 'hrfinance.read'),
}


def cases_for(actor, persona):
    return granted(actor, ['agent.extract', PERSONAS[persona][2]]).filter(synthetic=True, kind='project')


def check(actor, conversation):
    if conversation.actor_id != actor.pk or not cases_for(actor, conversation.persona).filter(pk=conversation.case_id).exists():
        raise PermissionDenied('This conversation is unavailable for your current access.')


def work_intent(actor, turn_id, definition, case_id=None, *, lock=False):
    turns = AssistantTurn.objects.select_related('conversation__case', 'conversation__actor')
    if lock:
        turns = turns.select_for_update(of=('self',))
    try:
        turn = get_object_or_404(turns, pk=turn_id, conversation__actor=actor, status='answered', next_work=definition)
    except ValidationError:
        raise ValidationError('Open a current suggestion from your Assistant conversation.') from None
    check(actor, turn.conversation)
    if case_id is not None and str(turn.conversation.case_id) != str(case_id):
        raise ValidationError('This suggestion belongs to a different project.')
    if not turn.started_work_id and not turn.transferred_to_id:
        sources, permitted = tool_context(turn.conversation)
        if digest(sources) != turn.context_hash or definition not in permitted:
            raise ValidationError('The suggestion needs a fresh answer before you start work.')
    return turn


def cited_record(turn, field):
    ids = {item['record']['pk'] for item in turn.sources if item.get('record', {}).get('field') == field}
    return ids.pop() if len(ids) == 1 else None


@transaction.atomic
def start_from_answer(actor, turn_id, case_id, definition, field, record_id, start_native):
    turn = work_intent(actor, turn_id, definition, case_id, lock=True)
    cited = cited_record(turn, field)
    if cited is not None and record_id != cited:
        raise ValidationError('To use a different source, start the work from the line chooser.')
    if turn.started_work_id:
        return turn.started_work
    work = start_native()
    turn.started_work = work
    turn.save(update_fields=['started_work'])
    return work


@transaction.atomic
def transfer(actor, turn_id, target):
    if target not in PERSONAS:
        raise PermissionDenied('Choose a department you can use.')
    turn = work_intent(actor, turn_id, 'assistant:' + target, lock=True)
    if not cases_for(actor, target).filter(pk=turn.conversation.case_id).exists():
        raise PermissionDenied('This department is unavailable for your current access.')
    if turn.transferred_to_id:
        return turn.transferred_to
    conversation = AssistantConversation.objects.create(actor=actor, case=turn.conversation.case, persona=target)
    # The next department receives the original question and loads its own allowed records.
    reserve(actor, conversation.pk, uuid4(), turn.question)
    turn.transferred_to = conversation
    turn.save(update_fields=['transferred_to'])
    return conversation


def tool_context(conversation):
    actor, case, persona = conversation.actor, conversation.case, conversation.persona
    check(actor, conversation)
    sources = []

    def source(label, fact, route, *args, record=None):
        item = {'label': label, 'fact': fact, 'url': reverse(route, args=args)}
        if record is not None:
            item['record'] = record
        sources.append(item)

    source('Workspace', case.title, 'case', case.pk)
    next_work = []
    if persona == 'tola':
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.workflows.factory_views import visible
        from apps.pmo import planning

        work = visible(actor).filter(case=case).exclude(definition__startswith='finance-').exclude(
            definition='pmo-finance/v1',
        ).order_by('-updated_at', '-pk')[:6]
        for item in work:
            status = item.status.replace('_', ' ')
            source(DEFINITIONS[item.definition]['title'],
                   f'Last recorded status: {status}. Updated {item.updated_at.isoformat()}.', 'factory_detail', item.pk)
        if granted(actor, ['factory.start', 'planning.read']).filter(pk=case.pk).exists():
            try:
                packet, _ = planning.packet(case)
            except (PermissionDenied, ValidationError):
                pass
            else:
                source('Current planning packet', f'Planning packet version {packet.version} is available for intake.',
                       'planning', case.pk, record={'field': 'packet', 'pk': packet.pk})
                next_work.append('planning/v1')
    elif persona == 'chidi':
        from apps.finance.fixed_charge import preparation_access
        from apps.finance.models import Handoff, Invoice

        invoices = Invoice.objects.filter(case=case).select_related(
            'preparation', 'case', 'invoiceissue', 'invoicedelivery',
        ).order_by('-pk')[:8]
        for invoice in invoices:
            try:
                preparation_access(actor, invoice.preparation)
            except (PermissionDenied, ValidationError):
                continue
            state = 'draft recorded'
            if getattr(invoice, 'invoiceissue', None):
                state = 'issued'
            if getattr(invoice, 'invoicedelivery', None):
                state += ', delivery receipt recorded'
            source(f'{invoice.reference} v{invoice.version}',
                   f'{invoice.currency} {invoice.amount:f}. Invoice state: {state}. Payment is separate.',
                   'finance_settlement', case.pk)
        if granted(actor, ['factory.start', 'finance.read']).filter(pk=case.pk).exists():
            handoffs = list(Handoff.objects.filter(case=case).select_related('milestone').order_by('-pk')[:5])
            for handoff in handoffs:
                source('Milestone handoff', f'Finance received completion evidence for {handoff.milestone.name}.',
                       'case', case.pk, record={'field': 'handoff', 'pk': handoff.pk})
            if handoffs:
                next_work.append('pmo-finance/v1')
    else:
        from apps.finance.hrfinance import check_snapshot_access
        from apps.finance.models import HRReadSnapshot

        snapshots = HRReadSnapshot.objects.filter(contract__need__case=case, status='accepted').select_related(
            'contract__need__case',
        ).order_by('-pk')[:5]
        for snapshot in snapshots:
            try:
                check_snapshot_access(actor, snapshot)
            except (PermissionDenied, ValidationError):
                continue
            source(f'HR handoff #{snapshot.pk}', 'An accepted read-only handoff is available under current access.',
                   'hrfinance_snapshot', case.pk, snapshot.pk)
    next_work.extend('assistant:' + target for target in PERSONAS
                     if target != persona and cases_for(actor, target).filter(pk=case.pk).exists())
    return sources, next_work


@transaction.atomic
def reserve(actor, conversation_id, operation_key, question):
    conversation = AssistantConversation.objects.select_for_update(of=('self',)).select_related('case').get(pk=conversation_id)
    check(actor, conversation)
    previous = AssistantTurn.objects.filter(pk=operation_key).first()
    if previous is not None:
        if previous.conversation_id != conversation.pk or previous.question != question:
            raise ValidationError('This request key has already been used. Reload and try again.')
        return previous
    if conversation.turns.filter(status__in=['queued', 'running']).exists():
        raise ValidationError('Wait for the current answer before sending another question.')
    if not os.getenv('OPENROUTER_MODEL'):
        raise ValidationError('The department assistant needs a configured model.')
    turn, _ = AssistantTurn.objects.get_or_create(pk=operation_key, defaults={'conversation': conversation, 'question': question})
    if turn.conversation_id != conversation.pk or turn.question != question:
        raise ValidationError('This request key has already been used. Reload and try again.')
    conversation.save(update_fields=['updated_at'])
    return turn


def worker_once():
    model = os.getenv('OPENROUTER_MODEL')
    if not model or not os.getenv('OPENROUTER_API_KEY'):
        return False
    with transaction.atomic():
        AssistantTurn.objects.filter(status='running', started_at__lt=timezone.now() - timedelta(minutes=5)).update(status='held')
        turn = AssistantTurn.objects.select_for_update(skip_locked=True).filter(status='queued').order_by('created_at', 'pk').first()
        if turn is None:
            return False
        turn.status = 'running'
        turn.started_at = timezone.now()
        turn.save(update_fields=['status', 'started_at'])
    conversation = turn.conversation
    try:
        sources, next_work = tool_context(conversation)
        context_hash = digest(sources)
        handles = {f'S{index}': source for index, source in enumerate(sources, start=1)}
        context = [{'handle': handle, 'label': source['label'], 'fact': source['fact']} for handle, source in handles.items()]
        recent = list(conversation.turns.filter(status='answered', created_at__lt=turn.created_at)
                      .order_by('-created_at', '-pk')[:3])
        history = [{'question': entry.question[:1000], 'answer': entry.answer[:1000]} for entry in reversed(recent)
                   if entry.sources and entry.context_hash == context_hash]
        raw = openrouter.answer(model, PERSONAS[conversation.persona][1], turn.question, context, next_work, history)
        if (not isinstance(raw, dict) or set(raw) != {'answer', 'citations', 'next_work'}
                or not isinstance(raw['answer'], str) or not 0 < len(raw['answer'].strip()) <= 4000
                or not isinstance(raw['citations'], list) or len(raw['citations']) > len(handles)
                or not all(isinstance(handle, str) and handle in handles for handle in raw['citations'])
                or raw['next_work'] not in ['', *next_work]):
            raise ValidationError('The assistant reply could not be verified.')
        cited = [handles[handle] for handle in dict.fromkeys(raw['citations'])]
        current, current_next = tool_context(conversation)
        if current != sources or (raw['next_work'] and raw['next_work'] not in current_next):
            raise ValidationError('Source access or records changed while the assistant was working.')
        # Without a source, show only a fixed insufficient-evidence message.
        answer = raw['answer'].strip() if cited else 'I could not answer from the available records.'
        AssistantTurn.objects.filter(pk=turn.pk, status='running').update(
            status='answered', answer=answer, sources=cited, context_hash=context_hash, next_work=raw['next_work'] if cited else '',
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning('Assistant turn %s held: %s', turn.pk, type(exc).__name__)
        AssistantTurn.objects.filter(pk=turn.pk, status='running').update(status='held')
    return True
