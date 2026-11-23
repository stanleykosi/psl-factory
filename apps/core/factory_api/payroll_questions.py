"""Participant-scoped aggregate payroll questions and HR replies."""

from time import monotonic
from uuid import UUID as parse_uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from adapters.payroll_questions import REPLIES, TOPICS
from apps.core.read_budget import ReadLimit, limit_queries
from apps.core.views import accessible_case
from apps.finance import payroll_questions as domain
from apps.finance.payroll_models import PayrollPublication
from apps.finance.payroll_question_models import PayrollReportQuestion
from apps.policy.hrfinance_validators import MONTH

from .http import BOOLEAN, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


HEAD = {**ID, 'minimum': 0}
QUESTION_QUERIES = 950
QUESTION_SECONDS = 8
ACTION = choice('dispatched', 'answered', 'received', 'cancelled')
CARD = obj({'id': ID, 'head': HEAD, 'question': TEXT, 'period': MONTH, 'publication': ID,
    'state': choice('recorded', 'dispatched', 'answered', 'received', 'cancelled', 'held', 'owner_needed'),
    'can_cancel': BOOLEAN, 'can_send': BOOLEAN, 'can_answer': BOOLEAN, 'can_receive': BOOLEAN,
    'reply': nullable(TEXT), 'owner_name': nullable(TEXT)})
OPTION = obj({'value': TEXT, 'label': TEXT})


def selected(actor, case):
    return PayrollReportQuestion.objects.filter(case=case).filter(
        Q(actor=actor) | Q(events__kind='dispatched', events__data__owner_id=actor.pk)
    ).select_related('case', 'actor').distinct()


@endpoint(response=obj({'revision': REVISION, 'can_ask': BOOLEAN, 'items': array(CARD, limit=10),
    'deferred_questions': array(ID, limit=10), 'report_check_deferred': BOOLEAN,
    'next_page': nullable(PAGE), 'topics': array(OPTION), 'reply_options': array(OPTION)}),
    query={'report': ID, 'page': PAGE}, summary='Read the aggregate questions in which you participate and allowed replies')
@transaction.atomic
def options(request, case_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    report_param = request.GET.get('report')
    if report_param is not None and (not report_param.isascii() or not report_param.isdecimal()
            or len(report_param) > 19 or not 1 <= int(report_param) <= ID['maximum']):
        raise Problem(422, 'invalid_filter', 'Choose an exact aggregate report.')
    page = page_number(request)
    offset = (page - 1) * 10
    items = []
    deferred = []
    can_ask = False
    report_check_deferred = False
    reader = domain.Reader(actor, case)
    records = list(selected(actor, case).order_by('-pk')[offset:offset + 11])
    with limit_queries(QUESTION_QUERIES, deadline=monotonic() + QUESTION_SECONDS):
        if report_param is not None:
            try:
                report = PayrollPublication.objects.defer('payload').select_related('request').filter(
                    request__case=case, pk=int(report_param)).first()
                if report:
                    reader.admit_publication(actor, report)
                    can_ask = True
            except (PermissionDenied, ValidationError):
                pass
            except ReadLimit:
                report_check_deferred = True
        for record in records[:10]:
            try:
                items.append(domain.projection(actor, record, reader))
            except (PermissionDenied, ValidationError):
                continue
            except ReadLimit:
                deferred.append(record.pk)
    return {'revision': reader.case.revision, 'items': items, 'can_ask': can_ask,
            'deferred_questions': deferred, 'report_check_deferred': report_check_deferred,
            'next_page': page + 1 if len(records) > 10 and page < PAGE['maximum'] else None,
            'topics': [{'value': key, 'label': label} for key, label in TOPICS.items()] if can_ask else [],
            'reply_options': [{'value': key, 'label': label} for key, label in REPLIES.items()]
                             if any(item['can_answer'] for item in items) else []}


@endpoint(method='POST', request=obj({'revision': REVISION, 'report_id': ID, 'topic': choice(*TOPICS), 'operation_key': UUID}),
    response=obj({'question_id': ID, 'revision': REVISION}), status=201,
    summary='Prepare a closed-topic HR question for an exact authorised aggregate report')
def ask(request, case_id, *, body):
    case = accessible_case(request.user, case_id)
    question = domain.record(request.user, case.pk, body['report_id'], body['topic'],
                             parse_uuid(body['operation_key']), body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'question_id': question.pk, 'revision': case.revision}


@endpoint(response=obj({'revision': REVISION, 'item': CARD, 'reply_options': array(OPTION)}),
    summary='Read one exact aggregate payroll question and current HR reply')
@transaction.atomic
def detail(request, case_id, question_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    question = get_object_or_404(selected(actor, case), pk=question_id)
    with limit_queries(QUESTION_QUERIES, deadline=monotonic() + QUESTION_SECONDS):
        reader = domain.Reader(actor, case)
        item = domain.projection(actor, question, reader)
    return {'revision': reader.case.revision, 'item': item,
            'reply_options': [{'value': key, 'label': label} for key, label in REPLIES.items()] if item['can_answer'] else []}


@endpoint(method='POST', request={'oneOf': [
    obj({'revision': REVISION, 'head': HEAD, 'action': {'const': 'answered'}, 'reply': choice(*REPLIES)}),
    obj({'revision': REVISION, 'head': HEAD, 'action': choice('dispatched', 'received', 'cancelled')}),
]}, response=obj({'revision': REVISION, 'head': ID, 'state': ACTION}),
    summary='Dispatch, answer, acknowledge or cancel the exact private payroll question')
def act(request, case_id, question_id, *, body):
    case = accessible_case(request.user, case_id)
    get_object_or_404(selected(request.user, case), pk=question_id)
    try:
        event = domain.advance(request.user, case.pk, question_id, body['action'], body['head'],
                               body['revision'], body.get('reply'))
    except domain.StaleQuestion as exc:
        raise Problem(409, 'stale_version', exc.messages[0]) from exc
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'head': event.pk, 'state': event.kind}
