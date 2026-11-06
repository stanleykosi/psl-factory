from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse,Http404
from django.shortcuts import render,redirect
from django.db import transaction
from apps.core.views import accessible_case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.services import resolve
from apps.policy.support_drafts import draft_support_policy
from apps.policy.support_channel_validators import SCHEMAS
from . import support_channel as d,support_channel_delivery as worker,support_clock_corrections as corrections

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 receipts=lambda:forms.ModelChoiceField(d.Receipt.objects.filter(job__claim__case=c))
 defs={
 'contract':('Capture private channel protocol/meaning evidence','support.channel.capture',{'body':forms.CharField(max_length=12000,widget=forms.Textarea)}),
 'policy':('Draft versioned channel or clock policy','policy.configure',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()}),
 'source_evidence':('Capture private successor or correction evidence','support.channel.capture',{'kind':forms.ChoiceField(choices=[(x,x) for x in ['agent_private_channel_successor','agent_private_clock_correction','agent_private_clock_review']]),'body':forms.CharField(max_length=12000,widget=forms.Textarea)}),
 'successor':('Record explicit source receipt revision','support.channel.successor',{'predecessor':forms.ModelChoiceField(d.Claim.objects.filter(case=c)),'reference':forms.CharField(max_length=100),'receipt_version':forms.CharField(max_length=100),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='agent_private_channel_successor'))}),
 'correct':('Propose current clock correction without rewriting events','support.channel.correct',{'mode':forms.ChoiceField(choices=[(x,x) for x in ['revalidate','replace','late','withdraw']]),'receipt':forms.ModelChoiceField(d.Receipt.objects.filter(job__claim__case=c),required=False),'reference':forms.CharField(max_length=100),'predecessor':forms.ModelChoiceField(corrections.Correction.objects.filter(case=c),required=False),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='agent_private_clock_correction')),'reason':forms.CharField(max_length=400)}),
 'correct_review':('Independently review current clock correction','support.channel.correct_review',{'correction':forms.ModelChoiceField(corrections.Correction.objects.filter(case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','return','withdraw']]),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='agent_private_clock_review'))}),
 'claim':('Capture supplied customer receipt identity','support.channel.capture',{'packet':forms.ModelChoiceField(d.release.Packet.objects.filter(case=c)),'reference':forms.CharField(max_length=100),'external_ref':forms.CharField(max_length=100),'receipt_version':forms.CharField(max_length=100)}),
 'check':('Reserve read-only channel receipt verification','support.channel.verify',{'claim':forms.ModelChoiceField(d.Claim.objects.filter(case=c)),'reference':forms.CharField(max_length=100)}),
 'review':('Independently review exact gateway receipt','support.channel.review',{'receipt':receipts(),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','return','withdraw']])}),
 'attest':('Human attest customer-delivery clock','support.channel.attest',{'receipt':receipts(),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='support_response'))}),
 'operate':('Recover read-only receipt check','support.channel.operate',{'job':forms.ModelChoiceField(d.Job.objects.filter(claim__case=c)),'operation':forms.ChoiceField(choices=[(x,x) for x in ['retry','cancel']]),'reason':forms.CharField(max_length=400)})}
 return [{'key':key,'title':title,'form':type('ChannelCommand',(CommandForm,),fields)(data if data and data.get('action')==key else None,initial={'action':key,'revision':c.revision},auto_id='id_'+key+'_%s')} for key,(title,permission,fields) in defs.items() if permission in grants]
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.access(request.user,c);cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  selected=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if not selected:raise PermissionDenied
  f=selected['form']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Valid typed command required');return redirect('support_channels',case_id=c.pk)
  v=f.cleaned_data;a=request.user;k=selected['key'];revision=v['revision']
  try:
   if k=='contract':
    with transaction.atomic():d.locked(a,c.pk,'capture',revision);add_evidence(a,c.pk,'agent_private_support_channel_contract',v['body'],'supplied:channel-protocol')
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'read',revision);draft_support_policy(a,c.pk,v['component'],v['content'],v['evidence'].pk,v['effective_from'])
   elif k=='source_evidence':
    with transaction.atomic():d.locked(a,c.pk,'capture',revision);add_evidence(a,c.pk,v['kind'],v['body'],'supplied:clock-successor')
   elif k=='successor':corrections.successor(a,c.pk,v['predecessor'].pk,v['reference'],v['receipt_version'],v['evidence'].pk,revision)
   elif k=='correct':corrections.propose(a,c.pk,v['mode'],v['receipt'].pk if v['receipt'] else None,v['reference'],v['predecessor'].pk if v['predecessor'] else None,v['evidence'].pk,v['reason'],revision)
   elif k=='correct_review':corrections.review(a,c.pk,v['correction'].pk,v['verdict'],v['evidence'].pk,revision)
   elif k=='claim':d.capture(a,c.pk,v['packet'].pk,v['reference'],v['external_ref'],v['receipt_version'],revision)
   elif k=='check':d.reserve(a,c.pk,v['claim'].pk,v['reference'],revision)
   elif k=='review':d.review(a,c.pk,v['receipt'].pk,v['verdict'],revision)
   elif k=='attest':d.attest(a,c.pk,v['receipt'].pk,v['evidence'].pk,revision)
   elif k=='operate':worker.operate(a,c.pk,v['job'].pk,v['operation'],v['reason'],revision)
   messages.success(request,'Channel evidence updated; clock attestations record ordered responses and independently reviewed corrections change only the current metric projection. No message was dispatched.')
  except (ValidationError,ValueError,TypeError):messages.error(request,'Held by exact source/identity/policy, independent review, release window, authority, clock order or budget. Preserve observations and use correction for late evidence.')
  return redirect('support_channels',case_id=c.pk)
 response=render(request,'baas/support_channels.html',{'case':c,'policies':[resolve(k,c) for k in SCHEMAS],'commands':cmds,'contracts':c.evidence.filter(kind='agent_private_support_channel_contract').order_by('-pk')[:20],'rows':[d.inspect(request.user,c.pk,r.pk) for r in d.Claim.objects.filter(case=c).order_by('-pk')[:30]],'schema':SCHEMAS,'clock_enrolled':d.enrolled(c),'corrections':corrections.history(request.user,c),'correction_sources':c.evidence.filter(kind__in=['agent_private_channel_successor','agent_private_clock_correction','agent_private_clock_review']).order_by('-pk')[:30]});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 try:result=d.inspect(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(result,headers={'Cache-Control':'no-store'})
@login_required
def guidance(request,case_id):
 from apps.agents.support_channels import investigate
 return JsonResponse(investigate(request.user,case_id),headers={'Cache-Control':'no-store'})
