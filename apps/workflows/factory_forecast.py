"""Forecast factory connection. Native Finance owns money, reviews and priorities."""
import hashlib
import json
from datetime import timedelta
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import lock_case, add_evidence, event
from apps.identity.services import require
from apps.documents.contracts import digest
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.finance import forecast, forecast_documents
from apps.finance.models import ForecastRun, ForecastBinding
from .models import FactoryWork as Work, FactoryActivity as Activity, FactoryAttempt as Attempt
from . import factory_forecast_sources as sources
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION = 'finance-forecast/v1'
KIND = 'agent_private_forecast_intake'


def finding(exc):
    return '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)


def source(work, actor=None, current=True):
    actor = actor or work.actor
    e = work.source_head
    if not e or e.case_id != work.case_id or e.kind != KIND or e.sha256 != hashlib.sha256(e.body.encode()).hexdigest():
        raise ValidationError('Exact forecast intake required')
    try:
        value = json.loads(e.body)
    except (TypeError, ValueError):
        raise ValidationError('Typed forecast intake required') from None
    audit = Audit.objects.filter(case=work.case, actor_id=e.created_by_id, action__in=['factory.forecast_intake', 'factory.forecast_source'], data={'evidence_id':e.pk, 'sha256':e.sha256}).first()
    scenario, rows = sources.selection(actor, work.case, value, current=current)
    if not audit or scenario.reference != work.request['scenario_reference']:
        raise ValidationError('Exact native scenario intake provenance required')
    if current:
        for action in ['case.read', 'finance.read', 'evidence.add', 'factory.start' if audit.action == 'factory.forecast_intake' else 'factory.manage']:
            require(e.created_by, work.case, action)
    return scenario, value


def capture(actor, case, value, action):
    e = add_evidence(actor, case.pk, KIND, json.dumps(value, sort_keys=True), 'psl:'+sources.PROTOCOL)
    event(actor, case, action, evidence_id=e.pk, sha256=e.sha256)
    return e


@transaction.atomic
def start(actor, case_id, key, value, reference, expected=None):
    from .factory import access
    case = lock_case(actor, case_id, 'factory.start', expected)
    access(actor, case, 'factory.start', DEFINITION)
    require(actor, case, 'evidence.add')
    scenario, rows = sources.selection(actor, case, value)
    if not isinstance(key, str) or not key.isascii() or not 1 <= len(key) <= 100 or not isinstance(reference, str) or not reference.strip() or len(reference) > 160:
        raise ValidationError('Bounded work identity and description required')
    payload = {'scenario_reference':scenario.reference, 'reference':reference}
    sha = digest(payload)
    business = digest([str(case.pk), DEFINITION, scenario.reference])
    old = Work.objects.filter(case=case).filter(Q(key=key) | Q(definition=DEFINITION, business_key=business)).first()
    if old:
        if old.actor_id != actor.pk or old.definition != DEFINITION or old.key == key and old.request_hash != sha:
            raise ValidationError('IDEMPOTENCY_CONFLICT: changed forecast intent')
        _, previous = source(old, actor)
        if previous != value:
            raise ValidationError('Correct the exact source selection in the existing forecast work')
        return old
    w = Work.objects.create(case=case, actor=actor, key=key, definition=DEFINITION, request=payload, request_hash=sha, business_key=business, source_head=capture(actor, case, value, 'factory.forecast_intake'))
    event(actor, case, 'factory.started', work=w.pk, definition=DEFINITION)
    return w


def observed(work, field):
    return Attempt.objects.filter(activity__work=work, phase='observed', result__head=work.source_head_id, **{'result__has_key':field}).order_by('-pk').values_list('result__'+field, flat=True).first()


def calculation(work, actor=None):
    _, value = source(work, actor)
    pk = observed(work, 'forecast_run')
    return sources.selected_run(actor or work.execution_actor, work.case, value, pk, current=False) if pk else None


def document(work):
    return ForecastBinding.objects.select_related('version__document', 'version__template').filter(version_id=observed(work, 'document_version'), run__case=work.case).first()


def principal(work, value, name, *, calculation_only=False):
    from django.contrib.auth import get_user_model
    u = get_user_model().objects.filter(pk=value[name], is_active=True).first()
    if not u:
        raise ValidationError('owner_needed: Configure the forecast '+name.replace('_id', ''))
    actions = ['case.read', 'finance.read', 'factory.execute'] + (['finance.forecast.calculate'] + ([] if calculation_only else ['finance.publish', 'document.draft']) if name == 'preparer_id' else ['document.publish'])
    try:
        for action in actions:
            require(u, work.case, action)
    except PermissionDenied:
        raise ValidationError('owner_needed: Forecast principal lacks current native permissions') from None
    return u


def report(work, actor=None):
    _, value = source(work, actor)
    r = calculation(work, actor)
    status = {'stage':'calculate', 'run':r.pk if r else None, 'finding':''}
    if not r:
        return status
    try:
        status['stage'] = 'rework'
        forecast.ensure_current(r)
        status['stage'] = 'review'
        forecast.approved(r)
        status['stage'] = 'publication'
        verify(work, actor)
        status['stage'] = 'complete'
    except (ValidationError, PermissionDenied) as exc:
        status['finding'] = finding(exc)
    return status


def snapshot(work, value, reader=None):
    from .factory import access
    actor = reader or work.execution_actor
    access(actor, work.case, 'factory.read' if reader is not None else 'factory.execute', DEFINITION)
    scenario, selected = source(work, actor)
    _, rows = sources.selection(actor, work.case, selected)
    latest = {KIND:work.source_head}
    for e in rows:
        if e.kind not in latest or latest[e.kind].version < e.version:
            latest[e.kind] = e
    missing = [k for k in value['required_evidence_kinds'] if k not in latest]
    cutoff = timezone.now()-timedelta(seconds=value['max_age_seconds'])
    stale = [k for k in value['required_evidence_kinds'] if any(e.kind == k and e.created_at < cutoff for e in rows)]
    native = report(work, actor)
    jobs = list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    state = {'case_revision':work.case.revision, 'profile':work.policy_id, 'sources':[(e.pk, e.sha256) for e in rows]+[(work.source_head_id,work.source_head.sha256)], 'native':native, 'checks':{'selection':digest(selected)}, 'jobs':[(j.pk,j.status) for j in jobs]}
    state['hash'] = digest(state)
    state['work_revision'] = work.revision
    return state, latest, missing, stale, [], jobs


def eligible(work, value, state, latest, missing, stale, tasks, jobs):
    job = pending_job(jobs)
    if job:
        return ['ACT11' if job.status == 'pending' else 'ACT12'], 'Deliver or reconcile the original aggregate forecast report'
    if any(j.status in ['held','leased'] for j in jobs):
        return [], 'Resolve the original controlled delivery before changing sources'
    if not Activity.objects.filter(work=work, key=investigation_key(work,state), status='succeeded').exists():
        return ['ACT04'], 'Investigate selected assumptions, openings, coverage and calculation pins'
    if missing or stale:
        return [], 'Required forecast evidence missing or stale: '+', '.join(missing+stale)
    stage = state['native']['stage']
    if stage == 'calculate':
        return ['ACT08'], 'Calculate the exact scenario using native Finance rules'
    if stage == 'rework':
        return [], 'Native calculation changed; explicitly correct the same source selection or select a revised scenario before recalculation'
    if stage == 'review':
        return [], 'Await native readiness and exact human forecast review: '+state['native']['finding']
    if stage == 'complete':
        return ['ACT13'], 'Verify reviewed forecast and every aggregate recipient receipt'
    binding = document(work)
    return (['ACT09'], 'Prepare the reviewed aggregate forecast') if not binding else (['ACT11'], 'Reserve current reviewed aggregate report delivery')


def act(work, choice, value, latest, missing, tasks, jobs):
    from .factory import access
    case = lock_case(work.execution_actor, work.case_id, 'factory.execute')
    access(work.execution_actor, case, 'factory.execute', DEFINITION)
    from apps.identity.models import Grant
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision != work.case.revision:
        raise ValidationError('STALE_VERSION: forecast sources changed')
    _, selected = source(work, work.execution_actor)
    kind = choice['activity']
    r = calculation(work)
    if kind == 'ACT04':
        return {'head':work.source_head_id, 'investigation':sources.investigation(work.execution_actor, case, selected, r.pk if r else None)}
    if kind == 'ACT08':
        u = principal(work, value, 'preparer_id', calculation_only=True)
        r = sources.prepare(u, case.pk, selected, case.revision)
        return {'head':work.source_head_id, 'forecast_run':r.pk}
    if kind == 'ACT09':
        if not r:
            raise ValidationError('Calculate this exact selected scenario first')
        u = principal(work, value, 'preparer_id')
        v = forecast_documents.draft(u, case.pk, r.pk, selected['template_id'], selected['audience'], case.revision)
        return {'head':work.source_head_id, 'document_version':v.pk, 'forecast_run':r.pk}
    if kind in ['ACT11','ACT12']:
        job = pending_job(jobs)
        if job:
            return {'head':work.source_head_id, 'publication_job':job.pk}
        if kind == 'ACT12':
            raise ValidationError('No original uncertain delivery')
        from apps.documents.controlled import reserve_publication
        u = principal(work, value, 'executor_id')
        binding = document(work)
        if not binding:
            raise ValidationError('Prepare an exact native forecast document')
        p = reserve_publication(u, case.pk, binding.version_id, case.revision, factory_work_id=work.pk)
        return {'head':work.source_head_id, 'publication':p.pk}
    if kind == 'ACT13':
        result = verify(work, work.execution_actor)
        work.status = 'verified'
        return result
    raise ValidationError('Actual verification, matching, reviews and priorities require human native actions')


def publication_scope(actor, case, version, work_id):
    from .factory import access, profile
    w = Work.objects.select_related('case','actor','source_head').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION)
    config,value = profile(w)
    if w.policy_id != config.pk or principal(w,value,'executor_id').pk != actor.pk:
        raise PermissionDenied('Exact current publisher and factory policy required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:
        raise ValidationError('Forecast publication is stopped')
    _,selected = source(w,actor)
    binding = document(w)
    r = calculation(w,actor)
    if not binding or not r or binding.run_id != r.pk or binding.version_id != version.pk or version.template_id != selected['template_id'] or version.audience != selected['audience']:
        raise ValidationError('Exact observed selected forecast document required')
    if forecast_documents.report_inputs(r,version.audience) != binding.snapshot:
        raise ValidationError('Forecast report inputs changed')
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}


def verify(work, actor=None):
    from .factory import profile
    from apps.documents.controlled import current_version, validate_review, publication_requirements
    _, selected = source(work,actor)
    binding = document(work)
    r = calculation(work,actor)
    if not binding or not r or binding.run_id != r.pk:
        raise ValidationError('Await exact reviewed aggregate forecast')
    review = forecast.approved(r)
    v = binding.version
    if v.template_id != selected['template_id'] or v.audience != selected['audience']:
        raise ValidationError('Exact selected template and audience required for final verification')
    if forecast_documents.report_inputs(r,v.audience) != binding.snapshot:
        raise ValidationError('Exact current native forecast report inputs required for final verification')
    current_version(work.case,v.pk)
    dr = validate_review(work.case,v)
    policies,recipients,retention = publication_requirements(work.case,v)
    config,value = profile(work,recovery=True)
    user = principal(work,value,'executor_id')
    principal(work,value,'preparer_id')
    p = Publication.objects.filter(version=v,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=user).first()
    if not p or p.policies != policies or p.recipient_ids != recipients or p.retention_days != retention or p.review_id != (dr.pk if dr else None):
        raise ValidationError('Await current exact forecast publication')
    receipts = list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if not receipts or {x.recipient_id for x in receipts} != set(recipients) or any(x.payload != v.payload or x.payload_sha256 != v.payload_sha256 for x in receipts):
        raise ValidationError('Every exact aggregate forecast recipient receipt required')
    return {'verified':True,'head':work.source_head_id,'forecast_run':r.pk,'forecast_review':review.pk,'document_version':v.pk,'publication':p.pk,'receipt_ids':[x.pk for x in receipts],'cash_mutated':False,'execution_authorized':False}


@transaction.atomic
def correct(actor, work_id, expected, case_expected, selected, reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending, has_receipt
    w = Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    w.case = lock_case(actor,w.case_id,'evidence.add',case_expected)
    if type(expected) is not int or w.revision != expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:
        raise ValidationError('STALE_VERSION: refresh exact forecast work')
    if w.lease_until and w.lease_until > timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():
        raise ValidationError('Resolve original effects before source correction')
    planning = pending(w)
    if planning and not has_receipt(planning):
        raise ValidationError('Reconcile original planning response before source correction')
    old,previous = source(w,actor,False)
    scenario,rows = sources.selection(actor,w.case,selected)
    if scenario.reference != old.reference:
        raise ValidationError('Correct only this native scenario reference')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:
        raise ValidationError('Explain the source-owned forecast correction')
    if selected == previous:
        binding = document(w)
        r = calculation(w,actor)
        stale = False
        try:
            if r:forecast.ensure_current(r)
            if binding:
                from apps.documents.controlled import current_version
                current_version(w.case,binding.version_id)
        except (ValidationError,PermissionDenied):
            stale = True
        cancelled = PublicationJob.objects.filter(publication__factory_work=w,publication__version_id=binding.version_id if binding else None,status='cancelled').exists()
        if not stale and not cancelled:
            raise ValidationError('Provide changed sources or resolve a stale/cancelled original output')
    old_head = w.source_head_id
    w.source_head = capture(actor,w.case,selected,'factory.forecast_source')
    w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,w.case,'factory.forecast_corrected',work=w.pk,previous=old_head,current=w.source_head_id,reason=reason)
    return w


@transaction.atomic
def human_action(actor, work_id, expected, case_expected, scenario_id, action, data):
    """Exact-work wrapper; never exposed to factory coordinator tools."""
    from .factory import access
    w = Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION)
    scenario, selected = source(w,actor)
    if type(expected) is not int or w.revision != expected or scenario_id != scenario.pk or w.cancel_requested or w.lease_until and w.lease_until > timezone.now():
        raise ValidationError('STALE_VERSION: refresh exact selected forecast work')
    r = calculation(w,actor)
    if action in ['review','priority'] and (not r or data['run'].pk != r.pk):
        raise ValidationError('Choose the exact current work calculation pin')
    if action == 'review':
        result = forecast.review(actor,w.case_id,r.pk,data['role'],data['verdict'],data['evidence'].pk,data['reason'],case_expected)
    elif action == 'priority':
        result = forecast.prioritize(actor,w.case_id,r.pk,data['role'],data['reference'],data['description'],data['owner'].pk,data['due_at'],data['evidence'].pk,data['reason'],case_expected)
    elif action == 'actual':
        result = forecast.capture_actual(actor,w.case_id,data['evidence'].pk,case_expected,data['lot'].pk if data['lot'] else None)
    elif action == 'verify':
        result = forecast.verify_actual(actor,w.case_id,data['actual'].pk,data['role'],data['evidence'].pk,case_expected)
    elif action == 'match':
        if data['scenario'].pk != scenario.pk:
            raise ValidationError('Match only the exact selected native scenario')
        result = forecast.match(actor,w.case_id,scenario.pk,data['item_key'],data['actual'].pk,data['amount'],data['operation_key'],data['evidence'].pk,case_expected)
    elif action == 'unmatch':
        if data['match'].root_id != forecast.root_of(scenario).pk:
            raise ValidationError('Reverse only a match from this exact scenario lineage')
        result = forecast.unmatch(actor,w.case_id,data['match'].pk,data['evidence'].pk,data['reason'],case_expected)
    else:
        raise ValidationError('Choose an explicit native human forecast action')
    event(actor,w.case,'factory.forecast_human_action',work=w.pk,scenario=scenario.pk,native_action=action,native_record=result.pk)
    return result


def projection(actor, work):
    from .factory import access, profile
    access(actor,work.case,'factory.read',DEFINITION)
    scenario,selected = source(work,actor,False)
    status={'stage':'source','finding':''};options=[];next_action='Review selected forecast sources';issue=''
    current=True
    try:
        source(work,actor)
        status=report(work,actor)
        _,value=profile(work)
        state,*args=snapshot(work,value,reader=actor)
        options,next_action=eligible(work,value,state,*args)
    except (ValidationError,PermissionDenied) as exc:
        current=False;issue=finding(exc);next_action=issue
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    changed=False
    if work.status=='verified':
        try:verify(work,actor)
        except (ValidationError,PermissionDenied) as exc:changed=True;issue=finding(exc)
    can_correct=False
    try:
        require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add')
        can_correct=not work.cancel_requested and work.status not in ['cancelled','followup_needed'] and not (work.lease_until and work.lease_until>timezone.now()) and not any(j.status in ['pending','unknown','leased','held'] for j in jobs)
    except PermissionDenied:pass
    run_id=observed(work,'forecast_run')
    r=sources.selected_run(actor,work.case,selected,run_id,current=False) if run_id else None
    for job in jobs:
        job.can_operate=False;job.can_retry=False
        job.receipts=list(PublicationReceipt.objects.filter(publication=job.publication).order_by('pk'))
        try:
            require(actor,work.case,'document.operate')
            job.can_operate=not (work.lease_until and work.lease_until>timezone.now()) and not job.receipts and (job.status in ['pending','unknown','held'] or job.status=='leased' and job.lease_until and job.lease_until<=timezone.now())
            job.can_retry=job.can_operate and not work.cancel_requested and job.status=='held'
        except PermissionDenied:pass
    review_roles=[]
    if current and r and status['stage']=='review' and not work.cancel_requested and not (work.lease_until and work.lease_until>timezone.now()):
        from apps.policy.document_validators import ROLES
        try:
            require(actor,work.case,'finance.forecast.review');forecast.review_snapshot(r)
            for role in ROLES:
                try:
                    forecast.review_authority(actor,work.case,'forecast_rollover' if scenario.parent_id else 'forecast',role,'approve',r.actor_id);review_roles.append(role)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    can_restart=False;restart_policy=None
    try:
        require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add')
        from apps.policy.services import active_component
        from .factory_definitions import definition
        restart_policy=active_component(definition(DEFINITION)['component'],work.case).pk
        can_restart=work.cancel_requested and work.status=='cancelled' and not (work.lease_until and work.lease_until>timezone.now()) and not any(j.status in ['pending','unknown','leased','held'] for j in jobs) and not PublicationReceipt.objects.filter(publication__factory_work=work).exists()
    except (PermissionDenied,ValidationError):pass
    return {'can_restart':can_restart,'restart_policy':restart_policy,'review_roles':review_roles,'scenario':scenario,'selection':selected,'run':r,'document':document(work),'jobs':jobs,'status':status,'finding':issue,'intake_current':current,'readiness_changed':changed,'next_options':options,'next_action':next_action,'can_correct':can_correct}


def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh original forecast delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain forecast delivery needs reconciliation')
        event(actor,w.case,'factory.reconciliation_requested',work=w.pk,publication_job=job.pk)
    run_publication_once(adapter,case_id=w.case_id,job_id=job.pk)
    with transaction.atomic():
        w=Work.objects.select_for_update().get(pk=work_id);job.refresh_from_db()
        w.status=cancellation_status(w) if w.cancel_requested else 'waiting_effect' if job.status=='unknown' else 'blocked' if job.status=='held' else 'ready'
        w.finding=job.error if job.status in ['held','unknown'] else '';w.observation_hash='';w.revision+=1;w.save()
    return w


@transaction.atomic
def operate(actor,work_id,expected,case_expected,job_id,action,reason):
    from .factory import access,cancellation_status
    from apps.documents.delivery import operate_publication
    w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);require(actor,w.case,'document.operate')
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh exact forecast and engagement versions')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for the current worker before operating delivery')
    if not PublicationJob.objects.filter(pk=job_id,publication__factory_work=w).exists():raise ValidationError('Choose this work original delivery')
    if action not in ['cancel','retry'] or not isinstance(reason,str):raise ValidationError('Choose a native recovery action and explain it')
    operate_publication(actor,w.case_id,job_id,action,reason,case_expected)
    w.status=cancellation_status(w) if w.cancel_requested else 'ready' if action=='retry' else 'blocked'
    w.finding='' if action=='retry' else 'Delivery cancelled. Review a current source package before another publication.'
    w.observation_hash='';w.revision+=1;w.save();return w


@transaction.atomic
def cancel(actor,work_id,expected):
    from .factory import access,manage,cancellation_status
    if type(expected) is not int or expected<1:raise ValidationError('Exact rendered work version required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh current forecast work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Delivered or accepted work requires native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping work cannot undo an already delivered document or forecast review.'
    w.lease_until=None;w.revision+=1;w.save();return w


@transaction.atomic
def restart(actor, work_id, expected, case_expected, selected, configuration_id, reason):
    """Fresh human instruction after settled, never-delivered preparation only."""
    from .factory import access, profile
    from .factory_definitions import definition
    from apps.agents.factory_coordinator import pending, has_receipt
    from apps.policy.services import active_component
    w = Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    w.case=lock_case(actor,w.case_id,'evidence.add',case_expected)
    if type(expected) is not int or w.revision!=expected or w.status!='cancelled' or not w.cancel_requested:
        raise ValidationError('Only settled stopped forecast preparation can receive a fresh instruction')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():
        raise ValidationError('Resolve every original effect before restarting')
    planning=pending(w)
    if planning and not has_receipt(planning):
        raise ValidationError('Resolve the original planning response before restarting')
    if PublicationReceipt.objects.filter(publication__factory_work=w).exists():
        raise ValidationError('Delivered forecasts require source-owned follow-up, not restart')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:
        raise ValidationError('Explain the explicit fresh preparation instruction')
    old,previous=source(w,actor,False)
    scenario,rows=sources.selection(actor,w.case,selected)
    if scenario.reference!=old.reference:
        raise ValidationError('Restart only the exact native scenario reference')
    config=active_component(definition(DEFINITION)['component'],w.case)
    if type(configuration_id) is not int or config.pk!=configuration_id:
        raise ValidationError('Explicitly select the exact current reviewed operating policy')
    old_policy=w.policy_id
    if old_policy and old_policy!=config.pk:
        require(actor,w.case,'policy.activate')
    w.policy=config
    _,value=profile(w)
    principal(w,value,'preparer_id');principal(w,value,'executor_id')
    if w.budget_limit==0 and w.budget_used==0:
        w.budget_limit=value['max_tokens']
    old_head=w.source_head_id
    w.source_head=capture(actor,w.case,selected,'factory.forecast_source')
    w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,w.case,'factory.forecast_restarted',work=w.pk,previous=old_head,current=w.source_head_id,previous_policy=old_policy,current_policy=config.pk,reason=reason,spent=w.budget_used,lifetime_allowance=w.budget_limit)
    return w
