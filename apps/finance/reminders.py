"""Payment follow-up from the exact issued balance and reviewed billing contact."""
from datetime import timedelta
from decimal import Decimal, localcontext
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from adapters.reminders import check_evidence

from apps.core.client_contacts import authorize
from apps.core.models import ClientContactRevision
from apps.core.services import bump, event, lock_case
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.pmo.services import subject
from apps.policy.reminder_validators import COMPONENT
from apps.policy.services import active_component, reference_values

from . import corrections
from .models import InvoiceIssue
from .reminder_models import PaymentReminderDraft, PaymentReminderDispatch, PaymentReminderReceipt, PaymentReminderSetAside
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
def draft(actor, case_id, issue_id, title, body, expected):
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
    hash_ = digest(values)
    if previous and previous.sha256 == hash_ and not hasattr(previous, 'set_aside'):
        return previous
    item = PaymentReminderDraft.objects.create(issue=issue, contact=destination, number=previous.number+1 if previous else 1,
                                               subject=title, body=body, balance=balance, sha256=hash_, actor=actor)
    event(actor, case, 'reminder.draft_saved', draft=item.pk, issue=issue.pk)
    bump(case)
    return item


def _latest(issue, draft_id):
    current = issue.reminder_drafts.select_related('contact').order_by('-number').first()
    if current is None or current.pk != draft_id or hasattr(current, 'set_aside'):
        raise ValidationError('Select the current reminder version.')
    return current


def send_ready(actor, case, issue, item):
    require(actor, case, 'finance.reminder.send')
    cfg, values = _settings(case)
    if actor.pk not in values['sender_ids']:
        raise PermissionDenied('A configured Finance sender is required.')
    if item.contact_id not in values['contact_revision_ids'] or item.contact != contact(issue):
        raise ValidationError('The current billing contact needs approval for reminder delivery.')
    if item.balance != facts(issue) or corrections.unresolved(issue):
        raise ValidationError('The balance changed or has an unresolved correction. Prepare a fresh draft.')
    if issue.invoice.due_date is None or timezone.localdate() < issue.invoice.due_date + timedelta(days=values['days_after_due']):
        raise ValidationError('The usual reminder date has not arrived or its due date is unknown.')
    deliveries = PaymentReminderDispatch.objects.filter(draft__issue=issue)
    if deliveries.filter(receipt__isnull=True).exists():
        raise ValidationError('Confirm the earlier delivery outcome before sending another reminder.')
    earlier = PaymentReminderReceipt.objects.filter(dispatch__in=deliveries, delivered=True).order_by('-created_at').first()
    if earlier and timezone.localdate() < timezone.localdate(earlier.created_at) + timedelta(days=values['minimum_days_between']):
        raise ValidationError('The configured interval between reminders has not elapsed.')
    return cfg, values


@transaction.atomic
def dispatch(actor, case_id, issue_id, draft_id, expected):
    case = lock_case(actor, case_id, 'finance.reminder.send', expected)
    issue = exact(actor, case, issue_id)
    item = _latest(issue, draft_id)
    if hasattr(item, 'dispatch'):
        if item.dispatch.actor_id != actor.pk:
            raise PermissionDenied('The original reservation belongs to another sender.')
        return item.dispatch
    cfg, values = send_ready(actor, case, issue, item)
    row = PaymentReminderDispatch.objects.create(draft=item, configuration=cfg, mode=values['mode'],
                                                 operation_key=uuid4(), actor=actor)
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
    cfg, values = _settings(case)
    if (cfg.pk != row.configuration_id or actor.pk not in values['sender_ids'] or item.contact_id not in values['contact_revision_ids']
            or item.contact != contact(issue) or item.balance != facts(issue) or corrections.unresolved(issue)):
        raise ValidationError('Current scope or balance changed; hold this dispatch for reconciliation.')
    return _record(actor, case, row, f'synthetic-reminder:{row.operation_key}', True)
