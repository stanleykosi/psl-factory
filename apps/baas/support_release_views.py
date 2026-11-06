from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from apps.core.views import accessible_case
from apps.finance.forms import CommandForm
from apps.identity.models import Grant
from apps.policy.services import resolve
from apps.policy.support_drafts import draft_support_policy
from apps.policy.support_release_validators import COMPONENT,SCHEMAS
from . import support_release as d

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 defs={
 'policy':('Draft response release policy','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()}),
 'prepare':('Prepare exact reviewed packet','support.response.prepare',{'draft':forms.ModelChoiceField(d.native.Draft.objects.filter(case=c)),'reference':forms.CharField(max_length=100)}),
 'decide':('Human release or withdrawal','support.response.release',{'packet':forms.ModelChoiceField(d.Packet.objects.filter(case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['release','withdraw']])}),
 'operate':('Recover internal delivery','support.response.operate',{'job':forms.ModelChoiceField(d.Job.objects.filter(packet__case=c)),'operation':forms.ChoiceField(choices=[(x,x) for x in ['retry','cancel']]),'reason':forms.CharField(max_length=1000)})}
 result=[]
 for k,(title,permission,fields) in defs.items():
  if permission in grants:
   cls=type('ResponseCommand',(CommandForm,),fields);result.append({'key':k,'title':title,'form':cls(data if data and data.get('action')==k else None,initial={'action':k,'revision':c.revision})})
 return result

@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.access(request.user,c);cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  selected=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if not selected:raise PermissionDenied
  f=selected['form']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Valid typed command required');return redirect('support_responses',case_id=c.pk)
  v=f.cleaned_data;a=request.user;rev=v['revision'];k=selected['key']
  try:
   if k=='prepare':
    from apps.agents.support_responses import prepare
    prepare(a,c.pk,v['draft'].pk,v['reference'],rev)
   elif k=='decide':d.decide(a,c.pk,v['packet'].pk,v['verdict'],rev)
   elif k=='operate':d.operate(a,c.pk,v['job'].pk,v['operation'],v['reason'],rev)
   elif k=='policy':
    from django.db import transaction
    with transaction.atomic():d.native.locked(a,c.pk,'policy.configure',rev);draft_support_policy(a,c.pk,COMPONENT,v['content'],v['evidence'].pk,v['effective_from'])
   messages.success(request,'Response history updated. Internal delivery does not establish customer response time.')
  except (ValidationError,ValueError,TypeError):messages.error(request,'Held by current source, draft review, human release, destination or budget controls.')
  return redirect('support_responses',case_id=c.pk)
 rows=[d.inspect(request.user,c.pk,p.pk) for p in d.Packet.objects.filter(case=c).order_by('-pk')[:30]]
 response=render(request,'baas/support_responses.html',{'case':c,'policy':resolve(COMPONENT,c),'schema':SCHEMAS,'rows':rows,'commands':cmds});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 try:value=d.inspect(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
@login_required
def receipt(request,case_id,pk):
 try:value=d.receive(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})

@login_required
def diagnostics(request,case_id):
 from apps.agents.support_response_operations import investigate
 return JsonResponse(investigate(request.user,case_id),headers={'Cache-Control':'no-store'})
