"""AF09 coordination over native planning, P02 decisions and delivery sources."""
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case,event
from apps.documents.contracts import digest
from apps.pmo import planning,engagement
from apps.pmo.models import DeliverySource,ApprovalRequest,ApprovalRouteJob,ApprovalRouteReceipt,Baseline
from adapters.factory_planning import NativePlanningAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity

DEFINITION='planning/v1'
PROCESS_IDS=['P17','P21','P25','P26','P63']

@transaction.atomic
def start(actor,case_id,key,packet_id,reference,expected):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION)
    planning.readable(actor,case)
    if not isinstance(key,str) or not 1<=len(key)<=100 or not key.isascii():raise ValidationError('Bounded work identity required')
    if not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Planning work reference required')
    packet,value=planning.packet(case,packet_id)
    payload={'packet':packet.pk,'engagement':value['engagement_id'],'reference':reference}
    business_key=digest([DEFINITION,str(case.pk),value['engagement_id']])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business_key)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request['engagement']!=value['engagement_id']:raise ValidationError('IDEMPOTENCY_CONFLICT: planning intent or initiator differs')
        if old.key==key and old.request_hash!=digest(payload):raise ValidationError('IDEMPOTENCY_CONFLICT: same key has changed payload')
        return old
    work=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,business_key=business_key,
        request=payload,request_hash=digest(payload),source_head=packet)
    event(actor,case,'factory.started',work=work.pk,definition=DEFINITION)
    return work

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);planning.readable(actor,work.case)
    packet,payload=planning.packet(work.case)
    if payload['engagement_id']!=work.request['engagement']:raise ValidationError('Engagement changed; reviewed source-owned recovery is required')
    source=engagement.current_capture(work.case)
    ids={source.evidence_id}
    for key in planning.SOURCE_KINDS:
        if payload['payload'][key] is not None:ids.add(payload['payload'][key])
    records=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=ids)).order_by('pk'))
    latest={e.kind:e for e in records}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    report=planning.report(actor,work.case_id)
    # A superseded readiness artifact does not block preparing a valid successor.
    if report['status']!='source_referenced_ready':
        try:
            inputs=planning.inputs(work.case,packet,Baseline.objects.filter(case=work.case,signed__isnull=False).exists(),actor)
            report.update(status='source_referenced_ready',readiness_id=None,readiness_inputs=inputs)
        except (ValidationError,PermissionDenied):pass
    marker=Audit.objects.filter(case=work.case,action='planning.requests_opened',data__packet_id=packet.pk).order_by('-pk').first()
    request_ids=list(marker.data['requests'].values()) if marker else []
    jobs=list(ApprovalRouteJob.objects.filter(Q(request_id__in=request_ids)|Q(request__case=work.case,intent__factory_execution__work=work.pk,status__in=['pending','unknown','leased'])).order_by('pk'))
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in records],
        'source_head':work.source_head_id,'current_packet':packet.pk,'report':report,'requests':marker.data if marker else None,
        'jobs':[(j.pk,j.status,j.intent) for j in jobs],
        'routing_receipts':list(ApprovalRouteReceipt.objects.filter(job__in=jobs).values_list('pk','operation_key'))}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,observed,latest,missing,stale,tasks,jobs):
    if work.source_head_id!=observed['current_packet']:
        pending=next((j for j in jobs if j.status in ['pending','unknown','leased']),None)
        if pending:return (['ACT12'],'Reconcile the original department request before adopting changed sources') if pending.status=='unknown' else ([], 'Stop or reconcile outstanding department routing before adopting changed sources')
        return ['ACT07'],'Adopt the current native packet within the same planning engagement'
    if missing or stale:return [],'Planning source information needs correction: '+', '.join(missing+stale)
    key=digest(['ACT04',observed['sources'],work.source_head_id])
    if not Activity.objects.filter(work=work,key=key,status='succeeded').exists():return ['ACT04'],'Investigate planning evidence and dependencies'
    if observed['requests'] is None:return ['ACT10'],'Open separate department-owned scope and estimate decisions'
    routed={j.request_id for j in jobs}
    if set(observed['requests']['requests'].values())-routed:return ['ACT10'],'Route each exact request to its current department owner'
    if any(j.status=='held' for j in jobs):return [],'Department request routing needs controlled operator recovery'
    pending=next((j for j in jobs if j.status in ['pending','unknown','leased']),None)
    if pending:
        if pending.intent.get('factory_execution',{}).get('work')!=work.pk:return [],'An existing native request needs its own authorised operator; the agent cannot take over its dispatch'
        if pending.status=='leased':return [],'The native department routing worker owns the current attempt'
        return ['ACT12' if pending.status=='unknown' else 'ACT11'],'Reconcile the original department request' if pending.status=='unknown' else 'Deliver the current department request'
    report=observed['report']
    if report['status']!='source_referenced_ready':return [],report.get('finding','Waiting for source-owned planning decisions')
    if not report.get('readiness_id'):return ['ACT08'],'Prepare current planning readiness evidence'
    ready=report['readiness_id']
    source=DeliverySource.objects.filter(dossier__case=work.case,kind='scope_baseline',evidence_id=ready).first()
    if not source:return ['ACT11'],'Hand current planning readiness to delivery'
    return ['ACT13'],'Verify the current planning artifact and internal handoff'

def act(work,choice,value,latest,missing,tasks,jobs):
    adapter=NativePlanningAdapter();kind=choice['activity']
    case=planning.locked(work.execution_actor,work.case_id,'read')
    from .factory import access
    access(work.execution_actor,case,'factory.execute',DEFINITION)
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: planning sources changed before the command')
    if kind!='ACT07':planning.packet(case,work.source_head_id)
    if kind=='ACT07':
        packet,payload=planning.packet(work.case)
        if payload['engagement_id']!=work.request['engagement'] or packet.version<=work.source_head.version:raise ValidationError('Same-engagement forward packet successor required')
        previous=work.source_head_id;work.source_head=packet
        event(work.execution_actor,work.case,'factory.source_adopted',work=work.pk,previous=previous,current=packet.pk)
        return {'previous_packet':previous,'packet':packet.pk,'budget_reset':False}
    if kind=='ACT04':return {'investigation':adapter.investigate(work)}
    if kind=='ACT10':
        from apps.pmo import approval_routing
        marker=Audit.objects.filter(case=work.case,action='planning.requests_opened',data__packet_id=work.source_head_id).order_by('-pk').first()
        pair=adapter.route(work)
        if marker is None:return {'department_requests':pair,'decisions_created':False}
        from apps.policy.services import active_component,reference_values
        from apps.policy.approval_validators import ROUTES,CONTRACTS
        try:
            routes=reference_values(active_component(ROUTES,work.case))[0]
            for pk in pair['requests'].values():
                request=ApprovalRequest.objects.get(pk=pk,case=work.case)
                if not any(r['kind']==request.kind for r in routes['routes']):raise ValidationError('Missing exact department owner route')
        except ValidationError as exc:raise ValidationError('owner_needed: Configure current department-owned routes before delivery; recorded requests remain available') from exc
        try:active_component(CONTRACTS,work.case)
        except ValidationError as exc:raise ValidationError('configuration_needed: Configure the department source evidence contracts before delivery') from exc
        reserved=[approval_routing.reserve(work.execution_actor,work.case_id,pk,factory_work_id=work.pk).pk for pk in pair['requests'].values()]
        return {'department_requests':pair,'routing_jobs':reserved,'decisions_created':False}
    if kind in ['ACT11','ACT12']:
        pending=next((j for j in jobs if j.status in ['pending','unknown']),None)
        if pending:return {'approval_job':pending.pk,'approval_granted':False}
    if kind=='ACT08':return {'readiness':adapter.prepare(work).pk,'native_verified':False}
    ready=planning.latest(work.case,'ready')
    if not ready:raise ValidationError('Current native planning readiness required')
    if kind=='ACT11':
        source=adapter.handoff(work,ready)
        return {'delivery_source':source.pk,'dossier':source.dossier_id,'native_verified':False}
    if kind=='ACT13':
        source=DeliverySource.objects.filter(dossier__case=work.case,kind='scope_baseline',evidence=ready).first()
        if not source:raise ValidationError('Native delivery handoff required')
        result=adapter.verify(work,ready,source);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered planning command')

def operator_projection(actor,work):
    """Actual department ownership; no agent-produced nominations or decision task copies."""
    from django.contrib.auth import get_user_model
    from apps.pmo import approvals
    from .factory import profile
    from .factory_views import permitted
    planning.readable(actor,work.case)
    marker=Audit.objects.filter(case=work.case,action='planning.requests_opened',data__packet_id=work.source_head_id).order_by('-pk').first()
    request_ids=list(marker.data['requests'].values()) if marker else []
    jobs=list(ApprovalRouteJob.objects.filter(Q(request_id__in=request_ids)|Q(request__case=work.case,intent__factory_execution__work=work.pk,status__in=['pending','unknown','leased'])).order_by('pk'))
    owners=[];needs_me=False;department_wait=False;requests=[]
    for request in ApprovalRequest.objects.filter(case=work.case,pk__in=request_ids):
        try:
            view=approvals.visibility(actor,request);requests.append(view)
            if view['status']=='referenced_accepted':continue
            _,_,route,_,_=approvals.rules(work.case,request.kind)
            owner=get_user_model().objects.get(pk=route['owner_id'])
            approvals.owner_authority(owner,work.case,route,'approval.verify')
            from apps.identity.services import require
            require(owner,work.case,'approval.source.read:'+route['system'])
            if view['status']=='unavailable' and actor.pk!=owner.pk:continue
            owners.append(owner.get_full_name() or owner.username);department_wait=True
            needs_me=needs_me or actor.pk==owner.pk
        except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):continue
    result={'department_wait':department_wait,'department_requests':requests,'jobs':jobs}
    if work.status=='verified':
        try:verified_output(work)
        except (ValidationError,PermissionDenied):
            result.update(state='Prior handoff needs recheck',blocker='Planning sources, criteria or source authority changed after the recorded handoff.',next_action='Review the changed planning evidence before continuing',readiness_changed=True,can_reassess=permitted(actor,work,'factory.manage'))
            if permitted(actor,work,'factory.manage'):result['needs_me']=True
        return result
    if work.status=='cancelled':return result
    if needs_me:result.update(needs_me=True,next_action='Review the department source evidence and record your own observation')
    if owners and (work.status=='waiting' or needs_me):result['owner']=', '.join(dict.fromkeys(owners))
    if department_wait and work.status in ['waiting','ready']:result['blocker']='Awaiting current department source observations.'
    unknown=any(j.status=='unknown' for j in jobs)
    if unknown:
        result.update(state='Request delivery uncertain',next_action='Reconcile the original department request',can_advance=False)
        try:
            from .factory_execution import can_control
            profile(work,recovery=True);result['can_reconcile']=can_control(actor,work) and not (work.lease_until and work.lease_until>timezone.now())
        except (ValidationError,PermissionDenied):result['can_reconcile']=False
    return result

def verified_output(work):
    from .models import FactoryAttempt
    record=FactoryAttempt.objects.filter(activity__work=work,activity__kind='ACT13',phase='observed').order_by('-pk').first()
    if not record:raise ValidationError('No recorded planning postcondition')
    result=record.result
    ready=Evidence.objects.filter(case=work.case,pk=result.get('readiness'),kind='planning_readiness').first()
    source=DeliverySource.objects.filter(dossier__case=work.case,pk=result.get('delivery_source')).first()
    if not ready or not source:raise ValidationError('Exact recorded planning output required')
    return NativePlanningAdapter().verify(work,ready,source)

def owner_panels(actor,work):
    """Expose only the current owner's exact native source and matching read evidence."""
    from apps.pmo import approvals
    from adapters.approvals import SuppliedApprovalReadAdapter
    from apps.identity.services import require
    planning.readable(actor,work.case)
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:return []
    try:packet,_=planning.packet(work.case,work.source_head_id)
    except (ValidationError,PermissionDenied):return []
    marker=Audit.objects.filter(case=work.case,action='planning.requests_opened',data__packet_id=packet.pk).order_by('-pk').first()
    if not marker:return []
    panels=[]
    for request in ApprovalRequest.objects.filter(case=work.case,pk__in=marker.data['requests'].values()):
        source=request.source_receipts.order_by('-pk').first()
        if not source:continue
        try:
            _,route,_=approvals.context(source)
            approvals.owner_authority(actor,work.case,route,'approval.verify');require(actor,work.case,'approval.source.read:'+source.system)
            old=source.observations.order_by('-pk').first()
            if old:
                try:approvals.current_observation(old);continue
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):continue
        candidates=[]
        for e in Evidence.objects.filter(case=work.case,kind='approval_observation').order_by('-pk')[:100]:
            try:
                value=SuppliedApprovalReadAdapter().read(e,approvals.READ,'approval_observation')
                if (value['receipt_id'],value['system'],value['external_ref'],value['source_version'])==(source.pk,source.system,source.external_ref,source.source_version):candidates.append(e)
            except ValidationError:continue
        panels.append({'request':request,'receipt':source,'owner_role':route['owner_role'],'evidence':candidates})
    return panels

@transaction.atomic
def observe_department(actor,work_id,expected,request_id,receipt_id,evidence_id):
    from . import factory
    from apps.pmo import approvals
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
    case=planning.locked(actor,work.case_id,'read')
    factory.access(actor,case,'factory.read',DEFINITION)
    if work.revision!=expected:raise ValidationError('STALE_VERSION: refresh the exact planning work')
    panel=next((p for p in owner_panels(actor,work) if p['request'].pk==request_id and p['receipt'].pk==receipt_id),None)
    if not panel or evidence_id not in [e.pk for e in panel['evidence']]:raise PermissionDenied('Current department owner, source and exact matching read evidence required')
    # The native observation is the only human record. No factory approval is created.
    result=approvals.observe(actor,work.case_id,receipt_id,evidence_id)
    if work.status=='waiting':work.status='ready';work.finding=''
    work.revision+=1;work.save()
    event(actor,work.case,'factory.owner_observed',work=work.pk,observation=result.pk,approval_granted=False)
    return result

def attempt_projection(attempt):
    """Readable work history without indirect department-source disclosure."""
    if attempt.phase=='failed':return {'status':'held','next_action':'Review current planning sources and authority'}
    result=attempt.result
    # Full native investigations remain durable. Detail readers receive references and
    # scoped findings; source bodies/observations use their own native readers.
    keys={'child','activity','packet','previous_packet','readiness','delivery_source','dossier','verified','verification_scope','native_verified','environment','budget_reset','approval_granted'}
    out={key:value for key,value in result.items() if key in keys}
    if 'investigation' in result:
        investigation=result['investigation']
        out['investigation']={key:investigation[key] for key in ['capability','provider','status','native_verified','unknown_source_fields','unresolved_question_keys'] if key in investigation}
    if 'department_requests' in result:out['department_requests']='Separate native requests recorded; no approval granted'
    if 'approval_job' in result:out['request_delivery']='Selected native receipt worker requested; inspect its observed status'
    return out

@transaction.atomic
def reassess(actor,work_id,expected,reason):
    from . import factory
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
    factory.access(actor,work.case,'factory.manage',DEFINITION)
    if work.revision!=expected or work.status!='verified' or work.cancel_requested:raise ValidationError('STALE_VERSION: select a previously verified planning handoff')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: wait for the current worker')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed reassessment in at most2000 characters')
    try:verified_output(work)
    except (ValidationError,PermissionDenied):pass
    else:raise ValidationError('The recorded planning output remains current; no reassessment is needed')
    previous=work.source_head_id
    work.status='ready';work.finding='';work.revision+=1;work.save()
    event(actor,work.case,'factory.reassessment',work=work.pk,previous_packet=previous,reason=reason,spent=work.budget_used)
    return work

def reconcile(actor,work_id,expected):
    from . import factory
    with transaction.atomic():
        work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
        factory.access(actor,work.case,'factory.execute',DEFINITION)
        from .factory_execution import require_control
        require_control(actor,work)
        if work.revision!=expected:raise ValidationError('STALE_VERSION: refresh this work')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
        factory.profile(work,recovery=True)
        if work.cancel_requested:raise ValidationError('Cancelled routing needs its native operator reconciliation')
        job=ApprovalRouteJob.objects.filter(request__case=work.case,intent__factory_execution__work=work.pk,status='unknown').order_by('pk').first()
        if not job:raise ValidationError('No uncertain native department request to reconcile')
        event(actor,work.case,'factory.reconciliation_requested',work=work.pk,scope='department_request')
    from apps.pmo.approval_routing import run_once
    run_once(case_id=work.case_id,job_id=job.pk,lookup_only=True)
    with transaction.atomic():
        work=Work.objects.select_for_update().get(pk=work_id);job.refresh_from_db()
        work.status='waiting_effect' if job.status=='unknown' else 'blocked' if job.status=='held' else 'ready'
        work.finding=job.error if job.status in ['unknown','held'] else '';work.observation_hash='';work.revision+=1;work.save()
    return work
