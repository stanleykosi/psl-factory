from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values
from decimal import Decimal,localcontext
from apps.pmo.services import subject
from adapters.financial_corrections import parse_successor
from .analysis import note
from .models import CashSuccessor,CashVerification,CashReversal,CashSuccessorAcceptance,CashAssignment
from . import cash,financial_reviews

@transaction.atomic
def capture(actor,case_id,parent_id,evidence_id,verification_id,legal_id,reason,expected):
    case=lock_case(actor,case_id,'finance.cash.successor.request',expected);require(actor,case,'finance.read');note(reason)
    parent=cash.lot_for(case,parent_id);e=subject(case,evidence_id,'cash_report');value=parse_successor(e.body)
    base=cash.lot_payload(parent)
    if {k:v for k,v in base.items() if k!='amount'}!={k:v for k,v in value.items() if k!='amount'}:raise ValidationError('Successor preserves source transaction/customer/currency/basis/time; only amount correction is supported')
    if base['amount']==value['amount']:raise ValidationError('Successor must correct the reported amount, not duplicate a cash lot')
    old=CashSuccessor.objects.filter(case=case,parent=parent,evidence=e).first()
    if old:return old
    r=CashSuccessor.objects.create(case=case,parent=parent,evidence=e,verification_evidence=subject(case,verification_id,'cash_verification'),
        legal_evidence=subject(case,legal_id,'cash_correction'),payload=value,reason=reason,actor=actor)
    event(actor,case,'cash.successor_requested',request=r.pk,parent=parent.pk);bump(case);return r

def review_snapshot(r):
    require(r.actor,r.case,'finance.cash.successor.request')
    parent=r.parent;receipt=parent.receipt
    latest=CashVerification.objects.filter(receipt=receipt).order_by('-pk').first()
    if latest.pk!=parent.pk or CashSuccessorAcceptance.objects.filter(parent=parent).exists():raise ValidationError('Another successor already advanced this transaction lineage')
    reversal=CashReversal.objects.filter(lot=parent).first()
    if not reversal:raise ValidationError('Full predecessor cash-lot reversal is required; reporting remains available')
    if r.payload['amount'] is None:raise ValidationError('Corrected amount remains unknown')
    if parse_successor(r.verification_evidence.body)!=r.payload:raise ValidationError('Corrected verification statement differs from exact successor report')
    p=financial_reviews.policy(r.case,'cash_successor')
    if r.legal_evidence.kind!=p['legal']['evidence_kind']:raise ValidationError('Missing configured successor legal evidence')
    source=active_component('D14.receipt_verification_source_ref',r.case);recorder=active_component('D14.recorder_authority_ref',r.case)
    v=reference_values(source)[0]
    if (r.payload['source'],r.payload['currency'],r.payload['amount_basis'])!=(v['source'],v['currency'],v['amount_basis']):raise ValidationError('Corrected statement does not match configured source dimensions')
    if v['require_independent_evidence'] and r.evidence.source==r.verification_evidence.source:raise ValidationError('Corrected verification requires a distinct declared source locator')
    with localcontext() as ctx:
        ctx.prec=512
        amount=Decimal(r.payload['amount'])
        if amount!=amount.quantize(Decimal(1).scaleb(-v['decimal_places'])):raise ValidationError('Corrected amount exceeds verification precision')
    assignment=cash.assigned(receipt)
    matching=None
    if p['rule']['assignment']=='unmatched' and assignment and assignment.coverage_id:matching=active_component('D14.allocation_rule_ref',r.case).pk
    return {'implementation':'cash-successor/v1','parent':parent.pk,'parent_amount':str(parent.amount),'reversal':reversal.pk,'policy':p,
        'source':source.pk,'recorder':recorder.pk,'assignment':assignment.pk if assignment else None,'matching':matching,'report_hash':r.evidence.sha256,'verification_hash':r.verification_evidence.sha256,'legal_hash':r.legal_evidence.sha256}

@transaction.atomic
def apply(actor,case_id,request_id,role,expected):
    case=lock_case(actor,case_id,'finance.cash.successor.apply',expected)
    r=CashSuccessor.objects.filter(case=case,pk=request_id).first()
    if not r:raise ValidationError('Select this case successor request')
    previous=CashSuccessorAcceptance.objects.filter(request=r).first()
    if previous:return previous
    review=financial_reviews.approved(r)
    auth=financial_reviews.execution_authority(actor,r,'cash_successor',role,'finance.cash.successor.apply')
    amount,verification=cash.verification_facts(actor,case,r.payload,r.evidence,r.actor_id,role,r.verification_evidence_id)
    prior=cash.assigned(r.parent.receipt)
    if auth['rule']['assignment']=='unmatched' and prior and prior.coverage_id:
        matching,assignment_auth=cash.authority(actor,case,'D14.allocation_rule_ref',role,'finance.cash.assign')
        if not matching['allow_reassignment']:raise ValidationError('Configured matching does not allow successor ownership reset')
        CashAssignment.objects.create(receipt=r.parent.receipt,coverage=None,evidence=r.legal_evidence,authority=assignment_auth,reason=r.reason,actor=actor)
    lot=CashVerification.objects.create(receipt=r.parent.receipt,successor=r,amount=amount,evidence=r.verification_evidence,authority=verification,actor=actor)
    accepted=CashSuccessorAcceptance.objects.create(request=r,parent=r.parent,lot=lot,review=review,authority=auth,actor=actor)
    event(actor,case,'cash.successor_verified',request=r.pk,parent=r.parent_id,lot=lot.pk,acceptance=accepted.pk);bump(case);return accepted
