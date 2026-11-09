"""P28: independently authored progress -> exact plan, issue and escalation facts.

Supplied source is not remote authenticity. A PM correlation is not plan approval,
issue closure or permission to communicate. Source capture survives policy holds.
"""
import hashlib
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case, add_evidence, event, bump
from apps.documents.contracts import validate
from apps.identity.services import require
from apps.policy.services import decision_authority
from .delivery import dossier_for, ensure_open, approved_plan
from .issue_access import issue_subject, state_public
from .issues import owned, current_issue
from .clocks import aware
from .models import DeliveryProgressSource as Source, DeliveryProgressObservation as Observation, DeliveryProgressCorrelation as Correlation, EscalationProfile

KIND = 'agent_private_delivery_progress'
PROTOCOL = 'delivery-progress-observation/v1'
FIELDS = {'type':'object','properties':{'activity_ref':{'type':'string','minLength':1,'maxLength':240},
    'dependency_ref':{'type':['string','null'],'minLength':1,'maxLength':240},
    'summary':{'type':'string','minLength':1,'maxLength':4000},
    'timeline_impact':{'type':['boolean','null']}, 'scope_change':{'type':['boolean','null']}},
    'required':['activity_ref','dependency_ref','summary','timeline_impact','scope_change'],'additionalProperties':False}


def bounded(value, length, label):
    if not isinstance(value,str) or not value.strip() or len(value)>length:raise ValidationError(label+' must be explicit and bounded')
    return value


def readable(actor, case):
    for action in ['case.read','delivery.read','delivery.progress.read']:require(actor,case,action)


def source_authority(source):
    case=source.dossier.case
    for action in ['case.read','delivery.read','delivery.progress.configure']:require(source.actor,case,action)
    for action in ['case.read','delivery.read','delivery.progress.observe']:require(source.participant,case,action)
    issue_subject(case,source.evidence_id)


def source_for(actor,case,pk):
    readable(actor,case)
    source=Source.objects.select_related('dossier__case','actor','participant').filter(pk=pk,dossier__case=case).first()
    if not source:raise ValidationError('Select this project exact progress source')
    source_authority(source)
    return source


@transaction.atomic
def configure(actor,case_id,dossier_id,team,identity,reference,participant_id,mode,evidence_id,expected,*,max_age_seconds=None):
    case=lock_case(actor,case_id,'delivery.progress.configure',expected);readable(actor,case)
    d=dossier_for(case,dossier_id,current=False);ensure_open(d)
    if team not in ['Engineering','QA'] or mode not in ['supplied','synthetic_mock'] or mode=='synthetic_mock' and not case.synthetic:
        raise ValidationError('Explicit Engineering/QA supplied source or labelled synthetic mock required')
    if max_age_seconds is not None and (type(max_age_seconds) is not int or max_age_seconds<1):raise ValidationError('Source age threshold must be explicit positive seconds or unknown')
    participant=get_user_model().objects.filter(pk=participant_id,is_active=True).first()
    if not participant:raise ValidationError('Select an active source participant')
    if max_age_seconds is not None and participant.pk!=actor.pk:raise PermissionDenied('Only the explicitly selected source participant may supply an age threshold against source-scope evidence')
    for action in ['case.read','delivery.read','delivery.progress.observe']:require(participant,case,action)
    if Source.objects.filter(dossier=d,source_identity=identity,source_ref=reference).exists():raise ValidationError('Source scope already exists; inspect its independent observation history')
    row=Source.objects.create(dossier=d,team=team,source_identity=bounded(identity,200,'Source identity'),source_ref=bounded(reference,240,'Source reference'),
        participant=participant,mode=mode,max_age_seconds=max_age_seconds,evidence=issue_subject(case,evidence_id),actor=actor)
    event(actor,case,'delivery.progress.source',source=row.pk);bump(case);return row


@transaction.atomic
def observe(actor,case_id,source_id,previous_id,version,observed_at,availability,fields,expected):
    case=lock_case(actor,case_id,'delivery.progress.observe',expected);source=source_for(actor,case,source_id);ensure_open(source.dossier)
    if source.participant_id!=actor.pk:raise PermissionDenied('Only the explicitly selected source participant records this source')
    previous=source.observations.order_by('-pk').first()
    if previous_id!=(previous.pk if previous else None):raise ValidationError('STALE_VERSION: refresh the exact source observation before correction')
    at=aware(observed_at)
    if at>timezone.now():raise ValidationError('Observation time must be actual, never a future estimate')
    if availability not in ['available','unavailable','unknown']:raise ValidationError('Explicit source availability required')
    validate(FIELDS if availability=='available' else {'type':'object','maxProperties':0},fields)
    for key,value in fields.items():
        if isinstance(value,str):bounded(value,4000,key)
    version=bounded(version,100,'Independent source revision')
    if source.observations.filter(source_version=version).exists():raise ValidationError('Source revision already captured; inspect history rather than overwrite it')
    data={'protocol':PROTOCOL,'source_id':source.pk,'source_version':version,'previous_id':previous_id,
        'observed_at':at.isoformat(),'availability':availability,'fields':fields}
    evidence=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:delivery-progress:'+str(source.pk))
    row=Observation.objects.create(source=source,previous=previous,source_version=version,observed_at=at,availability=availability,
        fields=fields,evidence=evidence,source_sha256=evidence.sha256,actor=actor)
    event(actor,case,'delivery.progress.observed',observation=row.pk,evidence=evidence.pk);bump(case);return row


def observation_current(actor,row):
    source_for(actor,row.source.dossier.case,row.source_id)
    for action in ['delivery.progress.observe','evidence.add']:require(row.actor,row.source.dossier.case,action)
    if row.actor_id!=row.source.participant_id or row.evidence.created_by_id!=row.actor_id:raise ValidationError('Exact source participant provenance required')
    data={'protocol':PROTOCOL,'source_id':row.source_id,'source_version':row.source_version,'previous_id':row.previous_id,
        'observed_at':row.observed_at.isoformat(),'availability':row.availability,'fields':row.fields}
    if row.evidence.kind!=KIND or row.source_sha256!=row.evidence.sha256 or hashlib.sha256(row.evidence.body.encode()).hexdigest()!=row.source_sha256 or json.loads(row.evidence.body)!=data:
        raise ValidationError('Exact immutable source observation/hash required')
    if row.source.observations.order_by('-pk').first().pk!=row.pk:raise ValidationError('Source observation corrected; retain history and explicitly correlate the successor')
    return row


def freshness(row):
    seconds=row.source.max_age_seconds
    return 'unknown' if seconds is None else 'stale' if (timezone.now()-row.observed_at).total_seconds()>seconds else 'fresh'


def require_freshness(row):
    if freshness(row)=='stale':raise ValidationError('Source observation exceeds its explicit age threshold; capture current owner evidence')


def correlation_current(row,actor=None):
    actor=actor or row.actor;source=row.observation.source;case=source.dossier.case
    readable(actor,case);require(actor,case,'issue.read');observation_current(actor,row.observation);require_freshness(row.observation)
    require(row.actor,case,'delivery.manage');readable(row.actor,case);require(row.actor,case,'issue.read')
    if row.snapshot['pm_authority']!=decision_authority(row.actor,case,'PM'):raise ValidationError('PM correlation authority changed')
    if Correlation.objects.filter(observation__source=source).order_by('-pk').first().pk!=row.pk:raise ValidationError('Correlation replaced; retain the earlier decision')
    d=dossier_for(case,source.dossier_id)
    if approved_plan(d).pk!=row.planning_id or row.snapshot['baseline']!=d.baseline:raise ValidationError('Planning approval/baseline changed; explicit correlation required')
    state=row.issue_state;issue=current_issue(case,state.issue_id,state.pk)
    if not state_public(state):raise PermissionDenied('Current authoritative issue source is private')
    from apps.identity.models import Grant
    if not state.actor.is_active or not Grant.objects.filter(user=state.actor,case=case,action__in=['issue.manage','issue.work'],active=True).exists():raise PermissionDenied('Current issue source authority required')
    owned(case,state.owner_id)
    issue_subject(case,row.evidence_id)
    if row.profile_id:
        profile=row.profile
        if profile.state_id!=state.pk or EscalationProfile.objects.filter(state__issue=issue).order_by('-pk').first().pk!=profile.pk or profile.timeline_impact is not row.observation.fields['timeline_impact']:
            raise ValidationError('Exact current issue escalation profile required')
        require(profile.actor,case,'issue.escalate');issue_subject(case,profile.evidence_id)
    return row


@transaction.atomic
def correlate(actor,case_id,observation_id,previous_id,planning_id,issue_id,state_id,profile_id,impact,evidence_id,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);readable(actor,case);require(actor,case,'issue.read')
    row=Observation.objects.select_related('source__dossier__case','source__participant','source__actor','evidence').filter(pk=observation_id,source__dossier__case=case).first()
    if not row:raise ValidationError('Select this project exact observation')
    observation_current(actor,row);require_freshness(row);d=dossier_for(case,row.source.dossier_id);ensure_open(d)
    if row.availability!='available':raise ValidationError('Source unavailable/unknown; capture and investigate, do not invent plan impact')
    old=Correlation.objects.filter(observation__source=row.source).order_by('-pk').first()
    if previous_id!=(old.pk if old else None):raise ValidationError('STALE_VERSION: refresh current correlation')
    plan=approved_plan(d)
    if plan.pk!=planning_id:raise ValidationError('Select the exact current approved Planning record')
    issue=current_issue(case,issue_id,state_id)
    if not state_public(issue.current):raise PermissionDenied('Current authoritative issue source is private')
    owned(case,issue.current.owner_id)
    profile=None
    if profile_id:
        from .escalations import current_profile
        profile=current_profile(case,profile_id)
        if profile.state_id!=state_id or profile.timeline_impact is not row.fields['timeline_impact']:raise ValidationError('Escalation profile must match this issue state and explicit source timeline impact')
        require(profile.actor,case,'issue.escalate');issue_subject(case,profile.evidence_id)
    if row.fields['timeline_impact'] is True and profile is None:raise ValidationError('Timeline impact needs an explicit current native escalation profile; no severity or route is inferred')
    result=Correlation.objects.create(observation=row,previous=old,planning=plan,issue_state=issue.current,profile=profile,
        impact=bounded(impact,4000,'PM plan-impact interpretation'),snapshot={'baseline':d.baseline,'pm_authority':decision_authority(actor,case,'PM')},
        evidence=issue_subject(case,evidence_id),actor=actor)
    event(actor,case,'delivery.progress.correlated',correlation=result.pk);bump(case)
    if profile and row.fields['timeline_impact'] is True:
        from .escalations import scan_profile
        scan_profile(actor,case.pk,profile.pk)
    return result


def validate_profile_origin(profile):
    row=Correlation.objects.filter(profile=profile).first()
    if row:correlation_current(row)


def report(actor,dossier):
    readable(actor,dossier.case)
    sources=list(dossier.progress_sources.order_by('pk')[:101])
    if len(sources)>100:raise ValidationError('Narrow progress source scope: at most 100 sources per observation')
    rows=[]
    for source in sources:
        # A withdrawn source grant hides both the identifiers and private fields.
        source_authority(source)
        obs=source.observations.order_by('-pk').first()
        item={'source_id':source.pk,'team':source.team,'source_identity':source.source_identity,'source_ref':source.source_ref,
            'mode':source.mode,'source_authenticity_verified':False,'freshness':'unknown','correlation_status':'unlinked',
            'questions':['Ask the source participant for a current observation.']}
        if obs:
            observation_current(actor,obs)
            item.update(observation_id=obs.pk,source_version=obs.source_version,observed_at=obs.observed_at.isoformat(),availability=obs.availability,
                evidence_id=obs.evidence_id,source_sha256=obs.source_sha256,fields=obs.fields,freshness=freshness(obs),max_age_seconds=source.max_age_seconds,
                questions=['PM: link the exact approved plan and authoritative issue; retain the issue owner and next action.'])
            try:require(actor,dossier.case,'issue.read')
            except PermissionDenied:
                corr=None;item.update(correlation_status='restricted',questions=['Source capture remains available. Issue correlations require current issue read access.'])
            else:
                corr=Correlation.objects.filter(observation__source=source).order_by('-pk').first()
                if corr and (not state_public(corr.issue_state.issue.current) or not state_public(corr.issue_state)):
                    corr=None;item.update(correlation_status='restricted',questions=['Source capture remains available. Use the issue native scoped interface for private issue evidence.'])
            if corr:
                current=corr.issue_state.issue.current
                item.update(current_issue_state_id=current.pk,current_owner_id=current.owner_id,current_next_action=current.next_action)
                try:correlation_current(corr,actor);status='current';questions=[]
                except ValidationError as exc:status='stale';questions=[str(exc)]
                except PermissionDenied:status='stale';questions=['Correlation authority changed; obtain a current source-bound PM interpretation.']
                item.update(correlation_id=corr.pk,correlation_status=status,correlated_observation_id=corr.observation_id,
                    planning_id=corr.planning_id,baseline=corr.snapshot['baseline'],issue_id=corr.issue_state.issue_id,
                    issue_state_id=corr.issue_state_id,owner_id=corr.issue_state.owner_id,next_action=corr.issue_state.next_action,
                    impact=corr.impact,profile_id=corr.profile_id,questions=questions)
                if corr.profile_id:
                    from .escalations import timing
                    clock=timing(corr.profile);clock.pop('as_of');clock.pop('elapsed_hours')
                    historical=dict(clock) if status!='current' else None
                    if status!='current':
                        for key in ['immediate','active','internal_24h','internal_48h','client_24h']:clock[key]=False
                    item['escalation']=dict(clock,current=status=='current',historical_timing=historical,request_ids=list(corr.profile.requests.values_list('pk',flat=True)))
                    try:
                        require(actor,dossier.case,'document.read')
                    except PermissionDenied:pass
                    else:
                        from apps.documents.models import PublicationReceipt, PublicationJob
                        communications=[]
                        for request in corr.profile.requests.order_by('pk')[:101]:
                            if len(communications)==100:raise ValidationError('Narrow communication scope before reviewing more than 100 requests')
                            receipts=PublicationReceipt.objects.filter(publication__version__escalationdocumentbinding__request=request)
                            jobs=PublicationJob.objects.filter(publication__version__escalationdocumentbinding__request=request)
                            communications.append({'request_id':request.pk,'direction':request.direction,'target':request.target,
                                'decision_ids':list(request.decisions.values_list('pk',flat=True)),
                                'receipt_ids':list(receipts.values_list('pk',flat=True)),
                                'jobs':list(jobs.values('pk','status')),'current_correlation':status=='current'})
                        item['communications']=communications
            if freshness(obs)=='stale':item['questions'].append('Observation is stale under the explicit source threshold; capture current source evidence before correlation.')
            if obs.fields.get('scope_change') is True:item['questions'].append('Source reports scope change: use P56 change control, never rewrite the baseline from progress.')
            if obs.fields.get('timeline_impact') is None:item['questions'].append('Source timeline impact is unknown; obtain an explicit owner statement, not a guessed date.')
        rows.append(item)
    return {'sources':rows,'coverage':'at_most_100_explicit_source_streams','source_authenticity_verified':False,
        'approval_granted':False,'baseline_changed':False,'issue_resolution_verified':False,'communications_dispatched':False}


def optional_report(actor,dossier):
    try:return report(actor,dossier)
    except (PermissionDenied,ValidationError):return {'status':'restricted_or_stale','summary':'Open scoped progress tracking with current source and issue permissions.'}
