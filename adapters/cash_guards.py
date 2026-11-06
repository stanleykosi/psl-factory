"""Native cash verification/allocation facts only; no cash lot or allocation is created."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from apps.identity.services import require
from apps.finance import cash
from apps.finance.models import CashReceipt,CashVerification,CashAllocation,CashReversal,InvoiceIssue
from apps.policy.impact import digest


def readable(actor,case):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current Finance cash reader required')
    for action in ['case.read','finance.read']:require(actor,case,action)


def verify(actor,case,cash_receipt_id,role,cash_verification_evidence_id):
    r,amount,auth,old=cash.guard_verify(actor,case,cash_receipt_id,role,cash_verification_evidence_id)
    return r,{'authority':auth,'amount_sha256':digest(str(amount)),'existing_authority':old.authority if old else {},
        'scope':'cash_verification_only','cash_created':False,'business_approval':False},old


def allocate(actor,case,cash_lot_id,issued_invoice_id,cash_amount,operation_key,role,cash_allocation_evidence_id):
    lot,issue,n,auth,e,old=cash.guard_allocate(actor,case,cash_lot_id,issued_invoice_id,cash_amount,operation_key,role,cash_allocation_evidence_id)
    return lot,{'authority':auth,'amount_sha256':digest(str(n)),'existing_authority':old.authority if old else {},
        'scope':'cash_allocation_only','cash_allocated':False,'business_approval':False},old


def head(actor,case,args):
    readable(actor,case)
    if 'cash_receipt_id' in args:r=CashReceipt.objects.filter(case=case,pk=args['cash_receipt_id']).first()
    else:
        lot=CashVerification.objects.select_related('receipt').filter(receipt__case=case,pk=args['cash_lot_id']).first()
        r=lot.receipt if lot else None
    if not r:return None
    lots=list(r.cashverification_set.values_list('pk',flat=True))
    position=None
    if 'cash_lot_id' in args:
        from apps.finance.corrections import state
        issue=InvoiceIssue.objects.filter(invoice__case=case,pk=args['issued_invoice_id']).first()
        if lot and issue:position=digest({'cash_remaining':str(cash.cash_remaining(lot)),'open':str(cash.open_amount(issue)),'invoice':state(issue)})
    return {'receipt':r.pk,'report_sha256':r.evidence.sha256,'lots':lots,
        'assignments':list(r.cashassignment_set.values_list('pk',flat=True)),
        'allocations':list(CashAllocation.objects.filter(lot_id__in=lots).values_list('pk',flat=True)),
        'reversals':list(CashReversal.objects.filter(Q(lot_id__in=lots)|Q(allocation__lot_id__in=lots)).values_list('pk',flat=True)),
        'position_sha256':position,
        'scope':'cash_facts_only','business_approval':False,'cash_changed':False}
