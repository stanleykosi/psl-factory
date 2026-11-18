"""Team ownership preserves the factory coordinator and the actual external responder."""
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from adapters.issue_team import reply_facts
from apps.core.services import event, lock_case
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.issue_team_validators import COMPONENT, validate_value
from apps.policy.services import active_component, reference_values, role_policy

from . import issues
from .issue_access import issue_subject, state_public
from .issue_team_models import IssueTeamAssignment, IssueTeamReply
from .issue_models import Issue


def latest(issue):
    return issue.team_assignments.select_related('recorder', 'policy').order_by('-number').first()


def rules(case):
    configuration = active_component(COMPONENT, case)
    value = reference_values(configuration)[0]
    validate_value(value, configuration.envelope['value']['schema_ref'])
    return configuration, value


def resolution_authority(actor, case, role, value):
    if role not in value.get('resolution_recorder_roles', []):
        raise PermissionDenied('A configured resolution recorder must record the team fix.')
    policy = role_policy(actor, case, role)
    return {'protocol': 'issue-team-resolution-authority/v1', 'role': role,
            'policies': {policy.component: policy.pk}}


def recorder_authority(actor, case, role, value):
    for action in ['case.read', 'issue.read', 'issue.own', 'issue.work', 'evidence.add', 'factory.read']:
        require(actor, case, action)
    if role not in value['recorder_roles']:
        raise PermissionDenied('This role is outside the configured team-response recorders.')
    policy = role_policy(actor, case, role)
    return {policy.component: policy.pk}


def current(assignment, issue):
    if latest(issue).pk != assignment.pk or issue.current.owner_id != assignment.recorder_id:
        raise ValidationError('Review the current team and follow-up coordinator.')
    if assignment.mode != 'team' or not assignment.team_key:
        raise ValidationError('Choose the external owner before recording its response.')
    configuration, value = rules(issue.case)
    team = next((team for team in value['teams'] if team['key'] == assignment.team_key), None)
    if (configuration.pk != assignment.policy_id or team is None or team['label'] != assignment.team_label or
        recorder_authority(assignment.recorder, issue.case, assignment.recorder_role, value) != assignment.authority):
        raise ValidationError('Team or recorder authority changed. Review the assignment first.')
    proof = issue_subject(issue.case, assignment.evidence_id)
    for action in ['case.read', 'evidence.add']:
        require(proof.created_by, issue.case, action)
    for action in ['case.read', 'issue.read', 'issue.manage']:
        require(assignment.actor, issue.case, action)
    return value


@transaction.atomic
def assign(actor, case_id, issue_id, state_id, mode, team_key, recorder_id, recorder_role,
           evidence_id, reason, expected, *, work_id=None, source_id=None):
    if any(type(value) is not int or value < 1 for value in [issue_id, state_id, recorder_id, evidence_id, expected]):
        raise ValidationError('Use exact current issue, evidence and coordinator references.')
    work = None
    if work_id is not None:
        from apps.workflows import factory, factory_issues
        from apps.workflows.models import FactoryWork

        if any(type(value) is not int or value < 1 for value in [work_id, source_id]):
            raise ValidationError('Use the exact current investigation and source.')
        work = FactoryWork.objects.select_for_update(of=('self',), skip_locked=True).filter(
            pk=work_id, case_id=case_id, definition=factory_issues.DEFINITION).first()
        if work is None:
            raise ValidationError('The investigation is busy or unavailable. Reload its owner settings.')
    elif source_id is not None:
        raise ValidationError('A source update needs its exact investigation.')
    case = lock_case(actor, case_id, 'issue.manage', expected)
    require(actor, case, 'issue.read')
    issue = issues.current_issue(case, issue_id, state_id)
    if not state_public(issue.current) or issue.current.status == 'Closed':
        raise ValidationError('Choose an open, readable issue for owner assignment.')
    if mode not in {'team', 'internal'} or not isinstance(team_key, str):
        raise ValidationError('Choose an external team or a factory account.')
    issues.note_required(reason)
    if len(reason) > 2000:
        raise ValidationError('Keep the assignment reason within two thousand characters.')
    proof = issue_subject(case, evidence_id)
    require(proof.created_by, case, 'case.read')
    require(proof.created_by, case, 'evidence.add')
    recorder = issues.owned(case, recorder_id)
    if work is not None:
        if (work.request.get('issue_id') != issue.pk or work.source_head_id != source_id or
                work.cancel_requested or work.status in {'verified', 'cancelled', 'followup_needed'}):
            raise ValidationError('Open the current issue investigation before changing its owner.')
        factory.access(actor, case, 'factory.manage', factory_issues.DEFINITION)
        require(actor, case, 'evidence.add')
        factory_issues.source(work, actor, current=False)
    configuration, authority, label = None, {}, ''
    if mode == 'team' and team_key:
        configuration, value = rules(case)
        team = next((team for team in value['teams'] if team['key'] == team_key), None)
        if team is None:
            raise ValidationError('Choose a currently configured team.')
        authority = recorder_authority(recorder, case, recorder_role, value)
        label = team['label']
    elif team_key or recorder_role:
        raise ValidationError('An unassigned team or factory account has no external team-role claim.')
    state = issues.update_issue(actor, case.pk, issue.pk, issue.current_id, 'manage', proof.pk,
                                reason, case.revision, owner_id=recorder.pk)
    previous = latest(issue)
    work_input = factory_issues.inputs(actor, case, issue.pk)[1] if work else {}
    result = IssueTeamAssignment.objects.create(issue=issue, state=state,
        number=previous.number + 1 if previous else 1, mode=mode, team_key=team_key,
        team_label=label, recorder=recorder, recorder_role=recorder_role, policy=configuration,
        authority=authority, evidence=proof, reason=reason.strip(), actor=actor,
        auto_work=work, requested_source_id=source_id, work_input=work_input)
    event(actor, case, 'issue.team_assigned', assignment=result.pk, issue=issue.pk,
          mode=mode, recorder=recorder.pk, external_owner=label or None)
    return result


@transaction.atomic
def record_reply(actor, case_id, issue_id, state_id, assignment_id, operation_key, operation,
                 evidence_id, note, next_action, party, channel, responded_at, source_ref, expected,
                 *, fix_id=None, root_cause_id=None, resolution_role=None):
    if any(type(value) is not int or value < 1 for value in [issue_id, state_id, assignment_id, evidence_id, expected]):
        raise ValidationError('Use exact current issue and assignment references.')
    case = lock_case(actor, case_id, 'issue.work')
    require(actor, case, 'issue.read')
    issue = Issue.objects.select_related('case', 'current').filter(case=case, pk=issue_id).first()
    if issue is None or not state_public(issue.current):
        raise ValidationError('Choose this project current readable issue.')
    assignment = IssueTeamAssignment.objects.filter(issue=issue, pk=assignment_id).first()
    if assignment is None or actor.pk != assignment.recorder_id:
        raise PermissionDenied('The current follow-up coordinator records this team response.')
    value = current(assignment, issue)
    if operation not in {'acknowledge', 'start', 'progress', 'resolve'}:
        raise ValidationError('Record resolution, severity and closure through their issue-register controls.')
    authority = assignment.authority
    resolution = {}
    if operation == 'resolve':
        if 'resolution_recorder_roles' not in value:
            raise ValidationError('Resolution recording needs reviewed team resolution rules.')
        authority = resolution_authority(actor, case, resolution_role, value)
        if type(fix_id) is not int or fix_id < 1 or (root_cause_id is not None and
                (type(root_cause_id) is not int or root_cause_id < 1)):
            raise ValidationError('Choose the exact documented fix and, when required, its root cause.')
        issue_subject(case, fix_id, 'resolution')
        if root_cause_id:
            issue_subject(case, root_cause_id, 'root_cause')
        resolution = {'fix': fix_id, 'root_cause': root_cause_id, 'resolution_authority': authority}
    elif fix_id is not None or root_cause_id is not None or resolution_role is not None:
        raise ValidationError('Fix evidence and resolution authority belong to the resolution step.')
    proof = issue_subject(case, evidence_id)
    require(proof.created_by, case, 'case.read')
    require(proof.created_by, case, 'evidence.add')
    if not isinstance(next_action, str) or not next_action.strip() or len(next_action) > 1000:
        raise ValidationError('Record the next action within one thousand characters.')
    facts = reply_facts(party, channel, responded_at, source_ref, value['channels'])
    try:
        key = UUID(str(operation_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Reload the current response form before recording it.') from None
    intent = digest({'issue': issue.pk, 'state': state_id, 'assignment': assignment.pk,
        'actor': actor.pk, 'operation': operation, 'proof': proof.pk, 'note': note,
        'next_action': next_action, **{**facts, 'responded_at': facts['responded_at'].isoformat()}, **resolution})
    old = IssueTeamReply.objects.filter(operation_key=key).first()
    if old:
        if old.assignment_id != assignment.pk or old.intent_sha256 != intent:
            raise ValidationError('This response key already identifies different source facts.')
        return old
    if case.revision != expected or issue.current_id != state_id:
        raise ValidationError('The issue changed. Reload its current response form.')
    state = issues._update_state(actor, case, issue, operation, proof.pk, note, next_action=next_action,
                                 fix_id=fix_id, root_cause_id=root_cause_id)
    result = IssueTeamReply.objects.create(assignment=assignment, state=state, operation_key=key,
        intent_sha256=intent, operation=operation, evidence=proof, proof_sha256=proof.sha256,
        authority=authority, actor=actor, **facts)
    event(actor, case, 'issue.team_reply_recorded', reply=result.pk, issue=issue.pk,
          team=assignment.team_key, recorder=actor.pk, source_clock='human_attested')
    return result


def validate_reply(reply, issue):
    current(reply.assignment, issue)
    proof = issue_subject(issue.case, reply.evidence_id)
    require(proof.created_by, issue.case, 'case.read')
    require(proof.created_by, issue.case, 'evidence.add')
    if (reply.actor_id != reply.assignment.recorder_id or reply.state.issue_id != issue.pk or
        reply.state.actor_id != reply.actor_id or reply.state.evidence_id != proof.pk or
        reply.proof_sha256 != proof.sha256):
        raise ValidationError('Review the exact current team response and its human recorder.')
    value = rules(issue.case)[1]
    authority = reply.assignment.authority
    if reply.operation == 'resolve':
        authority = resolution_authority(reply.actor, issue.case, reply.authority.get('role'), value)
        if reply.state.status != 'Resolved':
            raise ValidationError('Review the original resolved issue state.')
        issue_subject(issue.case, reply.state.fix_id, 'resolution')
        if reply.state.root_cause_id:
            issue_subject(issue.case, reply.state.root_cause_id, 'root_cause')
        if reply.state.severity == 'Critical' and not reply.state.root_cause_id:
            raise ValidationError('Critical resolution needs the documented root cause.')
    if authority != reply.authority:
        raise ValidationError('The team response authority changed. Obtain a current review.')
    reply_facts(reply.party, reply.channel, reply.responded_at, reply.source_ref, value['channels'])
    return reply


def projection(actor, issue):
    require(actor, issue.case, 'case.read')
    require(actor, issue.case, 'issue.read')
    assignment = latest(issue)
    if assignment is None or assignment.mode == 'internal':
        return {'mode': 'internal', 'status': 'current', 'assignment': assignment,
                'can_record': False, 'label': issue.current.owner.get_full_name() or issue.current.owner.username}
    result = {'mode': 'team', 'status': 'unavailable', 'assignment': assignment,
              'label': assignment.team_label or 'Owner needed', 'can_record': False,
              'finding': 'Review the external team and its current follow-up coordinator.'}
    if not assignment.team_key:
        result.update(status='unassigned', finding='Choose the external team in the issue owner settings.')
        return result
    try:
        value = current(assignment, issue)
    except (PermissionDenied, ValidationError):
        return result
    result.update(status='current', finding='', channels=value['channels'],
                  can_record=actor.pk == assignment.recorder_id,
                  can_resolve=False, resolution_finding='Resolution recorder roles need an owner decision.')
    if actor.pk == assignment.recorder_id and value.get('resolution_recorder_roles'):
        for role in value['resolution_recorder_roles']:
            try:
                resolution_authority(actor, issue.case, role, value)
            except (PermissionDenied, ValidationError):
                continue
            result.update(can_resolve=issue.current.status in {'Open','In Progress'}, resolution_finding='')
            break
    return result


def acknowledgement_clock(issue, state=None):
    """Retain recording time; use source time only under an explicit current rule."""
    state = state or issue.current
    result = {'status': 'known', 'at': state.acknowledged_at,
              'basis': 'recorded_at', 'reply_id': None, 'policies': {}}
    assignment = latest(issue)
    if assignment is None or assignment.mode == 'internal':
        return result
    result.update(status='unknown', at=None, basis=None,
                  finding='Choose the external-team acknowledgement clock in its current rules.')
    if state.pk != issue.current_id:
        result['finding'] = 'The issue changed. Assess the current source-bound escalation profile.'
        return result
    try:
        value = current(assignment, issue)
        basis = value.get('acknowledgement_clock')
        if not basis:
            return result
        result['policies'][COMPONENT] = assignment.policy_id
        reply = assignment.replies.filter(operation='acknowledge',
            state__acknowledged_at=state.acknowledged_at).select_related('state').first()
        if reply is None:
            if issue.current.acknowledged_at:
                result['finding'] = 'The current team has no source-bound acknowledgement. Review the owner change.'
                return result
            result.update(status='known', basis=basis, finding='')
            return result
        validate_reply(reply, issue)
        result.update(status='known', basis=basis, reply_id=reply.pk, finding='',
                      at=reply.responded_at if basis == 'human_attested_source_time' else reply.state.acknowledged_at)
    except (PermissionDenied, ValidationError):
        result['finding'] = 'Review the current team, reply evidence and recorder authority before assessing its clock.'
    return result
