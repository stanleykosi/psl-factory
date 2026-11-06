from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.finance import financial_reviews,corrections,cash
from apps.finance.models import InvoiceCorrection,InvoiceCorrectionAcceptance,CashSuccessorAcceptance,FinancialCorrectionReview
from .models import AgentRun

@transaction.atomic
def investigate(actor,case_id,kind,request_id,expected):
    case=lock_case(actor,case_id,'agent.financial_corrections',expected);require(actor,case,'finance.read')
    r=financial_reviews.request_for(case,kind,request_id);citations={r.evidence_id};findings=[];applied=False
    if kind=='invoice':
        a=InvoiceCorrectionAcceptance.objects.filter(correction=r).first();applied=a is not None
        state=corrections.state(r.issue);citations.add(r.issue.invoice.preparation.coverage.evidence_id)
        if r.allocation_evidence_id:citations.add(r.allocation_evidence_id)
        lineage={'issue':r.issue_id,'canonical_obligation':r.issue.obligation_key,'original_face':str(r.issue.invoice.amount),'current_adjusted_face':state['face'],
            'voided':state['voided'],'applied_notes':state['applied'],'active_allocations':state['allocations'],'acceptance':a.pk if a else None}
    else:
        a=CashSuccessorAcceptance.objects.filter(request=r).first();applied=a is not None
        citations.update([r.verification_evidence_id,r.legal_evidence_id,r.parent.evidence_id,r.parent.receipt.evidence_id])
        lineage={'source':r.parent.receipt.source,'transaction':r.parent.receipt.transaction_ref,'parent_lot':r.parent_id,'parent_gross':str(r.parent.amount),
            'parent_available':str(cash.cash_remaining(r.parent)),'proposed_amount':r.payload['amount'],'accepted_lot':a.lot_id if a else None,'acceptance':a.pk if a else None}
    q={'correction':r} if kind=='invoice' else {'successor':r}
    citations.update(FinancialCorrectionReview.objects.filter(**q).values_list('evidence_id',flat=True))
    if not applied:
        try:financial_reviews.approved(r)
        except (ValidationError,PermissionDenied) as exc:findings+=getattr(exc,'messages',[str(exc)])
        try:financial_reviews.snapshot(r)
        except (ValidationError,PermissionDenied) as exc:findings+=getattr(exc,'messages',[str(exc)])
    result={'capability':'A03/A04/A05/A07 bounded financial correction investigation','kind':kind,'request':r.pk,'applied':applied,'lineage':lineage,'findings':list(dict.fromkeys(findings))[:50],
        'citations':list(case.evidence.filter(pk__in=citations).values('id','kind','sha256')),'next_work':'Reconcile uncertain effects before retry; preserve original invoices, lots and reversals. Obtain an exact current configured human review before a new correction effect.',
        'approval_granted':False,'correction_executed':False,'cash_mutated':False,'ledger_posted':False,'deployment_authorized':False,'external_authenticity_verified':False}
    run=AgentRun.objects.create(case=case,actor=actor,evidence=r.evidence,provider='deterministic-financial-corrections-v1',process_id='F32',result=result)
    event(actor,case,'agent.financial_corrections',run=run.pk,kind=kind,request=r.pk);return run
