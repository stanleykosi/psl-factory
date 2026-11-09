"""Explicit reassignment after acknowledgement; no renewed receipt or invoice approval."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.documents.contracts import validate
from apps.identity.services import require
from . import contract_coverage as cc
from .models import (CoveragePreparationContinuation, CoveragePreparationRequest,
    CoveragePreparationReceipt, CoverageAssessment, CoverageFixedCharge, InvoiceJob)

ID={'type':'integer','minimum':1}
DECLARATION=cc.obj({'implementation':{'const':'fixed-preparation-continuation/v1'},
    'receipt':ID,'request':ID,'assessment':ID,'recipient':ID,
    'previous':{'anyOf':[ID,{'type':'null'}]},'reason':{'type':'string','minLength':1,'maxLength':1000}})


def latest(request):
    return CoveragePreparationContinuation.objects.filter(receipt__request=request).order_by('-version').first()


def identity(record):
    validate(DECLARATION,record.payload)
    receipt=cc.receipt_identity(record.receipt);request=receipt.request
    expected={'implementation':'fixed-preparation-continuation/v1','receipt':receipt.pk,'request':request.pk,
        'assessment':record.assessment_id,'recipient':record.recipient_id,'previous':record.previous_id,
        'reason':record.payload['reason']}
    if record.payload!=expected or not record.payload['reason'].strip():
        raise ValidationError('Exact continuation identity and reason required')
    if receipt.preparation_id:
        raise ValidationError('A usage-bound acknowledgement is not a fixed-contract continuation')
    if record.assessment.terms.case_id!=request.assessment.terms.case_id:
        raise ValidationError('Continuation must retain the exact case and source-backed obligation')
    previous=record.previous
    if record.version!=(previous.version+1 if previous else 1) or previous and previous.receipt_id!=receipt.pk:
        raise ValidationError('Exact append-only continuation predecessor required')
    rows=[r for r in record.assessment.result['obligations'] if r['key']==request.obligation_key]
    if len(rows)!=1 or cc.obligation(record.assessment.terms,{k:rows[0][k] for k in ['start','end','bill_on']})!=request.obligation_key:
        raise ValidationError('Continuation changes the exact source-backed obligation')
    terms=record.assessment.terms
    proof=cc.evidence(terms.case,record.evidence_id,'coverage_continuation',
        [terms.register.reference,terms.contract.reference],'prepare')
    if cc.supplied_json(proof)!=expected:raise ValidationError('Continuation differs from exact private evidence')
    return record


def access(actor,record,*,current=False):
    require(actor,record.assessment.terms.case,'case.read')
    cc.terms_access(actor,record.assessment.terms,'read',current=False)
    identity(record)
    if current:
        if latest(record.receipt.request).pk!=record.pk:raise ValidationError('A newer continuation exists')
        require(record.actor,record.assessment.terms.case,'case.read')
        require(record.recipient,record.assessment.terms.case,'case.read')
        cc.terms_access(record.actor,record.assessment.terms,'prepare')
        cc.terms_access(record.recipient,record.assessment.terms,'read')
        cc.terms_access(record.recipient,record.assessment.terms,'receive')
        require(record.recipient,record.assessment.terms.case,'finance.billing.prepare')
        require(record.recipient,record.assessment.terms.case,'finance.read')
        if cc.active_findings(actor,record.assessment.terms):raise ValidationError('Current continuation source interpretation requires reconciliation')
    return record


def unresolved(request):
    # A transfer never grants permission to send again while any prior effect is uncertain.
    if InvoiceJob.objects.filter(invoice__preparation__fixed_charge__request=request,
            status__in=['leased','unknown','held']).exists():
        raise ValidationError('Reconcile the original uncertain invoice receipt before continuation')
    from .fixed_charge import conflicting_effect
    charge=CoverageFixedCharge.objects.filter(request=request).order_by('-version').first()
    if charge:
        from .fixed_charge import obligation
        if InvoiceJob.objects.filter(invoice__obligation_key=obligation(charge),status__in=['leased','unknown','held']).exists():
            raise ValidationError('Reconcile the original exact-obligation effect before continuation')
        conflicting_effect(charge,permit_own_issue=True)


@transaction.atomic
def assign(actor,case_id,request_id,assessment_id,recipient_id,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'coverage.prepare',expected);require(actor,case,'case.read')
    request=cc.exact(case,CoveragePreparationRequest,request_id)
    receipt=CoveragePreparationReceipt.objects.filter(request=request).first()
    if not receipt:raise ValidationError('A committed original acknowledgement is required')
    assessment=cc.exact(case,CoverageAssessment,assessment_id)
    cc.terms_access(actor,assessment.terms,'prepare')
    recipient=get_user_model().objects.filter(pk=recipient_id,is_active=True).first()
    if not recipient:raise PermissionDenied('Current same-case Finance recipient required')
    require(recipient,case,'case.read');cc.terms_access(recipient,assessment.terms,'read')
    cc.terms_access(recipient,assessment.terms,'receive');require(recipient,case,'finance.billing.prepare');require(recipient,case,'finance.read')
    prior=latest(request)
    # Exact replay recovers existing history; it does not silently renew its authorizer.
    if prior and (prior.assessment_id,prior.recipient_id,prior.evidence_id,prior.payload['reason'])==(assessment.pk,recipient.pk,evidence_id,reason):
        return access(actor,prior,current=True)
    if prior and prior.assessment_id==assessment.pk and prior.recipient_id==recipient.pk:
        try:access(actor,prior,current=True)
        except (PermissionDenied,ValidationError):pass
        else:return prior
    result=cc.current_assessment(actor,assessment)
    if result['status']!='assessed':raise ValidationError('Current coverage assessment is held')
    unresolved(request)
    payload={'implementation':'fixed-preparation-continuation/v1','receipt':receipt.pk,'request':request.pk,
        'assessment':assessment.pk,'recipient':recipient.pk,'previous':prior.pk if prior else None,'reason':reason}
    record=CoveragePreparationContinuation(receipt=receipt,assessment=assessment,recipient=recipient,
        previous=prior,version=prior.version+1 if prior else 1,payload=payload,evidence_id=evidence_id,actor=actor)
    identity(record)
    record.save(force_insert=True)
    event(actor,case,'coverage.preparation_continued',continuation=record.pk,receipt=receipt.pk,recipient=recipient.pk)
    bump(case)
    return record
