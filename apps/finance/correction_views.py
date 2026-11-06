from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.finance_drafts import draft_finance_policy
from apps.agents.financial_corrections import investigate
from apps.agents.models import AgentRun
from . import corrections,cash_successors,financial_reviews
from .models import InvoiceCorrection,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery,CashSuccessor,CashSuccessorAcceptance,FinancialCorrectionReview,InvoiceJob
from .correction_forms import commands

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'finance.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            entry=next((x for x in forms if x['action']==request.POST.get('action')),None)
            if not entry or not entry['form'].is_valid():raise ValidationError(entry['form'].errors.as_text() if entry else 'Choose a correction action')
            d=entry['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='note':corrections.capture(a,c,d['issue'].pk,d['evidence'].pk,d['allocation_evidence'].pk if d['allocation_evidence'] else None,d['reason'],v)
            elif action=='successor':cash_successors.capture(a,c,d['parent'].pk,d['report'].pk,d['verification'].pk,d['legal'].pk,d['reason'],v)
            elif action in ['review','investigate']:
                key='correction' if d['kind']=='invoice' else 'successor';other='successor' if key=='correction' else 'correction'
                if not d[key] or d[other]:raise ValidationError('Select exactly the financial subject being reviewed or investigated')
                if action=='review':financial_reviews.review(a,c,d['kind'],d[key].pk,d['role'],d['verdict'],d['evidence'].pk,d['reason'],v)
                else:investigate(a,c,d['kind'],d[key].pk,v)
            elif action=='reserve':corrections.reserve(a,c,d['correction'].pk,d['effect'],d['role'],v)
            elif action=='apply_successor':cash_successors.apply(a,c,d['successor'].pk,d['role'],v)
            elif action=='policy':
                with transaction.atomic():
                    lock_case(a,c,'policy.configure',v);draft_finance_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'Financial correction evidence and history updated');return redirect('finance_corrections',case_id=c)
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    notes=list(InvoiceCorrection.objects.filter(case=case).order_by('-pk')[:40]);successors=list(CashSuccessor.objects.filter(case=case).order_by('-pk')[:40])
    for item in notes+successors:
        invoice=isinstance(item,InvoiceCorrection)
        accepted=InvoiceCorrectionAcceptance.objects.filter(correction=item).first() if invoice else CashSuccessorAcceptance.objects.filter(request=item).first()
        item.acceptance=accepted;item.findings=[]
        if not accepted:
            try:financial_reviews.approved(item)
            except (ValidationError,PermissionDenied) as exc:item.findings=getattr(exc,'messages',[str(exc)])
    return render(request,'finance/corrections.html',{'case':case,'commands':forms,'notes':notes,'successors':successors,
        'jobs':InvoiceJob.objects.filter(invoice__case=case,kind__in=['adjust','adjust_deliver']).order_by('-pk')[:40],
        'reviews':FinancialCorrectionReview.objects.filter(correction__case=case).union(FinancialCorrectionReview.objects.filter(successor__case=case)).order_by('-pk')[:40],
        'agents':AgentRun.objects.filter(case=case,provider='deterministic-financial-corrections-v1').order_by('-pk')[:5]})
