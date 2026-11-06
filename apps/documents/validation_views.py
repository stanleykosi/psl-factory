from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.validation_validators import SCHEMAS,PRIVATE_SCHEMA,PRIVATE_VALUE,NATIVE_SCHEMA,NATIVE_VALUE
from apps.policy.validation_drafts import draft_validation_policy
from apps.policy.services import resolve
from apps.agents.validation import investigate
from apps.agents.models import AgentRun
from .validation_forms import commands
from .validation_models import DiscoverySource,ValidationExample,ValidationPackage,ValidationReview,ValidationReplay,ValidationFollowup
from . import validation as domain

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'validation.read')
    forms=commands(case,request.POST if request.method=='POST' else None,request.user)
    from apps.identity.models import Grant
    actions=set(Grant.objects.filter(case=case,user=request.user,active=True).values_list('action',flat=True))
    permissions={'source':['validation.source.capture'],'pack':['validation.source.capture'],'example':['validation.example.capture'],'package':['validation.package.prepare'],'review':['validation.review','validation.accept'],'replay':['validation.replay.record'],'native_replay':['validation.replay.record'],'native_subject':['validation.example.capture','validation.review'],'followup':['validation.followup'],'investigate':['agent.validation'],'policy':['policy.configure']}
    forms=[f for f in forms if actions.intersection(permissions[f['action']])]
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
            if not f or not f.is_valid():raise ValidationError(f.errors.as_text() if f else 'Choose an evidence validation action')
            if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected fields cannot grant owner or acceptance authority')
            d=f.cleaned_data;a=request.user;c=case.pk;v=d['revision'];key=d['action']
            if key=='source':domain.capture_source(a,c,d['reference'],d['evidence'].pk,d['metadata'],v)
            elif key=='pack':domain.import_pack(a,c,d['path'],d['reference'],d['metadata'],v)
            elif key=='example':domain.capture_example(a,c,d['reference'],d['process_ids'],d['scenario'],d['expected_output'],d['evidence'].pk,v)
            elif key=='package':domain.prepare_package(a,c,d['reference'],d['payload'],d['evidence'].pk,v)
            elif key=='review':domain.review(a,c,d['package'].pk,d['kind'],d['verdict'],d['operation_key'],d['evidence'].pk,d['reason'],v)
            elif key=='replay':domain.record_replay(a,c,d['package'].pk,d['evidence'].pk,d['operation_key'],v)
            elif key=='native_subject':
                from adapters.native_subjects import planned
                if v!=case.revision:raise ValidationError('Refresh the source selection before preparing its fingerprint')
                value=planned(a,case,d['family'],d['source_id'],d['reference'],d['operation'],d['related_id'],d['effect_key'])
                messages.info(request,'Planned subject fingerprint: '+value['subject_sha256']+'. Choose expected state and receipt outcome independently; no work was executed.')
                return redirect('validation',case_id=c)
            elif key=='native_replay':
                from .native_validation import record
                record(a,c,d['package'].pk,d['example_id'],d['family'],d['job_id'],d['evidence'].pk,d['operation_key'],v)
            elif key=='followup':domain.followup(a,c,d['package'].pk,d['gap_key'],d['owner'].pk,d['due_at'],d['evidence'].pk,d['reason'],v)
            elif key=='investigate':investigate(a,c,v)
            elif key=='policy':
                with transaction.atomic():lock_case(a,c,'policy.configure',v);draft_validation_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'Evidence validation history updated; no policy activated, procedure published or deployment authorised');return redirect('validation',case_id=c)
        except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    from apps.finance.acceptance import visible_packages
    visible=visible_packages(request.user,case)
    packages=list(visible.order_by('-pk')[:30])
    for p in packages:p.position=domain.position(p,request.user)
    response=render(request,'documents/validation.html',{'case':case,'commands':forms,'sources':DiscoverySource.objects.filter(case=case).select_related('evidence').order_by('-pk')[:60],'examples':ValidationExample.objects.filter(case=case).order_by('-pk')[:60],'packages':packages,'reviews':ValidationReview.objects.filter(package__in=visible).select_related('actor').order_by('-pk')[:50],'replays':ValidationReplay.objects.filter(package__in=visible).order_by('-pk')[:50],'followups':ValidationFollowup.objects.filter(package__in=visible).select_related('action__current').order_by('-pk')[:50],'policies':[resolve(k,case) for k in SCHEMAS],'schemas':{'source':domain.SOURCE,'package':domain.PACKAGE,'policies':{k:v[1] for k,v in SCHEMAS.items()},'private_readiness_acceptance':{PRIVATE_SCHEMA:PRIVATE_VALUE},'native_execution_acceptance':{NATIVE_SCHEMA:NATIVE_VALUE}},'agents':AgentRun.objects.filter(case=case,provider='deterministic-validation-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response

@login_required
def export(request,case_id,review_id):
    from adapters.validation_evidence import LocalAcceptanceReportAdapter
    return JsonResponse(LocalAcceptanceReportAdapter().read(request.user,case_id,review_id),headers={'Cache-Control':'no-store'})
