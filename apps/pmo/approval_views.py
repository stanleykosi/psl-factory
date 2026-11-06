from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse,Http404
from django.shortcuts import render,redirect
from django.db import transaction
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.approval_validators import SCHEMAS
from apps.policy.approval_drafts import draft_approval_policy
from apps.agents.approvals import investigate
from apps.agents.models import AgentRun
from . import approvals as d,approval_routing as routing
from .approval_forms import commands
from .models import ApprovalRequest,ApprovalSourceReceipt,ApprovalRouteJob,ApprovalRouteReceipt

@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required')
   v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];e=v['evidence'].pk if v.get('evidence') else None
   if k=='request':d.create_request(a,c.pk,v['reference'],v['candidate'].pk,v['kind'],v['build_ref'] or None,v['release_ref'] or None,e,rev,v['predecessor'])
   elif k=='contract':d.review_contract(a,c.pk,v['kind'],e,v['verdict'],rev)
   elif k=='capture':d.capture(a,c.pk,v['request'].pk,e,rev)
   elif k=='observe':d.observe(a,c.pk,v['receipt'].pk,e,rev)
   elif k=='route':routing.reserve(a,c.pk,v['request'].pk,v['purpose'],rev)
   elif k=='operate':routing.operate(a,c.pk,v['job'].pk,v['operation'],v['reason'],rev)
   elif k=='export':d.export_gate(a,c.pk,v['observation'].pk,rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_approval_policy(a,c.pk,v['component'],v['content'],e,v['effective_from'])
   messages.success(request,'Prerequisite evidence and routing history updated; department approval remains external');return redirect('approvals',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('approvals',case_id=c.pk)
 rows=[d.visibility(request.user,r) for r in ApprovalRequest.objects.filter(case=c).select_related('case','candidate__requirements').order_by('-pk')[:100]]
 response=render(request,'pmo/approvals.html',{'case':c,'rows':rows,'commands':forms,'policies':[resolve(k,c) for k in SCHEMAS],'schemas':SCHEMAS,'source_schema':d.SOURCE,'observation_schema':d.READ,'jobs':ApprovalRouteJob.objects.filter(request__case=c).order_by('-pk')[:40],'agents':AgentRun.objects.filter(case=c,actor=request.user,provider='deterministic-approvals-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c)
 rows=[d.visibility(request.user,r) for r in ApprovalRequest.objects.filter(case=c).select_related('case','candidate__requirements').order_by('-pk')[:100]]
 return JsonResponse({'requests':rows,'coverage':'At most 100 current/historical request versions; source access checked per request','approval_granted':False,'native_verified':False},headers={'Cache-Control':'no-store'})

@login_required
def source(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);s=ApprovalSourceReceipt.objects.filter(request__case=c,pk=pk).first()
 if not s:raise Http404
 require(request.user,c,'approval.source.read:'+s.system)
 return JsonResponse({'receipt_id':s.pk,'payload':s.payload,'sha256':s.sha256,'evidence_id':s.evidence_id,'observations':list(s.observations.order_by('-pk').values('id','status','payload','actor_id')),'native_verified':False},headers={'Cache-Control':'no-store'})

@login_required
def inbox(request):
 rows=[]
 for receipt in ApprovalRouteReceipt.objects.filter(recipient=request.user).select_related('job__request__case','job__request__candidate__requirements').order_by('-pk')[:100]:
  r=receipt.job.request
  try:
   d.readable(request.user,r.case);d.current_request(r);_,_,route,_,_=d.rules(r.case,r.kind);d.owner_authority(request.user,r.case,route,'approval.receive')
  except (PermissionDenied,ValidationError):continue
  rows.append({'receipt':receipt,'case':r.case,'request':r})
 response=render(request,'pmo/approval_inbox.html',{'rows':rows});response['Cache-Control']='no-store';return response
