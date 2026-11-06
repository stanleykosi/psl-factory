from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.bu_validators import SCHEMAS
from apps.policy.bu_drafts import draft_bu_policy
from apps.agents.bu import investigate
from apps.agents.models import AgentRun
from .bu_forms import commands
from .bu_models import BUWork,BUReport
from . import bu as domain
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);require(request.user,c,'bu.read');forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
   if not f or not f.is_valid():raise ValidationError('Choose a permitted command with valid typed fields')
   if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected authority or source fields')
   d=f.cleaned_data;k=d['action'];a=request.user;pk=c.pk;v=d['revision'];key=d.get('operation_key');e=d['evidence'].pk if d.get('evidence') else None
   if k=='rule':domain.rule(a,pk,d['payroll'].pk,d['reference'],key,d['payload'],v)
   elif k=='staff':domain.staff(a,pk,d['payroll'].pk,d['reference'],key,d['declared'],d['rule_ids'],v)
   elif k=='capture':
    s=domain.capture(a,pk,d['reference'],key,d['scope'],d['body'],v)
    if not s.metadata['accepted']:messages.error(request,'Rejected export: '+', '.join(s.metadata['codes'])+'; no row values retained')
   elif k=='event':domain.attribute(a,pk,d['source'].pk,d['reference'],key,v,d.get('comparison') or None)
   elif k=='review':domain.review(a,pk,d['work'].pk,d['purpose'],d['verdict'],key,e,v)
   elif k=='publish':domain.publish(a,pk,d['work'].pk,key,v)
   elif k=='receive':domain.receive(a,pk,d['report'].pk,v)
   elif k=='investigate':investigate(a,pk,v)
   elif k=='policy':
    with transaction.atomic():domain.locked(a,pk,'policy.configure',v);draft_bu_policy(a,pk,d['component'],d['content'],e,d['effective_from'])
   messages.success(request,'Versioned BU history updated');return redirect('bu',case_id=pk)
  except (ValidationError,ValueError,TypeError) as exc:
   messages.error(request,'Capture held; check source contract and retry intent. No supplied row values reflected.' if request.POST.get('action') in ['capture','rule','staff'] else str(exc));return redirect('bu',case_id=c.pk)
 rows=list(BUWork.objects.defer('payload').filter(case=c).order_by('-pk')[:60])
 for w in rows:
  try:domain.current(w,check_comparison=False);w.current=True
  except (ValidationError,PermissionDenied):w.current=False
  try:domain.private_access(request.user,w);w.can_read=True
  except (ValidationError,PermissionDenied):w.can_read=False
 response=render(request,'finance/bu.html',{'case':c,'works':rows,'reports':BUReport.objects.defer('payload').filter(work__case=c).order_by('-pk')[:30],'commands':forms,'policies':[resolve(k,c) for k in SCHEMAS],'schemas':SCHEMAS,'rule_schema':domain.RULE,'agents':AgentRun.objects.filter(case=c,provider='deterministic-bu-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
def inspect(request,case_id,kind,pk):
 c=accessible_case(request.user,case_id)
 if kind=='work':get_object_or_404(BUWork.objects.defer('payload'),case=c,pk=pk)
 elif kind=='report':get_object_or_404(BUReport.objects.defer('payload'),work__case=c,pk=pk)
 else:return JsonResponse({'status':'unknown type'},status=404)
 try:value=domain.read_private(request.user,c.pk,pk) if kind=='work' else domain.read_report(request.user,pk)
 except ValidationError:return JsonResponse({'status':'held','reason':'Current source, review, access or policy requires reassessment'},status=409,headers={'Cache-Control':'no-store'})
 response=render(request,'finance/bu_inspect.html',{'case':c,'kind':kind,'record_id':pk,'value':value});response['Cache-Control']='no-store';return response
