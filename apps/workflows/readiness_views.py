from django import forms
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.readiness_validators import SCHEMAS
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.services import resolve
from apps.agents.integrations import investigate
from apps.agents.models import AgentRun
from apps.finance.publication_readiness import visible_jobs
from apps.policy.readiness_validators import NATIVE_VALUE,PRIVATE_VALUE,FILE_VALUE
from .private_protection_readiness import visible_jobs as private_jobs
from .private_file_readiness import visible_jobs as file_jobs
from .accepted_protection_readiness import visible_jobs as accepted_jobs
from . import readiness as d,readiness_delivery as w
from .readiness_models import IntegrationContract,IntegrationProbe,IntegrationObservation,IntegrationAssessment,IntegrationReview,IntegrationSelection
class AcceptedProtectionJobChoice(forms.ModelChoiceField):
 def label_from_instance(self,j):return f"#{j.pk} {j.kind} / {j.plan.reference} v{j.plan.version} / {j.status}"

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True));key=lambda:forms.CharField(max_length=100)
 def evidence(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
 def contract():return forms.ModelChoiceField(d.visible_contracts(a,c))
 def choice(values):return forms.ChoiceField(choices=[(v,v) for v in values])
 defs={
 'capture':('Capture versioned integration contract','integration.capture',{'native_accepted_protection_job':AcceptedProtectionJobChoice(accepted_jobs(a,c),required=False,label='AF13 protection operator job'),'native_file_job':forms.ModelChoiceField(file_jobs(a,c),required=False),'native_protection_job':forms.ModelChoiceField(private_jobs(a,c),required=False),'native_publication_job':forms.ModelChoiceField(visible_jobs(a,c),required=False), 'reference':key(),'payload':forms.JSONField(widget=forms.Textarea),'evidence':evidence('integration_contract'),'predecessor':forms.IntegerField(min_value=1,required=False)}),
 'supplied':('Capture supplied readiness report','integration.capture',{'contract':contract(),'operation_key':key(),'evidence':evidence('integration_report')}),
 'policy':('Draft typed adapter/provider readiness rules','policy.configure',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea),'evidence':evidence('policy_decision'),'effective_from':forms.DateTimeField()}),
 'probe':('Reserve authenticated bounded probe','integration.probe',{'contract':contract(),'operation_key':key(),'kind':choice(['health','receipt','evaluation']),'source_job':forms.IntegerField(min_value=1,required=False)}),
 'canary':('Evaluate enrolled provider using fixed public canary','integration.probe',{'operation_key':key()}),
 'assess':('Assess current authenticated capability evidence','integration.assess',{'contract':contract(),'operation_key':key()}),
 'review':('Review exact readiness assessment','integration.review',{'assessment':forms.ModelChoiceField(IntegrationAssessment.objects.filter(contract__in=d.visible_contracts(a,c))),'verdict':choice(['confirm','return','withdraw']),'operation_key':key(),'evidence':evidence('integration_review')}),
 'select':('Enroll source family in readiness dependency','integration.select',{'contract':contract(),'evidence':evidence('integration_selection')}),
 'operate':('Reconcile readiness probe','integration.operate',{'job':forms.ModelChoiceField(IntegrationProbe.objects.filter(contract__in=d.visible_contracts(a,c))),'operation':choice(['retry','cancel']),'reason':forms.CharField(max_length=400)}),
 'investigate':('Investigate integration readiness gaps','agent.integrations',{})}
 return [{'title':title,'form':type('Integration'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants and (k=='investigate' or 'integration.source.read' in grants)]
@login_required
@transaction.atomic
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);c=d.locked(request.user,c.pk,'integration.read');forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((r['form'] for r in forms if r['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Typed permitted command required')
   v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];eid=v['evidence'].pk if v.get('evidence') else None
   if k=='capture':
    if v.get('native_accepted_protection_job'):
     if any(v.get(k) for k in ['native_file_job','native_protection_job','native_publication_job']):raise ValidationError('Choose one exact native source')
     from apps.agents.accepted_protection_readiness import prepare
     if Grant.objects.filter(case=c,user=a,action='agent.integrations',active=True).exists():prepare(a,c.pk,v['reference'],v['payload'],eid,v['native_accepted_protection_job'].pk,rev,v['predecessor'])
     else:d.capture(a,c.pk,v['reference'],v['payload'],eid,rev,v['predecessor'],native_accepted_protection_job=v['native_accepted_protection_job'].pk)
    elif v.get('native_file_job'):
     if v.get('native_publication_job') or v.get('native_protection_job'):raise ValidationError('Choose one exact native source')
     from apps.agents.private_file_readiness import prepare
     prepare(a,c.pk,v['reference'],v['payload'],eid,v['native_file_job'].pk,rev,v['predecessor'])
    elif v.get('native_protection_job'):
     if v.get('native_publication_job'):raise ValidationError('Choose one native source')
     from apps.agents.private_protection_readiness import prepare
     prepare(a,c.pk,v['reference'],v['payload'],eid,v['native_protection_job'].pk,rev,v['predecessor'])
    else:d.capture(a,c.pk,v['reference'],v['payload'],eid,rev,v['predecessor'],native_publication_job=v['native_publication_job'].pk if v.get('native_publication_job') else None)
   elif k=='supplied':d.supplied(a,c.pk,v['contract'].pk,v['operation_key'],eid,rev)
   elif k=='policy':
    from django.db import transaction
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_readiness_policy(a,c.pk,v['component'],v['content'],eid,v['effective_from'])
   elif k=='probe':w.reserve(a,c.pk,v['contract'].pk,v['operation_key'],v['kind'],v['source_job'],rev)
   elif k=='canary':
    from apps.agents.readiness_gateway import canary
    canary(a,c.pk,v['operation_key'],rev)
   elif k=='assess':d.assess(a,c.pk,v['contract'].pk,v['operation_key'],rev)
   elif k=='review':d.review(a,c.pk,v['assessment'].pk,v['verdict'],v['operation_key'],eid,rev)
   elif k=='select':d.select(a,c.pk,v['contract'].pk,eid,rev)
   elif k=='operate':w.operate(a,c.pk,v['job'].pk,v['operation'],v['reason'],rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   messages.success(request,'Versioned readiness history updated; business authority and operational acceptance remain separate.')
  except (ValidationError,ValueError,TypeError,ConnectionError):messages.error(request,'Readiness action held by scoped configuration, identity or evidence controls; no raw endpoint error or credential is displayed.')
  return redirect('integration_readiness',case_id=c.pk)
 response=render(request,'workflows/readiness.html',{'case':c,'policies':[resolve(k,c) for k in SCHEMAS],'contracts':d.visible_contracts(request.user,c).order_by('-pk')[:30],'probes':IntegrationProbe.objects.filter(contract__in=d.visible_contracts(request.user,c)).order_by('-pk')[:50],'observations':IntegrationObservation.objects.filter(contract__in=d.visible_contracts(request.user,c)).order_by('-pk')[:50],'assessments':[{'row':r,'report':d.report(request.user,c.pk,r.pk)} for r in IntegrationAssessment.objects.filter(contract__in=d.visible_contracts(request.user,c)).order_by('-pk')[:20]],'selections':IntegrationSelection.objects.filter(case=c,contract__in=d.visible_contracts(request.user,c)).order_by('-pk')[:30],'commands':forms,'schemas':{'contract':d.CONTRACT,'supplied_report':d.SUPPLIED,'policy':SCHEMAS,'native_adapter_policy':NATIVE_VALUE,'private_protection_policy':PRIVATE_VALUE,'private_file_policy_v2':FILE_VALUE,'accepted_protection_policy':SCHEMAS['INT.accepted_protection_readiness'][1]},'accepted_protection_guidance':accepted_guidance(request.user,c),'private_file_guidance':file_guidance(request.user,c),'private_protection_guidance':private_guidance(request.user,c),'native_guidance':native_guidance(request.user,c),'investigations':AgentRun.objects.filter(case=c,actor=request.user,provider='deterministic-integrations-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
@transaction.atomic
def source(request,case_id,kind,pk):
 c=accessible_case(request.user,case_id);c=d.locked(request.user,c.pk,'integration.read');d.readable(request.user,c,True);model=IntegrationContract if kind=='contract' else IntegrationObservation if kind=='observation' else None
 r=model.objects.filter(**({'case':c} if kind=='contract' else {'contract__case':c}),pk=pk).first() if model else None
 if not r:raise Http404
 d.contract_access(request.user,r if kind=='contract' else r.contract)
 value={'id':r.pk,'payload':r.payload,'sha256':r.sha256}
 if kind=='contract':
  from apps.finance.publication_readiness import binding
  b=binding(r)
  if b:value['native_publication']=b.snapshot
  from .private_protection_readiness import binding as private_binding
  b=private_binding(r)
  if b:value['native_protection']=b.snapshot
  from .private_file_readiness import binding as file_binding
  b=file_binding(r)
  if b:value['native_file']=b.snapshot
  from .accepted_protection_readiness import binding as accepted_binding
  b=accepted_binding(r)
  if b:value['native_accepted_protection']=b.snapshot
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
@login_required
def report(request,case_id,pk):
 accessible_case(request.user,case_id)
 try:value=d.report(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})


def native_guidance(actor,case):
 from django.core.exceptions import PermissionDenied
 from apps.finance.publication_readiness import investigate
 try:return investigate(actor,case)
 except PermissionDenied:return None


def private_guidance(actor,case):
 from django.core.exceptions import PermissionDenied
 from apps.agents.private_protection_readiness import investigate
 try:return investigate(actor,case)
 except PermissionDenied:return None

def file_guidance(actor,case):
 from django.core.exceptions import PermissionDenied
 from apps.agents.private_file_readiness import investigate
 try:return investigate(actor,case)
 except PermissionDenied:return None

def accepted_guidance(actor,case):
 from django.core.exceptions import PermissionDenied
 from apps.agents.accepted_protection_readiness import investigate
 try:return investigate(actor,case)
 except PermissionDenied:return None
