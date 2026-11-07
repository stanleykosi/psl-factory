from datetime import timedelta, timezone as dt_timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import resolve, reference_values, decision_authority, active_component
from apps.documents.contracts import digest
from apps.documents.controlled import create_version
from apps.documents.models import Template
from .models import Issue, EscalationProfile, EscalationRequest, EscalationDecision, EscalationDocumentBinding, EscalationSignal, EscalationScanCursor
from .issues import current_issue
from .services import subject
from .commercial import note_required
from .clocks import aware


@transaction.atomic
def capture_profile(actor,case_id,issue_id,state_id,classification,timeline_impact,trigger_at,evidence_id,note,expected):
    case=lock_case(actor,case_id,'issue.escalate',expected)
    issue=current_issue(case,issue_id,state_id)
    if classification not in ['unclassified','internal','client_dependent'] or timeline_impact is not None and type(timeline_impact) is not bool:
        raise ValidationError('Choose an explicit dependency classification and true/false/unknown timeline impact')
    note_required(note)
    trigger=aware(trigger_at) if trigger_at else None
    if trigger and trigger>timezone.now():raise ValidationError('Actual issue trigger cannot be in the future')
    result=EscalationProfile.objects.create(state=issue.current,classification=classification,timeline_impact=timeline_impact,
        trigger_at=trigger,evidence=subject(case,evidence_id),note=note,actor=actor)
    event(actor,case,'issue.escalation_profile',profile=result.pk,state=state_id)
    bump(case)
    return result


def current_profile(case,pk):
    p=EscalationProfile.objects.select_related('state__issue').filter(pk=pk,state__issue__case=case).first()
    if not p or p.state.issue.current_id!=p.state_id or EscalationProfile.objects.filter(state__issue=p.state.issue).order_by('-pk').first().pk!=p.pk:
        raise ValidationError('Issue or escalation facts changed; capture a current source-bound profile')
    from .progress import validate_profile_origin
    validate_profile_origin(p)
    return p


def timing(profile,as_of=None):
    now=aware(as_of or timezone.now());s=profile.state;active=s.status in ['Open','In Progress']
    result={'as_of':now.isoformat(),'clock_mode':'live' if as_of is None else 'labelled_test_clock', 'active':active,'immediate':active and profile.timeline_impact is True,
        'timeline_impact_unknown':profile.timeline_impact is None,'classification':profile.classification,
        'clock_status':'UNCONFIGURED','anchor':None,'elapsed_hours':None,'acknowledgement_due_at':None,
        'acknowledgement_status':'UNKNOWN','internal_24h':None,'internal_48h':None,'client_24h':None,'policies':{},'gaps':[]}
    clock=resolve('D04.clock_anchor_pause_rules',s.issue.case)
    params=resolve('D04.deadline_parameters',s.issue.case)
    rules=reference_values(clock.configuration)[0].get('issues') if clock.status=='ACTIVE' else None
    parameters=reference_values(params.configuration)[0].get('issues',{}) if params.status=='ACTIVE' else {}
    if not rules:
        result['gaps'].append('Issue clock anchor/basis/pause is not configured: '+clock.status)
        return result
    result['policies'][clock.component]=clock.configuration.pk
    if params.status=='ACTIVE':result['policies'][params.component]=params.configuration.pk
    else:result['gaps'].append('Issue acknowledgement/routing parameters unavailable: '+params.status)
    anchor=s.issue.states.order_by('number').first().created_at if rules['anchor']=='logged_at' else profile.trigger_at
    if not anchor:
        result['gaps'].append('Configured issue trigger timestamp is unknown');return result
    anchor=anchor.astimezone(dt_timezone.utc)
    result['anchor']=anchor.isoformat()
    if anchor>now:
        result['clock_status']='FUTURE_ANCHOR';result['gaps'].append('Clock anchor follows observation time');return result
    elapsed=(now.astimezone(dt_timezone.utc)-anchor).total_seconds()/3600
    result.update(clock_status='EVALUATED',elapsed_hours=elapsed)
    result['internal_24h']=active and profile.classification=='internal' and elapsed>=24
    result['internal_48h']=active and profile.classification=='internal' and elapsed>=48
    result['client_24h']=active and profile.classification=='client_dependent' and elapsed>=24
    routes=parameters.get('internal_24h_routes',{})
    result['internal_24h_target']=routes.get(s.severity)
    if profile.classification=='internal' and not result['internal_24h_target']:
        result['gaps'].append('Severity-to-PMO/CTO routing is unknown')
    if 'acknowledgement_hours' in parameters:
        due=anchor+timedelta(hours=parameters['acknowledgement_hours']);result['acknowledgement_due_at']=due.isoformat()
        result['acknowledgement_status']=('LATE' if s.acknowledged_at>due else 'ON_TIME') if s.acknowledged_at else ('OVERDUE' if now>=due else 'PENDING')
    return result


@transaction.atomic
def request_escalation(actor,case_id,profile_id,direction,target,evidence_id,note,expected):
    case=lock_case(actor,case_id,'issue.escalate',expected);profile=current_profile(case,profile_id)
    note_required(note)
    if direction not in ['escalate','de_escalate'] or target not in ['PMO','CTO','Client']:
        raise ValidationError('Choose a source escalation direction and explicit destination')
    evidence=subject(case,evidence_id)
    if EscalationRequest.objects.filter(profile=profile,direction=direction,target=target,evidence=evidence).exists():
        raise ValidationError('This source-bound request already exists; inspect its history')
    r=EscalationRequest.objects.create(profile=profile,direction=direction,target=target,evidence=evidence,note=note,actor=actor)
    event(actor,case,'issue.escalation_requested',request=r.pk,target=target,direction=direction)
    bump(case);return r


def current_request(case,pk):
    r=EscalationRequest.objects.select_related('profile__state__issue').filter(pk=pk,profile__state__issue__case=case).first()
    if not r:raise ValidationError('Request must belong to this case')
    current_profile(case,r.profile_id)
    return r


@transaction.atomic
def decide_escalation(actor,case_id,request_id,role,verdict,note,expected,delegated=False):
    case=lock_case(actor,case_id,'issue.escalation_decide',expected);r=current_request(case,request_id)
    note_required(note)
    if r.target!='Client' or role not in ['PMO Lead','Head of PMO'] or verdict not in ['approve','return','reject']:
        raise ValidationError('Client escalation/de-escalation needs PMO Lead or Head of PMO decision')
    last=r.decisions.order_by('-pk').first()
    if last and last.verdict in ['return','reject']:raise ValidationError('Returned/rejected requests require new source facts and a new request')
    authority=decision_authority(actor,case,role,verdict,delegated)
    if last and last.verdict==verdict and last.authority==authority:raise ValidationError('This exact decision is already current')
    result=EscalationDecision.objects.create(request=r,role=role,verdict=verdict,note=note,actor=actor,delegated=delegated,authority=authority)
    event(actor,case,'issue.escalation_decision',decision=result.pk,request=r.pk,role=role,verdict=verdict)
    bump(case);return result


def approved_request(case,r):
    if r.target!='Client':return None
    d=r.decisions.order_by('-pk').first()
    if not d or d.verdict!='approve':raise ValidationError('Client escalation/de-escalation decision is pending')
    require(d.actor,case,'issue.escalation_decide')
    if decision_authority(d.actor,case,d.role,'approve',d.delegated)!=d.authority:
        raise ValidationError('Escalation decision authority changed; obtain a current decision')
    return d


@transaction.atomic
def draft_escalation(actor,case_id,request_id,template_id,expected):
    case=lock_case(actor,case_id,'issue.escalate',expected);r=current_request(case,request_id)
    decision=approved_request(case,r)
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type__in=['status_report','project_artifact']).first()
    if not template:raise ValidationError('Choose a case-controlled escalation template')
    from adapters.escalations import LocalIssueEscalationAdapter
    audience='client' if r.target=='Client' else 'internal'
    fields=LocalIssueEscalationAdapter().fields(r,template,audience)
    version=create_version(actor,case.pk,template.pk,f'Issue {r.profile.state.issue.reference}: {r.direction} to {r.target} #{r.pk}',audience,fields,case.revision)
    EscalationDocumentBinding.objects.create(version=version,request=r,decision=decision)
    return version


def binding_findings(binding):
    try:
        case=binding.request.profile.state.issue.case
        r=current_request(case,binding.request_id);d=approved_request(case,r)
        if (d.pk if d else None)!=binding.decision_id:return ['Escalation decision changed; draft and review a fresh communication']
    except (ValidationError,PermissionDenied) as exc:return ['Issue escalation source/authority changed: '+str(exc)]
    return []


def recipient_requirements(binding,case,recipients):
    target=binding.request.target
    if target=='Client':return {}
    assignment=active_component('D05.role_principal_assignments',case)
    users={r['user_id'] for r in reference_values(assignment) if r['role']==target}
    if not users.intersection(recipients):raise ValidationError('Configured internal audience has no currently assigned '+target+' recipient')
    return {assignment.component:assignment.pk}


@transaction.atomic
def scan_profile(actor,case_id,profile_id,as_of=None):
    case=lock_case(actor,case_id,'issue.escalate')
    if as_of is not None and not case.synthetic:raise ValidationError('Injected scan clocks are restricted to synthetic test cases')
    profile=current_profile(case,profile_id);result=timing(profile,as_of)
    signals=[]
    if result['active']:
        if result['immediate']:signals.append(('immediate',None,{}))
        if result.get('internal_24h'):signals.append(('internal_24h',result.get('internal_24h_target'),result['policies']))
        if result.get('internal_48h'):signals.append(('internal_48h','CTO',result['policies']))
        if result.get('client_24h'):signals.append(('client_24h','Client',result['policies']))
        if result['acknowledgement_status']=='OVERDUE':signals.append(('acknowledgement_overdue','Owner',result['policies']))
    created=[]
    for kind,target,policies in signals:
        signal,new=EscalationSignal.objects.get_or_create(profile=profile,kind=kind,policy_key=digest(policies),
            defaults={'target':target,'policies':policies,'observed_at':aware(as_of or timezone.now()),'actor':actor})
        if new:
            created.append(signal.pk);event(actor,case,'issue.escalation_signal',signal=signal.pk,kind=kind,target=target)
    if created:bump(case)
    return created


@transaction.atomic
def scan_due(limit=100):
    # Persist urgency only. There is no decision, request, publication or external dispatch tool here.
    if type(limit) is not int or not 1<=limit<=1000:raise ValidationError('Scan limit must be 1 to 1000')
    cursor,_=EscalationScanCursor.objects.get_or_create(name='issue-urgency-v1')
    cursor=EscalationScanCursor.objects.select_for_update().get(pk=cursor.pk)
    profiles=EscalationProfile.objects.select_related('actor','state__issue').order_by('state__issue_id','-pk').distinct('state__issue_id')
    batch=list(profiles.filter(state__issue_id__gt=cursor.after_issue_id)[:limit])
    if not batch:batch=list(profiles[:limit])
    count=0
    for p in batch:
        try:count+=len(scan_profile(p.actor,p.state.issue.case_id,p.pk))
        except (ValidationError,PermissionDenied):continue
    if batch:
        cursor.after_issue_id=batch[-1].state.issue_id;cursor.save(update_fields=['after_issue_id'])
    return count
