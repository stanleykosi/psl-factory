from django.db import transaction
from django.utils import timezone
from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.finance.models import ReceivableSnapshot,CashReceipt,InvoiceIssue,InvoiceReview
from apps.finance.receivables import calculate
from apps.finance.billing import digest
from .models import AgentRun

@transaction.atomic
def investigate(actor,case_id,snapshot_id,expected):
    case=lock_case(actor,case_id,'agent.receivables',expected);require(actor,case,'finance.read')
    s=ReceivableSnapshot.objects.filter(case=case,pk=snapshot_id).first()
    if not s:raise ValidationError('Select this case receivable snapshot')
    manifest,result=calculate(case,s.as_of)
    citations=set(CashReceipt.objects.filter(case=case).values_list('evidence_id',flat=True))
    from apps.finance.models import CashVerification,CashAssignment,CashAllocation,CashReversal
    for model,lookup in [(CashVerification,'receipt__case'),(CashAssignment,'receipt__case'),(CashAllocation,'lot__receipt__case')]:citations.update(model.objects.filter(**{lookup:case}).values_list('evidence_id',flat=True))
    citations.update(InvoiceReview.objects.filter(invoice__case=case).values_list('evidence_id',flat=True))
    citations.update(CashReversal.objects.filter(lot__receipt__case=case).values_list('evidence_id',flat=True));citations.update(CashReversal.objects.filter(allocation__lot__receipt__case=case).values_list('evidence_id',flat=True))
    from apps.policy.models import Configuration
    from apps.policy.services import reference_values
    from apps.finance.models import CashVerification
    for issue in InvoiceIssue.objects.filter(invoice__case=case).select_related('invoice__preparation__coverage','invoice__preparation__usage'):
        prep=issue.invoice.preparation;citations.add(prep.coverage.evidence_id)
        if prep.usage_id:citations.add(prep.usage.evidence_id)
        for item in prep.snapshot['policies'].values():
            if item['id']:
                config=Configuration.objects.get(case=case,pk=item['id']);citations.update(int(r.split(':')[-1]) for r in config.envelope['evidence_refs'])
                if item['status']=='ACTIVE':
                    for value in reference_values(config):
                        if 'oracle_evidence_id' in value:citations.add(value['oracle_evidence_id'])
    from apps.finance import cash
    alternatives=[]
    with localcontext() as ctx:
        ctx.prec=512
        for lot in CashVerification.objects.filter(receipt__case=case).select_related('receipt'):
            available=cash.cash_remaining(lot);assignment=cash.assigned(lot.receipt)
            if available<=0 or not assignment or not assignment.coverage_id:continue
            for issue in InvoiceIssue.objects.filter(invoice__case=case).select_related('invoice__preparation__coverage'):
                from apps.finance.corrections import unresolved,state
                if unresolved(issue) or state(issue)['voided']:continue
                cov=issue.invoice.preparation.coverage;v=cash.lot_payload(lot);open_=cash.open_amount(issue)
                if open_>0 and (cov.customer,cov.contract,issue.invoice.currency,issue.invoice.amount_basis)==(v['customer'],assignment.coverage.contract,v['currency'],v['amount_basis']):
                    alternatives.append({'lot':lot.pk,'issue':issue.pk,'invoice_reference':issue.invoice.reference,'maximum_individual_amount':format(min(available,open_),'f'),'alternatives_not_combined':True,'human_selection_required':True})
                if len(alternatives)>=20:break
            if len(alternatives)>=20:break
    from apps.finance.models import InvoiceCorrection,CashSuccessor,FinancialCorrectionReview
    citations.update(InvoiceCorrection.objects.filter(case=case).values_list('evidence_id',flat=True))
    for successor in CashSuccessor.objects.filter(case=case):citations.update([successor.evidence_id,successor.verification_evidence_id,successor.legal_evidence_id])
    citations.update(FinancialCorrectionReview.objects.filter(correction__case=case).values_list('evidence_id',flat=True));citations.update(FinancialCorrectionReview.objects.filter(successor__case=case).values_list('evidence_id',flat=True))
    source=case.evidence.filter(pk__in=citations).first()
    if not source:raise ValidationError('Capture a cited Finance source before investigation')
    output={'capability':'A03/A04/A05/A07 bounded invoice/cash conservation investigation','snapshot':s.pk,'current':s.as_of==timezone.localdate() and digest({'manifest':manifest,'result':result})==s.sha256,
        'groups':result['groups'][:100],'unmatched_cash':result['unmatched_cash'][:100],'reported_unverified':result['reported_unverified'][:100],'uncertain_issuance':result['uncertain_issuance'][:100],'matching_alternatives':alternatives,
        'findings':result['findings'],'citations':list(case.evidence.filter(pk__in=citations).values('id','kind','sha256')),
        'next_work':'Reconcile uncertain invoice effects before retrying. Investigate unmatched cash and propose explicit same-contract matching within both capacities; a configured human must execute allocation.',
        'invoice_issued':False,'allocation_executed':False,'cash_changed':False,'debt_waived':False,'deployment_authorized':False,'external_authenticity_verified':False}
    r=AgentRun.objects.create(case=case,actor=actor,evidence=source,provider='deterministic-receivables-v1',process_id='F32',result=output)
    event(actor,case,'agent.receivables',snapshot=s.pk,run=r.pk);return r
