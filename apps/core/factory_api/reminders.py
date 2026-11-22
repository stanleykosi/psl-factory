"""Payment reminders, delivery reservations and verified channel readback."""
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.finance import reminders
from apps.finance.reminder_views import DraftForm
from apps.identity.services import active_case_grants, require

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .workspaces import DATES


MODE = choice('manual_evidence', 'synthetic_mailbox')
RECEIPT = obj({'id': ID, 'reference': TEXT, 'delivered': BOOLEAN, 'recorded_at': DATETIME})
DISPATCH = obj({'id': ID, 'mode': MODE, 'scheduled_for': nullable(DATETIME), 'receipt': nullable(RECEIPT)})
DRAFT = obj({'id': ID, 'number': REVISION, 'subject': TEXT, 'message': TEXT, 'set_aside': BOOLEAN,
             'attachment_url': nullable(TEXT), 'mailbox_download_url': nullable(TEXT),
             'dispatch': nullable(DISPATCH)})
RIGHTS = ('finance.reminder.prepare', 'finance.reminder.send', 'finance.reminder.confirm')
CHOICE = obj({'id': ID, 'label': TEXT})


def exact(actor, case_id, issue_id):
    case = accessible_case(actor, case_id)
    try:
        return case, reminders.exact(actor, case, issue_id)
    except ValidationError as exc:
        raise Http404 from exc


def receipt_payload(row):
    if row is None:
        return None
    return {'id': row.pk, 'reference': row.reference, 'delivered': row.delivered, 'recorded_at': row.created_at}


def dispatch_payload(row):
    if row is None:
        return None
    return {'id': row.pk, 'mode': row.mode, 'scheduled_for': row.scheduled_for,
            'receipt': receipt_payload(getattr(row, 'receipt', None))}


def draft_payload(case, issue, row):
    dispatch = getattr(row, 'dispatch', None)
    receipt = getattr(dispatch, 'receipt', None)
    url_args = [case.pk, issue.pk, row.pk]
    return {'id': row.pk, 'number': row.number, 'subject': row.subject, 'message': row.body,
            'set_aside': hasattr(row, 'set_aside'), 'dispatch': dispatch_payload(dispatch),
            'attachment_url': reverse('design_reminder_download', args=[*url_args, 'pdf']) if row.attachment_id else None,
            'mailbox_download_url': reverse('design_reminder_download', args=[*url_args, 'email'])
            if case.synthetic and dispatch and dispatch.mode == 'synthetic_mailbox' and receipt and receipt.delivered else None}


def proof_choices(case):
    return public_evidence(case.evidence.filter(kind='payment_reminder_receipt')).only('kind', 'version')


@endpoint(response=obj({
    'revision': REVISION, 'issue_id': ID, 'reference': TEXT,
    'balance': obj({'due_date': nullable(DATES), 'currency': TEXT, 'amount_basis': TEXT, 'owed': TEXT}),
    'recipient': nullable(obj({'id': ID, 'name': TEXT, 'email': {'type': 'string'}})),
    'suggested_subject': TEXT, 'suggested_message': TEXT, 'mode': nullable(MODE), 'hold': nullable(TEXT),
    'can_prepare': BOOLEAN, 'can_schedule': BOOLEAN, 'can_confirm': BOOLEAN,
    'history': array(DRAFT, limit=20), 'attachments': array(CHOICE, limit=50), 'receipt_proofs': array(CHOICE, limit=25),
}), summary='Read the exact outstanding balance, reminder history and current delivery controls')
def detail(http, case_id, issue_id):
    actor = http.user
    case, issue = exact(actor, case_id, issue_id)
    rights = {action for _, action in active_case_grants(actor, [case.pk], actions=RIGHTS)}
    history = list(issue.reminder_drafts.select_related('dispatch__receipt', 'set_aside').order_by('-number')[:20])
    current = history[0] if history else None
    contact, balance = reminders.contact(issue), reminders.facts(issue)
    subject, message = reminders.suggested(issue, balance)
    can_prepare = 'finance.reminder.prepare' in rights
    can_confirm = False
    if 'finance.reminder.confirm' in rights:
        try:
            _, rules = reminders._settings(case)
            can_confirm = actor.pk in rules['receipt_recorder_ids']
        except ValidationError:
            pass
    attachments = (DraftForm(actor, case).fields['attachment'].queryset.only('name') if can_prepare else [])
    mode, hold, scheduling = None, None, False
    if current and not hasattr(current, 'dispatch') and not hasattr(current, 'set_aside'):
        try:
            _, values = reminders._bound_content(actor, case, issue, current)
            scheduling = values['mode'] == 'synthetic_mailbox' and bool(values.get('schedule_days_ahead'))
            _, settings = reminders.send_ready(actor, case, issue, current)
            mode = settings['mode']
        except PermissionDenied:
            hold = 'A configured Finance sender can release the saved draft.'
        except ValidationError as exc:
            hold = exc.messages[0]
    return {'revision': case.revision, 'issue_id': issue.pk, 'reference': issue.invoice.reference,
            'balance': {**{name: balance[name] for name in ('currency', 'amount_basis', 'owed')},
                        'due_date': balance['due_date'] or None},
            'recipient': {'id': contact.pk, 'name': contact.name, 'email': contact.email} if contact else None,
            'suggested_subject': subject, 'suggested_message': message, 'mode': mode, 'hold': hold,
            'can_prepare': can_prepare, 'can_schedule': scheduling, 'can_confirm': can_confirm,
            'history': [draft_payload(case, issue, item) for item in history],
            'attachments': [{'id': upload.pk, 'label': upload.name} for upload in attachments],
            'receipt_proofs': [{'id': row.pk, 'label': f'Channel evidence · version {row.version}'}
                               for row in proof_choices(case).order_by('-pk')[:25]] if can_confirm else []}


@endpoint(method='POST', request=obj({
    'revision': REVISION, 'subject': {**TEXT, 'maxLength': 180}, 'message': {**TEXT, 'maxLength': 10000},
    'attachment_id': nullable(ID), 'attachment_checked': BOOLEAN,
}, optional=('attachment_id', 'attachment_checked')), response=DRAFT, status=201,
          summary='Save the reminder draft and optional exact checked invoice PDF')
def draft(http, case_id, issue_id, *, body):
    actor = http.user
    case, issue = exact(actor, case_id, issue_id)
    require(actor, case, 'finance.reminder.prepare')
    form = DraftForm(actor, case, {'subject': body['subject'], 'body': body['message'],
                                   'attachment': body.get('attachment_id'), 'attachment_checked': body.get('attachment_checked')})
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the reminder draft and invoice attachment.',
                      fields=[{'name': key, 'message': errors[0]} for key, errors in form.errors.items()])
    values = form.cleaned_data
    try:
        result = reminders.draft(actor, case.pk, issue.pk, values['subject'], values['body'], body['revision'],
                                 attachment_id=values['attachment'].pk if values['attachment'] else None)
    except OSError as exc:
        raise Problem(503, 'storage_unavailable', 'The exact invoice PDF could not be checked.') from exc
    return draft_payload(case, issue, result)


COMMAND = {'oneOf': [
    obj({'action': {'const': 'send'}, 'draft_id': ID, 'revision': REVISION, 'scheduled_for': nullable(DATETIME)},
        optional=('scheduled_for',)),
    obj({'action': {'const': 'set_aside'}, 'draft_id': ID, 'revision': REVISION, 'reason': {**TEXT, 'maxLength': 1000}}),
    obj({'action': {'const': 'cancel_schedule'}, 'dispatch_id': ID, 'revision': REVISION}),
    obj({'action': {'const': 'check_mailbox'}, 'dispatch_id': ID}),
    obj({'action': {'const': 'confirm'}, 'dispatch_id': ID, 'revision': REVISION, 'evidence_id': ID,
         'delivered': BOOLEAN, 'reference': {**TEXT, 'maxLength': 160}}),
]}


@endpoint(method='POST', request=COMMAND, response=obj({
    'revision': REVISION, 'dispatch': nullable(DISPATCH), 'receipt': nullable(RECEIPT),
}), summary='Release, schedule, reconcile or close an exact payment reminder')
def command(http, case_id, issue_id, *, body):
    actor = http.user
    case, issue = exact(actor, case_id, issue_id)
    action, revision = body['action'], body.get('revision')
    dispatch, receipt = None, None
    if action == 'send':
        scheduled = body.get('scheduled_for')
        dispatch = reminders.dispatch(actor, case.pk, issue.pk, body['draft_id'], revision,
                                      scheduled_for=datetime.fromisoformat(scheduled) if scheduled else None)
    elif action == 'set_aside':
        reminders.set_aside(actor, case.pk, issue.pk, body['draft_id'], body['reason'], revision)
    elif action == 'cancel_schedule':
        receipt = reminders.cancel_schedule(actor, case.pk, issue.pk, body['dispatch_id'], revision)
    elif action == 'check_mailbox':
        receipt = reminders.check_mailbox(actor, case.pk, issue.pk, body['dispatch_id'])
    elif action == 'confirm':
        if not proof_choices(case).filter(pk=body['evidence_id']).exists():
            raise Http404
        receipt = reminders.confirm(actor, case.pk, issue.pk, body['dispatch_id'], body['reference'],
                                    body['delivered'], body['evidence_id'], revision)
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'dispatch': dispatch_payload(dispatch), 'receipt': receipt_payload(receipt)}
