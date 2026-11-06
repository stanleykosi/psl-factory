from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from .billing import digest
from .rules import number
from . import cash
from .models import Invoice,InvoiceIssue,InvoiceJob,CashReceipt,CashVerification,CashAssignment,CashAllocation,CashReversal,ReceivableSnapshot
from apps.policy.services import resolve,reference_values


def facts(case):
    issues=list(InvoiceIssue.objects.filter(invoice__case=case).select_related('invoice__preparation__coverage'))
    receipts=list(CashReceipt.objects.filter(case=case));lots=list(CashVerification.objects.filter(receipt__case=case).select_related('receipt'))
    assignments=list(CashAssignment.objects.filter(receipt__case=case).order_by('pk'));allocs=list(CashAllocation.objects.filter(lot__receipt__case=case))
    reversals=list(CashReversal.objects.filter(actor__isnull=False).filter(lot__receipt__case=case))+list(CashReversal.objects.filter(allocation__lot__receipt__case=case))
    jobs=list(InvoiceJob.objects.filter(invoice__case=case))
    manifest={'implementation':'receivables/v2','issues':[r.pk for r in issues],'reported_receipts':[r.pk for r in receipts],'verified_lots':[r.pk for r in lots],
        'assignments':[r.pk for r in assignments],'allocations':[r.pk for r in allocs],'reversals':sorted(r.pk for r in reversals),
        'invoice_jobs':[[j.pk,j.status,j.fence] for j in jobs]}
    from .models import InvoiceCorrection,InvoiceCorrectionAcceptance,CashSuccessor,CashSuccessorAcceptance
    manifest['invoice_corrections']=list(InvoiceCorrection.objects.filter(case=case).values_list('pk',flat=True))
    manifest['applied_corrections']=list(InvoiceCorrectionAcceptance.objects.filter(correction__case=case).values_list('pk','sha256'))
    manifest['successor_requests']=list(CashSuccessor.objects.filter(case=case).values_list('pk',flat=True))
    manifest['accepted_successors']=list(CashSuccessorAcceptance.objects.filter(request__case=case).values_list('pk',flat=True))
    return manifest,issues,receipts,lots,assignments,allocs,reversals,jobs

def calculate(case,as_of):
    manifest,issues,receipts,lots,assignments,allocs,reversals,jobs=facts(case)
    manifest['as_of']=as_of.isoformat()
    groups={};rows=[];findings=[];pending=[]
    assignment={a.receipt_id:a for a in assignments};reversed_lots={r.lot_id for r in reversals if r.lot_id};reversed_allocs={r.allocation_id for r in reversals if r.allocation_id}
    live=[a for a in allocs if a.pk not in reversed_allocs and a.lot_id not in reversed_lots]
    method=resolve('D14.allocation_rule_ref',case);manifest['ageing_policy']={'status':method.status,'id':method.configuration.pk if method.configuration else None}
    overdue_enabled=method.status=='ACTIVE' and reference_values(method.configuration)[0]['overdue_definition']=='due_date_before_as_of'
    def group(customer,contract,currency,basis):
        key=(customer,contract,currency,basis)
        if key not in groups:groups[key]={'customer':customer,'contract':contract,'currency':currency,'amount_basis':basis,'receivable':Decimal(0),'verified_cash':Decimal(0),'unallocated_cash':Decimal(0),'overdue':Decimal(0) if overdue_enabled else None}
        return groups[key]
    with localcontext() as ctx:
        ctx.prec=512
        for issue in issues:
            from .corrections import adjusted_face,state
            i=issue.invoice;cov=i.preparation.coverage;face=adjusted_face(issue);applied=sum((a.amount for a in live if a.issue_id==issue.pk),Decimal(0));open_=face-applied
            if open_<0:findings.append(f'Invoice {i.pk}: allocation conflict; negative open amount');open_=None
            g=group(cov.customer,cov.contract,i.currency,i.amount_basis)
            if open_ is None:g['receivable']=None
            elif g['receivable'] is not None:g['receivable']+=open_
            overdue=None if not overdue_enabled or i.due_date is None or open_ is None else open_ if i.due_date<as_of else Decimal(0)
            if overdue is None:g['overdue']=None
            elif g['overdue'] is not None:g['overdue']+=overdue
            rows.append({'invoice':i.pk,'issue':issue.pk,'reference':i.reference,'face':number(i.amount),'adjusted_face':number(face),'voided':state(issue)['voided'],'allocated':number(applied),'open':number(open_),'overdue':number(overdue),'due_date':i.due_date.isoformat() if i.due_date else None,'currency':i.currency,'amount_basis':i.amount_basis})
        unmatched=[]
        for lot in lots:
            v=cash.lot_payload(lot);active=lot.pk not in reversed_lots;value=lot.amount if active else Decimal(0)
            applied=sum((a.amount for a in live if a.lot_id==lot.pk),Decimal(0));remaining=value-applied;a=assignment.get(lot.receipt_id)
            if remaining<0:findings.append(f'Cash lot {lot.pk}: negative available capacity');remaining=None
            if not a or not a.coverage_id:
                unmatched.append({'lot':lot.pk,'receipt':lot.receipt_id,'customer':v['customer'],'amount':number(value),'unallocated':number(remaining),'currency':v['currency'],'amount_basis':v['amount_basis'],'reversed':not active})
            else:
                g=group(v['customer'],a.coverage.contract,v['currency'],v['amount_basis']);g['verified_cash']+=value
                if remaining is None:g['unallocated_cash']=None
                elif g['unallocated_cash'] is not None:g['unallocated_cash']+=remaining
        proven={r.receipt_id for r in lots}
        reported=[{'receipt':r.pk,'source':r.source,'transaction':r.transaction_ref,'amount':r.payload['amount'],'currency':r.payload['currency'],'amount_basis':r.payload['amount_basis']} for r in receipts if r.pk not in proven]
    issued_invoice_ids={r.invoice_id for r in issues};issued_keys={r.obligation_key for r in issues};latest={}
    for i in Invoice.objects.filter(case=case).order_by('pk'):latest[i.obligation_key]=i
    drafts=[{'invoice':i.pk,'reference':i.reference,'amount':number(i.amount),'currency':i.currency,'amount_basis':i.amount_basis} for key,i in latest.items() if key not in issued_keys]
    uncertain=[{'job':j.pk,'invoice':j.invoice_id,'kind':j.kind,'status':j.status} for j in jobs if j.kind=='issue' and j.status in ['unknown','leased'] and j.invoice_id not in issued_invoice_ids]
    from .models import InvoiceCorrection,InvoiceCorrectionAcceptance,CashSuccessor,CashSuccessorAcceptance
    correction_queue=[{'correction':c.pk,'reference':c.reference,'kind':c.kind,'invoice':c.issue.invoice_id} for c in InvoiceCorrection.objects.filter(case=case) if not InvoiceCorrectionAcceptance.objects.filter(correction=c).exists()]
    successor_queue=[{'request':s.pk,'parent':s.parent_id,'amount':s.payload['amount']} for s in CashSuccessor.objects.filter(case=case) if not CashSuccessorAcceptance.objects.filter(request=s).exists()]
    uncertain_corrections=[{'job':j.pk,'correction':j.intent.get('correction'),'status':j.status} for j in jobs if j.kind=='adjust' and j.status in ['unknown','leased'] and not InvoiceCorrectionAcceptance.objects.filter(correction_id=j.intent.get('correction')).exists()]
    result={'groups':[{k:number(v) if isinstance(v,Decimal) else v for k,v in g.items()} for g in groups.values()],
        'invoices':rows,'pending_corrections':correction_queue,'uncertain_corrections':uncertain_corrections,'pending_cash_successors':successor_queue,'unmatched_cash':unmatched,'reported_unverified':reported,'unbilled_drafts':drafts,'uncertain_issuance':uncertain,'findings':findings,
        'coverage':'exact_case_captured_records_only','payment_assessment':'UNKNOWN: D13 payment basis/qualification not evaluated','deployment_authorized':False,'ledger_posted':False}
    manifest['invoice_versions']=[[i.pk,i.sha256] for i in latest.values()]
    return manifest,result

@transaction.atomic
def snapshot(actor,case_id,as_of,expected):
    case=lock_case(actor,case_id,'finance.receivables',expected)
    from apps.identity.services import require
    require(actor,case,'finance.read')
    if as_of!=timezone.localdate():raise ValidationError('This snapshot implementation supports actual current-day evidence only; historical reconstruction is a separate method')
    manifest,result=calculate(case,as_of)
    record=ReceivableSnapshot.objects.create(case=case,as_of=as_of,manifest=manifest,result=result,sha256=digest({'manifest':manifest,'result':result}),actor=actor)
    event(actor,case,'finance.receivables_snapshot',snapshot=record.pk);bump(case);return record
