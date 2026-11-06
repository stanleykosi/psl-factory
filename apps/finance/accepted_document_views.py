from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from django.db import transaction
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.ledger_validators import PUBLICATION,SCHEMAS
from apps.policy.ledger_drafts import draft_ledger_policy
from apps.policy.services import resolve
from apps.agents.accepted_finance import investigate,prepare
from . import accepted_documents as d

def visible(a,c):
 ids=[]
 for b in d.Binding.objects.filter(handoff__case=c):
  try:d.access(a,b)
  except PermissionDenied:continue
  ids.append(b.version_id)
 return d.Version.objects.filter(pk__in=ids)

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True));hands=[]
 for row in d.h.Handoff.objects.filter(case=c):
  try:d.h.access(a,row)
  except PermissionDenied:continue
  hands.append(row.pk)
 defs={
 'draft':('Prepare exact accepted metadata','finance.accepted.draft',{'handoff':forms.ModelChoiceField(d.h.Handoff.objects.filter(pk__in=hands)),'template':forms.ModelChoiceField(d.Template.objects.filter(case=c,definition__document_type=d.TYPE)),'audience':forms.ChoiceField(choices=[(x,x) for x in ['internal','management','client']]),'document_id':forms.IntegerField(min_value=1,required=False)}),
 'review':('Independent metadata document decision','finance.accepted.review',{'version':forms.ModelChoiceField(visible(a,c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['approve','return','reject','withdraw']]),'note':forms.CharField(max_length=2000,widget=forms.Textarea)}),
 'publish':('Reserve human-controlled metadata publication','finance.accepted.publish',{'version':forms.ModelChoiceField(visible(a,c))}),
 'operate':('Recover native publication without resetting intent or budget','document.operate',{'job':forms.ModelChoiceField(d.PublicationJob.objects.filter(publication__version__in=visible(a,c))),'operation':forms.ChoiceField(choices=[('retry','retry held'),('cancel','cancel known uncommitted')]),'reason':forms.CharField(max_length=2000,widget=forms.Textarea)}),
 'template':('Register metadata template','document.template',{'name':forms.CharField(max_length=160),'definition':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
 'policy':('Draft metadata field, audience and human authority policy','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()})}
 return [{'key':k,'title':title,'form':type('AcceptedMetadataCommand',(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants]

@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.h.readable(request.user,c);cmds=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  row=next((x for x in cmds if x['key']==request.POST.get('action')),None)
  if row is None:raise PermissionDenied
  f=row['form']
  if not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:messages.error(request,'Valid permitted typed command required');return redirect('accepted_finance',case_id=c.pk)
  v=f.cleaned_data;a=request.user;k=row['key']
  try:
   if k=='draft':prepare(a,c.pk,v['handoff'].pk,v['template'].pk,v['audience'],v['revision'],v['document_id'])
   elif k=='review':d.review(a,c.pk,v['version'].pk,v['verdict'],v['note'],v['revision'])
   elif k=='publish':d.publish(a,c.pk,v['version'].pk,v['revision'])
   elif k=='operate':d.operate(a,c.pk,v['job'].pk,v['operation'],v['reason'],v['revision'])
   else:
    with transaction.atomic():
     d.h.locked(a,c.pk,'policy.configure' if k=='policy' else 'document.template',v['revision'])
     if k=='policy':draft_ledger_policy(a,c.pk,PUBLICATION,v['content'],v['evidence'].pk,v['effective_from'])
     else:
      from apps.documents.controlled import register_template
      if not isinstance(v['definition'],dict) or v['definition'].get('document_type')!=d.TYPE:raise ValidationError('Metadata template required')
      register_template(a,c.pk,v['name'],v['definition'],v['evidence'].pk,v['revision'])
   messages.success(request,'Metadata work recorded; delivery uses the publication worker.')
  except (ValidationError,ValueError,TypeError,ConnectionError):messages.error(request,'Held by exact source, acceptance, audience or independent review controls.')
  return redirect('accepted_finance',case_id=c.pk)
 response=render(request,'finance/accepted_documents.html',{'case':c,'rows':[d.report(request.user,c.pk,x.pk) for x in visible(request.user,c).order_by('-pk')[:30]],'commands':cmds,'policy':resolve(PUBLICATION,c),'schema':SCHEMAS[PUBLICATION],'guidance':investigate(request.user,c.pk) if Grant.objects.filter(case=c,user=request.user,action='agent.document',active=True).exists() else None});response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,pk):
 accessible_case(request.user,case_id)
 try:value=d.report(request.user,case_id,pk)
 except ValidationError:raise Http404 from None
 return JsonResponse(value,headers={'Cache-Control':'no-store'})
