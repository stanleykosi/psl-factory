"""Reviewed requirement citations and observed client clarifications for the exact bid."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.evidence_access import public_evidence
from apps.core.models import Audit
from apps.core.services import bump, event, lock_case
from apps.pmo import rfp_answers
from apps.workflows import factory_rfp
from apps.workflows.models import FactoryWork

from .commands import require_line
from .delivery import RESPONSE
from .http import DATETIME, ID, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import result


CITATION = 'factory.rfp_requirement_cited'
CLARIFICATION = 'factory.rfp_clarification_observed'
KEY = {**TEXT, 'maxLength': 100}
BODY = {**TEXT, 'maxLength': 4000}


def records(work, action):
    return Audit.objects.filter(case_id=work.case_id, action=action, data__work=work.pk, data__head=work.source_head_id)


def citation_data(work):
    citations = {}
    for item in records(work, CITATION).order_by('-pk')[:200].values_list('data', flat=True):
        citations.setdefault(item['key'], {'wording': item['text'], 'page': item['page'], 'evidence_id': item['evidence_id']})
    return citations


@endpoint(method='POST', request={'oneOf': [
    obj({**VERSIONS, 'action': {'const': 'cite'}, 'key': KEY, 'operation_key': UUID, 'text': BODY,
         'page': nullable(ID), 'checked': {'const': True}}),
    obj({**VERSIONS, 'action': choice('record_question', 'record_reply'), 'key': KEY, 'operation_key': UUID,
         'text': BODY, 'observed_at': DATETIME, 'evidence_id': ID, 'question_id': nullable(ID)}),
]}, response=RESPONSE, status=201, summary='Record the inspected requirement location or an actual client clarification')
@transaction.atomic
def capture(request, work_id, *, body):
    actor = request.user
    scoped = require_line(actor, work_id, factory_rfp.DEFINITION)
    work = FactoryWork.objects.select_for_update().select_related('case').get(pk=scoped.pk)
    case = lock_case(actor, work.case_id, 'rfp.prepare')
    work.case = case
    if work.cancel_requested or work.status in ('cancelled', 'verified', 'followup_needed'):
        raise Problem(409, 'stale_version', 'Open the current bid before adding a source or clarification.')
    anchors, writable = rfp_answers.read_state(actor, work)
    if not writable or anchors is None:
        raise PermissionDenied('The current bid owner records requirement sources and client clarifications.')
    row = rfp_answers.row_for(work, body['key'])
    source = rfp_answers.source_for(actor, work, row)
    text = body['text'].strip()
    if not text:
        raise ValidationError('Enter the exact wording.')
    action = body['action']
    common = {'work': work.pk, 'head': work.source_head_id, 'key': row['key'], 'text': text,
              'operation_key': str(body['operation_key'])}
    if action == 'cite':
        if ' '.join(text.split()) not in ' '.join(source.body.split()):
            raise ValidationError('Quote the wording from the retained requirement source.')
        event_type = CITATION
        data = {**common, 'page': body['page'], 'evidence_id': source.pk}
    else:
        if row['disposition'] != 'clarification':
            raise ValidationError('Choose a requirement marked for client clarification.')
        evidence = get_object_or_404(public_evidence(case.evidence.all()), pk=body['evidence_id'])
        observed_at = parse_datetime(body['observed_at'])
        if observed_at is None or timezone.is_naive(observed_at) or observed_at > timezone.now():
            raise ValidationError('Enter the actual question or reply time.')
        event_type = CLARIFICATION
        question_id = body['question_id']
        if action == 'record_reply':
            question = get_object_or_404(records(work, event_type), pk=question_id, data__key=row['key'], data__kind='question')
            if observed_at < parse_datetime(question.data['observed_at']):
                raise ValidationError('The reply must follow the recorded question.')
        elif question_id is not None:
            raise ValidationError('A new client question has no earlier question ID.')
        data = {**common, 'kind': 'question' if action == 'record_question' else 'reply',
                'question_id': question_id, 'observed_at': observed_at.isoformat(), 'evidence_id': evidence.pk}
    prior = records(work, event_type).filter(data__operation_key=data['operation_key']).first()
    if prior is not None:
        if prior.actor_id != actor.pk or prior.data != data:
            raise Problem(409, 'idempotency_conflict', 'The source or clarification changed on retry.')
        return {**result(work), 'record_id': prior.pk}
    if (work.revision, case.revision) != (body['expected_revision'], body['case_revision']):
        raise Problem(409, 'stale_version', 'Review the current bid before recording this information.')
    saved = event(actor, case, event_type, **data)
    bump(case)
    return {**result(work), 'record_id': saved.pk}


@endpoint(response=obj({'items': array(obj({'id': ID, 'key': KEY, 'kind': choice('question', 'reply'),
    'question_id': nullable(ID), 'text': BODY, 'at': DATETIME, 'evidence_id': ID}), limit=100),
    'has_more': {'type': 'boolean'}}), summary='Read the recorded questions and replies for current bid requirements')
def clarifications(request, work_id):
    work = require_line(request.user, work_id, factory_rfp.DEFINITION)
    rfp_answers.anchors(request.user, work)
    rows = list(records(work, CLARIFICATION).order_by('-pk')[:101])
    proofs = set(public_evidence(work.case.evidence.filter(pk__in=[row.data['evidence_id'] for row in rows]))
                 .values_list('pk', flat=True))
    return {'items': [{'id': row.pk, 'at': row.data['observed_at'],
                       **{key: row.data[key] for key in ('key', 'kind', 'question_id', 'text', 'evidence_id')}}
                      for row in rows[:100] if row.data['evidence_id'] in proofs], 'has_more': len(rows) > 100}
