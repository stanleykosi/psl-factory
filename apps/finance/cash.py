from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,IntegrityError
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.pmo.services import subject
from adapters.cash_statements import parse
from .analysis import note
from .billing import exact
from .rules import decimal
from .models import BillingCoverage,InvoiceIssue,CashReceipt,CashVerification,CashAssignment,CashAllocation,CashReversal


def exact_receipt(case,pk):return exact(case,CashReceipt,pk)
def lot_for(case,pk):
    lot=CashVerification.objects.filter(pk=pk,receipt__case=case).first()
    if not lot:raise ValidationError('Select exact case verified cash lot')
    return lot

def assigned(receipt):return CashAssignment.objects.filter(receipt=receipt).order_by('-pk').first()
def allocations(lot=None,issue=None):
    q=CashAllocation.objects.all()
    if lot:q=q.filter(lot=lot)
    if issue:q=q.filter(issue=issue)
    return q.filter(cashreversal__isnull=True,lot__cashreversal__isnull=True)

def sum_amount(q):
    with localcontext() as c:
        c.prec=512;return sum((r.amount for r in q),Decimal(0))

def cash_remaining(lot):
    if CashReversal.objects.filter(lot=lot).exists():return Decimal(0)
    with localcontext() as ctx:
        ctx.prec=512;return lot.amount-sum_amount(allocations(lot=lot))
def lot_payload(lot):return lot.successor.payload if lot.successor_id else lot.receipt.payload

def open_amount(issue):
    from .corrections import adjusted_face
    with localcontext() as ctx:
        ctx.prec=512;return adjusted_face(issue)-sum_amount(allocations(issue=issue))

def authority(actor,case,component,role,action,source_actor=None):
    from apps.identity.models import Grant
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    return authority_facts(actor,case,component,role,action)


def authority_facts(actor,case,component,role,action):
    require(actor,case,action);config=active_component(component,case);values=reference_values(config)
    rule=values[0]
    if role not in rule['roles']:raise PermissionDenied('Role is not configured for this cash action')
    auth=dict(decision_authority(actor,case,role),**{component:config.pk,'rule':rule})
    return rule,auth

@transaction.atomic
def report(actor,case_id,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.cash.record',expected);e=subject(case,evidence_id,'cash_report');value=parse(e.body)
    previous=CashReceipt.objects.filter(tenant=case.tenant,source=value['source'],transaction_ref=value['transaction_ref']).first()
    if previous:
        if previous.case_id!=case.pk:raise ValidationError('Source transaction identity is already registered in this tenant; reconcile under authorised Finance access')
        if previous.payload!=value:raise ValidationError('Same source transaction has changed facts; investigate explicit correction, never duplicate cash')
        return previous
    try:
        with transaction.atomic():r=CashReceipt.objects.create(case=case,tenant=case.tenant,source=value['source'],transaction_ref=value['transaction_ref'],payload=value,evidence=e,actor=actor)
    except IntegrityError:
        raise ValidationError('Source transaction identity was concurrently registered; reconcile before retry')
    event(actor,case,'cash.reported',receipt=r.pk);bump(case);return r

@transaction.atomic
def verify(actor,case_id,receipt_id,role,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.cash.verify',expected)
    r,amount,auth,old=guard_verify(actor,case,receipt_id,role,evidence_id,lock=True)
    if old:return old
    lot=CashVerification.objects.create(receipt=r,amount=amount,evidence_id=evidence_id,authority=auth,actor=actor)
    event(actor,case,'cash.verified',lot=lot.pk,receipt=r.pk);bump(case);return lot


def guard_verify(actor,case,receipt_id,role,evidence_id,*,lock=False):
    require(actor,case,'finance.cash.verify');r=exact_receipt(case,receipt_id)
    old=CashVerification.objects.filter(receipt=r,successor__isnull=True).first()
    if old:return r,None,{},old
    amount,auth=verification_facts(actor,case,r.payload,r.evidence,r.actor_id,role,evidence_id,lock=lock)
    return r,amount,auth,None

def verification_facts(actor,case,payload,report_evidence,report_actor_id,role,evidence_id,*,lock=True):
    source_config=active_component('D14.receipt_verification_source_ref',case);source=reference_values(source_config)[0]
    rule,auth=(authority if lock else authority_facts)(actor,case,'D14.recorder_authority_ref',role,'finance.cash.verify')
    if report_actor_id==actor.pk and not rule['allow_reporter_verify']:raise PermissionDenied('Configured cash verifier must differ from reporter')
    e=subject(case,evidence_id,'cash_verification');v=parse(e.body)
    if v!=payload or v['amount'] is None:raise ValidationError('Verification source must match exact reported known cash facts')
    if (v['source'],v['currency'],v['amount_basis'])!=(source['source'],source['currency'],source['amount_basis']):raise ValidationError('Receipt does not match configured verification source/dimensions')
    if source['require_independent_evidence'] and e.source==report_evidence.source:raise ValidationError('Configured independent verification evidence requires a distinct declared source locator from the report')
    amount=decimal(v['amount'],positive=True)
    with localcontext() as c:
        c.prec=512
        if amount!=amount.quantize(Decimal(1).scaleb(-source['decimal_places'])):raise ValidationError('Receipt exceeds configured cash precision')
    auth[source_config.component]=source_config.pk
    return amount,auth

def correction_authority(actor,case,target,role,lot):
    from apps.identity.models import Grant
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    require(actor,case,'finance.cash.reverse')
    c=active_component('D14.adjustment_correction_rule_refs',case);legal=active_component('D14.legal_document_requirements',case)
    matches=[r for r in reference_values(c) if r['target']==target];docs=[r for r in reference_values(legal) if r['target']==target]
    if len(matches)!=1 or len(docs)!=1:raise ValidationError('Configure exact cash correction target and legal evidence requirements')
    rule=matches[0]
    if role not in rule['roles'] or rule['require_distinct_verifier'] and lot.actor_id==actor.pk:raise PermissionDenied('Current cash correction role/separation rule is not satisfied')
    return dict(decision_authority(actor,case,role),**{c.component:c.pk,legal.component:legal.pk,'rule':rule,'legal':docs[0]})

@transaction.atomic
def reverse(actor,case_id,target,subject_id,role,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.cash.reverse',expected);note(reason)
    if target=='lot':lot=lot_for(case,subject_id);allocation=None
    elif target=='allocation':
        allocation=CashAllocation.objects.filter(pk=subject_id,lot__receipt__case=case).first()
        if not allocation:raise ValidationError('Select exact case allocation')
        lot=allocation.lot
    else:raise ValidationError('Only full cash-lot or allocation reversals are implemented')
    auth=correction_authority(actor,case,target,role,lot);e=subject(case,evidence_id,'cash_correction')
    if CashReversal.objects.filter(**{target:lot if target=='lot' else allocation}).exists():raise ValidationError('Exact cash subject already fully reversed')
    if target=='allocation' and CashReversal.objects.filter(lot=lot).exists():raise ValidationError('Cash lot was already reversed atomically')
    if target=='lot':
        for a in allocations(lot=lot):CashReversal.objects.create(allocation=a,evidence=e,authority=auth,reason=reason,actor=actor)
    r=CashReversal.objects.create(lot=lot if target=='lot' else None,allocation=allocation,evidence=e,authority=auth,reason=reason,actor=actor)
    event(actor,case,'cash.full_reversal',target=target,subject=subject_id,reversal=r.pk);bump(case);return r

@transaction.atomic
def assign(actor,case_id,receipt_id,coverage_id,role,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.cash.assign',expected);r=exact_receipt(case,receipt_id);note(reason)
    cov=exact(case,BillingCoverage,coverage_id) if coverage_id else None
    rule,auth=authority(actor,case,'D14.allocation_rule_ref',role,'finance.cash.assign')
    if cov and cov.customer!=r.payload['customer']:raise ValidationError('Cash customer differs from contract coverage')
    prior=assigned(r);lot=CashVerification.objects.filter(receipt=r).order_by('-pk').first()
    if prior and prior.coverage_id==coverage_id:raise ValidationError('Receipt already has this assignment')
    if prior and not rule['allow_reassignment']:raise ValidationError('Configured allocation policy does not allow reassignment')
    if prior and lot and allocations(lot=lot).exists():
        reversal_auth=correction_authority(actor,case,'allocation',role,lot)
        for a in allocations(lot=lot):CashReversal.objects.create(allocation=a,evidence=subject(case,evidence_id,'cash_correction'),authority=reversal_auth,reason=reason,actor=actor)
    e=subject(case,evidence_id,'cash_correction')
    a=CashAssignment.objects.create(receipt=r,coverage=cov,evidence=e,authority=auth,reason=reason,actor=actor)
    event(actor,case,'cash.assigned',receipt=r.pk,coverage=cov.pk if cov else None,assignment=a.pk);bump(case);return a

@transaction.atomic
def allocate(actor,case_id,lot_id,issue_id,amount,operation_key,role,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.cash.allocate',expected)
    lot,issue,n,auth,e,old=guard_allocate(actor,case,lot_id,issue_id,amount,operation_key,role,evidence_id,lock=True)
    if old:return old
    row=CashAllocation.objects.create(lot=lot,issue=issue,amount=n,operation_key=operation_key,evidence=e,authority=auth,actor=actor)
    event(actor,case,'cash.allocated',allocation=row.pk,lot=lot.pk,invoice=issue.invoice_id);bump(case);return row


def guard_allocate(actor,case,lot_id,issue_id,amount,operation_key,role,evidence_id,*,lock=False):
    require(actor,case,'finance.cash.allocate');lot=lot_for(case,lot_id)
    issue=InvoiceIssue.objects.filter(pk=issue_id,invoice__case=case).select_related('invoice__preparation__coverage').first()
    if not issue:raise ValidationError('Allocation requires exact case proven invoice issuance')
    from adapters.billing_usage import KEY
    if not KEY.fullmatch(operation_key):raise ValidationError('Explicit bounded allocation operation key required')
    n=decimal(amount,positive=True)
    old=CashAllocation.objects.filter(lot=lot,operation_key=operation_key).first()
    if old:
        if old.issue_id!=issue.pk or old.amount!=n:raise ValidationError('Allocation operation identity changed facts')
        return lot,issue,n,{},None,old
    rule,auth=(authority if lock else authority_facts)(actor,case,'D14.allocation_rule_ref',role,'finance.cash.allocate')
    with localcontext() as ctx:
        ctx.prec=512
        if n!=n.quantize(Decimal(1).scaleb(-rule['decimal_places'])):raise ValidationError('Allocation exceeds configured precision; no implicit rounding')
    if lot.actor_id==actor.pk and not rule['allow_verifier_allocation']:raise PermissionDenied('Configured allocator must differ from verifier')
    if CashReversal.objects.filter(lot=lot).exists():raise ValidationError('Cash lot has been reversed')
    from .corrections import unresolved,state
    if unresolved(issue):raise ValidationError('Invoice correction is reserved or uncertain; reconcile before new allocation')
    if state(issue)['voided']:raise ValidationError('Voided obligation cannot consume cash')
    a=assigned(lot.receipt);cov=issue.invoice.preparation.coverage;v=lot_payload(lot)
    if not a or not a.coverage_id:raise ValidationError('Assign verified receipt to an explicit contract before allocating')
    if (a.coverage.customer,a.coverage.contract)!=(cov.customer,cov.contract):raise ValidationError('Receipt and invoice belong to different customer/contract')
    if (v['currency'],v['amount_basis'])!=(issue.invoice.currency,issue.invoice.amount_basis):raise ValidationError('Receipt and invoice currency/basis differ; no implicit FX')
    with localcontext() as c:
        c.prec=512
        if n>cash_remaining(lot) or n>open_amount(issue):raise ValidationError('Allocation exceeds current verified cash or open invoice capacity')
    return lot,issue,n,auth,subject(case,evidence_id,'cash_allocation'),None
