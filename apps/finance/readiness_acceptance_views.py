from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse,Http404
from django.shortcuts import render,redirect
from django.db import transaction
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.policy.validation_validators import ACCEPTANCE,PRIVATE_SCHEMA,PRIVATE_VALUE
from apps.policy.validation_drafts import draft_validation_policy
from apps.policy.services import resolve
from apps.agents import private_readiness as agent
from apps.finance.forms import CommandForm
from adapters.private_readiness import PrivateReadinessEvidenceAdapter as Adapter
from . import readiness_acceptance as d

def assessments(a,c):
 ids=[]
 for row in d.IntegrationAssessment.objects.filter(contract__case=c,contract__finance_publication_readiness__isnull=False).select_related('contract__case'):
  try:Adapter().access(a,row)
  except PermissionDenied:continue
  ids.append(row.pk)
 return d.IntegrationAssessment.objects.filter(pk__in=ids)

def commands(a,c,data=None):
 from .acceptance import visible_packages
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True));key=lambda:forms.CharField(max_length=100)
 defs={
 'prepare':('Prepare private readiness evidence packet','validation.package.prepare',{'assessment':forms.ModelChoiceField(assessments(a,c)),'package':forms.ModelChoiceField(visible_packages(a,c)),'reference':key(),'predecessor':forms.IntegerField(min_value=1,required=False)}),
 'review':('Record separate AF13 owner decision','validation.review' if 'validation.review' in grants else 'validation.accept',{'packet':forms.ModelChoiceField(d.visible(a,c)),'kind':forms.ChoiceField(choices=[(x,x) for x in ['meaning','expectations','acceptance'] if ('validation.accept' if x=='acceptance' else 'validation.review') in grants]),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['approve','return','disputed','reject','revoke']]),'operation_key':key(),'reason':forms.CharField(max_length=4000,widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='owner_validation'))}),
 'policy':('Draft private readiness acceptance criteria','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()})}
 return [{'key':k,'title':title,'form':type('PrivateReadinessCommand',(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants]

@login_required
@transaction.atomic
@d.evaluation.evaluated
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);c=d.af.locked(request.user,c.pk,'validation.read');cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  row=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if row is None:raise PermissionDenied
  f=row['form']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Valid permitted typed command required');return redirect('private_readiness_acceptance',case_id=c.pk)
  v=f.cleaned_data;a=request.user
  try:
   if row['key']=='prepare':agent.prepare(a,c.pk,v['assessment'].pk,v['package'].pk,v['reference'],v['predecessor'],v['revision'])
   elif row['key']=='review':
    with transaction.atomic():
     d.af.locked(a,c.pk,'validation.read',v['revision']);d.package_access(a,v['packet'].package)
     d.af.review(a,c.pk,v['packet'].package_id,v['kind'],v['verdict'],v['operation_key'],v['evidence'].pk,v['reason'],None)
   else:
    if not isinstance(v['content'],dict) or 'private_readiness' not in v['content']:raise ValidationError('Explicit v2 private readiness criteria required')
    with transaction.atomic():d.af.locked(a,c.pk,'policy.configure',v['revision']);draft_validation_policy(a,c.pk,ACCEPTANCE,v['content'],v['evidence'].pk,v['effective_from'])
   messages.success(request,'Private evidence history updated. Operational acceptance remains separate.')
  except (ValidationError,ValueError,TypeError,ConnectionError):messages.error(request,'Held by exact private source, readiness, package, policy or human review controls.')
  return redirect('private_readiness_acceptance',case_id=c.pk)
 response=render(request,'finance/readiness_acceptance.html',{'case':c,'commands':cmds,'rows':[d.report(request.user,c.pk,b.pk) for b in d.visible(request.user,c).order_by('-pk')[:30]],'policy':resolve(ACCEPTANCE,c),'schema':{PRIVATE_SCHEMA:PRIVATE_VALUE},'guidance':agent.investigate(request.user,c.pk) if Grant.objects.filter(case=c,user=request.user,action='agent.validation',active=True).exists() else None});response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,pk):
 accessible_case(request.user,case_id)
 try:value=d.report(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})

@login_required
def export(request,case_id,pk):
 accessible_case(request.user,case_id)
 try:value=d.export(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
