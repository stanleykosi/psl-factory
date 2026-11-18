"""Per-requirement model drafts feed the native, independently reviewed bid."""
import os
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.agents.rfp_answer_models import RFPAnswerReview, RFPAnswerSuggestion
from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.services import event, lock_case
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.workflows import factory_rfp
from apps.workflows.models import FactoryWork

from . import rfp

MAX_SOURCE_BYTES = 64000
DISPOSITIONS = {'addressed', 'clarification', 'out_of_scope'}


def revisions(work_id, expected, case_revision):
    if any(type(value) is not int or value < 1 for value in [work_id, expected, case_revision]):
        raise ValidationError('Use exact current work and project revisions.')


def authorize(actor, work):
    from apps.workflows.factory import access

    access(actor, work.case, 'factory.read', factory_rfp.DEFINITION)
    for action in ['rfp.read', 'rfp.prepare']:
        require(actor, work.case, action)
    root = factory_rfp.subject(work)
    if rfp.current_assignment(root).pm_id != actor.pk:
        raise PermissionDenied('The assigned project manager reviews requirement answers.')
    return root


def anchors(actor, work):
    root = authorize(actor, work)
    data = factory_rfp.inputs(work)
    if data['intake'] != root.current_intake_id or not factory_rfp.instruction_current(work):
        raise ValidationError('Review the current received bid and its source owner first.')
    return {
        'intake': data['intake'], 'assignment': rfp.current_assignment(root).pk,
        'sources': data['sources'], 'response_evidence': data['response_evidence'],
        'public_terms': data['public_terms'],
    }


def row_for(work, key):
    row = next((row for row in factory_rfp.inputs(work)['matrix'] if row['key'] == key), None)
    if row is None:
        raise ValidationError('Choose a current requirement from this bid.')
    return row


def source_for(actor, work, row):
    source = public_evidence(Evidence.objects.filter(case=work.case, pk=row['evidence_id'])).select_related('created_by').first()
    if source is None or source.kind not in {'requirements', 'rfp_intake'}:
        raise ValidationError('The original requirement source needs authorised review.')
    require(source.created_by, work.case, 'evidence.add')
    if len(source.body.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValidationError('Select a requirement source of at most 64,000 bytes for this answer.')
    return source


def context_for(suggestion, *, pending=True):
    actor = suggestion.turn.conversation.actor
    work = FactoryWork.objects.select_related('case', 'source_head__created_by').get(pk=suggestion.work_id)
    current = anchors(actor, work)
    source = source_for(actor, work, suggestion.row)
    if current != suggestion.context or (pending and row_for(work, suggestion.key) != suggestion.row):
        raise ValidationError('This requirement changed. Ask for a fresh suggestion.')
    return [{
        'label': 'Requirement ' + suggestion.key,
        'fact': {'requirement': suggestion.key, 'source': source.body,
                 'current_answer': suggestion.row['response'], 'coverage': suggestion.row['disposition']},
        'url': reverse('factory_rfp_answers', args=[work.pk]),
        'record': {'field': 'rfp_requirement', 'pk': source.pk, 'sha256': source.sha256},
    }], []


def writable(actor, work):
    authorize(actor, work)
    require(actor, work.case, 'factory.manage')
    require(actor, work.case, 'evidence.add')
    rfp.ensure_open(factory_rfp.subject(work))
    if work.cancel_requested or work.status in {'verified', 'cancelled', 'followup_needed'}:
        raise ValidationError('This bid has a final or stopped outcome.')
    if work.lease_until and work.lease_until > timezone.now():
        raise ValidationError('Wait for the current agent step to finish.')
    if factory_rfp.submission_for(work) or factory_rfp.pending_jobs(work).exists() or factory_rfp.uncaptured(work):
        raise ValidationError('Resolve original submission receipts before changing bid answers.')


@transaction.atomic
def request(actor, work_id, key, operation_key, expected, case_revision):
    revisions(work_id, expected, case_revision)
    if not isinstance(key, str) or not key.strip() or len(key) > 100:
        raise ValidationError('Choose a named requirement from this bid.')
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head__created_by').get(
        pk=work_id, definition=factory_rfp.DEFINITION)
    writable(actor, work)
    lock_case(actor, work.case_id, 'agent.rfp', case_revision)
    try:
        operation_key = UUID(str(operation_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Reload the suggestion form before trying again.') from None
    previous = RFPAnswerSuggestion.objects.select_related('turn__conversation').filter(turn_id=operation_key).first()
    if previous:
        if previous.work_id != work.pk or previous.key != key or previous.turn.conversation.actor_id != actor.pk:
            raise ValidationError('This request key belongs to a different answer.')
        return previous
    if work.revision != expected:
        raise ValidationError('The bid changed. Reload its current answers.')
    from apps.agents.assistant import cases_for

    if not cases_for(actor, 'tola').filter(pk=work.case_id).exists():
        raise PermissionDenied('The model connection is available for authorised test projects.')
    if not os.getenv('OPENROUTER_MODEL'):
        raise ValidationError('Tola needs a configured model before drafting an answer.')
    row = row_for(work, key)
    context = anchors(actor, work)
    source_for(actor, work, row)
    active = RFPAnswerSuggestion.objects.filter(work=work, key=key, turn__status__in=['queued', 'running']).first()
    if active:
        raise ValidationError('Tola is already working on this requirement.')
    conversation = AssistantConversation.objects.create(actor=actor, case=work.case, persona='tola')
    turn = AssistantTurn.objects.create(pk=operation_key, conversation=conversation,
        question='Draft a concise bid answer for the selected requirement. Use only the supplied source. '
                 'State uncertainties and avoid unsupported capabilities or commitments. The project manager will review it.')
    suggestion = RFPAnswerSuggestion.objects.create(turn=turn, work=work, source_head=work.source_head,
        key=key, row=row, context=context)
    event(actor, work.case, 'rfp.answer_requested', suggestion=suggestion.pk, work=work.pk)
    return suggestion


def latest_review(suggestion):
    return suggestion.reviews.select_related('actor').order_by('-pk').first()


def reviewed_row(suggestion, verdict, answer, disposition):
    turn = suggestion.turn
    if turn.status != 'answered' or not turn.sources:
        raise ValidationError('Wait for a cited answer before reviewing this suggestion.')
    current, _ = context_for(suggestion)
    if digest(current) != turn.context_hash:
        raise ValidationError('The suggested answer needs a fresh source check.')
    if verdict == 'accept':
        answer = turn.answer
    if verdict not in {'accept', 'edit', 'replace'} or disposition not in DISPOSITIONS:
        raise ValidationError('Choose how this requirement is covered and how to use the suggestion.')
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 4000:
        raise ValidationError('Write the answer to save for this requirement.')
    return dict(suggestion.row, response=answer.strip(), disposition=disposition)


@transaction.atomic
def review(actor, work_id, expected, case_revision, decisions):
    revisions(work_id, expected, case_revision)
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head__created_by').get(
        pk=work_id, definition=factory_rfp.DEFINITION)
    writable(actor, work)
    if type(expected) is not int or work.revision != expected:
        raise ValidationError('The bid changed. Reload its current answers.')
    case = lock_case(actor, work.case_id, 'evidence.add', case_revision)
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 100:
        raise ValidationError('Select one to one hundred current suggestions.')
    changes = {}
    rows = []
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != {'suggestion', 'predecessor', 'verdict', 'answer', 'disposition', 'note'}:
            raise ValidationError('Use the current answer review form.')
        if (type(decision['suggestion']) is not int or decision['suggestion'] < 1
                or type(decision['predecessor']) is not int or decision['predecessor'] < 0):
            raise ValidationError('Use exact suggestion and review references.')
        suggestion = RFPAnswerSuggestion.objects.select_related('turn__conversation__actor').filter(
            pk=decision['suggestion'], work=work).first()
        if suggestion is None or suggestion.key in changes:
            raise ValidationError('Choose each current requirement once.')
        if suggestion.turn.conversation.actor_id != actor.pk:
            raise PermissionDenied('Review your own requested suggestion for this assigned bid.')
        previous = latest_review(suggestion)
        if (previous.pk if previous else 0) != decision['predecessor']:
            raise ValidationError('A newer answer review exists. Reload it before continuing.')
        if previous and previous.verdict != 'undo':
            raise ValidationError('This suggestion is already reviewed. Undo it or ask for a fresh suggestion.')
        note = decision['note']
        if not isinstance(note, str) or len(note) > 2000:
            raise ValidationError('Keep the internal reason within two thousand characters.')
        row = reviewed_row(suggestion, decision['verdict'], decision['answer'], decision['disposition'])
        changes[suggestion.key] = row
        rows.append((suggestion, previous, decision, row))
    data = factory_rfp.inputs(work)
    payload = {key: data[key] for key in factory_rfp.FIELDS}
    payload['matrix'] = [changes.get(row['key'], row) for row in data['matrix']]
    updated = factory_rfp.correct(actor, work.pk, expected, case.revision, payload,
        'Project manager reviewed requirement answers.')
    recorded = []
    for suggestion, previous, decision, row in rows:
        recorded.append(RFPAnswerReview.objects.create(suggestion=suggestion, predecessor=previous,
            actor=actor, verdict=decision['verdict'], row=row, note=decision['note'].strip(), source_head=updated.source_head))
    event(actor, case, 'rfp.answers_reviewed', reviews=[item.pk for item in recorded], work=work.pk)
    from apps.workflows.factory_progress import wake_waiting

    wake_waiting(work.pk)
    return recorded


@transaction.atomic
def undo(actor, work_id, review_id, expected, case_revision):
    revisions(work_id, expected, case_revision)
    if type(review_id) is not int or review_id < 1:
        raise ValidationError('Choose an exact answer review to undo.')
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head__created_by').get(
        pk=work_id, definition=factory_rfp.DEFINITION)
    writable(actor, work)
    case = lock_case(actor, work.case_id, 'evidence.add', case_revision)
    previous = RFPAnswerReview.objects.select_related('suggestion__turn__conversation__actor').filter(
        pk=review_id, suggestion__work=work, actor=actor).first()
    if previous is None or previous.verdict == 'undo' or latest_review(previous.suggestion).pk != previous.pk:
        raise ValidationError('Choose the current accepted answer to undo.')
    suggestion = previous.suggestion
    context_for(suggestion, pending=False)
    if row_for(work, suggestion.key) != previous.row:
        raise ValidationError('This answer changed again. Review the current wording before undoing.')
    data = factory_rfp.inputs(work)
    payload = {key: data[key] for key in factory_rfp.FIELDS}
    payload['matrix'] = [suggestion.row if row['key'] == suggestion.key else row for row in data['matrix']]
    updated = factory_rfp.correct(actor, work.pk, expected, case.revision, payload,
        'Project manager undid the requirement answer review.')
    result = RFPAnswerReview.objects.create(suggestion=suggestion, predecessor=previous, actor=actor,
        verdict='undo', row=suggestion.row, source_head=updated.source_head)
    event(actor, case, 'rfp.answer_undone', review=result.pk, work=work.pk)
    from apps.workflows.factory_progress import wake_waiting

    wake_waiting(work.pk)
    return result
