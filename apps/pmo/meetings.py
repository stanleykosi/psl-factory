from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import validate
from apps.policy.services import active_component, reference_values
from .services import subject
from .models import Meeting, MeetingVersion, ActionItem, ActionState, MeetingActionLink
from .clocks import aware, calculate_action_due

MEETING_KINDS=['alignment','kickoff','status','retrospective','other']


def scoped_person(case,user_id,action):
    if user_id is None:return None
    if type(user_id) is not int:raise ValidationError('Use an authenticated internal person reference')
    person=get_user_model().objects.filter(pk=user_id,is_active=True).first()
    if not person or not Grant.objects.filter(case=case,user=person,action=action,active=True).exists():
        raise ValidationError('Person lacks this case participation/ownership grant')
    return person


@transaction.atomic
def record_meeting(actor,case_id,reference,kind,occurred_at,purpose,summary,participant_ids,decisions,evidence_id,expected,meeting_id=None):
    case=lock_case(actor,case_id,'meeting.record',expected)
    occurred_at=aware(occurred_at,'Meeting time')
    if case.kind!='project' or kind not in MEETING_KINDS or not reference.strip() or len(reference)>160 or not purpose.strip() or len(purpose)>240 or not summary.strip() or len(summary)>16000:
        raise ValidationError('Meeting needs a project, reference, kind, purpose and bounded source-backed summary')
    validate({'type':'array','maxItems':50,'uniqueItems':True,'items':{'type':'integer','minimum':1}},participant_ids)
    for pk in participant_ids:scoped_person(case,pk,'meeting.participate')
    validate({'type':'array','maxItems':50,'items':{'type':'object','properties':{
        'text':{'type':'string','minLength':1,'maxLength':2000},'evidence_id':{'type':'integer','minimum':1},
        'change_evidence_id':{'type':['integer','null'],'minimum':1}},'required':['text','evidence_id'],'additionalProperties':False}},decisions)
    evidence=subject(case,evidence_id)
    for decision in decisions:
        subject(case,decision['evidence_id'])
        if decision.get('change_evidence_id'):subject(case,decision['change_evidence_id'],'change_request')
    if meeting_id:
        meeting=Meeting.objects.filter(case=case,pk=meeting_id,reference=reference).first()
        if not meeting:raise ValidationError('Revision must identify the same case meeting')
        number=meeting.versions.count()+1
    else:
        if Meeting.objects.filter(case=case,reference=reference).exists():raise ValidationError('Meeting reference exists; create a new revision')
        meeting=Meeting.objects.create(case=case,reference=reference);number=1
    version=MeetingVersion.objects.create(meeting=meeting,number=number,kind=kind,occurred_at=occurred_at,purpose=purpose,summary=summary,
        participant_ids=participant_ids,decisions=decisions,evidence=evidence,created_by=actor)
    meeting.current=version;meeting.save(update_fields=['current'])
    event(actor,case,'meeting.recorded',meeting=meeting.pk,version=version.pk,scope_changed=False)
    bump(case)
    return version


@transaction.atomic
def create_action(actor,case_id,reference,description,owner_id,due_at,evidence_id,reason,expected,meeting_id=None,calculated=False,change_evidence_id=None):
    case=lock_case(actor,case_id,'action.manage',expected)
    if not reference.strip() or len(reference)>160 or not description.strip() or len(description)>1000 or not reason.strip() or len(reason)>4000:
        raise ValidationError('Action needs a bounded reference, description and source rationale')
    if ActionItem.objects.filter(case=case,reference=reference).exists():raise ValidationError('Action reference already exists')
    meeting=Meeting.objects.filter(case=case,pk=meeting_id).first() if meeting_id else None
    if meeting_id and not meeting:raise ValidationError('Meeting is outside this project')
    owner=scoped_person(case,owner_id,'action.own');evidence=subject(case,evidence_id)
    change=subject(case,change_evidence_id,'change_request') if change_evidence_id else None
    policies={};clock_meta={};basis='explicit'
    if calculated:
        if due_at is not None:raise ValidationError('Choose an explicit deadline or a calculated deadline, not both')
        due_at,policies,clock_meta=calculate_action_due(case,meeting.current.occurred_at if meeting else None,timezone.now());basis='calculated'
        clock_meta['meeting_version']=meeting.current_id if meeting else None
    elif due_at is not None:due_at=aware(due_at,'Action deadline')
    item=ActionItem.objects.create(case=case,meeting=meeting,reference=reference)
    state=ActionState.objects.create(item=item,number=1,description=description,owner=owner,due_at=due_at,due_basis=basis,clock_meta=clock_meta,
        policies=policies,evidence=evidence,change_evidence=change,reason=reason,actor=actor)
    item.current=state;item.save(update_fields=['current'])
    if meeting:MeetingActionLink.objects.create(meeting=meeting,item=item,evidence=evidence,actor=actor)
    event(actor,case,'action.recorded',item=item.pk,state=state.pk,owner=owner_id,due_at=due_at.isoformat() if due_at else None,policies=policies,scope_changed=False)
    bump(case)
    return item


@transaction.atomic
def change_action(actor,case_id,item_id,operation,evidence_id,reason,expected,expected_action,owner_id=None,due_at=None):
    management=operation in ['assign','reopen','cancel']
    case=lock_case(actor,case_id,'action.manage' if management else 'action.work',expected)
    item=ActionItem.objects.select_related('current').filter(case=case,pk=item_id).first()
    if not item or item.current.number!=expected_action:raise ValidationError('Unknown action or stale action revision')
    old=item.current;evidence=subject(case,evidence_id)
    if not reason.strip() or len(reason)>4000:raise ValidationError('An action change needs evidence and a bounded reason')
    if not management:
        if old.owner_id!=actor.pk:raise PermissionDenied('Only the current action owner can perform this work transition')
        require(actor,case,'action.own')
    data={key:getattr(old,key) for key in ['description','owner','due_at','due_basis','clock_meta','status','paused_at','policies','change_evidence']}
    if operation=='assign' and old.status not in ['completed','cancelled']:
        data.update(owner=scoped_person(case,owner_id,'action.own'),due_at=aware(due_at,'Action deadline') if due_at is not None else None,
            due_basis='explicit',status='open',paused_at=None,policies={},clock_meta={})
    elif operation=='start' and old.status=='open':data['status']='in_progress'
    elif operation=='complete' and old.status in ['open','in_progress']:
        data.update(status='completed',paused_at=None)
    elif operation=='cancel' and old.status not in ['completed','cancelled']:data.update(status='cancelled',paused_at=None)
    elif operation=='reopen' and old.status in ['completed','cancelled']:data.update(status='open',paused_at=None)
    elif operation=='pause' and old.status in ['open','in_progress']:
        config=active_component('D04.clock_anchor_pause_rules',case);rules=reference_values(config)[0]
        behavior=rules.get('pause_behavior')
        if behavior not in ['no_extension','extend_elapsed']:raise ValidationError('D04 pause behavior is unconfigured or not permitted')
        data.update(status='paused',paused_at=timezone.now(),policies=dict(old.policies,**{config.component:config.pk}),clock_meta=dict(old.clock_meta,pause_behavior=behavior))
    elif operation=='resume' and old.status=='paused':
        config=active_component('D04.clock_anchor_pause_rules',case);behavior=reference_values(config)[0].get('pause_behavior')
        if old.policies.get(config.component)!=config.pk or behavior!=old.clock_meta.get('pause_behavior'):
            raise ValidationError('Pause policy changed; a manager must explicitly reset the commitment and deadline')
        due=old.due_at
        if behavior=='extend_elapsed' and due:due=due+(timezone.now()-old.paused_at)
        data.update(status='in_progress',paused_at=None,due_at=due)
    else:raise ValidationError('Unsupported action transition for its current status')
    state=ActionState.objects.create(item=item,number=old.number+1,actor=actor,evidence=evidence,reason=reason,**data)
    item.current=state;item.save(update_fields=['current'])
    event(actor,case,'action.'+operation,item=item.pk,state=state.pk,prior_state=old.pk)
    bump(case)
    return state


def action_timing(state,at=None):
    at=at or timezone.now()
    if state.status in ['completed','cancelled']:return 'CLOSED'
    if state.due_at is None:return 'UNKNOWN'
    if state.status=='paused' and state.clock_meta.get('pause_behavior')=='extend_elapsed':return 'PAUSED'
    return 'OVERDUE' if at>state.due_at else 'NOT_DUE'


@transaction.atomic
def link_action(actor,case_id,meeting_id,item_id,evidence_id,expected):
    case=lock_case(actor,case_id,'meeting.record',expected)
    meeting=Meeting.objects.filter(case=case,pk=meeting_id).first()
    item=ActionItem.objects.filter(case=case,pk=item_id).first()
    evidence=subject(case,evidence_id)
    if not meeting or not item:raise ValidationError('Meeting and existing commitment must belong to this project')
    if MeetingActionLink.objects.filter(meeting=meeting,item=item).exists():raise ValidationError('Commitment is already linked to this meeting')
    link=MeetingActionLink.objects.create(meeting=meeting,item=item,evidence=evidence,actor=actor)
    event(actor,case,'meeting.action_linked',meeting=meeting.pk,item=item.pk,link=link.pk)
    bump(case)
    return link


def meeting_actions(meeting):
    return ActionItem.objects.filter(meetingactionlink__meeting=meeting).select_related('current').order_by('pk')
