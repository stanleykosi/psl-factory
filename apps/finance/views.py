from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.finance_drafts import draft_finance_policy
from apps.agents.finance_analysis import investigate_finance
from apps.agents.models import AgentRun
from . import analysis
from .documents import draft_report
from .services import capture_import,validate_import
from .models import FinancialImport,FinanceSource,FinanceRun,FinanceReview,FinanceDocumentBinding,FinanceAdjustment
from .forms import commands

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'finance.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            command=next((f for f in forms if f['action']==request.POST.get('action')),None)
            if not command or not command['form'].is_valid():raise ValidationError(command['form'].errors.as_text() if command else 'Select a supported Finance action')
            d=command['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='capture':capture_import(a,c,d['evidence'].pk,v)
            elif action=='validate':validate_import(a,c,d['batch'].pk,v)
            elif action=='source':analysis.capture_source(a,c,d['batch'].pk,d['entity'],d['accounting_basis'],d['extracted_at'],d['completeness'],d['control_total'] or None,d['evidence'].pk,v)
            elif action=='policy':draft_finance_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            elif action=='review':
                target=d['source'] if d['purpose']=='source' else d['adjustment'] if d['purpose']=='adjustment' else d['run'] if d['purpose']=='output' else d['configuration']
                if not target:raise ValidationError('Choose the exact subject for this review purpose')
                analysis.review(a,c,d['purpose'],target.pk,d['role'],d['verdict'],d['evidence'].pk,d['note'],v)
            elif action=='adjust':analysis.adjustment(a,c,d['source'].pk,d['reference'],d['kind'],d['lines'],d['evidence'].pk,d['note'],v)
            elif action=='map':analysis.map_source(a,c,d['source'].pk,[x.pk for x in d['adjustments']],v)
            elif action=='allocate':analysis.allocate(a,c,d['parent'].pk,d['metrics'],v)
            elif action=='calculate':analysis.calculate(a,c,d['parent'].pk,v)
            elif action=='report':draft_report(a,c,d['run'].pk,d['template'].pk,d['audience'],v)
            elif action=='investigate':investigate_finance(a,c,d['run'].pk,v)
            messages.success(request,'Finance evidence and preview history updated');return redirect('finance_analysis',case_id=c)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    runs=list(FinanceRun.objects.filter(case=case).order_by('-pk')[:30])
    for run in runs:
        run.current_findings=[]
        try:analysis.ensure_current(run)
        except (ValidationError,PermissionDenied) as exc:run.current_findings=getattr(exc,'messages',[str(exc)])
    return render(request,'finance/analysis.html',{'case':case,'commands':forms,'sources':FinanceSource.objects.filter(case=case).order_by('-pk'),
        'runs':runs,'reviews':FinanceReview.objects.filter(case=case).order_by('-pk')[:30],
        'bindings':FinanceDocumentBinding.objects.filter(run__case=case),'adjustments':FinanceAdjustment.objects.filter(source__case=case),
        'imports':FinancialImport.objects.filter(case=case),'agents':AgentRun.objects.filter(case=case,provider='deterministic-finance-lineage-v1').order_by('-pk')[:5]})
