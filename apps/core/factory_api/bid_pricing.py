"""Current bid calculation and reviewed Security estimate requests."""

from datetime import date
from uuid import UUID as real_uuid

from django.core.exceptions import PermissionDenied, ValidationError

from adapters.costing import VALUE
from apps.core.evidence_access import public_evidence
from apps.finance.rules import decimal
from apps.pmo import rfp_estimate_model as model, rfp_estimate_requests as estimate
from apps.workflows import factory_rfp, factory_rfp_adjustments as adjustments, factory_rfp_pricing as pricing

from .commands import require_line
from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


AMOUNT = {'type': 'string', 'maxLength': 64}
NOTE = {**TEXT, 'maxLength': 2000}
KEY = {**TEXT, 'maxLength': 100}
CHANNEL = choice('email', 'whatsapp')
DATE = {'type': 'string', 'format': 'date'}
FILE = obj({'id': ID, 'name': TEXT})
APPROVAL_STATUS = {'Not yet recorded': 'pending', 'Approved': 'approved', 'Returned': 'returned',
                   'Rejected': 'rejected', 'Withdrawn': 'withdrawn', 'Recorded decision': 'recorded',
                   'Earlier decision needs fresh review': 'review_needed'}


@endpoint(response=obj({**VERSIONS, 'commercial_revision_id': nullable(ID), 'commercial_revision': nullable(ID),
    'inputs': array(obj({'label': TEXT, 'version': nullable(ID)})), 'amounts': array(VALUE),
    'approvals': array(obj({'label': TEXT, 'role': TEXT, 'status': TEXT, 'status_code': choice(*APPROVAL_STATUS.values()),
                           'recorded_at': nullable(DATETIME)})),
    'costing_note': TEXT, 'current': BOOLEAN, 'estimate_missing': BOOLEAN, 'security_estimate_missing': BOOLEAN,
    'can_open_calculator': BOOLEAN, 'adjustment_run_id': nullable(ID),
    'adjustment_targets': array(obj({'key': KEY, 'label': TEXT, 'max_absolute_value': AMOUNT})),
    'adjustment_currency': nullable(TEXT), 'can_configure': BOOLEAN}),
    summary='Read the reviewed bid calculation sources, amounts, approval and exact adjustment choices')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_rfp.DEFINITION)
    row = pricing.inspect(actor, work)
    run, targets = None, {}
    try:
        run, targets, _, _ = adjustments.contract(actor, work)
    except (PermissionDenied, ValidationError):
        pass
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'commercial_revision_id': row['revision_id'], 'commercial_revision': row['revision'],
            'inputs': [{'label': label, 'version': version} for label, version in row['inputs']],
            'amounts': row['amounts'], 'approvals': [
                {'label': label, 'role': role, 'status': status, 'status_code': APPROVAL_STATUS[status], 'recorded_at': at}
                for (role, _), (label, status, at) in zip(pricing.APPROVERS, row['approvals'], strict=True)],
            **{key: row[key] for key in ('costing_note', 'current', 'estimate_missing', 'security_estimate_missing',
                                         'can_open_calculator')},
            'adjustment_run_id': run.pk if run else None, 'adjustment_currency': run.rule.payload['currency'] if run else None,
            'adjustment_targets': [{'key': key, 'label': target['label'], 'max_absolute_value': target['max_absolute_value']}
                                   for key, target in targets.items()], 'can_configure': adjustments.can_configure(actor, work)}


@endpoint(method='POST', request=obj({**VERSIONS, 'target': KEY, 'amount': AMOUNT, 'reason': NOTE}),
          response=WORK_RESULT, summary='Apply an explicitly bounded adjustment and prepare fresh native bid review')
def adjust(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_rfp.DEFINITION)
    return result(adjustments.adjust(request.user, work.pk, body['expected_revision'], body['case_revision'],
                                     body['target'], decimal(body['amount']), body['reason']))


@endpoint(response=obj({'case_revision': REVISION, 'configuration_id': nullable(ID), 'channels': array(
    obj({'channel': CHANNEL, 'contact': TEXT, 'allow_attachment': BOOLEAN})),
    'draft_id': nullable(ID), 'draft_body': nullable(TEXT), 'model_turn_id': nullable(UUID),
    'model_status': nullable(TEXT), 'model_answer': nullable(TEXT), 'request_id': nullable(ID),
    'dispatch_id': nullable(ID), 'receipt': nullable(obj({'id': ID, 'reference': TEXT})),
    'can_use_model': BOOLEAN, 'attachments': array(FILE, limit=40), 'evidence': array(PROOF, limit=35)}),
    summary='Read the assigned Security estimate draft, authorised routes, review and original delivery receipt')
def security(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_rfp.DEFINITION)
    estimate.access(actor, work)
    config, routes = estimate.routes(work.case)
    draft = turn = answer = None
    try:
        _, pins = estimate.scope(actor, work)
    except (PermissionDenied, ValidationError):
        pass
    else:
        draft = estimate.current_draft(actor, work, pins)
        turn = model.latest(actor, work, pins)
        if turn and turn.status == 'answered':
            try:
                answer = model.checked_answer(actor, work, pins, turn.pk)
            except (PermissionDenied, ValidationError):
                pass
    reviewed = work.estimate_requests.filter(actor=actor).select_related('dispatch__receipt').order_by('-pk').first()
    dispatch = getattr(reviewed, 'dispatch', None)
    receipt = getattr(dispatch, 'receipt', None)
    evidence = public_evidence(work.case.evidence.filter(kind='policy_decision')).only('id', 'kind', 'version')
    return {'case_revision': work.case.revision, 'configuration_id': config.pk if config else None,
            'channels': [{key: row[key] for key in ('channel', 'contact', 'allow_attachment')} for row in routes.values()],
            'draft_id': draft.pk if draft else None, 'draft_body': draft.evidence.body if draft else None,
            'model_turn_id': str(turn.pk) if turn else None, 'model_status': turn.status if turn else None,
            'model_answer': answer.answer if answer else None, 'request_id': reviewed.pk if reviewed else None,
            'dispatch_id': dispatch.pk if dispatch else None,
            'receipt': {'id': receipt.pk, 'reference': receipt.reference} if receipt else None,
            'can_use_model': model.available(actor, work),
            'attachments': list(estimate.attachments(actor, work).values('id', 'name')[:40]) if any(
                route['allow_attachment'] for route in routes.values()) else [], 'evidence': proof_rows(evidence.order_by('-pk')[:35])}


COMMANDS = {
    'prepare': {}, 'prepare_with_assistant': {},
    'review': {'draft_id': ID, 'channel': CHANNEL, 'due_on': DATE, 'body': {**TEXT, 'maxLength': 4000},
               'evidence_id': ID, 'attachment_id': nullable(ID), 'model_turn_id': nullable(UUID)},
    'release': {'request_id': ID},
    'receipt': {'dispatch_id': ID, 'reference': {**TEXT, 'maxLength': 160}, 'delivered': BOOLEAN, 'evidence_id': ID},
}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': action}, 'case_revision': REVISION, **fields}) for action, fields in COMMANDS.items()
]}, response=obj({'id': nullable(ID), 'turn_id': nullable(UUID), 'case_revision': REVISION}), status=201,
    summary='Prepare, review, release or confirm one original Security estimate request')
def security_command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, factory_rfp.DEFINITION)
    args = (actor, work.pk, body['case_revision'])
    action = body['action']
    turn_id = None
    if action == 'prepare':
        row = estimate.prepare(*args)
    elif action == 'prepare_with_assistant':
        turn = model.request(*args)
        row, turn_id = None, str(turn.pk)
    elif action == 'review':
        row = estimate.review(*args, body['draft_id'], body['channel'], date.fromisoformat(body['due_on']), body['body'],
                              body['evidence_id'], body['attachment_id'],
                              real_uuid(body['model_turn_id']) if body['model_turn_id'] else None)
    elif action == 'release':
        row = estimate.release(*args, body['request_id'])
    else:
        row = estimate.record_receipt(*args, body['dispatch_id'], body['reference'], body['delivered'], body['evidence_id'])
    work.case.refresh_from_db(fields=['revision'])
    return {'id': row.pk if row else None, 'turn_id': turn_id, 'case_revision': work.case.revision}
