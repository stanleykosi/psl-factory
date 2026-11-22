"""Human disposition of an invoice shortfall. The receivable remains authoritative."""
from decimal import Decimal, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404

from apps.core.services import bump, event, lock_case
from apps.documents.contracts import digest
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import decision_authority, reference_values, resolve
from apps.policy.short_payment_validators import COMPONENT, TREATMENTS

from . import cash, corrections
from .fixed_charge import preparation_access
from .models import InvoiceIssue, InvoiceShortPaymentDecision
from .rules import number


def exact_issue(actor, case, issue_id):
    for action in ('case.read', 'finance.read', 'finance.short_payment.read'):
        require(actor, case, action)
    issue = InvoiceIssue.objects.select_related('invoice__preparation__coverage').filter(
        pk=issue_id, invoice__case=case).first()
    if issue is None:
        raise Http404
    preparation_access(actor, issue.invoice.preparation)
    return issue


def position(issue):
    source = corrections.state(issue)
    with localcontext() as precision:
        precision.prec = 512
        received = sum((Decimal(amount) for _, amount in source['allocations']), Decimal(0))
        owed = Decimal(source['face']) - received
    return {'source': source, 'invoiced': source['face'], 'received': number(received), 'owed': number(owed),
            'currency': issue.invoice.currency, 'amount_basis': issue.invoice.amount_basis,
            'short_payment': received > 0 and owed > 0 and not source['voided']}


def treatments(actor, case):
    rule = resolve(COMPONENT, case)
    if rule.status != 'ACTIVE':
        return 'Short-payment rule needed', {}, {}
    value = reference_values(rule.configuration)[0]
    if value['reviewer_id'] is None:
        return 'Finance reviewer needed', {}, {}
    if value['reviewer_id'] != actor.pk:
        return 'Waiting for the assigned Finance reviewer', {}, {}
    try:
        require(actor, case, 'finance.short_payment.decide')
        authority = decision_authority(actor, case, 'Finance')
    except (PermissionDenied, ValidationError):
        return 'Current Finance reviewer authority needed', {}, {}
    return 'Current Finance review rule', {key: TREATMENTS[key] for key in value['treatments']}, {
        **authority, COMPONENT: rule.configuration.pk}


@transaction.atomic
def decide(actor, case_id, issue_id, revision, expected_position, allocation_id, treatment, reason):
    case = lock_case(actor, case_id, 'finance.short_payment.decide', revision)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    issue = exact_issue(actor, case, issue_id)
    current = position(issue)
    fingerprint = digest(current)
    if fingerprint != expected_position or not current['short_payment'] or corrections.unresolved(issue):
        raise ValidationError('Review the current invoice balance and resolve pending corrections first.')
    _, permitted, authority = treatments(actor, case)
    if treatment not in permitted:
        raise PermissionDenied('This Finance decision requires current configured authority.')
    allocation = cash.allocations(issue=issue).filter(pk=allocation_id).first()
    if allocation is None:
        raise ValidationError('Select a current verified payment allocated to this exact invoice.')
    reason = reason.strip()
    if not 1 <= len(reason) <= 2000:
        raise ValidationError('Enter a reason of at most 2,000 characters.')
    previous = issue.short_payment_decisions.order_by('-pk').first()
    if previous and (previous.position_sha256, previous.allocation_id, previous.treatment, previous.reason,
                     previous.actor_id, previous.authority) == (fingerprint, allocation.pk, treatment, reason, actor.pk, authority):
        return previous
    result = InvoiceShortPaymentDecision.objects.create(
        issue=issue, allocation=allocation, position=current, position_sha256=fingerprint,
        treatment=treatment, reason=reason, authority=authority, actor=actor)
    event(actor, case, 'finance.short_payment.decided', issue=issue.pk, decision=result.pk)
    bump(case)
    return result
