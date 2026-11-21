"""Plain inputs for the native receipt, verification and allocation commands."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import logging
import re
import secrets

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import Http404

from adapters import case_uploads
from adapters.billing_usage import KEY
from adapters.cash_statements import parse
from apps.core.evidence_access import CASH_BANK_SOURCE_PREFIX
from apps.core.models import Audit
from apps.core.services import add_evidence, event, lock_case
from apps.identity.services import require
from apps.policy.services import active_component, reference_values
from apps.workflows.factory_ppe_opening import pdf_bytes
from . import cash
from .fixed_charge import preparation_access
from .models import CashReceipt, CashVerification, InvoiceIssue


PROOF = 'factory.cash_bank_proof_retained'
SOURCE_POLICY = 'D14.receipt_verification_source_ref'
VERIFIER_POLICY = 'D14.recorder_authority_ref'
ALLOCATION_POLICY = 'D14.allocation_rule_ref'
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Proof:
    name: str
    key: str
    size: int
    sha256: str
    locator: str


def issue_for(actor, case, issue_id):
    require(actor,case,'case.read')
    require(actor,case,'finance.read')
    issue=InvoiceIssue.objects.filter(invoice__case=case,pk=issue_id).select_related('invoice__preparation__coverage').first()
    if not issue:
        raise Http404('Invoice unavailable.')
    preparation_access(actor,issue.invoice.preparation)
    return issue


def read_receipt(case, issue, pk):
    receipt=CashReceipt.objects.filter(case=case,pk=pk).select_related('evidence','actor').first()
    if not receipt or receipt.payload['customer']!=issue.invoice.preparation.coverage.customer:
        raise Http404('Receipt unavailable.')
    return receipt


def roles_for(actor, case, component, action):
    require(actor,case,'evidence.add')
    policy=active_component(component,case)
    roles=[]
    for role in reference_values(policy)[0]['roles']:
        try:
            cash.authority_facts(actor,case,component,role,action)
        except (PermissionDenied,ValidationError):
            continue
        roles.append(role)
    return roles


def exact_proof(receipt, lot=None):
    row=lot or receipt
    evidence=row.evidence
    if not evidence.source.startswith(CASH_BANK_SOURCE_PREFIX):
        return None
    pin=Audit.objects.filter(case=receipt.case,action=PROOF,actor_id=row.actor_id,data__receipt=receipt.pk,
        data__lot=lot.pk if lot else None,data__evidence=evidence.pk,data__evidence_sha256=evidence.sha256
    ).values_list('data',flat=True).first()
    if not pin:
        return None
    key=pin.get('key')
    name=pin.get('name')
    size=pin.get('size')
    digest=pin.get('sha256')
    locator=pin.get('locator')
    if (not isinstance(key,str) or not re.fullmatch(f'bank-proof-{receipt.pk}-'+r'[0-9a-f]{48}',key)
            or not isinstance(name,str) or not name.lower().endswith('.pdf') or len(name)>160
            or type(size) is not int or not 0<size<=case_uploads.LIMIT
            or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest)
            or not isinstance(locator,str) or evidence.source!=CASH_BANK_SOURCE_PREFIX+locator):
        return None
    return Proof(name,key,size,digest,locator)


@contextmanager
def capture_transaction():
    staged=[]
    try:
        with transaction.atomic(durable=True):
            yield staged
    except Exception as exc:
        for key in staged:
            try:
                if not Audit.objects.filter(action=PROOF,data__key=key).exists():
                    case_uploads.discard_unbound(key)
            except (DatabaseError,OSError,ValidationError):
                LOGGER.warning('Private bank proof needs storage reconciliation')
        if isinstance(exc,OSError):
            raise ValidationError('Private bank proof storage is unavailable. Try again later.') from exc
        raise


def record_pdf(actor, case, receipt, evidence, locator, name, data, staged, lot=None):
    digest=hashlib.sha256(data).hexdigest()
    key=f'bank-proof-{receipt.pk}-'+secrets.token_hex(24)
    event(actor,case,PROOF,receipt=receipt.pk,lot=lot.pk if lot else None,evidence=evidence.pk,
          evidence_sha256=evidence.sha256,key=key,sha256=digest,size=len(data),name=name,locator=locator)
    staged.append(key)
    case_uploads.put(key,data)


def supplied_evidence(actor, case, kind, payload, locator):
    if not isinstance(locator,str) or not KEY.fullmatch(locator):
        raise ValidationError('Enter a bounded statement reference.')
    evidence=add_evidence(actor,case.pk,kind,json.dumps(payload,sort_keys=True),CASH_BANK_SOURCE_PREFIX+locator,case.revision)
    case.refresh_from_db(fields=['revision'])
    return evidence


def report(actor, case_id, issue_id, revision, facts, locator, file):
    with capture_transaction() as staged:
        case=lock_case(actor,case_id,'finance.cash.record',revision)
        issue=issue_for(actor,case,issue_id)
        require(actor,case,'evidence.add')
        value=parse(json.dumps(facts))
        if value['customer']!=issue.invoice.preparation.coverage.customer:
            raise ValidationError('Use the exact customer for this invoice.')
        name,data=pdf_bytes(file)
        previous=CashReceipt.objects.filter(case=case,source=value['source'],transaction_ref=value['transaction_ref']).first()
        if previous:
            proof=exact_proof(previous)
            if (previous.payload!=value or not proof or proof.locator!=locator
                    or proof.sha256!=hashlib.sha256(data).hexdigest()):
                raise ValidationError('This bank reference already has a receipt. Review the original before correcting it.')
            return previous
        evidence=supplied_evidence(actor,case,'cash_report',value,locator)
        receipt=cash.report(actor,case.pk,evidence.pk,case.revision)
        if receipt.evidence_id!=evidence.pk:
            raise ValidationError('This bank reference already has a receipt. Review the original.')
        record_pdf(actor,case,receipt,evidence,locator,name,data,staged)
        return receipt


def proof_policy(case):
    return reference_values(active_component(SOURCE_POLICY,case))[0]


def verify(actor, case_id, issue_id, receipt_id, revision, role, locator, file):
    with capture_transaction() as staged:
        case=lock_case(actor,case_id,'finance.cash.verify',revision)
        issue=issue_for(actor,case,issue_id)
        receipt=read_receipt(case,issue,receipt_id)
        require(actor,case,'evidence.add')
        require(receipt.actor,case,'finance.cash.record')
        require(receipt.actor,case,'evidence.add')
        original=exact_proof(receipt)
        if original is None or receipt.payload['amount'] is None:
            raise ValidationError('An exact report with a known bank amount is needed before verification.')
        if CashVerification.objects.filter(receipt=receipt,successor__isnull=True).exists():
            raise ValidationError('The original receipt already has a verification.')
        policy=proof_policy(case)
        if file:
            name,data=pdf_bytes(file)
            if policy['require_independent_evidence'] and (
                    locator==original.locator or hashlib.sha256(data).hexdigest()==original.sha256):
                raise ValidationError('The rule requires a different statement reference and independent file.')
        elif policy['require_independent_evidence']:
            raise ValidationError('Upload the independent bank statement required by the verification rule.')
        else:
            locator=original.locator
            name,data=original.name,case_uploads.read(original)
        evidence=supplied_evidence(actor,case,'cash_verification',receipt.payload,locator)
        lot=cash.verify(actor,case.pk,receipt.pk,role,evidence.pk,case.revision)
        record_pdf(actor,case,receipt,evidence,locator,name,data,staged,lot=lot)
        return lot


@transaction.atomic
def allocate(actor, case_id, issue_id, receipt_id, revision, role, amount, key, reason):
    case=lock_case(actor,case_id,'finance.cash.allocate',revision)
    issue=issue_for(actor,case,issue_id)
    receipt=read_receipt(case,issue,receipt_id)
    require(actor,case,'evidence.add')
    lot=CashVerification.objects.filter(receipt=receipt).order_by('-pk').first()
    if not lot:
        raise ValidationError('Verify the receipt before applying it to an invoice.')
    coverage=issue.invoice.preparation.coverage
    payload={'receipt':receipt.pk,'verified_lot':lot.pk,'issued_invoice':issue.pk,'amount':amount,'reason':reason}
    original=cash.assigned(receipt)
    if not original or not original.coverage_id:
        scoped=supplied_evidence(actor,case,'cash_correction',payload,'allocation-assignment')
        cash.assign(actor,case.pk,receipt.pk,coverage.pk,role,scoped.pk,reason,case.revision)
        case.refresh_from_db(fields=['revision'])
    elif (original.coverage.customer,original.coverage.contract)!=(coverage.customer,coverage.contract):
        raise ValidationError('The receipt is assigned to a different contract. Review the original assignment.')
    evidence=supplied_evidence(actor,case,'cash_allocation',payload,'allocation-treatment')
    row=cash.allocate(actor,case.pk,lot.pk,issue.pk,amount,key,role,evidence.pk,case.revision)
    if row.evidence_id!=evidence.pk:
        raise ValidationError('This exact allocation has already been recorded.')
    return row
