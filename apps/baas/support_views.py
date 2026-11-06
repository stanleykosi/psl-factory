from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect
from django.http import JsonResponse
from apps.core.views import accessible_case
from apps.identity.services import visible_cases
from apps.policy.services import resolve
from apps.policy.support_validators import SCHEMAS
from apps.policy.support_drafts import draft_support_policy
from apps.agents.support import investigate
from apps.agents.models import AgentRun
from . import support as d
from .support_forms import commands
from .models import SupportIntake,SupportLink,SupportEvent,SupportResult,SupportReport,SupportReview,SupportMerge
@login_required
def inbox(request):
 rows=[]
 for c in visible_cases(request.user).filter(kind='support').order_by('-created_at')[:100]:
  try:d.readable(request.user,c)
  except PermissionDenied:continue
  rows.append({'case':c,'head':d.head(c)})
 response=render(request,'baas/support_inbox.html',{'rows':rows});response['Cache-Control']='no-store';return response
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required')
   v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];e=v['evidence'].pk if v.get('evidence') else None
   if k=='capture':d.capture(a,c.pk,e,rev)
   elif k=='link':d.link(a,c.pk,v['intake'].pk,e,rev)
   elif k=='start':d.start(a,c.pk,v['owner'].pk,e,v['occurred_at'].isoformat(),rev)
   elif k=='transition':d.transition(a,c.pk,v['transition'],v['owner'].pk,e,v['occurred_at'].isoformat(),rev,v['response_kind'])
   elif k=='result':d.specialist_result(a,c.pk,v['pending'].pk,e,rev)
   elif k=='merge':d.merge(a,c.pk,v['target'].pk,e,v['occurred_at'].isoformat(),rev)
   elif k=='flow_review':d.review_flow(a,c.pk,e,v['verdict'],rev)
   elif k=='report':d.prepare_report(a,c.pk,e,rev)
   elif k=='report_review':d.review_report(a,c.pk,v['report'].pk,e,v['verdict'],rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_support_policy(a,c.pk,v['component'],v['content'],e,v['effective_from'])
   messages.success(request,'Support evidence and decision history updated');return redirect('support_flow',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('support_flow',case_id=c.pk)
 try:ready=d.approved_flow(c).pk
 except (ValidationError,PermissionDenied):ready=None
 target=None
 merged=SupportMerge.objects.filter(source=c).select_related('target').first()
 if merged:
  try:d.readable(request.user,merged.target);target=merged.target
  except PermissionDenied:pass
 flow=None
 try:flow=d.config(c,'B14.flow_rules')[1]
 except ValidationError:pass
 response=render(request,'baas/support.html',{'case':c,'canonical_target':target,'flow':flow,'commands':forms,'head':d.head(c),'flow_review':ready,'intakes':SupportIntake.objects.filter(case=c).order_by('-pk')[:40],'links':SupportLink.objects.filter(case=c),'events':SupportEvent.objects.filter(case=c).order_by('-version')[:80],'results':SupportResult.objects.filter(pending__case=c).order_by('-pk')[:30],'reports':SupportReport.objects.filter(case=c).order_by('-pk')[:20],'reviews':SupportReview.objects.filter(case=c).order_by('-pk')[:30],'policies':[resolve(k,c) for k in SCHEMAS],'policy_schemas':SCHEMAS,'source_schema':__import__('adapters.support',fromlist=['MESSAGE']).MESSAGE,'result_schema':d.RESULT,'agents':AgentRun.objects.filter(case=c,provider='deterministic-support-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c)
 try:v=d.read_report(request.user,c.pk,pk)
 except ValidationError:return JsonResponse({'status':'held','reason':'Current flow, source, owner and summary review required'},status=409,headers={'Cache-Control':'no-store'})
 if request.GET.get('format')=='json':return JsonResponse(v,headers={'Cache-Control':'no-store'})
 response=render(request,'baas/support_report.html',{'case':c,'value':v,'result':v['result']});response['Cache-Control']='no-store';return response
