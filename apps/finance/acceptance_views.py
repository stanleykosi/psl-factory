from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse,Http404
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.services import resolve
from apps.policy.ledger_validators import HANDOFF,SCHEMAS
from apps.policy.ledger_drafts import draft_ledger_policy
from apps.agents.boundary import visible_projections
from apps.agents.finance_acceptance import investigate
from . import acceptance as d

def visible(a,c):
 ids=[]
 for h in d.Handoff.objects.filter(case=c):
  try:d.access(a,h)
  except PermissionDenied:continue
  ids.append(h.pk)
 return d.Handoff.objects.filter(pk__in=ids)

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True));key=lambda:forms.CharField(max_length=100)
 defs={
 'prepare':('Prepare exact Finance evidence handoff','finance.handoff.prepare',{'draft':forms.ModelChoiceField(d.finance.Draft.objects.filter(case=c,source__projection__in=visible_projections(a,c))),'package':forms.ModelChoiceField(d.visible_packages(a,c)),'reference':key(),'predecessor':forms.IntegerField(min_value=1,required=False)}),
 'receive':('Acknowledge or return recipient receipt','finance.handoff.receive',{}),
 'validate':('Validate exact received evidence','finance.handoff.validate',{}),
 'accept':('Record separate scoped handoff acceptance','finance.handoff.accept',{}),
 'policy':('Draft exact recipient and package routing policy','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()})}
 for phase in ['receive','validate','accept']:
  defs[phase][2].update(handoff=forms.ModelChoiceField(visible(a,c)),verdict=forms.ChoiceField(choices=[(x,x) for x in ['confirm','return','withdraw']]),operation_key=key(),reason=forms.CharField(max_length=2000,widget=forms.Textarea))
 return [{'key':k,'title':title,'form':type('FinanceAcceptanceCommand',(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants]

@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  row=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if row is None:raise PermissionDenied
  f=row['form']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Valid permitted typed command required');return redirect('finance_acceptance',case_id=c.pk)
  v=f.cleaned_data;a=request.user;k=row['key']
  try:
   if k=='prepare':
    from apps.agents.finance_acceptance import prepare
    prepare(a,c.pk,v['draft'].pk,v['package'].pk,v['reference'],v['predecessor'],v['revision'])
   elif k in ['receive','validate','accept']:d.decide(a,c.pk,v['handoff'].pk,k,v['verdict'],v['operation_key'],v['reason'],v['revision'])
   elif k=='policy':
    from django.db import transaction
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',v['revision']);draft_ledger_policy(a,c.pk,HANDOFF,v['content'],v['evidence'].pk,v['effective_from'])
   messages.success(request,'Private handoff decision history recorded. AF13 reviews, accounting and deployment remain separate.')
  except (ValidationError,ValueError,TypeError,ConnectionError):messages.error(request,'Held by current source, package, routing, authority, review or freshness controls.')
  return redirect('finance_acceptance',case_id=c.pk)
 response=render(request,'finance/acceptance.html',{'case':c,'rows':[d.report(request.user,c.pk,h.pk) for h in visible(request.user,c).order_by('-pk')[:30]],'commands':cmds,'policy':resolve(HANDOFF,c),'schema':SCHEMAS[HANDOFF],'guidance':investigate(request.user,c.pk) if Grant.objects.filter(case=c,user=request.user,active=True,action='agent.validation').exists() else None});response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,pk):
 try:value=d.report(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
