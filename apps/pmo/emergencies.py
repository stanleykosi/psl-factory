"""P61/P62 local evidence controls. No deployment or financial effects."""
from datetime import timedelta, timezone as utc
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import require_operation, reference_values, decision_authority
from .models import (EmergencyProfile, EmergencyDecision, EmergencyAuthorization, EmergencyOutcome,
    EmergencyReview, EmergencyRetrospectiveDecision, EmergencyRetrospectiveRecord, DeliveryCandidate)
from .changes import current_change, require_open_version
from .commercial import note_required
from .services import subject
from .clocks import aware, configuration, local_time


def profile_for(case,pk,current=True):
    profile=EmergencyProfile.objects.select_related('version__change','candidate').filter(pk=pk,version__change__case=case).first()
    if not profile:raise ValidationError('Emergency profile must belong to this case')
    if current:
        current_change(case,profile.version_id)
        if profile.version.emergency_profiles.order_by('-pk').first().pk!=profile.pk:
            raise ValidationError('Emergency source profile changed; use its current version')
    return profile


def emergency_policy(case):
    results=require_operation('emergency.release_evaluate',case)
    configs={r.component:r.configuration for r in results}
    gates=reference_values(configs['D01.satisfied_gate_map'])[0]
    if 'emergency' not in gates:raise ValidationError('D01.satisfied_gate_map.emergency is unconfigured (v2 interface required)')
    return reference_values(configs['D01.emergency_glpi_relationship'])[0],{k:v.pk for k,v in configs.items()}


@transaction.atomic
def capture_profile(actor,case_id,version_id,candidate_id,critical_production,p1,evidence_id,note,expected):
    case=lock_case(actor,case_id,'emergency.manage',expected)
    version=current_change(case,version_id);require_open_version(version)
    if version.category!='Emergency' or not version.incident_id:raise ValidationError('Use an incident-linked Emergency change revision')
    if any(v is not None and type(v) is not bool for v in [critical_production,p1]):raise ValidationError('Use explicit true/false/unknown incident classifications')
    candidate=DeliveryCandidate.objects.filter(case=case,pk=candidate_id).first()
    if not candidate:raise ValidationError('Select this case release candidate')
    decision_authority(actor,case,'PM');note_required(note)
    result=EmergencyProfile.objects.create(version=version,candidate=candidate,critical_production=critical_production,p1=p1,
        evidence=subject(case,evidence_id,'incident_classification'),note=note,actor=actor)
    event(actor,case,'emergency.profiled',profile=result.pk,version=version.pk,p1=p1)
    bump(case);return result


def prescribed_role(role,authority_role):
    if role=='Incident Lead':
        if authority_role not in ['Security Lead','Engineering Lead']:raise ValidationError('Incident Lead must be Security Lead or Engineering Lead')
        return authority_role
    if role in ['Engineering Lead','CTO']:return role
    raise ValidationError('Choose a prescribed preauthorization role')


@transaction.atomic
def decide_emergency(actor,case_id,profile_id,role,authority_role,verdict,evidence_id,note,expected):
    case=lock_case(actor,case_id,'emergency.decide',expected);profile=profile_for(case,profile_id)
    if profile.version.emergency_profiles.filter(outcomes__isnull=False).exists():raise ValidationError('Implementation outcome is recorded; preauthorization cannot be backdated')
    policies={}
    if role.startswith('GLPI exception:'):
        policy,policies=emergency_policy(case);selected=role.removeprefix('GLPI exception:')
        if policy['mode']=='coexist' or selected not in policy['exception_roles']:raise ValidationError('GLPI exception role is not explicitly configured')
        authority_role=selected
    else:authority_role=prescribed_role(role,authority_role)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose an explicit human verdict')
    note_required(note);authority=decision_authority(actor,case,authority_role,verdict)
    result=EmergencyDecision.objects.create(profile=profile,role=role,authority_role=authority_role,verdict=verdict,
        policies=policies,authority=authority,evidence=subject(case,evidence_id,'emergency_decision'),note=note,actor=actor)
    event(actor,case,'emergency.decision',decision=result.pk,profile=profile.pk,role=role,verdict=verdict)
    bump(case);return result


def glpi_snapshot(case,candidate):
    result=[]
    for kind in ['glpi_security','glpi_cto','glpi_ceo']:
        record=candidate.gates.filter(kind=kind).order_by('-pk').first()
        verification=record.verifications.order_by('-pk').first() if record else None
        if not verification or verification.result['decision']!='accepted':raise ValidationError('Current source-verified GLPI evidence required: '+kind)
        require(verification.actor,case,'pmo.gate_verify')
        result.append([record.pk,verification.pk])
    return result


def preauthorization_inputs(case,profile,*,check_authority=True,historical=False):
    profile_for(case,profile.pk,current=not historical)
    if historical and (profile.version.change.current_id!=profile.version_id or
            profile.version.emergency_profiles.order_by('-pk').first().pk!=profile.pk):
        raise ValidationError('Emergency source revision/profile changed; preserve the original outcome history')
    if check_authority:
        require(profile.actor,case,'emergency.manage')
        decision_authority(profile.actor,case,'PM')
    if profile.critical_production is not True or profile.p1 is None:
        raise ValidationError('Confirm critical production applicability and explicit incident P1 basis; Critical never implies P1')
    policy,policies=emergency_policy(case)
    roles=['Incident Lead','Engineering Lead']+(['CTO'] if profile.p1 else [])
    roles+=['GLPI exception:'+r for r in policy['exception_roles']]
    decisions=[];people={}
    for role in roles:
        d=profile.decisions.filter(role=role).order_by('-pk').first()
        actual_role=policy['incident_lead_role'] if role=='Incident Lead' else role.removeprefix('GLPI exception:')
        if not d or d.verdict!='approve' or d.authority_role!=actual_role:
            raise ValidationError('Current prescribed emergency approval required: '+role)
        if check_authority:
            require(d.actor,case,'emergency.decide')
            if decision_authority(d.actor,case,actual_role)!=d.authority:
                raise ValidationError('Emergency approval authority changed: '+role)
        if d.policies and d.policies!=policies:
            raise ValidationError('Emergency approval authority/policy changed: '+role)
        decisions.append(d.pk);people[role]=d.actor_id
    if people['Incident Lead']==people['Engineering Lead'] and policy['incident_engineering_overlap']!='explicit_same_person':
        raise ValidationError('Incident Lead and Engineering Lead need distinct people under current policy')
    if check_authority and people['Incident Lead']==people['Engineering Lead'] and policy.get('role_eligibility')=='current_D05_bundle':
        from apps.policy.role_assignments import COMPONENT,eligibility
        from apps.policy.services import active_component,reference_values
        bundle=eligibility(case,reference_values(active_component(COMPONENT,case)),people['Incident Lead'])
        if bundle['eligibility']!='explicit_current' or not {policy['incident_lead_role'],'Engineering Lead'}<=set(bundle['roles']):
            raise ValidationError('Current exact explicit D05 eligibility required for the shared Emergency role bundle')
    gates=glpi_snapshot(case,profile.candidate) if policy['mode']=='coexist' else []
    return {'profile_id':profile.pk,'policies':policies,'decision_ids':decisions,'glpi':gates,'mode':policy['mode']}


@transaction.atomic
def authorize_emergency(actor,case_id,profile_id,expected):
    case=lock_case(actor,case_id,'emergency.authorize',expected);profile=profile_for(case,profile_id)
    if EmergencyOutcome.objects.filter(profile__version=profile.version).exists():raise ValidationError('Outcome already recorded; a later authorization cannot authorize earlier work')
    if EmergencyAuthorization.objects.filter(profile=profile).exists():raise ValidationError('Authorization already recorded; preserve its history')
    snapshot=preauthorization_inputs(case,profile)
    result=EmergencyAuthorization.objects.create(profile=profile,snapshot=snapshot,actor=actor)
    event(actor,case,'emergency.preauthorized',authorization=result.pk,profile=profile.pk,deployment_dispatched=False)
    bump(case);return result


@transaction.atomic
def capture_outcome(actor,case_id,profile_id,authorization_id,implemented_at,evidence_id,note,expected):
    # Recording an actual external outcome must remain possible even if authority is missing/stale.
    case=lock_case(actor,case_id,'emergency.record_outcome',expected);profile=profile_for(case,profile_id,current=False)
    implemented_at=aware(implemented_at)
    if implemented_at>timezone.now():raise ValidationError('Implementation timestamp must be an actual past instant')
    auth=EmergencyAuthorization.objects.filter(pk=authorization_id,profile=profile).first() if authorization_id else None
    if authorization_id and not auth:raise ValidationError('Authorization must belong to this exact emergency profile')
    if profile.outcomes.exists():raise ValidationError('Outcome already recorded; retain evidence and use an attributable new revision for corrections')
    note_required(note)
    result=EmergencyOutcome.objects.create(profile=profile,authorization=auth,implemented_at=implemented_at,
        evidence=subject(case,evidence_id,'change_implementation'),note=note,actor=actor)
    event(actor,case,'emergency.outcome_recorded',outcome=result.pk,authorization=authorization_id,
        preauthorization_preceded=bool(auth and auth.created_at<=implemented_at))
    bump(case);return result


def outcome_for(case,pk):
    outcome=EmergencyOutcome.objects.select_related('profile__version__change','profile__candidate','authorization').filter(pk=pk,profile__version__change__case=case).first()
    if not outcome:raise ValidationError('Choose an emergency outcome within this case')
    return outcome


def timing(case,outcome,as_of=None):
    now=aware(as_of) if as_of is not None else timezone.now()
    if as_of is not None and not case.synthetic:raise ValidationError('Injected observation clocks are restricted to synthetic cases')
    result={'policies':{},'log_due_at':None,'retrospective_due_at':None,'log_late':None,'findings':[],
        'synthetic_observation':as_of is not None}
    try:
        config,rules=configuration('D04.clock_anchor_pause_rules',case)
        if 'emergency' not in rules:raise ValidationError('D04.clock_anchor_pause_rules.emergency is unconfigured')
        result['policies'][config.component]=config.pk
        due=outcome.implemented_at.astimezone(utc.utc)+timedelta(hours=24)
        result['log_due_at']=due.isoformat();result['log_late']=outcome.created_at>due
    except ValidationError as exc:result['findings']+=exc.messages;return result
    try:
        from apps.policy.services import active_component
        tz=active_component('D04.iana_timezone',case);zone=ZoneInfo(tz.envelope['value'])
        calendar_config,calendar=configuration('D04.working_calendar_ref',case)
        params_config,params=configuration('D04.deadline_parameters',case)
        if 'emergency' not in params:raise ValidationError('D04.deadline_parameters.emergency is unconfigured')
        for c in [tz,calendar_config,params_config]:result['policies'][c.component]=c.pk
        day=outcome.implemented_at.astimezone(zone).date();remaining=params['emergency']['retrospective_working_days']
        def working(d):return d.weekday() in calendar['weekdays'] and d.isoformat() not in calendar['holidays']
        if rules['emergency']['anchor_day']=='include_if_working' and working(day):remaining-=1
        for _ in range(3660):
            if remaining==0:break
            day+=timedelta(days=1)
            if working(day):remaining-=1
        else:raise ValidationError('Emergency working calendar exceeded bounded horizon')
        due=local_time(day,calendar['due_time'],zone)
        if due<outcome.implemented_at:raise ValidationError('Configured retrospective deadline precedes implementation; correct anchor-day/time parameters')
        result['retrospective_due_at']=due.isoformat();result['retrospective_overdue']=now>due
    except ValidationError as exc:result['findings']+=exc.messages
    return result


@transaction.atomic
def record_review(actor,case_id,outcome_id,evidence_id,note,expected):
    case=lock_case(actor,case_id,'emergency.review',expected);outcome=outcome_for(case,outcome_id)
    if EmergencyRetrospectiveRecord.objects.filter(outcome=outcome).exists():raise ValidationError('Reconciled history is immutable; record a new change for further work')
    note_required(note)
    review=EmergencyReview.objects.create(outcome=outcome,evidence=subject(case,evidence_id,'post_implementation_review'),note=note,actor=actor)
    event(actor,case,'emergency.review_recorded',review=review.pk,outcome=outcome.pk);bump(case);return review


@transaction.atomic
def decide_retrospective(actor,case_id,outcome_id,role,verdict,evidence_id,note,expected):
    case=lock_case(actor,case_id,'emergency.retrospective_decide',expected);outcome=outcome_for(case,outcome_id)
    if EmergencyRetrospectiveRecord.objects.filter(outcome=outcome).exists():raise ValidationError('Retrospective record is historical')
    review=outcome.reviews.order_by('-pk').first()
    if not review:raise ValidationError('Mandatory post-implementation review required before retrospective decisions')
    if role not in ['Product','Engineering Lead'] or verdict not in ['approve','return','reject']:raise ValidationError('Choose a source-prescribed retrospective role/verdict')
    authority=decision_authority(actor,case,role,verdict);note_required(note)
    result=EmergencyRetrospectiveDecision.objects.create(review=review,role=role,verdict=verdict,authority=authority,
        timing=timing(case,outcome),evidence=subject(case,evidence_id,'emergency_decision'),note=note,actor=actor)
    event(actor,case,'emergency.retrospective_decision',decision=result.pk,outcome=outcome.pk,role=role,verdict=verdict)
    bump(case);return result


def completion_status(clock,decisions,due):
    return 'completed_with_lateness_exception' if clock['log_late'] or any(d.created_at>due for d in decisions) else 'evidenced_on_time'


def retrospective_inputs(case,outcome):
    auth=outcome.authorization
    if not auth or auth.created_at>outcome.implemented_at:raise ValidationError('Missing pre-implementation authorization remains an exception; retrospective decisions cannot replace it')
    from .recoveries import active_recovery
    recovered=active_recovery(case,'emergency_outcome',outcome.pk)
    if not recovered:require(auth.actor,case,'emergency.authorize')
    if preauthorization_inputs(case,outcome.profile,check_authority=not bool(recovered),historical=True)!=auth.snapshot:raise ValidationError('Emergency authorization source/policy changed; explicit recovery required')
    review=outcome.reviews.order_by('-pk').first()
    if not review:raise ValidationError('Mandatory post-implementation review missing')
    require(review.actor,case,'emergency.review')
    decisions=[]
    for role in ['Product','Engineering Lead']:
        d=review.decisions.filter(role=role).order_by('-pk').first()
        if not d or d.verdict!='approve':raise ValidationError('Current review-bound retrospective approval required: '+role)
        require(d.actor,case,'emergency.retrospective_decide')
        if decision_authority(d.actor,case,role)!=d.authority:raise ValidationError('Retrospective decision authority changed')
        decisions.append(d)
    clock=timing(case,outcome)
    if not clock['retrospective_due_at']:raise ValidationError(clock['findings'])
    if any(d.timing.get('retrospective_due_at') and d.timing['policies']!=clock['policies'] for d in decisions):
        raise ValidationError('Deadline policy changed; human owners must reaffirm decisions against the current clock, preserving earlier timing history')
    due=aware(clock['retrospective_due_at'])
    # Late completion is explicitly recorded as an exception, never backdated compliance.
    glpi=glpi_snapshot(case,outcome.profile.candidate) if auth.snapshot['mode']=='defer' else auth.snapshot['glpi']
    history=list(EmergencyRetrospectiveDecision.objects.filter(review__outcome=outcome).order_by('pk')[:201])
    if len(history)>200:raise ValidationError('Retrospective timing history exceeds bounded review budget')
    historic_late=any(d.timing.get('retrospective_due_at') and d.created_at>aware(d.timing['retrospective_due_at']) for d in history)
    status=completion_status(clock,decisions,due)
    if historic_late:status='completed_with_lateness_exception'
    return {'authorization_id':auth.pk,'review_id':review.pk,'decision_ids':[d.pk for d in decisions],
        'timing':clock,'glpi':glpi,'historic_lateness':historic_late,'status':status,
        'authority_recovery_id':recovered.pk if recovered else None}


@transaction.atomic
def reconcile_retrospective(actor,case_id,outcome_id,expected):
    case=lock_case(actor,case_id,'emergency.manage',expected);outcome=outcome_for(case,outcome_id)
    if EmergencyRetrospectiveRecord.objects.filter(outcome=outcome).exists():raise ValidationError('Retrospective already reconciled')
    snapshot=retrospective_inputs(case,outcome)
    result=EmergencyRetrospectiveRecord.objects.create(outcome=outcome,snapshot=snapshot,actor=actor)
    event(actor,case,'emergency.retrospective_reconciled',record=result.pk,outcome=outcome.pk,status=snapshot['status'])
    bump(case);return result
