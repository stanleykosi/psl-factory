from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.payroll_validators import SCHEMAS
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.agents.payroll import investigate
from apps.agents.models import AgentRun
from .payroll_forms import commands
from .payroll_models import PayrollRequest,PayrollInput,PayrollRun,PayrollPublication
from . import payroll as domain

@login_required
def workbench(request,case_id):
 case=accessible_case(request.user,case_id);require(request.user,case,'payroll.read');forms=commands(request.user,case,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
   if not f or not f.is_valid():raise ValidationError('Choose a permitted command with valid typed fields')
   if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected fields; supplied authority claims are not accepted')
   d=f.cleaned_data;k=d['action'];a=request.user;c=case.pk;v=d['revision'];e=d['evidence'].pk if d.get('evidence') else None
   if k=='request':domain.request(a,c,d['reference'],d['metadata'],e,v)
   elif k=='capture':
    r=domain.capture(a,c,d['request_record'].pk,d['provider'],d['operation_key'],d['body'],v)
    if not r.metadata['accepted']:messages.error(request,'Payroll export rejected: '+', '.join(r.metadata['codes'])+'; no source values retained')
   elif k=='combine':domain.combine(a,c,d['request_record'].pk,[i.pk for i in d['inputs']],d['operation_key'],v)
   elif k=='match':domain.match(a,c,d['parent'].pk,d['hr_snapshot'].pk,d['operation_key'],v)
   elif k=='aggregate':domain.aggregate(a,c,d['parent'].pk,d['operation_key'],v)
   elif k=='review':domain.review(a,c,d['subject_kind'],d['subject_id'],d['verdict'],d['operation_key'],e,v)
   elif k=='publish':domain.publish(a,c,d['run'].pk,d['operation_key'],v)
   elif k=='receive':domain.receive_report(a,c,d['publication'].pk,v)
   elif k=='hr_correction':domain.hr_correction(a,c,d['run'].pk,d['operation_key'],e,v)
   elif k=='investigate':investigate(a,c,v)
   elif k=='policy':
    with transaction.atomic():domain.locked(a,c,'policy.configure',v);draft_payroll_policy(a,c,d['component'],d['content'],e,d['effective_from'])
   messages.success(request,'Payroll working history updated; no payment, journal or HR source edit');return redirect('payroll',case_id=c)
  except (ValidationError,ValueError,TypeError) as exc:
   messages.error(request,'Capture held: check owner authority, contract, schema and retry key; source values are never reflected.' if request.POST.get('action')=='capture' else str(exc));return redirect('payroll',case_id=case.pk)
 inputs=list(PayrollInput.objects.defer('payload').filter(request__case=case).order_by('-pk')[:50]);runs=list(PayrollRun.objects.defer('result').filter(request__case=case).order_by('-pk')[:50])
 for i in inputs:
  try:domain.access(i.request,request.user,True);i.can_read_private=True
  except (ValidationError,PermissionDenied):i.can_read_private=False
  try:domain.input_current(i);i.current=True
  except (ValidationError,PermissionDenied):i.current=False
 for r in runs:
  try:domain.access(r.request,request.user,True);r.can_read_private=True
  except (ValidationError,PermissionDenied):r.can_read_private=False
  try:domain.run_current(r);r.current=True
  except (ValidationError,PermissionDenied):r.current=False
 response=render(request,'finance/payroll.html',{'case':case,'requests':PayrollRequest.objects.filter(case=case).order_by('-pk')[:30],'inputs':inputs,'runs':runs,'publications':PayrollPublication.objects.defer('payload').filter(request__case=case).order_by('-pk')[:30],'commands':forms,'policies':[resolve(k,case) for k in SCHEMAS],'schemas':SCHEMAS,'request_schema':domain.REQUEST,'agents':AgentRun.objects.filter(case=case,provider='deterministic-payroll-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response

@login_required
def data(request,case_id,kind,pk):
 case=accessible_case(request.user,case_id)
 model={'input':PayrollInput,'run':PayrollRun,'report':PayrollPublication}.get(kind)
 if not model:return JsonResponse({'status':'unknown record type'},status=404)
 q=model.objects.defer('result' if model==PayrollRun else 'payload');get_object_or_404(q,request__case=case,pk=pk)
 try:value=domain.private_input(request.user,case.pk,pk) if kind=='input' else domain.private_run(request.user,case.pk,pk) if kind=='run' else domain.read_publication(request.user,pk)
 except ValidationError:return JsonResponse({'status':'held','reason':'Current source, HR scope, review, retention or policy needs reassessment'},status=409,headers={'Cache-Control':'no-store'})
 return JsonResponse({'kind':kind,'id':pk,'data':value},headers={'Cache-Control':'no-store'})

@login_required
def inspect(request,case_id,kind,pk):
 # Reuse the exact scoped JSON boundary; never fall back to a raw ORM payload.
 response=data(request,case_id,kind,pk)
 if response.status_code!=200:return response
 import json
 value=json.loads(response.content)['data'];case=accessible_case(request.user,case_id)
 response=render(request,'finance/payroll_inspect.html',{'case':case,'kind':kind,'record_id':pk,'value':value})
 response['Cache-Control']='no-store'
 return response
