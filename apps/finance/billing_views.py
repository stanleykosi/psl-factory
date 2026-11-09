from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.agents.models import AgentRun
from apps.agents.billing import investigate
from apps.policy.finance_drafts import draft_finance_policy
from .models import BillingCoverage,BillingUsage,BillingPreparation
from .billing_forms import commands
from . import billing

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'finance.read')
    from .fixed_charge import case_access
    case_access(request.user,case)
    forms=commands(case,request.POST if request.method=='POST' else None)
    from . import draft_generation
    from .draft_generation_forms import commands as generation_commands
    forms += generation_commands(request.user,case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            command=next((x for x in forms if x['action']==request.POST.get('action')),None)
            if not command or not command['form'].is_valid():raise ValidationError(command['form'].errors.as_text() if command else 'Select a billing action')
            d=command['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='coverage':billing.register_coverage(a,c,*(d[k] for k in ['reference','customer','service','contract','currency','amount_basis','from_period','to_period','completeness']),d['evidence'].pk,v)
            elif action=='usage':billing.capture_usage(a,c,d['coverage'].pk,d['evidence'].pk,v,{'provider_ref':d['provider_ref'] or None,'extracted_at':d['extracted_at'].isoformat() if d['extracted_at'] else None,'completeness':d['completeness']})
            elif action=='prepare':billing.prepare(a,c,d['coverage'].pk,d['kind'],d['usage'].pk if d['usage'] else None,d['handoff'].pk if d['handoff'] else None,v)
            elif action=='generation_reserve':draft_generation.reserve(a,c,d['preparation'].pk,d['source'].pk,d['batch_ref'],d['operation_key'],v)
            elif action=='generation_run':draft_generation.run_once(a,c,d['generation'].pk)
            elif action=='generation_cancel':draft_generation.cancel(a,c,d['generation'].pk,d['reason'])
            elif action=='policy':
                # Policy lifecycle has its own lock; preserve the workbench optimistic revision guard.
                from django.db import transaction
                from apps.core.services import lock_case
                with transaction.atomic():
                    lock_case(a,c,'policy.configure',v)
                    draft_finance_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            elif action=='investigate':investigate(a,c,d['coverage'].pk,d['preparation'].pk if d['preparation'] else None,v)
            messages.success(request,'Billing evidence and preparation history updated');return redirect('finance_billing',case_id=c)
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    preparations=list(BillingPreparation.objects.filter(case=case).order_by('-pk')[:30])
    for p in preparations:
        p.current_findings=[]
        try:billing.ensure_current(p)
        except (ValidationError,PermissionDenied) as exc:p.current_findings=getattr(exc,'messages',[str(exc)])
    coverages=list(BillingCoverage.objects.filter(case=case).order_by('-pk'))
    for cov in coverages:cov.inventory=billing.coverage_inventory(cov)
    from .models import DraftGeneration
    generation_reports=[]
    for generation in DraftGeneration.objects.filter(case=case).order_by('-pk')[:30]:
        try:generation_reports.append(draft_generation.report(request.user,case.pk,generation.pk))
        except PermissionDenied:pass
    return render(request,'finance/billing.html',{'generation_reports':generation_reports,'case':case,'commands':forms,'coverages':coverages,
        'usage_batches':BillingUsage.objects.filter(coverage__case=case).order_by('-pk')[:30],'preparations':preparations,
        'agents':AgentRun.objects.filter(case=case,provider='deterministic-billing-investigation-v1').order_by('-pk')[:10]})
