from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect,get_object_or_404
from django.http import JsonResponse
from apps.core.views import accessible_case
from apps.policy.services import resolve
from apps.policy.ppe_validators import SCHEMAS
from apps.policy.ppe_drafts import draft_ppe_policy
from apps.agents.ppe import investigate
from apps.agents.models import AgentRun
from adapters.ppe import LocalPPEReportAdapter
from .models import ScheduleWork
from .ppe_forms import commands
from . import ppe as d
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required; no extra authority fields')
   v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];e=v['evidence'].pk if v.get('evidence') else None
   if k=='capture':d.capture(a,c.pk,v['reference'],e,rev)
   elif k=='prepare':d.prepare(a,c.pk,v['reference'],v['register'].pk,v['prior'].pk if v['prior'] else None,v['ledger'].pk if v['ledger'] else None,rev)
   elif k=='review':d.review(a,c.pk,v['work'].pk,v['purpose'],v['verdict'],e,v['note'],rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_ppe_policy(a,c.pk,v['component'],v['content'],e,v['effective_from'])
   messages.success(request,'PPE versioned evidence and decisions updated');return redirect('ppe',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('ppe',case_id=c.pk)
 rows=list(ScheduleWork.objects.filter(case=c,kind__startswith='ppe_').order_by('-pk')[:40])
 for w in rows:
  try:d.current(w);w.current=True
  except (ValidationError,PermissionDenied):w.current=False
  try:d.approved(w,'register' if w.kind=='ppe_register' else 'schedule');w.reviewed=w.current
  except (ValidationError,PermissionDenied):w.reviewed=False
 response=render(request,'finance/ppe.html',{'case':c,'works':rows,'commands':forms,'policies':[resolve(k,c) for k in SCHEMAS],'schema':d.REGISTER,'schemas':SCHEMAS,'agents':AgentRun.objects.filter(case=c,provider='deterministic-ppe-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);w=get_object_or_404(ScheduleWork,case=c,kind='ppe_schedule',pk=pk)
 try:value=LocalPPEReportAdapter().read(request.user,w)
 except ValidationError:return JsonResponse({'status':'held','reason':'Current source, rules, basis, reconciliation or human decision required'},status=409,headers={'Cache-Control':'no-store'})
 if request.GET.get('format')=='json':return JsonResponse(value,headers={'Cache-Control':'no-store'})
 response=render(request,'finance/ppe_report.html',{'case':c,'work':w,'value':value});response['Cache-Control']='no-store';return response
