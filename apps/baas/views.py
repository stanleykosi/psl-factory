from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.baas_drafts import draft_baas_policy
from apps.agents.models import AgentRun
from apps.agents.reconciliation import investigate
from . import reconciliation as recon,corrective,corrective_delivery
from .forms import commands
from .models import ReconciliationBatch,ReconciliationRun,CorrectiveRequest,CorrectiveDecision,CorrectiveJob,CorrectiveDelivery,EngineeringOutcome,OutcomeVerification

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'baas.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
            if not f or not f.is_valid():raise ValidationError(f.errors.as_text() if f else 'Choose a BaaS action')
            d=f.cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='capture':recon.capture(a,c,d['reference'],d['evidence'].pk,v)
            elif action=='attest':recon.attest(a,c,d['batch'].pk,d['role'],d['evidence'].pk,v)
            elif action=='calculate':recon.investigate(a,c,d['ledger'].pk if d['ledger'] else None,d['settlement'].pk if d['settlement'] else None,d['queue'].pk if d['queue'] else None,v)
            elif action=='request':corrective.capture(a,c,d['run'].pk,d['reference'],d['operation_key'],d['evidence'].pk,d['reason'],v)
            elif action=='decide':corrective.decide(a,c,d['request'].pk,d['role'],d['verdict'],d['evidence'].pk,d['reason'],v)
            elif action=='reserve':corrective.reserve(a,c,d['request'].pk,d['role'],v)
            elif action=='operate':corrective_delivery.operate(a,c,d['job'].pk,d['operation'],d['reason'],v)
            elif action=='outcome':corrective.record_outcome(a,c,d['delivery'].pk,d['evidence'].pk,v)
            elif action=='verify':corrective.verify_outcome(a,c,d['outcome'].pk,d['role'],d['evidence'].pk,v)
            elif action=='investigate':investigate(a,c,d['run'].pk,v)
            elif action=='policy':
                with transaction.atomic():
                    lock_case(a,c,'policy.configure',v);draft_baas_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'BaaS evidence and request history updated');return redirect('baas_reconciliation',case_id=c)
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    runs=list(ReconciliationRun.objects.filter(case=case).order_by('-pk')[:15]);requests=list(CorrectiveRequest.objects.filter(case=case).order_by('-pk')[:40])
    for r in runs:
        try:recon.ensure_current(r);r.current=True
        except (ValidationError,PermissionDenied):r.current=False
    for r in requests:
        r.holds=[]
        try:corrective.approved(r);r.approved=True
        except (ValidationError,PermissionDenied) as exc:r.approved=False;r.holds=getattr(exc,'messages',[str(exc)])
    return render(request,'baas/reconciliation.html',{'case':case,'commands':forms,'runs':runs,'requests':requests,'batches':ReconciliationBatch.objects.filter(case=case).order_by('-pk')[:40],
        'decisions':CorrectiveDecision.objects.filter(request__case=case).order_by('-pk')[:40],'jobs':CorrectiveJob.objects.filter(request__case=case).order_by('-pk')[:40],
        'deliveries':CorrectiveDelivery.objects.filter(request__case=case).order_by('-pk')[:40],'outcomes':EngineeringOutcome.objects.filter(delivery__request__case=case).order_by('-pk')[:40],
        'verifications':OutcomeVerification.objects.filter(delivery__request__case=case).order_by('-pk')[:40],'agents':AgentRun.objects.filter(case=case,provider='deterministic-reconciliation-v1').order_by('-pk')[:5]})

@login_required
def inbox(request):
    rows=[]
    for r in CorrectiveDelivery.objects.filter(recipient=request.user).select_related('request__case').order_by('-pk')[:100]:
        try:require(request.user,r.request.case,'baas.engineering.receive');require(request.user,r.request.case,'baas.read')
        except PermissionDenied:continue
        rows.append(r)
    return render(request,'baas/engineering_inbox.html',{'receipts':rows})
