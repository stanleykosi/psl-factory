from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.agents.models import AgentRun
from apps.agents.finance_performance import investigate
from .models import FinanceBudget,FinancePeriod,FinancePerformance,FinancePerformanceDecision,FinanceRestatement,FinancePerformanceBinding
from .performance_forms import commands
from . import performance
from .documents import draft_report


def chart_rows(result):
    rows=[]
    for item in result['chart']:
        values=[Decimal(item[k]) for k in ['actual','budget','prior'] if item[k] is not None]
        maximum=max([abs(v) for v in values],default=Decimal(0))
        bars=[]
        for column in ['actual','budget','prior']:
            value=item[column]
            number=None if value is None else Decimal(value)
            width=Decimal(0) if number is None or maximum==0 else abs(number)/maximum*45
            bars.append({'column':column,'value':value,'width':format(width,'.2f'),'left':format(50-width if number is not None and number<0 else Decimal(50),'.2f')})
        rows.append({'label':(item['bu'] or 'Company')+' / '+item['label'],'unit':item['unit'],'bars':bars})
    return rows


@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'finance.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            command=next((x for x in forms if x['action']==request.POST.get('action')),None)
            if not command or not command['form'].is_valid():raise ValidationError(command['form'].errors.as_text() if command else 'Select a performance action')
            d=command['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='budget':performance.capture_budget(a,c,d['reference'],d['cadence'],d['effective_at'],d['completeness'],d['evidence'].pk,d['approval'].pk,v,accounting_basis=d['accounting_basis'] or None)
            elif action=='seal':performance.seal_period(a,c,d['run'].pk,d['restatement'].pk if d['restatement'] else None,v)
            elif action=='build':performance.build(a,c,d['cutoff'],[p.pk for p in d['periods']],d['budget'].pk if d['budget'] else None,[p.pk for p in d['prior']],v)
            elif action=='decide':
                field={'period_method':'configuration'}.get(d['purpose'],d['purpose']);item=d[field]
                if not item:raise ValidationError('Select the exact decision subject')
                performance.decide(a,c,d['purpose'],item.pk,d['role'],d['verdict'],d['evidence'].pk,d['note'],v)
            elif action=='restate':performance.request_restatement(a,c,d['original'].pk,d['proposed'].pk,d['evidence'].pk,d['rationale'],v)
            elif action=='report':draft_report(a,c,d['performance'].pk,d['template'].pk,d['audience'],v,performance=True)
            elif action=='investigate':investigate(a,c,d['performance'].pk,v)
            messages.success(request,'Finance budget, performance and preserved history updated');return redirect('finance_performance',case_id=c)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    reports=list(FinancePerformance.objects.filter(case=case).order_by('-pk')[:20])
    for report in reports:
        report.current_findings=[]
        try:performance.ensure_current(report)
        except (ValidationError,PermissionDenied) as exc:report.current_findings=getattr(exc,'messages',[str(exc)])
        report.charts=chart_rows(report.result)
    return render(request,'finance/performance.html',{'case':case,'commands':forms,'reports':reports,
        'budgets':FinanceBudget.objects.filter(case=case).order_by('-pk'),'periods':FinancePeriod.objects.filter(case=case).order_by('-pk'),
        'decisions':FinancePerformanceDecision.objects.filter(case=case).order_by('-pk')[:30],'restatements':FinanceRestatement.objects.filter(case=case).order_by('-pk'),
        'bindings':FinancePerformanceBinding.objects.filter(run__case=case).order_by('-pk'),
        'agents':AgentRun.objects.filter(case=case,provider='deterministic-finance-performance-v1').order_by('-pk')[:5]})
