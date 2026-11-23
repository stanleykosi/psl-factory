"""Payment follow-up from the exact issued balance and reviewed billing contact."""
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from hashlib import sha256
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from adapters.reminders import check_evidence, encode_message, invoice_pdf, message_id, verify_message

from apps.agents.models import CaseUpload
from apps.core.client_contacts import authorize
from apps.core.models import Case, ClientContactRevision
from apps.core.services import bump, event, lock_case
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.pmo.services import subject
from apps.policy.reminder_validators import COMPONENT
from apps.policy.services import active_component, reference_values

from . import corrections
from .models import InvoiceIssue
from .reminder_models import (PaymentReminderDraft, PaymentReminderDispatch, PaymentReminderMailboxMessage,
                              PaymentReminderReceipt, PaymentReminderSetAside)
from .rules import number


def exact(actor, case, issue_id):
    require(actor, case, 'finance.reminder.read')
    authorize(actor, case, 'billing')
    issue = InvoiceIssue.objects.select_related('invoice__preparation__coverage').filter(
        pk=issue_id, invoice__case=case).first()
    if issue is None:
        raise ValidationError('Choose an issued invoice from this workspace.')
    return issue


def contact(issue):
    source = issue.invoice.preparation.coverage
    return ClientContactRevision.objects.filter(case=issue.invoice.case, purpose='billing',
                                                customer=source.customer).order_by('-number').first()


def facts(issue):
    state = corrections.state(issue)
    with localcontext() as precision:
        precision.prec = 512
        owed = Decimal(state['face']) - sum((Decimal(amount) for _, amount in state['allocations']), Decimal(0))
    return {'issue': issue.pk, 'source_sha256': digest(state), 'due_date': str(issue.invoice.due_date or ''),
            'currency': issue.invoice.currency, 'amount_basis': issue.invoice.amount_basis, 'owed': number(owed)}


def suggested(issue, balance):
    return (
        f'Payment follow-up for invoice {issue.invoice.reference}',
        f'Hello,\n\nWe are following up on invoice {issue.invoice.reference}, due {balance["due_date"] or "on the date in your invoice"}. '
        f'Our records show an outstanding balance of {balance["currency"]} {balance["owed"]}. '
        'If you have already paid, please share the payment reference so we can reconcile our records.\n\nThank you.',
    )


def _settings(case):
    cfg = active_component(COMPONENT, case)
    return cfg, reference_values(cfg)[0]


@transaction.atomic
def draft(actor, case_id, issue_id, title, body, expected, *, attachment_id=None):
    case = lock_case(actor, case_id, 'finance.reminder.prepare', expected)
    issue = exact(actor, case, issue_id)
    destination = contact(issue)
    if destination is None or not destination.email:
        raise ValidationError('Record the current billing contact before preparing this reminder.')
    balance = facts(issue)
    if Decimal(balance['owed']) <= 0:
        raise ValidationError('There is no positive issued balance to follow up.')
    if not title.strip() or len(title) > 180 or '\n' in title or '\r' in title or not body.strip() or len(body) > 10000:
        raise ValidationError('Enter a bounded subject and reminder message.')
    previous = issue.reminder_drafts.order_by('-number').first()
    values = {'issue': issue.pk, 'contact': destination.pk, 'subject': title, 'body': body, 'balance': balance}
    attachment = None
    if attachment_id is not None:
        attachment = CaseUpload.objects.filter(case=case, actor=actor, pk=attachment_id).first()
        if attachment is None:
            raise ValidationError('Choose an invoice PDF uploaded by you in this workspace.')
        invoice_pdf(attachment)
        values['attachment'] = {'id': attachment.pk, 'sha256': attachment.sha256}
    hash_ = digest(values)
    if previous and previous.sha256 == hash_ and not hasattr(previous, 'set_aside'):
        return previous
    item = PaymentReminderDraft.objects.create(issue=issue, contact=destination, number=previous.number+1 if previous else 1,
                                               subject=title, body=body, attachment=attachment, balance=balance, sha256=hash_, actor=actor)
    event(actor, case, 'reminder.draft_saved', draft=item.pk, issue=issue.pk)
    bump(case)
    return item


def _latest(issue, draft_id):
    current = issue.reminder_drafts.select_related('contact').order_by('-number').first()
    if current is None or current.pk != draft_id or hasattr(current, 'set_aside'):
        raise ValidationError('Select the current reminder version.')
    return current


def _bound_content(actor, case, issue, item):
    require(actor, case, 'finance.reminder.send')
    cfg, values = _settings(case)
    if actor.pk not in values['sender_ids']:
        raise PermissionDenied('A configured Finance sender is required.')
    if item.contact_id not in values['contact_revision_ids'] or item.contact != contact(issue):
        raise ValidationError('The current billing contact needs approval for reminder delivery.')
    if item.balance != facts(issue) or corrections.unresolved(issue):
        raise ValidationError('The balance changed or has an unresolved correction. Prepare a fresh draft.')
    if values.get('attachment_required') and not item.attachment_id:
        raise ValidationError('Attach the issued invoice PDF before releasing this reminder.')
    return cfg, values


def reminder_dates(issue, values):
    due = issue.invoice.due_date
    deliveries = PaymentReminderDispatch.objects.filter(draft__issue=issue)
    earlier = PaymentReminderReceipt.objects.filter(dispatch__in=deliveries, delivered=True).order_by('-created_at').first()
    due_on = due + timedelta(days=values['days_after_due']) if due else None
    interval_on = (timezone.localdate(earlier.created_at) + timedelta(days=values['minimum_days_between'])
                   if earlier else None)
    return due_on, interval_on, deliveries.filter(receipt__isnull=True).exists()


def send_ready(actor, case, issue, item, *, scheduled_for=None):
    cfg, values = _bound_content(actor, case, issue, item)
    now = timezone.now()
    if scheduled_for is not None:
        horizon = values.get('schedule_days_ahead')
        if (not horizon or values['mode'] != 'synthetic_mailbox' or not isinstance(scheduled_for, datetime) or timezone.is_naive(scheduled_for) or
                not now < scheduled_for <= now + timedelta(days=horizon)):
            raise ValidationError('Choose a future time within the configured scheduling window.')
    date = timezone.localdate(scheduled_for or now)
    due_on, interval_on, uncertain = reminder_dates(issue, values)
    if due_on is None or date < due_on:
        raise ValidationError('The usual reminder date has not arrived or its due date is unknown.')
    if uncertain:
        raise ValidationError('Confirm the earlier delivery outcome before sending another reminder.')
    if interval_on and date < interval_on:
        raise ValidationError('The configured interval between reminders has not elapsed.')
    return cfg, values


@transaction.atomic
def dispatch(actor, case_id, issue_id, draft_id, expected, *, scheduled_for=None):
    case = lock_case(actor, case_id, 'finance.reminder.send', expected)
    issue = exact(actor, case, issue_id)
    item = _latest(issue, draft_id)
    if hasattr(item, 'dispatch'):
        if item.dispatch.actor_id != actor.pk:
            raise PermissionDenied('The original reservation belongs to another sender.')
        if item.dispatch.scheduled_for != scheduled_for:
            raise ValidationError('This draft already has a release at a different time.')
        return item.dispatch
    cfg, values = send_ready(actor, case, issue, item, scheduled_for=scheduled_for)
    row = PaymentReminderDispatch.objects.create(draft=item, configuration=cfg, mode=values['mode'],
                                                 operation_key=uuid4(), actor=actor, scheduled_for=scheduled_for)
    event(actor, case, 'reminder.dispatch_reserved', draft=item.pk, dispatch=row.pk)
    bump(case)
    return row


@transaction.atomic
def set_aside(actor, case_id, issue_id, draft_id, reason, expected):
    case = lock_case(actor, case_id, 'finance.reminder.prepare', expected)
    item = _latest(exact(actor, case, issue_id), draft_id)
    if hasattr(item, 'dispatch') or not reason.strip() or len(reason) > 1000:
        raise ValidationError('Choose an unsent draft and enter a reason.')
    PaymentReminderSetAside.objects.create(draft=item, reason=reason, actor=actor)
    event(actor, case, 'reminder.set_aside', draft=item.pk)
    bump(case)


def _record(actor, case, row, reference, delivered, evidence=None):
    prior = PaymentReminderReceipt.objects.filter(dispatch=row).first()
    if prior:
        if (prior.reference, prior.delivered, prior.evidence_id) != (reference, delivered, evidence.pk if evidence else None):
            raise ValidationError('A different outcome is already recorded for this reminder.')
        return prior
    receipt = PaymentReminderReceipt.objects.create(dispatch=row, reference=reference, delivered=delivered,
                                                    sha256=row.draft.sha256, actor=actor, evidence=evidence)
    event(actor, case, 'reminder.delivery_checked', receipt=receipt.pk, dispatch=row.pk, delivered=delivered)
    bump(case)
    return receipt


@transaction.atomic
def confirm(actor, case_id, issue_id, dispatch_id, reference, delivered, evidence_id, expected):
    case = lock_case(actor, case_id, 'finance.reminder.confirm', expected)
    issue = exact(actor, case, issue_id)
    row = PaymentReminderDispatch.objects.select_related('draft').filter(pk=dispatch_id, draft__issue=issue).first()
    _, settings = _settings(case)
    if actor.pk not in settings['receipt_recorder_ids']:
        raise PermissionDenied('A configured receipt reviewer is required.')
    if row is None or row.mode != 'manual_evidence' or type(delivered) is not bool or not reference.strip() or len(reference) > 160:
        raise ValidationError('Choose exact dispatch evidence from the approved channel.')
    evidence = subject(case, evidence_id, 'payment_reminder_receipt')
    check_evidence(evidence.body, row.operation_key, row.draft.sha256, row.draft.contact.email, reference, delivered)
    return _record(actor, case, row, reference, delivered, evidence)


@transaction.atomic
def simulate(dispatch_id):
    """Synthetic delivery and retry readback share one committed receipt."""
    row = PaymentReminderDispatch.objects.select_related('actor', 'draft__issue__invoice').get(pk=dispatch_id)
    actor = row.actor
    case = lock_case(actor, row.draft.issue.invoice.case_id, 'finance.reminder.send')
    if row.mode != 'synthetic_inbox' or not case.synthetic:
        raise ValidationError('This dispatch requires its configured delivery channel.')
    prior = PaymentReminderReceipt.objects.filter(dispatch=row).first()
    if prior:
        return prior
    issue = exact(actor, case, row.draft.issue_id)
    item = row.draft
    cfg, _ = _bound_content(actor, case, issue, item)
    if cfg.pk != row.configuration_id:
        raise ValidationError('Current scope or balance changed; hold this dispatch for reconciliation.')
    return _record(actor, case, row, f'synthetic-reminder:{row.operation_key}', True)


def _mailbox_dispatch(dispatch_id):
    row = PaymentReminderDispatch.objects.select_related('draft__issue__invoice', 'draft__attachment',
                                                        'draft__contact', 'actor').get(pk=dispatch_id)
    case = Case.objects.select_for_update().get(pk=row.draft.issue.invoice.case_id)
    if row.mode != 'synthetic_mailbox' or not case.synthetic:
        raise ValidationError('This reminder has a different delivery channel.')
    return row, case


@transaction.atomic
def deliver_to_mailbox(dispatch_id):
    """The isolated transport commits the exact MIME message before receipt readback."""
    row, case = _mailbox_dispatch(dispatch_id)
    if PaymentReminderMailboxMessage.objects.filter(dispatch=row).exists():
        return
    if PaymentReminderReceipt.objects.filter(dispatch=row).exists():
        return
    if row.scheduled_for and timezone.now() < row.scheduled_for:
        return
    try:
        issue = exact(row.actor, case, row.draft.issue_id)
        cfg, _ = _bound_content(row.actor, case, issue, row.draft)
        if cfg.pk != row.configuration_id:
            raise ValidationError('Review the changed release rules.')
        wire = encode_message(row)
    except (PermissionDenied, ValidationError):
        # No mailbox record exists, and no external transfer has been attempted.
        return _record(row.actor, case, row, 'Release held after changes to the source or authority', False)
    PaymentReminderMailboxMessage.objects.create(dispatch=row, message=wire, sha256=sha256(wire).hexdigest())


@transaction.atomic
def verify_mailbox(dispatch_id):
    row, case = _mailbox_dispatch(dispatch_id)
    prior = PaymentReminderReceipt.objects.filter(dispatch=row).first()
    if prior:
        return prior
    received = PaymentReminderMailboxMessage.objects.filter(dispatch=row).first()
    if received is None:
        return None
    verify_message(row, bytes(received.message), received.sha256)
    return _record(row.actor, case, row, message_id(row), True)


def run_mailbox(dispatch_id):
    receipt = verify_mailbox(dispatch_id)
    if receipt is not None:
        return receipt
    deliver_to_mailbox(dispatch_id)
    return verify_mailbox(dispatch_id)


@transaction.atomic
def check_mailbox(actor, case_id, issue_id, dispatch_id):
    case = lock_case(actor, case_id, 'finance.reminder.confirm')
    issue = exact(actor, case, issue_id)
    _, values = _settings(case)
    if actor.pk not in values['receipt_recorder_ids']:
        raise PermissionDenied('A configured receipt reviewer is required.')
    if not PaymentReminderDispatch.objects.filter(pk=dispatch_id, draft__issue=issue, mode='synthetic_mailbox').exists():
        raise ValidationError('Choose the original test mailbox release.')
    return verify_mailbox(dispatch_id)


@transaction.atomic
def cancel_schedule(actor, case_id, issue_id, dispatch_id, expected):
    case = lock_case(actor, case_id, 'finance.reminder.send', expected)
    issue = exact(actor, case, issue_id)
    _, values = _settings(case)
    if actor.pk not in values['sender_ids']:
        raise PermissionDenied('A configured Finance sender is required.')
    row = PaymentReminderDispatch.objects.filter(draft__issue=issue, pk=dispatch_id, mode='synthetic_mailbox',
                                                 scheduled_for__isnull=False).select_related('draft').first()
    if row is None or PaymentReminderMailboxMessage.objects.filter(dispatch=row).exists():
        raise ValidationError('A message already accepted by the mailbox must be verified.')
    return _record(actor, case, row, 'Scheduled release cancelled', False)
