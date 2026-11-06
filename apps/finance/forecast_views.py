from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.db import transaction
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.finance_drafts import draft_finance_policy
from apps.agents.models import AgentRun
from apps.agents.forecast import investigate
from apps.documents.controlled import reserve_publication
from . import forecast,forecast_documents
from .forecast_forms import commands
from .models import ForecastScenario,ForecastRun,ForecastActual,ForecastReview,ForecastMatch,ForecastBinding,ForecastPriority

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'finance.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((r['form'] for r in forms if r['action']==request.POST.get('action')),None)
            if not f or not f.is_valid():raise ValidationError(f.errors.as_text() if f else 'Select a forecast action')
            d=f.cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='capture':forecast.capture(a,c,d['reference'],d['evidence'].pk,d['reason'],v,d['parent'].pk if d['parent'] else None)
            elif action=='prepare':forecast.prepare(a,c,d['scenario'].pk,v)
            elif action=='review':forecast.review(a,c,d['run'].pk,d['role'],d['verdict'],d['evidence'].pk,d['reason'],v)
            elif action=='actual':forecast.capture_actual(a,c,d['evidence'].pk,v,d['lot'].pk if d['lot'] else None)
            elif action=='verify':forecast.verify_actual(a,c,d['actual'].pk,d['role'],d['evidence'].pk,v)
            elif action=='match':forecast.match(a,c,d['scenario'].pk,d['item_key'],d['actual'].pk,d['amount'],d['operation_key'],d['evidence'].pk,v)
            elif action=='unmatch':forecast.unmatch(a,c,d['match'].pk,d['evidence'].pk,d['reason'],v)
            elif action=='priority':forecast.prioritize(a,c,d['run'].pk,d['role'],d['reference'],d['description'],d['owner'].pk,d['due_at'],d['evidence'].pk,d['reason'],v)
            elif action=='draft':forecast_documents.draft(a,c,d['run'].pk,d['template'].pk,d['audience'],v)
            elif action=='group_review':
                from .group_forecast import review
                review(a,c,d['version'].pk,d['role'],d['verdict'],d['reason'],v)
            elif action=='group_verify':
                from .group_forecast import verified
                verified(d['version'])
            elif action=='publish':reserve_publication(a,c,d['version'].pk,v)
            elif action=='investigate':investigate(a,c,d['run'].pk,v)
            elif action=='policy':
                with transaction.atomic():
                    lock_case(a,c,'policy.configure',v);draft_finance_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'Forecast evidence and history updated');return redirect('finance_forecast',case_id=c)
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    runs=list(ForecastRun.objects.filter(case=case).order_by('-pk')[:20])
    for r in runs:
        r.findings=[]
        try:forecast.ensure_current(r);r.current=True
        except (ValidationError,PermissionDenied) as exc:r.current=False;r.findings=getattr(exc,'messages',[str(exc)])
        r.approved=False
        try:forecast.approved(r);r.approved=True
        except (ValidationError,PermissionDenied):pass
    actuals=list(ForecastActual.objects.filter(case=case).order_by('-pk')[:50])
    for r in actuals:r.verified=forecast.actual_available(r)
    groups=[]
    from .group_forecast import inputs,approved,verified
    for r in runs:
        row={'run':r,'stage':'Prepare permitted group rows','finding':''}
        try:inputs(r)
        except (ValidationError,PermissionDenied) as exc:row.update(stage='Owner decision or current source needed',finding=str(exc))
        groups.append(row)
    for b in ForecastBinding.objects.filter(run__case=case,version__audience='group').select_related('version','run'):
        row={'run':b.run,'version':b.version,'stage':'Review disclosure and recipients','finding':''}
        try:
            approved(b.version);row['stage']='Controlled delivery and receipt verification';verified(b.version);row['stage']='Every recipient verified'
        except (ValidationError,PermissionDenied) as exc:row['finding']=str(exc)
        groups.append(row)
    response=render(request,'finance/forecast.html',{'case':case,'groups':groups,'commands':forms,'runs':runs,'actuals':actuals,
        'scenarios':ForecastScenario.objects.filter(case=case).order_by('-pk')[:30],'reviews':ForecastReview.objects.filter(run__case=case).order_by('-pk')[:30],
        'matches':ForecastMatch.objects.filter(case=case).order_by('-pk')[:50],'bindings':ForecastBinding.objects.filter(run__case=case).select_related('version__document').order_by('-pk')[:20],
        'priorities':ForecastPriority.objects.filter(review__run__case=case).select_related('action__current').order_by('-pk')[:30],
        'agents':AgentRun.objects.filter(case=case,provider='deterministic-forecast-v1').order_by('-pk')[:5]})

    response['Cache-Control']='no-store'
    return response
