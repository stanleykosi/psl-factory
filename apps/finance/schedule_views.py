from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Prefetch
from django.db.models.fields.json import KeyTextTransform
from django.shortcuts import render,redirect,get_object_or_404
from django.http import JsonResponse
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.schedule_validators import SCHEMAS
from apps.policy.schedule_drafts import draft_schedule_policy
from apps.agents.schedules import investigate
from apps.agents.models import AgentRun
from adapters.schedules import LocalScheduleReportAdapter
from .schedule_forms import commands
from .schedule_models import ScheduleWork,ScheduleAdjustment,ScheduleReview
from . import schedules as domain


def schedule_history(actor, case):
    reviews = ScheduleReview.objects.only('work_id', 'verdict', 'actor_id').order_by('-pk')[:10]
    works = list(ScheduleWork.objects.filter(case=case, kind__in=['income', 'inventory'])
                 .defer('payload', 'snapshot', 'result')
                 .annotate(recorded_status=KeyTextTransform('status', 'result'))
                 .prefetch_related(Prefetch('reviews', queryset=reviews, to_attr='recent_reviews'))
                 .order_by('-pk')[:50])
    with transaction.atomic():
        try:
            domain.locked(actor, case.pk, 'schedules.report')
        except PermissionDenied:
            return works
        for work in works:
            latest = work.recent_reviews[0] if work.recent_reviews else None
            try:
                if latest is None:
                    domain.current(work)
                elif latest.verdict == 'approve':
                    domain.approved(work)
                    work.reviewed = True
                else:
                    continue
                work.authorized_result = work.result
            except (PermissionDenied, ValidationError):
                continue
    return works


@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);domain.readable(request.user,c)
 forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
   if not f or not f.is_valid():raise ValidationError('Choose a permitted command with valid typed fields')
   if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected fields')
   d=f.cleaned_data;k=d['action'];a=request.user;v=d['revision'];e=d['evidence'].pk if d.get('evidence') else None
   if k in ['income','inventory']:domain.prepare(a,c.pk,k,d['reference'],d['parent'].pk if k=='income' else None,d.get('payload'),e,v)
   elif k=='review':domain.review(a,c.pk,d['work'].pk,d['verdict'],e,d['note'],v)
   elif k=='adjust':domain.export_adjustment(a,c.pk,d['work'].pk,d['kind'],e,v)
   elif k=='investigate':investigate(a,c.pk,v)
   elif k=='policy':
    with transaction.atomic():domain.locked(a,c.pk,'policy.configure',v);draft_schedule_policy(a,c.pk,d['component'],d['content'],e,d['effective_from'])
   messages.success(request,'Versioned income/schedule history updated');return redirect('finance_schedules',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('finance_schedules',case_id=c.pk)
 rows=schedule_history(request.user,c)
 response=render(request,'finance/schedules.html',{'case':c,'works':rows,'commands':forms,'policies':[resolve(k,c) for k in SCHEMAS],'schemas':SCHEMAS,'detail_schema':domain.DETAIL,'inventory_schema':domain.INVENTORY_BODY,'links':ScheduleAdjustment.objects.filter(work__case=c).order_by('-pk')[:30],'agents':AgentRun.objects.filter(case=c,provider='deterministic-schedules-v1').only('pk','created_at').order_by('-pk')[:5]})
 response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,pk):
 c=accessible_case(request.user,case_id);domain.readable(request.user,c);require(request.user,c,'schedules.report')
 w=get_object_or_404(ScheduleWork.objects.defer('payload','snapshot','result'),case=c,pk=pk,kind__in=['income','inventory'])
 try:value=LocalScheduleReportAdapter().read(request.user,w)
 except ValidationError:return JsonResponse({'status':'held','reason':'Rebuild/review current exact source, policy and authority'},status=409,headers={'Cache-Control':'no-store'})
 if request.GET.get('format')=='json':return JsonResponse(value,headers={'Cache-Control':'no-store'})
 response=render(request,'finance/schedule_report.html',{'case':c,'work':w,'value':value,'result':value['result']});response['Cache-Control']='no-store';return response
