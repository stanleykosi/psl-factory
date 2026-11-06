from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.identity.services import require
from apps.finance.forms import CommandForm
from apps.policy.support_agent_validators import COMPONENT,SCHEMAS
from apps.policy.support_drafts import draft_support_policy
from apps.policy.services import resolve
from apps.agents import boundary as gateway
from . import support_agent as d
from .support_models import SupportIntake

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 def draft():return forms.ModelChoiceField(d.Draft.objects.filter(case=c))
 defs={
 'policy':('Draft native source and reuse policy','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()}),
 'project':('Project linked intake fields','support.agent.project',{'intake':forms.ModelChoiceField(SupportIntake.objects.filter(case=c)),'reference':forms.CharField(max_length=100)}),
 'reuse':('Prepare draft from reviewed extraction','support.agent.draft',{'receipt':forms.ModelChoiceField(gateway.Receipt.objects.filter(job__projection__case=c,job__projection__evidence__kind=d.KIND)),'reference':forms.CharField(max_length=100)}),
 'revise':('Create human draft revision','support.agent.draft',{'draft':draft(),'body':forms.CharField(max_length=12000,widget=forms.Textarea)}),
 'review':('Review exact draft revision','support.agent.review',{'draft':draft(),'verdict':forms.ChoiceField(choices=[(v,v) for v in ['approve','return','withdraw']])})}
 result=[]
 for key,(title,permission,fields) in defs.items():
  if permission not in grants:continue
  cls=type('SupportAgentCommand',(CommandForm,),fields);f=cls(data if data and data.get('action')==key else None,initial={'action':key,'revision':c.revision});result.append({'key':key,'title':title,'form':f})
 return result
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.source_access(request.user,c);require(request.user,c,'support.agent.read');cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  selected=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if not selected:raise PermissionDenied
  f=selected['form']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Valid typed command required');return redirect('support_agents',case_id=c.pk)
  v=f.cleaned_data;a=request.user;k=selected['key'];rev=v['revision']
  try:
   if k=='project':d.project(a,c.pk,v['intake'].pk,v['reference'],rev)
   elif k=='reuse':
    from apps.agents.support_drafts import prepare
    prepare(a,c.pk,v['receipt'].pk,v['reference'],rev)
   elif k=='revise':d.revise(a,c.pk,v['draft'].pk,v['body'],rev)
   elif k=='review':d.review(a,c.pk,v['draft'].pk,v['verdict'],rev)
   elif k=='policy':
    from django.db import transaction
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_support_policy(a,c.pk,COMPONENT,v['content'],v['evidence'].pk,v['effective_from'])
   messages.success(request,'Private source/draft history updated; no response was sent or support state changed.')
  except (ValidationError,ValueError,TypeError):messages.error(request,'Held by current source, ownership, policy, review or budget controls.')
  return redirect('support_agents',case_id=c.pk)
 rows=[]
 for r in d.Draft.objects.filter(case=c).order_by('-pk')[:30]:
  value=d.report(request.user,c.pk,r.pk);rows.append({'row':r,'value':value})
 response=render(request,'baas/support_agents.html',{'case':c,'policy':resolve(COMPONENT,c),'schema':SCHEMAS,'sources':d.SupportProjection.objects.filter(case=c).order_by('-pk')[:30],'drafts':rows,'commands':cmds});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 try:value=d.report(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
