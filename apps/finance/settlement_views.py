from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.db import transaction
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.agents.models import AgentRun
from apps.agents.receivables import investigate
from apps.policy.finance_drafts import draft_finance_policy
from . import invoices,cash,receivables,invoice_delivery
from .models import Invoice,InvoiceReview,InvoiceIssue,InvoiceDelivery,InvoiceJob,CashReceipt,CashVerification,CashAssignment,CashAllocation,CashReversal,ReceivableSnapshot
from .settlement_forms import commands

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'finance.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            entry=next((x for x in forms if x['action']==request.POST.get('action')),None)
            if not entry or not entry['form'].is_valid():raise ValidationError(entry['form'].errors.as_text() if entry else 'Choose an invoice/cash action')
            d=entry['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='draft':invoices.draft(a,c,d['preparation'].pk,d['reference'],d['due_date'],v)
            elif action=='review':invoices.review(a,c,d['invoice'].pk,d['role'],d['verdict'],d['evidence'].pk,d['reason'],v,delegated=d['delegated'])
            elif action=='reserve':invoices.reserve(a,c,d['invoice'].pk,d['kind'],d['role'],v)
            elif action=='operate':invoice_delivery.operate(a,c,d['job'].pk,d['operation'],d['reason'],v)
            elif action=='report':cash.report(a,c,d['evidence'].pk,v)
            elif action=='verify':cash.verify(a,c,d['receipt'].pk,d['role'],d['evidence'].pk,v)
            elif action=='assign':cash.assign(a,c,d['receipt'].pk,d['coverage'].pk if d['coverage'] else None,d['role'],d['evidence'].pk,d['reason'],v)
            elif action=='allocate':cash.allocate(a,c,d['lot'].pk,d['issue'].pk,d['amount'],d['operation_key'],d['role'],d['evidence'].pk,v)
            elif action=='reverse':
                if (d['target']=='lot' and (not d['lot'] or d['allocation'])) or (d['target']=='allocation' and (not d['allocation'] or d['lot'])):raise ValidationError('Select exactly the cash subject being fully reversed')
                cash.reverse(a,c,d['target'],d[d['target']].pk,d['role'],d['evidence'].pk,d['reason'],v)
            elif action=='snapshot':receivables.snapshot(a,c,d['as_of'],v)
            elif action=='investigate':investigate(a,c,d['snapshot'].pk,v)
            elif action=='policy':
                with transaction.atomic():
                    lock_case(a,c,'policy.configure',v);draft_finance_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'Invoice and cash evidence history updated');return redirect('finance_settlement',case_id=c)
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    docs=list(Invoice.objects.filter(case=case).order_by('-pk')[:50])
    for i in docs:
        i.current_findings=[]
        if InvoiceIssue.objects.filter(invoice=i).exists():i.display_status='Issued obligation'
        else:
            i.display_status='Draft; not issued'
            try:invoices.reviewed(i)
            except (ValidationError,PermissionDenied) as exc:i.current_findings=getattr(exc,'messages',[str(exc)])
    from django.utils import timezone
    snapshots=list(ReceivableSnapshot.objects.filter(case=case).order_by('-pk')[:10])
    for s in snapshots:
        manifest,result=receivables.calculate(case,s.as_of)
        s.current=s.as_of==timezone.localdate() and receivables.digest({'manifest':manifest,'result':result})==s.sha256
    return render(request,'finance/settlement.html',{'case':case,'commands':forms,'invoices':docs,
        'jobs':InvoiceJob.objects.filter(invoice__case=case).order_by('-pk')[:50],'reviews':InvoiceReview.objects.filter(invoice__case=case).order_by('-pk')[:30],
        'receipts':CashReceipt.objects.filter(case=case).order_by('-pk')[:50],'lots':CashVerification.objects.filter(receipt__case=case).order_by('-pk')[:50],
        'assignments':CashAssignment.objects.filter(receipt__case=case).order_by('-pk')[:50],'allocations':CashAllocation.objects.filter(lot__receipt__case=case).order_by('-pk')[:50],
        'reversals':CashReversal.objects.filter(lot__receipt__case=case).union(CashReversal.objects.filter(allocation__lot__receipt__case=case)).order_by('-pk')[:50],
        'snapshots':snapshots,'agents':AgentRun.objects.filter(case=case,provider='deterministic-receivables-v1').order_by('-pk')[:5]})

@login_required
def inbox(request):
    rows=[]
    for receipt in InvoiceDelivery.objects.filter(recipient=request.user).select_related('invoice__case').order_by('-pk'):
        try:require(request.user,receipt.invoice.case,'finance.invoice.receive')
        except PermissionDenied:continue
        rows.append(receipt)
    from .models import InvoiceCorrectionDelivery
    notes=[]
    for receipt in InvoiceCorrectionDelivery.objects.filter(recipient=request.user).select_related('correction__case').order_by('-pk'):
        try:require(request.user,receipt.correction.case,'finance.invoice.receive')
        except PermissionDenied:continue
        notes.append(receipt)
    return render(request,'finance/invoice_inbox.html',{'receipts':rows,'notes':notes})
