from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from apps.core.views import accessible_case
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.agent_data_validators import COMPONENT,SCHEMAS
from apps.policy.services import resolve
from . import boundary as d
from . import boundary_delivery as w

def commands(a,c,data=None):
 visible=d.visible_projections(a,c)
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 def choice(items):return forms.ChoiceField(choices=[(x,x) for x in items])
 def projection():return forms.ModelChoiceField(visible)
 defs={
 'capture':('Capture private input','agent.data.source',{'body':forms.CharField(max_length=12000,widget=forms.Textarea),'source':forms.CharField(max_length=500)}),
 'project':('Prepare exact source projection','agent.data.project',{'evidence':forms.ModelChoiceField(Evidence.objects.filter(case=c,kind__in=d.SOURCE_KINDS)),'process':forms.CharField(max_length=10),'purpose':forms.CharField(max_length=100),'quotes':forms.JSONField(widget=forms.Textarea),'predecessor':forms.IntegerField(min_value=1,required=False)}),
 'policy':('Draft typed data policy','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(Evidence.objects.filter(case=c,kind='policy_decision')),'effective_from':forms.DateTimeField()}),
 'projection_review':('Review projection for egress','agent.data.review',{'projection':projection(),'verdict':choice(['confirm','return','withdraw'])}),
 'send':('Reserve reviewed extraction','agent.data.send',{'projection':projection(),'operation_key':forms.CharField(max_length=100)}),
 'result_review':('Review or correct private result','agent.data.review',{'receipt':forms.ModelChoiceField(d.Receipt.objects.filter(job__projection__in=visible)),'verdict':choice(['confirm','correct','return','withdraw']),'corrected':forms.JSONField(required=False,widget=forms.Textarea)}),
 'operate':('Retry held extraction through receipt lookup','agent.data.operate',{'job':forms.ModelChoiceField(d.Job.objects.filter(projection__in=visible,status='held'))}),
 }
 result=[]
 for key,(title,permission,fields) in defs.items():
  if permission not in grants or 'agent.data.source' not in grants:continue
  cls=type('PrivateEvidenceCommand',(CommandForm,),fields);f=cls(data if data and data.get('action')==key else None,initial={'action':key,'revision':c.revision});result.append({'key':key,'title':title,'form':f})
 return result

@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);private=Grant.objects.filter(case=c,user=request.user,action='agent.data.source',active=True).exists();cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  selected=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if not selected:from django.core.exceptions import PermissionDenied;raise PermissionDenied
  f=selected['form'];k=selected['key']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Invalid typed command.');return redirect('private_evidence',case_id=c.pk)
  v=f.cleaned_data;rev=v['revision'];a=request.user
  try:
   if k=='capture':
    from django.db import transaction
    with transaction.atomic():d.locked(a,c.pk,'agent.data.source',rev);add_evidence(a,c.pk,'agent_private_input',v['body'],v['source'])
   elif k=='project':d.project(a,c.pk,v['evidence'].pk,v['process'],v['purpose'],v['quotes'],v['predecessor'],rev)
   elif k=='policy':
    from django.db import transaction
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_readiness_policy(a,c.pk,COMPONENT,v['content'],v['evidence'].pk,v['effective_from'])
   elif k=='projection_review':d.review_projection(a,c.pk,v['projection'].pk,v['verdict'],rev)
   elif k=='send':d.reserve(a,c.pk,v['projection'].pk,v['operation_key'],rev)
   elif k=='result_review':d.review_result(a,c.pk,v['receipt'].pk,v['verdict'],v['corrected'],rev)
   elif k=='operate':w.operate(a,c.pk,v['job'].pk,'retry',rev)
   messages.success(request,'Private evidence history updated. Human review and business decisions remain separate.')
  except (ValidationError,ValueError,TypeError):messages.error(request,'Action held by source, policy, budget or current review controls.')
  return redirect('private_evidence',case_id=c.pk)
 visible=d.visible_projections(request.user,c) if private else d.Projection.objects.none()
 rows=list(visible.order_by('-pk')[:30])
 for p in rows:p.history=list(d.ProjectionReview.objects.filter(projection=p).order_by('-pk')[:10])
 response=render(request,'agents/private_evidence.html',{'case':c,'private':private,'commands':cmds,'projections':rows if private else [],'jobs':d.Job.objects.filter(projection__in=visible).order_by('-pk')[:30],'receipts':d.Receipt.objects.filter(job__projection__in=visible).order_by('-pk')[:30] if private else [],'policy':resolve(COMPONENT,c),'schema':SCHEMAS});response['Cache-Control']='no-store';return response

@login_required
def result(request,case_id,pk):
 return JsonResponse(d.inspect(request.user,case_id,pk),headers={'Cache-Control':'no-store'})

@login_required
def projection(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c,True);p=d.Projection.objects.filter(case=c,pk=pk).first()
 if not p:raise Http404
 d.source_access(request.user,p)
 value={'id':p.pk,'payload':p.payload,'sha256':p.sha256}
 if p.evidence.kind=='agent_private_ledger':
  import json
  from apps.finance.ledger_agents import binding
  r=binding(p);value['domain_source']={'lineage':r.lineage_id,'policy':r.policy_id,'packet':json.loads(p.evidence.body)}
 if p.evidence.kind=='agent_private_support':
  import json
  from apps.baas.support_agent import binding
  r=binding(p);value['domain_source']={'intake':r.intake_id,'policy':r.policy_id,'packet':json.loads(p.evidence.body)}
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
