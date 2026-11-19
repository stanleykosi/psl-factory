from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import resolve,active_component,reference_values
from apps.policy.payroll_validators import SCHEMAS,REPORT
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.agents.payroll import investigate
from apps.agents.models import AgentRun
from .payroll_forms import commands
from .payroll_models import PayrollRequest,PayrollInput,PayrollRun,PayrollPublication
from . import payroll as domain

SECTIONS = {
 'inputs': ('Payroll inputs', {'request','capture','combine','review'}, {'combine'}),
 'matching': ('Payroll matching', {'match','review','investigate'}, {'combine','match'}),
 'corrections': ('Payroll corrections', {'hr_correction','investigate'}, {'match'}),
}


def aggregate_panel(actor,request_record):
 """Recipient-only matching view: native reviewed totals, never employee rows."""
 try:
  require(actor,request_record.case,'payroll.report.read')
  rules=reference_values(active_component(REPORT,request_record.case))[0]
  if actor.pk not in rules['recipient_ids']:return None
 except (PermissionDenied,ValidationError):return None
 publication=PayrollPublication.objects.defer('payload').filter(request=request_record).order_by('-version').first()
 if publication is None:return {'status':'waiting'}
 try:
  value=domain.read_publication(actor,publication.pk)
  return {'status':'current','publication':publication.pk,'value':value}
 except PermissionDenied:return None
 except ValidationError:return {'status':'held'}

@login_required
@require_http_methods(['GET','HEAD','POST'])
def workbench(request,case_id,focus=None):
 case=accessible_case(request.user,case_id);require(request.user,case,'payroll.read')
 forms=commands(request.user,case,request.POST if request.method=='POST' else None, request.FILES)
 title='Restricted payroll run'
 if focus:
  title, actions, kinds=SECTIONS[focus]
  forms=[entry for entry in forms if entry['action'] in actions]
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
   if not f or not f.is_valid():raise ValidationError('Choose a permitted command with valid typed fields')
   if (set(request.POST)|set(request.FILES))-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected fields; supplied authority claims are not accepted')
   d=f.cleaned_data;k=d['action'];a=request.user;c=case.pk;v=d['revision'];e=d['evidence'].pk if d.get('evidence') else None
   if k=='review' and focus:
    scoped=PayrollRun.objects.filter(request__case=case,kind__in=kinds,pk=d['subject_id'])
    if not (focus=='inputs' and d['subject_kind']=='input' or d['subject_kind']=='run' and scoped.exists()):
     raise ValidationError('Select a review for this payroll screen.')
   if k=='request':domain.request(a,c,d['reference'],d['metadata'],e,v)
   elif k=='capture':
    r=domain.capture(a,c,d['request_record'].pk,d['provider'],d['operation_key'],d['body'],v,spreadsheet=d.get('spreadsheet'))
    if not r.metadata['accepted']:
     from .payroll_working import rejection_notice
     messages.error(request,rejection_notice(r.metadata['codes']))
     return redirect(request.path)
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
   messages.success(request,'Payroll history updated.');return redirect(request.path)
  except (ValidationError,ValueError,TypeError) as exc:
   messages.error(request,'The upload could not be accepted. Check the export format, source layout and extraction details for this provider and period.' if request.POST.get('action')=='capture' else str(exc));return redirect(request.path)
 inputs=list(PayrollInput.objects.defer('payload').select_related('request__case').filter(request__case=case).order_by('-pk')[:50]) if focus in {None,'inputs'} else []
 run_query=PayrollRun.objects.defer('result').select_related('request__case').filter(request__case=case)
 if focus:run_query=run_query.filter(kind__in=kinds)
 runs=list(run_query.order_by('-pk')[:50])
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
 navigation=[(key,label,reverse('design_payroll_'+key,args=[case.pk])) for key,(label,_,_) in SECTIONS.items()]
 working=None;selected_run=None
 if focus in ['inputs','matching'] and runs:
  selected=request.GET.get('worksheet','')
  selected_run=next((row for row in runs if str(row.pk)==selected),None) if selected else runs[0]
  if selected_run:
   try:
    from .payroll_working import rows
    value=domain.private_run(request.user,case.pk,selected_run.pk)
    working=rows(value,selected_run.kind,page=request.GET.get('working_page'),status=request.GET.get('working_status','all'))
    working.update(record_id=selected_run.pk,selectable_record=True,
                   currency=selected_run.request.metadata['currency'],period=selected_run.request.metadata['period'])
   except (PermissionDenied,ValidationError):pass
 recipient_report=aggregate_panel(request.user,selected_run.request) if focus=='matching' and selected_run and not selected_run.can_read_private else None
 actions=set(Grant.objects.filter(case=case,user=request.user,active=True).values_list('action',flat=True))
 response=render(request,'finance/payroll.html',{'case':case,'title':title,'focus':focus,'navigation':navigation,
  'requests':PayrollRequest.objects.filter(case=case).order_by('-pk')[:30],'inputs':inputs,'runs':runs,
  'publications':PayrollPublication.objects.defer('payload').filter(request__case=case).order_by('-pk')[:30] if not focus else [],
  'commands':forms,'policies':[resolve(k,case) for k in SCHEMAS],'schemas':SCHEMAS,'request_schema':domain.REQUEST,
  'agents':AgentRun.objects.filter(case=case,provider='deterministic-payroll-v1').order_by('-pk')[:5],
  'working':working,'selected_working_run':selected_run,'recipient_report':recipient_report,
  'can_configure_rows':{'policy.read','policy.configure'}<=actions,
  'can_hr_view':'hrfinance.read' in actions,'can_finance_view':'finance.read' in actions,
  'can_policy_view':'policy.read' in actions,'can_bu_view':'bu.read' in actions})
 response['Cache-Control']='no-store';return response

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
 value=json.loads(response.content)['data'];case=accessible_case(request.user,case_id);working=None
 if kind!='report':
  from .payroll_working import rows
  model=PayrollInput if kind=='input' else PayrollRun
  subject=model.objects.filter(pk=pk,request__case=case).values('request__metadata',*(['kind'] if kind=='run' else [])).get()
  try:working=rows(value,'input' if kind=='input' else subject['kind'],
                   page=request.GET.get('working_page'),status=request.GET.get('working_status','all'))
  except ValidationError:return JsonResponse({'status':'held','reason':'Choose a bounded payroll row view.'},status=400)
  working.update(record_id=pk,currency=subject['request__metadata']['currency'],period=subject['request__metadata']['period'])
 controls={key:item for key,item in value.items() if key not in ['rows','issues']}
 response=render(request,'finance/payroll_inspect.html',{'case':case,'kind':kind,'record_id':pk,'value':value,
                 'working':working,'working_controls':controls})
 response['Cache-Control']='no-store'
 return response
