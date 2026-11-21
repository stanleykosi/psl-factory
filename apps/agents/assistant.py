"""Department assistant backed by saved requests and scoped native readers."""
import os
import re
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from adapters import openrouter
from adapters.payroll_questions import TOPICS as PAYROLL_REPORT_TOPICS
from apps.core.workbench import granted
from apps.documents.contracts import digest

from .assistant_models import AssistantConversation, AssistantTurn


PERSONAS = {
    'tola': ('Tola', 'Project management', 'factory.read'),
    'chidi': ('Chidi', 'Finance', 'finance.read'),
    'zainab': ('Zainab', 'HR', 'hrfinance.read'),
}
INSUFFICIENT_EVIDENCE = 'I could not answer from the available records.'
PAYROLL_REPORT_QUESTIONS = tuple(PAYROLL_REPORT_TOPICS.values())


def cases_for(actor, persona):
    actions = ['agent.extract', PERSONAS[persona][2]]
    cases = granted(actor, actions)
    if persona == 'chidi':
        from apps.finance.bu_models import BUReceipt

        received = BUReceipt.objects.filter(actor=actor).values('report__work__case_id')
        aggregate_cases = granted(actor, ['agent.extract', 'bu.read', 'bu.report.read']).filter(pk__in=received)
        cases = cases | aggregate_cases
    elif persona == 'zainab':
        from apps.finance.payroll_models import PayrollReportReceipt

        received = PayrollReportReceipt.objects.filter(actor=actor).values('publication__request__case_id')
        report_cases = granted(actor, ['agent.extract', 'payroll.read', 'payroll.report.read']).filter(pk__in=received)
        cases = cases | report_cases
    return cases.filter(synthetic=True, kind='project')


def check(actor, conversation):
    if conversation.actor_id != actor.pk or not cases_for(actor, conversation.persona).filter(pk=conversation.case_id).exists():
        raise PermissionDenied('This conversation is unavailable for your current access.')


def payroll_report_only(conversation):
    return conversation.persona == 'zainab' and not granted(conversation.actor, ['hrfinance.read']).filter(
        pk=conversation.case_id).exists()


def payroll_report_sources(conversation):
    from .payroll import received_report_context

    packet = received_report_context(conversation.actor, conversation.case)
    if packet is None:
        return []
    publication = packet['publication_id']
    return [{'label': f'Reviewed staff-cost report {publication}',
             'fact': f'Report version {packet["report_version"]} for {packet["period"]} was received. '
                     'It covers reviewed staff-cost totals by business unit. Open the report for its '
                     'exact figures and the HR question options.',
             'url': reverse('payroll_inspect', args=[conversation.case_id, 'report', publication]),
             'record': {'field': 'payroll_report', 'pk': publication}}]


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
        sources, permitted = message_context(turn.conversation, turn.selected_sources or turn.focus)
        if digest(sources) != turn.context_hash or definition not in permitted:
            raise ValidationError('The suggestion needs a fresh answer before you start work.')
    return turn


def cited_record(turn, field):
    ids = {item['record']['pk'] for item in turn.sources if item.get('record', {}).get('field') == field}
    return ids.pop() if len(ids) == 1 else None


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
    if payroll_report_only(conversation):
        return payroll_report_sources(conversation), []
    sources = []

    def source(label, fact, route, *args, record=None):
        item = {'label': label, 'fact': fact, 'url': reverse(route, args=args)}
        if record is not None:
            item['record'] = record
        sources.append(item)

    source('Workspace', case.title, 'design_project', case.pk)
    next_work = []
    if persona == 'tola':
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.workflows.factory_views import visible
        from apps.core.evidence_access import public_evidence
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
        if granted(actor, ['factory.start', 'commercial.prepare', 'commercial.read', 'costing.read',
                           'costing.source.read', 'evidence.add']).filter(pk=case.pk).exists():
            requirements = public_evidence(case.evidence.filter(kind='requirements')).only('version').order_by('-version').first()
            if requirements:
                source('Commercial requirements', f'Requirements version {requirements.version} is available for commercial preparation.',
                       'commercial', case.pk, record={'field': 'requirements', 'pk': requirements.pk})
                next_work.append('commercial/v1')
        if granted(actor, ['factory.start', 'rfp.read', 'evidence.add']).filter(pk=case.pk).exists():
            from apps.pmo import rfp

            try:
                bid = rfp.root(case)
                rfp.ensure_open(bid)
            except (PermissionDenied, ValidationError):
                pass
            else:
                version = bid.current_intake
                if version is not None:
                    source('Received bid request', f'Bid request {bid.reference}, intake version {version.number}.',
                           'rfp', case.pk, record={'field': 'rfp_intake', 'pk': version.pk})
                    next_work.append('rfp-response/v1')
        if granted(actor, ['meeting.read']).filter(pk=case.pk).exists():
            from apps.pmo.models import Meeting, Milestone

            evidence_ids = public_evidence(case.evidence.all()).values('pk')
            meetings = Meeting.objects.filter(case=case, current__evidence_id__in=evidence_ids).select_related('current').order_by('-current__occurred_at', '-pk')[:5]
            for meeting in meetings:
                source(f'Meeting · {meeting.reference}',
                       f'{meeting.current.purpose}. Recorded meeting on {meeting.current.occurred_at.date().isoformat()}, version {meeting.current.number}.',
                       'meetings', case.pk, record={'field': 'meeting', 'pk': meeting.current_id})
            milestones = Milestone.objects.filter(case=case, evidence_id__in=evidence_ids).order_by('-completed_at', '-pk')[:5]
            for milestone in milestones:
                source(f'Milestone · {milestone.name}', f'Completion was recorded on {milestone.completed_at.date().isoformat()}.',
                       'design_project_tab', case.pk, 'milestones', record={'field': 'milestone', 'pk': milestone.pk})
    elif persona == 'chidi':
        from apps.finance import bu
        from apps.finance.bu_models import BUReceipt

        finance_reader = granted(actor, ['finance.read']).filter(pk=case.pk).exists()
        if finance_reader:
            from apps.finance.fixed_charge import preparation_access
            from apps.finance.models import Invoice

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
        if finance_reader and granted(actor, ['factory.start']).filter(pk=case.pk).exists():
            from apps.finance.models import Handoff

            handoffs = list(Handoff.objects.filter(case=case).select_related('milestone').order_by('-pk')[:5])
            for handoff in handoffs:
                source('Milestone handoff', f'Finance received completion evidence for {handoff.milestone.name}.',
                       'case', case.pk, record={'field': 'handoff', 'pk': handoff.pk})
            if handoffs:
                next_work.append('pmo-finance/v1')
        if granted(actor, ['bu.read', 'bu.report.read']).filter(pk=case.pk).exists():
            report_ids = BUReceipt.objects.filter(actor=actor, report__work__case=case).order_by('-report_id').values_list('report_id', flat=True)[:3]
            for report_id in report_ids:
                try:
                    value = bu.read_report(actor, report_id)
                except (PermissionDenied, ValidationError):
                    continue
                amounts = sorted(value['by_bu'].items())
                first = ', '.join(f'{unit}: {value["currency"]} {amount}' for unit, amount in amounts[:8])
                coverage = f' Showing eight of {len(amounts)} units.' if len(amounts) > 8 else ''
                source(f'Reviewed business unit report {report_id}',
                       f'{value["period"]}. Total allocated: {value["currency"]} {value["allocated_total"]}. '
                       f'{first}.{coverage} Totals cover the selected source population.',
                       'bu_inspect', case.pk, 'report', report_id, record={'field': 'bu_report', 'pk': report_id})
        if not finance_reader and len(sources) == 1:
            return [], []
    else:
        from apps.core.presentation import HR_FIELD_LABELS
        from apps.finance.hrfinance import check_snapshot_access
        from apps.finance.models import HRReadSnapshot

        snapshots = HRReadSnapshot.objects.defer('payload').filter(contract__need__case=case, status='accepted').select_related(
            'contract__need__case',
        ).order_by('-pk')[:5]
        for snapshot in snapshots:
            try:
                check_snapshot_access(actor, snapshot)
            except (PermissionDenied, ValidationError):
                continue
            details = snapshot.contract.payload
            field_names = ', '.join(HR_FIELD_LABELS[key] for key in details['fields'])
            source(f'HR handoff #{snapshot.pk}',
                   f"Accepted read-only handoff for {details['period']}. "
                   f"Purpose {details['purpose'].replace('_', ' ')}. Approved fields include {field_names}.",
                   'hrfinance_snapshot', case.pk, snapshot.pk)
    next_work.extend('assistant:' + target for target in PERSONAS
                     if target != persona and cases_for(actor, target).filter(pk=case.pk).exists())
    return sources, next_work


def source_focus(sources, focus):
    if not focus:
        return sources
    requested = {focus} if isinstance(focus, str) else set(focus)
    selected = [source for source in sources if digest(source) in requested]
    if {digest(source) for source in selected} != requested:
        raise ValidationError('The selected record changed or is no longer available.')
    return selected


def message_context(conversation, focus):
    sources, next_work = tool_context(conversation)
    return source_focus(sources, focus), next_work


def turn_context(turn, *, pending=True):
    suggestion = getattr(turn, 'rfp_answer', None)
    if suggestion is not None:
        from apps.pmo.rfp_answers import context_for

        check(turn.conversation.actor, turn.conversation)
        return context_for(suggestion, pending=pending)
    return message_context(turn.conversation, turn.selected_sources or turn.focus)


@transaction.atomic
def reserve(actor, conversation_id, operation_key, question, focus=''):
    keys = [focus] if isinstance(focus, str) and focus else [] if focus == '' else focus
    if not isinstance(keys, list) or len(keys) > 5 or any(
            not isinstance(key, str) or not re.fullmatch('[0-9a-f]{64}', key) for key in keys):
        raise ValidationError('Choose up to five current records.')
    keys = sorted(set(keys))
    conversation = AssistantConversation.objects.select_for_update(of=('self',)).select_related('case').get(pk=conversation_id)
    check(actor, conversation)
    if payroll_report_only(conversation) and (question not in PAYROLL_REPORT_QUESTIONS or len(keys) > 1):
        raise ValidationError('Choose a question about your received staff-cost report.')
    previous = AssistantTurn.objects.filter(pk=operation_key).first()
    if previous is not None:
        if (previous.conversation_id != conversation.pk or previous.question != question
                or (previous.selected_sources or ([previous.focus] if previous.focus else [])) != keys):
            raise ValidationError('This request key has already been used. Reload and try again.')
        return previous
    if conversation.turns.filter(status__in=['queued', 'running']).exists():
        raise ValidationError('Wait for the current answer before sending another question.')
    if not os.getenv('OPENROUTER_MODEL'):
        raise ValidationError('The department assistant needs a configured model.')
    if keys:
        message_context(conversation, keys)
    turn, _ = AssistantTurn.objects.get_or_create(pk=operation_key, defaults={
        'conversation': conversation, 'question': question, 'selected_sources': keys,
    })
    if (turn.conversation_id != conversation.pk or turn.question != question
            or (turn.selected_sources or ([turn.focus] if turn.focus else [])) != keys):
        raise ValidationError('This request key has already been used. Reload and try again.')
    conversation.save(update_fields=['updated_at'])
    return turn


@transaction.atomic
def claim_turn(turn_id=None):
    turns = AssistantTurn.objects.all()
    if turn_id is not None:
        turns = turns.filter(pk=turn_id)
    now = timezone.now()
    turns.filter(status='running', started_at__lt=now - timedelta(minutes=5)).update(status='held')
    turn = turns.select_for_update(skip_locked=True).filter(status='queued').order_by('created_at', 'pk').first()
    if turn is not None:
        turn.status = 'running'
        turn.started_at = timezone.now()
        turn.save(update_fields=['status', 'started_at'])
    return turn


def answer_claim(turn, model):
    if turn.status != 'running' or turn.started_at is None:
        raise ValidationError('A current Assistant claim is required.')
    claim = AssistantTurn.objects.filter(pk=turn.pk, status='running', started_at=turn.started_at)
    if not claim.exists():
        return False
    conversation = turn.conversation
    try:
        sources, next_work = turn_context(turn)
        report_only = payroll_report_only(conversation) or any(
            source.get('record', {}).get('field') == 'payroll_report' for source in sources)
        if report_only and turn.question not in PAYROLL_REPORT_QUESTIONS:
            raise ValidationError('A received-report conversation uses the listed payroll questions.')
        context_hash = digest(sources)
        if not sources:
            claim.update(
                status='answered', answer=INSUFFICIENT_EVIDENCE, sources=[], context_hash=context_hash, next_work='',
            )
            return True
        handles = {f'S{index}': source for index, source in enumerate(sources, start=1)}
        context = [{'handle': handle, 'label': source['label'], 'fact': source['fact']} for handle, source in handles.items()]
        history = []
        if not report_only:
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
        current, current_next = turn_context(turn)
        if current != sources or (raw['next_work'] and raw['next_work'] not in current_next):
            raise ValidationError('Source access or records changed while the assistant was working.')
        # Without a source, show only a fixed insufficient-evidence message.
        answer = raw['answer'].strip() if cited else INSUFFICIENT_EVIDENCE
        claim.update(
            status='answered', answer=answer, sources=cited, context_hash=context_hash, next_work=raw['next_work'] if cited else '',
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning('Assistant turn %s held: %s', turn.pk, type(exc).__name__)
        claim.update(status='held')
    return True


def worker_once():
    model = os.getenv('OPENROUTER_MODEL')
    if not model or not os.getenv('OPENROUTER_API_KEY'):
        return False
    turn = claim_turn()
    return answer_claim(turn, model) if turn is not None else False
