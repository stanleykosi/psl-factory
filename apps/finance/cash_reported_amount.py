"""Retain a known amount on an originally Unknown receipt before first verification."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from adapters.cash_statements import parse
from apps.core.services import bump, event, lock_case
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from .models import CashReceipt, CashReportedAmount, CashVerification


AUTHOR_ACTIONS = ('case.read', 'finance.read', 'evidence.add', 'finance.cash.record')


def authorize(actor, receipt):
    if actor.pk != receipt.actor_id:
        raise PermissionDenied('The original receipt recorder supplies its corrected amount.')
    for action in AUTHOR_ACTIONS:
        require(actor, receipt.case, action)


def checked_payload(receipt, evidence):
    value = parse(evidence.body)
    base = receipt.payload
    if (base['amount'] is not None or value['amount'] is None
            or {key: field for key, field in value.items() if key != 'amount'}
                != {key: field for key, field in base.items() if key != 'amount'}):
        raise ValidationError('A known amount is required for the same bank source and original receipt facts.')
    return value


def latest(receipt):
    if receipt.payload['amount'] is not None:
        return None
    return CashReportedAmount.objects.filter(receipt=receipt).select_related('evidence','actor').defer('evidence__body').first()


def current(receipt):
    supplement = latest(receipt)
    if not supplement:
        return None
    authorize(supplement.actor, receipt)
    if (supplement.evidence.case_id != receipt.case_id or supplement.evidence.kind != 'cash_report'
            or supplement.evidence.created_by_id != supplement.actor_id
            or supplement.evidence_id == receipt.evidence_id
            or checked_payload(receipt, supplement.evidence) != supplement.payload):
        raise ValidationError('Review the exact supplied amount and original receipt facts.')
    return supplement


@transaction.atomic
def record(actor, case_id, receipt_id, evidence_id, reason, expected):
    case = lock_case(actor, case_id, 'finance.cash.record', expected)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    receipt = CashReceipt.objects.filter(case=case,pk=receipt_id).first()
    if not receipt:
        raise ValidationError('Select the exact receipt in this workspace.')
    authorize(actor, receipt)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:
        raise ValidationError('Explain how the exact bank amount became known.')
    if CashVerification.objects.filter(receipt=receipt).exists():
        raise ValidationError('This receipt already has a verified lot. Use the original cash correction path.')
    evidence = subject(case,evidence_id,'cash_report',metadata_only=True)
    if evidence.created_by_id!=actor.pk or evidence.pk==receipt.evidence_id:
        raise PermissionDenied('Supply new statement evidence recorded by the original receipt holder.')
    value = checked_payload(receipt,evidence)
    previous = latest(receipt)
    if previous:
        if previous.evidence_id==evidence.pk and previous.reason==reason.strip():
            return previous
        raise ValidationError('The exact receipt already has a supplied amount awaiting verification.')
    supplement = CashReportedAmount.objects.create(receipt=receipt,evidence=evidence,payload=value,
                                                  reason=reason.strip(),actor=actor)
    event(actor,case,'cash.reported_amount_supplied',receipt=receipt.pk,supplement=supplement.pk)
    bump(case)
    return supplement
