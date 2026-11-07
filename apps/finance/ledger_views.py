from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.http import JsonResponse
from django.db import transaction
from apps.core.views import accessible_case
from apps.policy.ledger_validators import SCHEMAS
from apps.policy.ledger_drafts import draft_ledger_policy
from apps.policy.services import resolve
from apps.agents.ledger import investigate
from apps.agents.models import AgentRun
from . import ledger as d,ledger_resolution as resolutions,quickbooks_read as qbo
from .ledger_forms import commands
from .models import LedgerLineage
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Permitted typed command required')
   v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];e=v['evidence'].pk if v.get('evidence') else None
   if k=='capture':d.capture(a,c.pk,e,v['predecessor'].pk if v['predecessor'] else None,rev)
   elif k=='verify':d.verify(a,c.pk,v['lineage'].pk,e,rev)
   elif k=='qbo_reserve':qbo.reserve(a,c.pk,v['lineage'].pk,v['binding'],rev)
   elif k=='qbo_execute':qbo.execute(a,c.pk,v['intent'],rev)
   elif k=='review':d.review(a,c.pk,v['verification'].pk,e,v['verdict'],rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   elif k=='resolution_evidence':
    from apps.core.services import add_evidence
    with transaction.atomic():d.locked(a,c.pk,'ledger.capture',rev);add_evidence(a,c.pk,v['kind'],v['body'],'supplied:ledger-resolution')
   elif k=='resolve':resolutions.propose(a,c.pk,v['selected'].pk,list(v['retired'].values_list('pk',flat=True)),list(v['members'].values_list('pk',flat=True)),v['mode'],v['reference'],v['predecessor'].pk if v['predecessor'] else None,e,v['reason'],rev)
   elif k=='resolve_review':resolutions.review(a,c.pk,v['resolution'].pk,v['verdict'],e,rev)
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_ledger_policy(a,c.pk,v['component'],v['content'],e,v['effective_from'])
   messages.success(request,'Incumbent reference history updated');return redirect('ledger',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('ledger',case_id=c.pk)
 rows=list(LedgerLineage.objects.filter(case=c).order_by('-pk')[:40])
 for w in rows:
  try:d.report(request.user,c.pk,w.pk);w.reviewed=True
  except (ValidationError,PermissionDenied):w.reviewed=False
 response=render(request,'finance/ledger.html',{'case':c,'native_reads':qbo.visible(request.user,c),'works':rows,'resolutions':resolutions.visible_packets(request.user,c),'resolution_sources':resolutions.visible_evidence(request.user,c),'commands':forms,'policies':[resolve(k,c) for k in SCHEMAS],'policy_schemas':SCHEMAS,'source_schema':d.SOURCE,'response_schema':d.RESPONSE,'agents':AgentRun.objects.filter(case=c,provider='deterministic-ledger-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c)
 try:v=d.report(request.user,c.pk,pk)
 except ValidationError:return JsonResponse({'status':'held','reason':'Current unambiguous incumbent observation and Finance review required'},status=409,headers={'Cache-Control':'no-store'})
 return JsonResponse(v,headers={'Cache-Control':'no-store'})
