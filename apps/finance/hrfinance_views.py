from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.db import transaction
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.hrfinance_validators import SCHEMAS
from apps.policy.hrfinance_drafts import draft_hrfinance_policy
from apps.agents.hrfinance import investigate
from apps.agents.models import AgentRun
from .hrfinance_forms import commands
from .hrfinance_models import HRFinanceNeed,HRDisclosure,HRReadSnapshot
from . import hrfinance as domain

@login_required
def workbench(request,case_id):
 case=accessible_case(request.user,case_id);require(request.user,case,'hrfinance.read')
 forms=commands(request.user,case,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
   if not f or not f.is_valid():raise ValidationError('Choose a permitted command with valid typed fields')
   if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected command fields; authority claims are not accepted')
   d=f.cleaned_data;k=d['action'];a=request.user;c=case.pk;v=d['revision'];e=d['evidence'].pk if d.get('evidence') else None
   if k=='need':domain.need(a,c,d['reference'],d['payload'],e,v)
   elif k=='contract':domain.contract(a,c,d['need'].pk,d['operation_key'],e,v)
   elif k=='authorize':domain.decide(a,c,d['contract'].pk,d['verdict'],d['operation_key'],e,v)
   elif k=='capture':
    r=domain.capture(a,c,d['contract'].pk,d['operation_key'],d['body'],v)
    if r.status=='rejected':messages.error(request,'Export rejected: '+', '.join(r.manifest['findings'])+'. No row values retained.')
   elif k=='receive':domain.receive(a,c,d['snapshot'].pk,d['operation_key'],e,v)
   elif k=='correction':domain.correction(a,c,d['snapshot'].pk,d['operation_key'],e,v)
   elif k=='respond':domain.respond(a,c,d['request_record'].pk,d['successor'].pk,d['operation_key'],e,v)
   elif k=='bind':domain.draft_basis(a,c,d['snapshot'].pk,e,v)
   elif k=='investigate':investigate(a,c,v)
   elif k=='policy':
    with transaction.atomic():domain.locked(a,c,'policy.configure',v);draft_hrfinance_policy(a,c,d['component'],d['content'],e,d['effective_from'])
   messages.success(request,'HR/Finance workflow history updated; HR source remains read-only');return redirect('hrfinance',case_id=c)
  except (ValidationError,ValueError,TypeError) as exc:
   # Never reflect a supplied private export or schema instance in an error response.
   messages.error(request,str(exc) if request.POST.get('action')!='capture' else 'Capture held: check current authority, exact contract, operation key and export schema. No source rows are shown here.')
   return redirect('hrfinance',case_id=case.pk)
 contracts=list(HRDisclosure.objects.filter(need__case=case).order_by('-pk')[:30])
 for d in contracts:
  try:domain.authorized(d);d.status='Current HR-authorised disclosure'
  except (ValidationError,PermissionDenied):d.status='Awaiting HR authority or reassessment'
  d.snapshot_status=[]
  for s in d.snapshots.defer('payload').order_by('-pk')[:20]:
   try:domain.current_snapshot(s);current=True
   except (ValidationError,PermissionDenied):current=False
   try:domain.check_snapshot_access(request.user,s);readable=True
   except (ValidationError,PermissionDenied):readable=False
   d.snapshot_status.append({'id':s.pk,'status':s.status,'current':current,'readable':readable,'retain_until':s.retain_until,'findings':s.manifest['findings']})
 response=render(request,'finance/hrfinance.html',{'case':case,'needs':HRFinanceNeed.objects.filter(case=case).order_by('-pk')[:30],'contracts':contracts,'commands':forms,'policies':[resolve(k,case) for k in SCHEMAS],'schemas':SCHEMAS,'need_schema':domain.NEED,'agents':AgentRun.objects.filter(case=case,provider='deterministic-hrfinance-v1').order_by('-pk')[:5]})
 response['Cache-Control']='no-store';return response

@login_required
def snapshot(request,case_id,snapshot_id):
 case=accessible_case(request.user,case_id);s=get_object_or_404(HRReadSnapshot.objects.defer('payload'),contract__need__case=case,pk=snapshot_id)
 try:value=domain.read_snapshot(request.user,s)
 except ValidationError:return JsonResponse({'status':'held','message':'HR authority, source freshness or retention requires reassessment'},status=409,headers={'Cache-Control':'no-store'})
 return JsonResponse({'snapshot_id':s.pk,'sha256':s.sha256,'source_authenticity':'supplied export; not native verified','data':value},headers={'Cache-Control':'no-store'})
