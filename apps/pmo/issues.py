from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.identity.models import Grant
from apps.policy.services import decision_authority
from apps.documents.contracts import validate
from .models import Issue, IssueState, IssueClosureEntry
from .commercial import note_required
from .issue_access import issue_subject as subject

SEVERITIES=['Critical','High','Medium','Low']


def owned(case,pk):
    user=get_user_model().objects.filter(pk=pk,is_active=True).first()
    if not user or not Grant.objects.filter(case=case,user=user,action='issue.own',active=True).exists():
        raise ValidationError('Every issue requires an active case-scoped responsible owner')
    return user


def links(case,values):
    validate({'type':'array','maxItems':20,'uniqueItems':True,'items':{'type':'object','properties':{
        'kind':{'enum':['risk','incident','change']},'source_ref':{'type':'string','minLength':1,'maxLength':240},
        'evidence_id':{'type':'integer','minimum':1}},'required':['kind','source_ref','evidence_id'],'additionalProperties':False}},values)
    for item in values:
        subject(case,item['evidence_id'],{'risk':'risk_reference','incident':'incident','change':'change_request'}[item['kind']])
    return values


def current_issue(case,pk,state_id):
    issue=Issue.objects.select_related('current').filter(case=case,pk=pk).first()
    if not issue or issue.current_id!=state_id:raise ValidationError('Select this case current issue state; refresh stale commands')
    return issue


def save_state(actor,case,issue,values):
    state=IssueState.objects.create(issue=issue,number=issue.states.count()+1,actor=actor,**values)
    issue.current=state;issue.save(update_fields=['current'])
    event(actor,case,'issue.updated',issue=issue.pk,state=state.pk,status=state.status)
    bump(case)
    return state


@transaction.atomic
def log_issue(actor,case_id,reference,title,kind,owner_id,next_action,evidence_id,note,expected,severity=None,external_links=None):
    case=lock_case(actor,case_id,'issue.manage',expected)
    if case.kind!='project' or not reference.strip() or len(reference)>160 or not title.strip() or len(title)>240 or not kind.strip() or len(kind)>100:
        raise ValidationError('A project, unique issue ID, title and type are required')
    if not next_action.strip() or len(next_action)>1000:raise ValidationError('Every issue needs an explicit next action')
    note_required(note)
    if severity is not None:
        if severity not in SEVERITIES:raise ValidationError('Use the source Critical/High/Medium/Low severity values')
        decision_authority(actor,case,'PM')
    if Issue.objects.filter(tenant=case.tenant,reference=reference).exists():
        raise ValidationError('Issue identity already exists in this tenant; link the authoritative record instead of duplicating')
    issue=Issue.objects.create(case=case,tenant=case.tenant,reference=reference)
    return save_state(actor,case,issue,{'title':title,'kind':kind,'severity':severity,'owner':owned(case,owner_id),
        'next_action':next_action,'status':'Open','acknowledged_at':None,'resolved_at':None,
        'evidence':subject(case,evidence_id),'fix':None,'root_cause':None,'external_links':links(case,external_links or []),'note':note})


@transaction.atomic
def update_issue(actor,case_id,issue_id,state_id,operation,evidence_id,note,expected,next_action=None,owner_id=None,severity=None,fix_id=None,root_cause_id=None):
    case=lock_case(actor,case_id,'issue.manage' if operation=='manage' else 'issue.work',expected)
    issue=current_issue(case,issue_id,state_id);old=issue.current
    if old.status=='Closed':raise ValidationError('Closed history is preserved; reopen policy is not configured')
    note_required(note)
    values={k:getattr(old,k) for k in ['title','kind','severity','owner','next_action','status','acknowledged_at','resolved_at','fix','root_cause','external_links']}
    values.update(evidence=subject(case,evidence_id),note=note)
    if next_action is not None:
        if not next_action.strip() or len(next_action)>1000:raise ValidationError('An explicit next action is required')
        values['next_action']=next_action
    if operation=='manage':
        if owner_id is not None:values['owner']=owned(case,owner_id)
        if severity is not None:
            if severity not in SEVERITIES:raise ValidationError('Unknown severity')
            decision_authority(actor,case,'PM');values['severity']=severity
    else:
        if owner_id is not None or severity is not None:
            raise ValidationError('Owner reassignment and PM severity are separate manager operations')
        owned(case,old.owner_id)
        if actor.pk!=old.owner_id:raise ValidationError('Only the current responsible owner records work progress')
        if old.status not in ['Open','In Progress']:raise ValidationError('Resolved work awaits QA and PM closure log updates')
        if operation=='acknowledge':
            if old.acknowledged_at:raise ValidationError('Already acknowledged')
            values['acknowledged_at']=timezone.now()
        elif operation in ['start','progress','resolve']:
            if not old.acknowledged_at:raise ValidationError('Record owner acknowledgement first')
            values['status']='In Progress'
            if operation=='resolve':
                if not old.severity:raise ValidationError('PM must set severity before resolution')
                values['fix']=subject(case,fix_id,'resolution')
                values['root_cause']=subject(case,root_cause_id,'root_cause') if root_cause_id else old.root_cause
                if old.severity=='Critical' and not values['root_cause']:raise ValidationError('Critical issues require documented root cause')
                values['status']='Resolved';values['resolved_at']=timezone.now()
        else:raise ValidationError('Unsupported issue operation')
    return save_state(actor,case,issue,values)


@transaction.atomic
def close_issue_log(actor,case_id,issue_id,state_id,role,evidence_id,note,expected):
    case=lock_case(actor,case_id,'issue.close_log',expected)
    issue=current_issue(case,issue_id,state_id);state=issue.current
    if role not in ['QA','PM'] or state.status!='Resolved':raise ValidationError('QA and PM log updates close a resolved issue; no separate approval task')
    decision_authority(actor,case,role)
    note_required(note)
    if IssueClosureEntry.objects.filter(state=state,role=role).exists():raise ValidationError('This role already updated the closure log for this exact resolution')
    result=IssueClosureEntry.objects.create(state=state,role=role,evidence=subject(case,evidence_id),note=note,actor=actor)
    event(actor,case,'issue.closure_log',issue=issue.pk,entry=result.pk,role=role)
    if set(state.closure_entries.values_list('role',flat=True))=={'QA','PM'}:
        values={k:getattr(state,k) for k in ['title','kind','severity','owner','next_action','acknowledged_at','resolved_at','fix','root_cause','external_links']}
        values.update(status='Closed',evidence=result.evidence,note='QA and PM closure log updates completed')
        save_state(actor,case,issue,values)
    else:bump(case)
    return result

@transaction.atomic
def reopen_issue(actor,case_id,issue_id,state_id,role,evidence_id,note,next_action,expected):
    case=lock_case(actor,case_id,'issue.reopen',expected)
    issue=current_issue(case,issue_id,state_id);state=issue.current
    if state.status!='Closed':raise ValidationError('Only closed issues use the configured reopen operation')
    if not next_action.strip() or len(next_action)>1000:raise ValidationError('Reopened work needs an explicit next action')
    note_required(note)
    authority=decision_authority(actor,case,role,'reopen')
    values={k:getattr(state,k) for k in ['title','kind','severity','owner','external_links']}
    owned(case,state.owner_id)
    values.update(status='Open',acknowledged_at=None,resolved_at=None,fix=None,root_cause=None,
        evidence=subject(case,evidence_id),note=note,next_action=next_action)
    result=save_state(actor,case,issue,values)
    event(actor,case,'issue.reopened',state=result.pk,previous=state.pk,role=role,authority=authority)
    return result
