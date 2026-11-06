from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.d03_validators import SCHEMAS
from apps.policy.d03_drafts import draft_d03_policy
from apps.agents.billing_evidence import investigate
from apps.agents.models import AgentRun
from .d03_forms import commands
from . import billing_evidence as d
from .models import BillingEvidenceSource,BillingEvidenceReview,BillingControlReceipt,BillingReleaseProfile,BillingReleaseAssessment,BillingReleaseBinding
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required')
   v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];e=v['evidence'].pk if v.get('evidence') else None
   if k=='source':d.capture_source(a,c.pk,v['reference'],v['payload'],e,rev,v['predecessor'])
   elif k=='review':d.review_source(a,c.pk,v['source'].pk,v['verdict'],v['meaning'],v['operation_key'],e,rev)
   elif k=='enroll':d.enroll(a,c.pk,v['coverage'].pk,e,rev)
   elif k=='observe':d.observe_control(a,c.pk,v['invoice'].pk,e,rev)
   elif k=='assess':d.assess(a,c.pk,v['invoice'].pk,v['effect'],rev)
   elif k=='bind':d.bind(a,c.pk,v['assessment'].pk,rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_d03_policy(a,c.pk,v['component'],v['content'],e,v['effective_from'])
   messages.success(request,'Source/release evidence history updated; no signature gate, posting, sending or deployment inferred');return redirect('billing_evidence',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('billing_evidence',case_id=c.pk)
 sources=[]
 for s in BillingEvidenceSource.objects.filter(case=c).select_related('case').order_by('-pk')[:40]:
  try:r=d.confirmed(s);status='Current Finance confirmation'
  except (ValidationError,PermissionDenied):r=None;status='Unconfirmed, disputed or stale'
  sources.append({'source':s,'status':status})
 rows=[{'record':r,'report':d.report(request.user,c.pk,r.pk)} for r in BillingReleaseAssessment.objects.filter(invoice__case=c).order_by('-pk')[:25]]
 response=render(request,'finance/billing_evidence.html',{'case':c,'sources':sources,'assessments':rows,'profiles':BillingReleaseProfile.objects.filter(coverage__case=c),'bindings':BillingReleaseBinding.objects.filter(assessment__invoice__case=c).order_by('-pk')[:30],'commands':forms,'policies':[resolve(k,c) for k in SCHEMAS],'schemas':{'source':d.SOURCE,'control':d.CONTROL,'policy':SCHEMAS},'agents':AgentRun.objects.filter(case=c,actor=request.user,provider='deterministic-billing-evidence-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 c=accessible_case(request.user,case_id);return JsonResponse(d.report(request.user,c.pk,pk),headers={'Cache-Control':'no-store'})
@login_required
def source(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);require(request.user,c,'d03.source.read');s=BillingEvidenceSource.objects.filter(case=c,pk=pk).first()
 if not s:raise Http404
 return JsonResponse({'source':s.pk,'payload':s.payload,'sha256':s.sha256,'creator':s.actor_id,'created_at':s.created_at,'reviews':list(BillingEvidenceReview.objects.filter(source=s).order_by('-pk').values('id','verdict','meaning','actor_id','created_at')),'native_flow_verified':False},headers={'Cache-Control':'no-store'})
@login_required
def controls(request,case_id,pk):
 from .models import Invoice
 c=accessible_case(request.user,case_id);d.readable(request.user,c);require(request.user,c,'d03.source.read')
 i=Invoice.objects.filter(case=c,pk=pk).first()
 if not i:raise Http404
 return JsonResponse({'invoice':i.pk,'receipts':list(BillingControlReceipt.objects.filter(invoice=i).order_by('-pk').values('id','effect','control_key','payload','sha256','actor_id','created_at')),'native_flow_verified':False},headers={'Cache-Control':'no-store'})
