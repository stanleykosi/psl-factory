"""P50/P51/P54/P55 scoped investigation and native owner follow-up, not issue closure."""
import hashlib,json
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from apps.core.models import Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.read_observation import read_observation
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from apps.pmo.models import Issue
from apps.pmo.issue_access import state_public
from apps.pmo import issue_references as refs
from apps.pmo.issues import update_issue,owned
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask,TaskEvent
from .factory_delivery import investigation_key

DEFINITION='pmo-issues/v1'
KIND='agent_private_issue_intake'
PROTOCOL='factory-issue-intake/v1'
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'issue_id':{'type':'integer','minimum':1},'state_id':{'type':'integer','minimum':1},'reference_revision_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}},'required':['protocol','issue_id','state_id','reference_revision_id'],'additionalProperties':False}


def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)


def inputs(actor,case,issue_id):
    require(actor,case,'issue.read')
    issue=Issue.objects.select_related('case','current__owner').filter(pk=issue_id,case=case).first()
    if not issue or not issue.current or not state_public(issue.current):raise ValidationError('Select a current public native issue')
    report=refs.report(actor,issue)
    return issue,{'protocol':PROTOCOL,'issue_id':issue.pk,'state_id':issue.current_id,'reference_revision_id':report['revision_id']}


def capture(actor,case,data,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e


def source(work,actor=None,current=True):
    actor=actor or work.execution_actor
    require(actor,work.case,'issue.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact native issue intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed issue source required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.issue_intake','factory.issue_source','factory.issue_owner_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or data['issue_id']!=work.request['issue_id']:raise ValidationError('Exact issue intake provenance required')
    issue,now=inputs(actor,work.case,data['issue_id'])
    if current and now!=data:raise ValidationError('STALE_VERSION: issue or reference head changed; explicitly adopt the current source')
    if current:
        for action in ['case.read','issue.read','evidence.add',{'factory.issue_intake':'factory.start','factory.issue_source':'factory.manage','factory.issue_owner_source':'issue.work'}[audit.action]]:require(e.created_by,work.case,action)
    return issue,data


@transaction.atomic
def start(actor,case_id,key,issue_id,expected):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION)
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100:raise ValidationError('Bounded work identity required')
    issue,data=inputs(actor,case,issue_id)
    payload={'issue_id':issue.pk};business=digest([str(case.pk),DEFINITION,issue.pk]);sha=digest(payload)
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: correct the existing issue investigation')
        source(old,actor,False);return old
    if issue.current.status not in ['Open','In Progress']:raise ValidationError('Owner follow-up starts on active issues; resolved or closed issues retain their native closure and reopen flow')
    work=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,case,data,'factory.issue_intake'))
    event(actor,case,'factory.started',work=work.pk,definition=DEFINITION);return work


def report(work,actor=None,max_age_seconds=None):
    issue,data=source(work,actor);s=issue.current
    reference=refs.report(actor or work.execution_actor,issue,max_age_seconds)
    gaps=[]
    if not s.acknowledged_at:gaps.append('Owner acknowledgement is not recorded')
    if not s.severity:gaps.append('PM severity classification is not recorded')
    if s.severity=='Critical' and not s.root_cause_id:gaps.append('Critical root-cause evidence is not recorded')
    for r in reference['references']:
        if r['availability']!='available':gaps.append(f"{r['kind']} {r['source_ref']}: source availability is {r['availability']}")
        if r['currentness']!='current':gaps.append(f"{r['kind']} {r['source_ref']}: {r['currentness']} source observation")
        if r['freshness']=='stale':gaps.append(f"{r['kind']} {r['source_ref']}: configured observation age exceeded")
    from apps.pmo.issue_teams import projection as team_projection
    team = team_projection(actor or work.execution_actor, issue)
    owner = {'mode':team['mode'],'status':team['status'],'label':team['label']}
    if team['assignment']:
        owner.update(assignment_id=team['assignment'].pk, recorder_id=team['assignment'].recorder_id,
                     policy_id=team['assignment'].policy_id)
    if team.get('finding'):gaps.append(team['finding'])
    return {'issue_id':issue.pk,'state_id':s.pk,'owner_id':s.owner_id,'status':s.status,'severity':s.severity,'acknowledged':s.acknowledged_at is not None,'acknowledged_at':s.acknowledged_at.isoformat() if s.acknowledged_at else None,'resolved_at':s.resolved_at.isoformat() if s.resolved_at else None,'fix_evidence_id':s.fix_id,'root_cause_evidence_id':s.root_cause_id,'next_action':s.next_action,'evidence_id':s.evidence_id,'references':reference,'gaps':gaps,'sla_evaluated':False,'severity_mapping_inferred':False,'issue_resolution_verified':False,'external_lifecycle_changed':False,'owner_context':owner}


def tasks(work):return HumanTask.objects.filter(case=work.case,kind='issue_followup',factory_key__startswith=f'factory:{work.pk}:').order_by('pk')


def response(work):
    return TaskEvent.objects.filter(task__in=tasks(work),action='issue.owner_response',data__head=work.source_head_id).order_by('-pk').first()


def investigation(work,state):
    attempts = Attempt.objects.filter(activity__work=work,activity__kind='ACT04',phase='observed')
    exact = attempts.filter(activity__key=investigation_key(work,state)).order_by('-pk').first()
    if exact:
        return exact
    # Earlier releases included display labels in the native projection. Keep
    # their immutable keys and reconstruct every source/check pin exactly.
    for attempt in attempts.filter(result__head=work.source_head_id).select_related('activity').order_by('-pk')[:2]:
        observed = attempt.result.get('investigation')
        if not isinstance(observed,dict) or canonical_report(observed) != canonical_report(state['native']):
            continue
        previous = dict(state,native=observed)
        if attempt.activity.key == investigation_key(work,previous):
            return attempt
    return None


def canonical_report(value):
    """Normalise known presentation-only additions while retaining authority pins."""
    result = dict(value)
    result['gaps'] = ['PM severity classification is not recorded' if gap ==
        'Project manager severity assessment is not recorded' else gap for gap in value.get('gaps',[])]
    owner = dict(value.get('owner_context') or {})
    owner.pop('label',None)
    if owner == {'mode':'internal','status':'current'}:
        owner = {}
    result.pop('owner_context',None)
    if owner:
        result['owner_context'] = owner
    return result


@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    issue,data=source(work,actor);n=report(work,actor,value.get('reference_max_age_seconds'))
    latest={KIND:work.source_head,'issue_evidence':issue.current.evidence}
    if issue.current.fix_id:latest['issue_fix']=issue.current.fix
    if issue.current.root_cause_id:latest['issue_root_cause']=issue.current.root_cause
    # Never pass raw supplied readback bodies to the coordinator. The scoped findings are the read projection.
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    ts=list(tasks(work));r=response(work)
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'native':n,'checks':{'reference_head':data['reference_revision_id'],'response':r.pk if r else None},'tasks':[(t.pk,t.status,t.revision) for t in ts]}
    state['hash']=digest(state);state['work_revision']=work.revision
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    return state,latest,missing,stale,ts,[]


def eligible(work,value,state,latest,missing,stale,ts,jobs):
    if missing or stale:return [],'Current configured intake sources required: '+', '.join(missing+stale)
    if state['native']['status'] not in ['Open','In Progress']:return [],'Continue resolved or closed issues through the native closure/reopen flow; stop this owner follow-up if no longer needed'
    if not investigation(work,state):return ['ACT04'],'Investigate the current issue and available source evidence'
    if state['native']['owner_context']['mode']=='team' and state['native']['owner_context']['status']!='current':
        return [],'Choose the team and its follow-up coordinator'
    if response(work):return ['ACT13'],'Verify the current investigation and recorded owner response'
    if any(t.status=='open' for t in ts):return [],'Waiting for the owner’s update'
    return ['ACT05'],'Request the owner’s update'


def act(work,choice,value,latest,missing,ts,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: sources changed')
    issue,data=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        require(work.execution_actor,case,'agent.issues')
        return {'head':work.source_head_id,'investigation':report(work,work.execution_actor,value.get('reference_max_age_seconds')),'issue_resolution_verified':False}
    if kind=='ACT05':
        owner=owned(case,issue.current.owner_id)
        for action in ['case.read','issue.read','issue.work','evidence.add']:require(owner,case,action)
        refs.report(owner,issue)
        row,created=HumanTask.objects.get_or_create(factory_key=f'factory:{work.pk}:issue:{work.source_head_id}',defaults={'case':case,'kind':'issue_followup','required_role':'Issue owner','created_by':work.execution_actor,'context':{'work':work.pk,'head':work.source_head_id,'issue_id':issue.pk,'state_id':issue.current_id,'owner_id':owner.pk}})
        if created:TaskEvent.objects.create(task=row,actor=work.execution_actor,action='issue.followup_opened',data={'work':work.pk,'head':work.source_head_id})
        return {'head':work.source_head_id,'task':row.pk,'waiting':'Waiting for the responsible issue owner; no approval was requested'}
    if kind=='ACT13':
        result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Issue severity, closure and external lifecycle decisions are not agent tools')


def verify(work,actor=None):
    from .factory import profile
    _,value=profile(work,recovery=True);state,*_=snapshot(work,value,reader=actor or work.execution_actor)
    if any(r['currentness']=='superseded' for r in state['native']['references']['references']):raise ValidationError('Correct superseded external source references before verification')
    step=investigation(work,state);reply=response(work)
    if not step or not reply or reply.task.status!='completed':raise ValidationError('Current scoped investigation and exact native owner follow-up required')
    issue,_=source(work,actor);require(reply.actor,work.case,'issue.work');owned(work.case,issue.current.owner_id)
    if reply.actor_id!=issue.current.owner_id or reply.data['state_id']!=issue.current_id:raise ValidationError('Current issue owner and exact response state required')
    from apps.pmo.issue_teams import latest as latest_team, validate_reply
    from apps.pmo.issue_team_models import IssueTeamReply
    assignment = latest_team(issue)
    if assignment and assignment.mode == 'team':
        external = IssueTeamReply.objects.select_related('assignment__recorder', 'state').filter(
            assignment=assignment, state_id=issue.current_id, actor_id=reply.actor_id).first()
        if external is None:
            raise ValidationError('An exact evidenced external team response is required.')
        validate_reply(external, issue)
    return {'verified':True,'verification_scope':'issue_investigation_and_owner_followup','head':work.source_head_id,'issue_id':issue.pk,'state_id':issue.current_id,'investigation_attempt':step.pk,'owner_response':reply.pk,'issue_resolution_verified':False,'external_lifecycle_changed':False}


def locked(actor,work_id,expected,case_expected,action):
    from .factory import access
    work=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,'factory.read',DEFINITION);work.case=lock_case(actor,work.case_id,action,case_expected)
    if work.revision!=expected:raise ValidationError('Refresh the current work revision')
    from django.utils import timezone
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('Wait for the current worker to stop')
    from apps.agents.factory_coordinator import pending,has_receipt
    p=pending(work)
    if p and not has_receipt(p):raise ValidationError('Reconcile the original uncertain planning effect before source changes')
    return work


@transaction.atomic
def respond(actor,work_id,expected,case_expected,task_id,task_revision,operation,evidence_id,note,next_action,*,team_reply=None):
    work=locked(actor,work_id,expected,case_expected,'issue.work')
    if work.cancel_requested or work.status in ['cancelled','verified','followup_needed']:raise ValidationError('Stopped or verified work cannot accept a new response')
    issue,_=source(work,actor)
    task=tasks(work).select_for_update().filter(pk=task_id,revision=task_revision,status='open').first()
    if not task or task.context!={'work':work.pk,'head':work.source_head_id,'issue_id':issue.pk,'state_id':issue.current_id,'owner_id':issue.current.owner_id} or actor.pk!=issue.current.owner_id:raise ValidationError('Only the current responsible owner may answer this exact follow-up')
    if operation not in ['acknowledge','start','progress']:raise ValidationError('Use native issue flows for resolution, severity or closure')
    from apps.pmo import issue_teams
    assignment = issue_teams.latest(issue)
    if assignment and assignment.mode == 'team':
        required = {'assignment_id','operation_key','party','channel','responded_at','source_ref'}
        if not isinstance(team_reply,dict) or set(team_reply)!=required:
            raise ValidationError('Record the actual external responder, source proof and reply time.')
        external = issue_teams.record_reply(actor,work.case_id,issue.pk,issue.current_id,
            team_reply['assignment_id'],team_reply['operation_key'],operation,evidence_id,note,next_action,
            team_reply['party'],team_reply['channel'],team_reply['responded_at'],team_reply['source_ref'],work.case.revision)
        state = external.state
    else:
        if team_reply is not None:raise ValidationError('This issue uses a named factory-account owner.')
        state=update_issue(actor,work.case_id,issue.pk,issue.current_id,operation,evidence_id,note,work.case.revision,next_action=next_action)
    work.case.refresh_from_db();_,data=inputs(actor,work.case,issue.pk)
    work.source_head=capture(actor,work.case,data,'factory.issue_owner_source')
    task.status='completed';task.revision+=1;task.save(update_fields=['status','revision'])
    TaskEvent.objects.create(task=task,actor=actor,action='issue.owner_response',data={'work':work.pk,'head':work.source_head_id,'state_id':state.pk,'evidence_id':evidence_id})
    work.status='ready';work.finding='';work.revision+=1;work.save()
    from .factory_progress import wake_waiting
    wake_waiting(work.pk)
    return work


@transaction.atomic
def refresh(actor,work_id,expected,case_expected,reason,restart=False):
    work=locked(actor,work_id,expected,case_expected,'factory.manage')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the explicit source reassessment')
    if work.cancel_requested and not (restart and work.status=='cancelled'):raise ValidationError('Settle cancellation before explicitly restarting')
    issue,data=inputs(actor,work.case,work.request['issue_id'])
    for t in tasks(work).select_for_update().filter(status='open'):
        TaskEvent.objects.create(task=t,actor=actor,action='issue.source_superseded',data={'reason':reason});t.status='returned';t.revision+=1;t.save(update_fields=['status','revision'])
    work.source_head=capture(actor,work.case,data,'factory.issue_source');work.status='ready';work.cancel_requested=False;work.finding='';work.revision+=1;work.save()
    event(actor,work.case,'factory.issue_reassessed',work=work.pk,head=work.source_head_id,reason=reason);return work


@transaction.atomic
def request_update(actor, work_id, expected, case_expected, background):
    """A new human request starts another exact follow-up within the original allowance."""
    if any(type(value) is not int or value < 1 for value in [work_id, expected, case_expected]):
        raise ValidationError('Use the exact current work and project revisions.')
    if type(background) is not bool:
        raise ValidationError('Choose whether to continue this update in the background.')
    work = locked(actor, work_id, expected, case_expected, 'factory.manage')
    if work.status != 'verified' or work.cancel_requested:
        raise ValidationError('Finish or recover the current follow-up before requesting another update.')
    issue, _ = inputs(actor, work.case, work.request['issue_id'])
    if issue.current.status not in {'Open', 'In Progress'}:
        raise ValidationError('Use the issue register for resolution and closure.')
    work = refresh(actor, work.pk, work.revision, work.case.revision,
                   'Requested another update from the current issue owner.')
    if background:
        from .factory_progress import set_progress
        set_progress(actor, work.pk, work.revision, True)
    return work


@transaction.atomic
def sync_owner(work_id):
    """Adopt only the exact source update requested by a human owner assignment."""
    from apps.pmo import issue_teams
    from apps.pmo.issue_team_models import IssueTeamAssignment
    from apps.agents.factory_coordinator import pending, has_receipt
    from .factory import access

    work = Work.objects.select_for_update(of=('self',), skip_locked=True).select_related('case', 'actor').filter(
        pk=work_id, definition=DEFINITION).first()
    if work is None or work.cancel_requested or work.status in {'verified', 'cancelled', 'followup_needed'}:
        return False
    assignment = IssueTeamAssignment.objects.select_related('actor', 'issue').filter(
        auto_work=work, requested_source_id=work.source_head_id).order_by('-number').first()
    if assignment is None:
        return False
    if work.lease_until and work.lease_until > timezone.now():
        return False
    outstanding = pending(work)
    if outstanding and not has_receipt(outstanding):
        return False
    case = lock_case(assignment.actor, work.case_id, 'factory.manage')
    access(assignment.actor, case, 'factory.read', DEFINITION)
    require(assignment.actor, case, 'issue.manage')
    require(assignment.actor, case, 'evidence.add')
    issue, data = inputs(assignment.actor, case, assignment.issue_id)
    if issue_teams.latest(issue).pk != assignment.pk or data != assignment.work_input:
        return False
    if assignment.mode == 'team' and assignment.team_key:
        issue_teams.current(assignment, issue)
    refresh(assignment.actor, work.pk, work.revision, case.revision,
            'Owner assignment ' + str(assignment.number) + '. ' + assignment.reason)
    from .factory_progress import wake_waiting
    wake_waiting(work.pk)
    return True


def projection(actor,work):
    from .factory import profile
    issue,data=source(work,actor,False);message='';changed=False;options=[];n=None;latest=None
    try:
        _,value=profile(work,recovery=True);state,*rest=snapshot(work,value,reader=actor);n=state['native'];options,message=eligible(work,value,state,*rest);latest=investigation(work,state)
        if work.status=='verified':verify(work,actor)
    except (ValidationError,PermissionDenied) as exc:message=finding(exc);changed=work.status=='verified'
    ts=list(tasks(work))
    owner_actions=set(Grant.objects.filter(case=work.case,user_id=issue.current.owner_id,user__is_active=True,
        active=True,action__in=['issue.own','issue.work']).values_list('action',flat=True))
    owner_available=owner_actions=={'issue.own','issue.work'}
    from apps.pmo.issue_teams import projection as team_projection
    team = team_projection(actor, issue)
    return {'issue':issue,'native':n,'finding':message,'readiness_changed':changed,'options':options,'tasks':ts,
        'owner_available':owner_available,'investigation':latest.result if latest else None,
        'can_respond':owner_available and actor.pk==issue.current.owner_id and not work.cancel_requested,
        'reference_head':data['reference_revision_id'],'team':team}
