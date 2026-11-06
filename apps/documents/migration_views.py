from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.migration_validators import COMPONENT,SCHEMAS
from apps.policy.migration_drafts import draft_migration_policy
from apps.agents.migration import investigate
from apps.agents.models import AgentRun
from .migration_forms import commands
from .migration_models import MigrationPlan,MigrationProof,MigrationAssessment,MigrationReadinessReview,MigrationAF13Binding
from . import migration_readiness as d
@login_required
def workbench(request,case_id):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
   if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required')
   v=f.cleaned_data;k=v['action'];a=request.user;rev=v['revision'];e=v['evidence'].pk if v.get('evidence') else None
   if k=='plan':d.capture_plan(a,c.pk,v['reference'],v['payload'],e,v['package'].pk if v['package'] else None,rev,v['predecessor'])
   elif k=='proof':d.capture_proof(a,c.pk,v['plan'].pk,e,rev)
   elif k=='inventory':d.observe_inventory(a,c.pk,v['plan'].pk,rev)
   elif k=='assess':d.assess(a,c.pk,v['plan'].pk,rev)
   elif k=='review':d.review(a,c.pk,v['assessment'].pk,v['purpose'],v['verdict'],v['operation_key'],e,v['reason'],rev)
   elif k=='bind':d.bind(a,c.pk,v['assessment'].pk,rev)
   elif k=='investigate':investigate(a,c.pk,rev)
   elif k=='policy':
    with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_migration_policy(a,c.pk,COMPONENT,v['content'],e,v['effective_from'])
   messages.success(request,'Migration evidence/readiness history updated; no migration, restore or deployment executed');return redirect('migration_readiness',case_id=c.pk)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));return redirect('migration_readiness',case_id=c.pk)
 rows=[]
 for r in MigrationAssessment.objects.filter(plan__case=c).order_by('-pk')[:25]:rows.append({'assessment':r,'report':d.report(request.user,c.pk,r.pk)})
 response=render(request,'documents/migration.html',{'case':c,'commands':forms,'policy':resolve(COMPONENT,c),'schemas':{'plan':d.PLAN,'proof':d.PROOF,'policy':SCHEMAS[COMPONENT][1]},'plans':MigrationPlan.objects.filter(case=c).order_by('-pk')[:40],'assessments':rows,'reviews':MigrationReadinessReview.objects.filter(assessment__plan__case=c).order_by('-pk')[:40],'bindings':MigrationAF13Binding.objects.filter(package__case=c).order_by('-pk')[:30],'agents':AgentRun.objects.filter(case=c,actor=request.user,provider='deterministic-migration-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response
@login_required
def report(request,case_id,pk):
 c=accessible_case(request.user,case_id);return JsonResponse(d.report(request.user,c.pk,pk),headers={'Cache-Control':'no-store'})
@login_required
def evidence(request,case_id,pk):
 c=accessible_case(request.user,case_id);d.readable(request.user,c);require(request.user,c,'migration.evidence.read');p=MigrationPlan.objects.filter(case=c,pk=pk).first()
 if not p:raise Http404
 return JsonResponse({'plan':p.pk,'proofs':list(MigrationProof.objects.filter(plan=p).order_by('-pk').values('id','kind','payload','sha256','actor_id','created_at')),'native_execution_verified':False},headers={'Cache-Control':'no-store'})
