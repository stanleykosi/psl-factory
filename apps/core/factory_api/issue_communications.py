"""Reviewed owner messages and original delivery evidence."""

from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.identity.services import require
from apps.pmo import issue_messages as native
from apps.pmo.issue_access import public_current_issues
from apps.pmo.issue_message_models import IssueMessageDispatch, IssueMessageDraft, IssueMessageReview
from apps.policy.document_validators import ROLES

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .issues import REASON, project


KIND = choice('request', 'reminder')
ROLE = choice(*ROLES)
VERDICT = choice('approve', 'return', 'reject')
CHANNEL = choice('email', 'whatsapp', 'ticket')
BODY = {**TEXT, 'maxLength': 3000}
RECORD = obj({'id': nullable(ID), 'case_revision': REVISION})
RECEIPT = obj({'id': ID, 'delivered': BOOLEAN, 'delivered_at': nullable(DATETIME), 'recorded_at': DATETIME,
               'source_evidence_id': nullable(ID), 'reference': TEXT})
ITEM = obj({'draft_id': ID, 'version': ID, 'kind': KIND, 'body': BODY, 'status': TEXT,
            'review_id': nullable(ID), 'verdict': nullable(VERDICT), 'dispatch_id': nullable(ID),
            'receipt': nullable(RECEIPT), 'finding': {'type': 'string'}})
TIMING = obj({'last_receipt_id': nullable(ID), 'reminder_due_at': nullable(DATETIME),
              'escalation_due_at': nullable(DATETIME), 'reminder_overdue': BOOLEAN, 'escalation_overdue': BOOLEAN,
              'escalation_target': nullable(TEXT), 'finding': {'type': 'string'}})


def scope(request, case_id, issue_id):
    case = project(request.user, case_id)
    require(request.user, case, 'issue.message.read')
    issue = get_object_or_404(public_current_issues(case).select_related('current'), pk=issue_id)
    return case, issue


def item(actor, draft):
    native.readable(actor, draft)
    review = IssueMessageReview.objects.filter(draft=draft).first()
    dispatch = None
    visible_receipt = None
    label, finding = 'Review needed', ''
    if review:
        try:
            native.review_readable(actor, review)
        except (ValidationError, PermissionDenied):
            review = None
            label = 'Review needs access'
    if review:
        dispatch = IssueMessageDispatch.objects.filter(review=review).first()
        if dispatch:
            label, receipt, finding = native.status(dispatch, actor)
            if receipt:
                visible_receipt = {'id': receipt.pk, 'delivered': receipt.delivered,
                                   'delivered_at': receipt.delivered_at, 'recorded_at': receipt.created_at,
                                   'source_evidence_id': receipt.source_evidence_id, 'reference': receipt.reference}
        else:
            label = {'approve': 'Wording approved', 'return': 'Returned for changes', 'reject': 'Rejected'}[review.verdict]
    return {'draft_id': draft.pk, 'version': draft.number, 'kind': draft.kind, 'body': draft.body, 'status': label,
            'review_id': review.pk if review else None, 'verdict': review.verdict if review else None,
            'dispatch_id': dispatch.pk if dispatch else None, 'receipt': visible_receipt, 'finding': finding}


@endpoint(response=obj({'case_revision': REVISION, 'state_id': ID, 'items': array(ITEM, limit=20),
                        'evidence': array(PROOF, limit=35), 'timing': nullable(TIMING)}),
          summary='Read scoped owner message versions, human reviews and exact original receipt evidence')
def index(request, case_id, issue_id):
    case, issue = scope(request, case_id, issue_id)
    with limit_queries(1000):
        messages = []
        for draft in issue.message_drafts.select_related('issue__case', 'state', 'actor').order_by('-number')[:20]:
            try:
                messages.append(item(request.user, draft))
            except (PermissionDenied, ValidationError):
                continue
        proofs = public_evidence(case.evidence.filter(kind__in=('document', 'support_message', 'project_artifact',
            'issue_delivery_source'))).only('id', 'kind', 'version').order_by('-pk')[:35]
        timing = None
        try:
            schedule = native.chronology(request.user, case, issue_id)
        except (PermissionDenied, ValidationError):
            pass
        else:
            now = timezone.now()
            timing = {key: schedule[key] for key in ('reminder_due_at', 'escalation_due_at', 'escalation_target', 'finding')}
            timing['last_receipt_id'] = schedule['last_delivery'].pk if schedule['last_delivery'] else None
            for name in ('reminder', 'escalation'):
                due = schedule[f'{name}_due_at']
                timing[f'{name}_overdue'] = due is not None and now >= due and issue.current.acknowledged_at is None
        return {'case_revision': case.revision, 'state_id': issue.current_id, 'items': messages,
                'evidence': proof_rows(proofs), 'timing': timing}


COMMANDS = {
    'prepare': {'state_id': ID, 'kind': KIND, 'operation_key': UUID},
    'edit': {'state_id': ID, 'kind': KIND, 'operation_key': UUID, 'draft_id': ID, 'body': BODY,
             'evidence_id': ID, 'reason': REASON},
    'review': {'draft_id': ID, 'role': ROLE, 'verdict': VERDICT, 'evidence_id': ID, 'reason': REASON},
    'release': {'review_id': ID, 'role': ROLE, 'channel': CHANNEL, 'not_before': nullable(DATETIME)},
    'begin_manual': {'dispatch_id': ID},
    'attest': {'dispatch_id': ID, 'role': ROLE, 'source_evidence_id': ID, 'reference': {**TEXT, 'maxLength': 160},
               'delivered': BOOLEAN, 'delivered_at': nullable(DATETIME), 'checked': BOOLEAN},
    'lookup': {'dispatch_id': ID, 'role': ROLE},
    'cancel': {'dispatch_id': ID, 'role': ROLE, 'reason': REASON},
}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': action}, 'case_revision': REVISION, **fields}) for action, fields in COMMANDS.items()
]}, response=RECORD, status=201, summary='Prepare, review, release or recover this issue’s exact owner message')
def command(request, case_id, issue_id, *, body):
    case, issue = scope(request, case_id, issue_id)
    actor = request.user
    action = body['action']
    expected = body['case_revision']
    for key, model, relation in (('draft_id', IssueMessageDraft, 'issue'), ('review_id', IssueMessageReview, 'draft__issue'),
                                 ('dispatch_id', IssueMessageDispatch, 'review__draft__issue')):
        if key in body:
            get_object_or_404(model, pk=body[key], **{relation: issue})
    if action in ('prepare', 'edit'):
        extra = {'previous_id': body['draft_id'], 'body': body['body'], 'evidence_id': body['evidence_id'],
                 'reason': body['reason']} if action == 'edit' else {}
        row = native.prepare(actor, case.pk, issue.pk, body['state_id'], body['kind'], body['operation_key'],
                             expected, **extra)
    elif action == 'review':
        row = native.review(actor, case.pk, body['draft_id'], body['role'], body['verdict'], body['evidence_id'],
                            body['reason'], expected)
    elif action == 'release':
        when = datetime.fromisoformat(body['not_before']) if body['not_before'] else None
        row = native.release(actor, case.pk, body['review_id'], body['role'], body['channel'], expected, not_before=when)
    elif action == 'begin_manual':
        row = native.begin_manual(actor, case.pk, body['dispatch_id'], expected)
    elif action == 'attest':
        when = datetime.fromisoformat(body['delivered_at']) if body['delivered_at'] else None
        row = native.attest(actor, case.pk, body['dispatch_id'], body['role'], body['source_evidence_id'], body['reference'],
                            body['delivered'], when, body['checked'], expected)
    elif action == 'lookup':
        row = native.recover(actor, case.pk, body['dispatch_id'], body['role'], expected)
    else:
        row = native.cancel(actor, case.pk, body['dispatch_id'], body['role'], body['reason'], expected)
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk if row else None, 'case_revision': case.revision}
