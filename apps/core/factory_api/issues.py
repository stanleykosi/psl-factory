"""Project issue register and exact owner follow-up controls."""

from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.pmo import issue_teams, issues as native
from apps.pmo.issue_access import public_current_issues
from apps.policy.document_validators import ROLES
from apps.policy.issue_team_validators import CHANNELS
from apps.workflows import factory_issues as flow
from apps.workflows.factory_issue_views import presentation

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


REASON = {**TEXT, 'maxLength': 2000}
NEXT = {**TEXT, 'maxLength': 1000}
SEVERITY = nullable(choice(*native.SEVERITIES))
ACTION = choice('acknowledge', 'start', 'progress', 'resolve', 'manage')
OWNER = obj({'id': ID, 'name': TEXT})
ROLE = choice(*ROLES)
STATE = obj({'id': ID, 'state_id': ID, 'reference': TEXT, 'title': TEXT, 'kind': TEXT,
             'status': choice('Open', 'In Progress', 'Resolved', 'Closed'),
             'severity': SEVERITY, 'owner_id': ID, 'next_action': TEXT,
             'acknowledged_at': nullable(DATETIME), 'resolved_at': nullable(DATETIME)})
RECORD = obj({'issue_id': ID, 'state_id': ID, 'case_revision': REVISION})
LINK = obj({'kind': choice('risk', 'incident', 'change'), 'source_ref': {**TEXT, 'maxLength': 240}, 'evidence_id': ID})


def project(actor, case_id):
    case = accessible_case(actor, case_id, source_action='issue.read')
    require(actor, case, 'issue.read')
    return case


def record(case, state):
    case.refresh_from_db(fields=['revision'])
    return {'issue_id': state.issue_id, 'state_id': state.pk, 'case_revision': case.revision}


def state(issue):
    row = issue.current
    return {'id': issue.pk, 'state_id': row.pk, 'reference': issue.reference, 'title': row.title, 'kind': row.kind,
            'status': row.status, 'severity': row.severity or None, 'owner_id': row.owner_id, 'next_action': row.next_action,
            'acknowledged_at': row.acknowledged_at, 'resolved_at': row.resolved_at}


@endpoint(response=obj({'case_revision': REVISION, 'issues': array(STATE, limit=50), 'next_before': nullable(ID),
                        'owners': array(OWNER, limit=100), 'proofs': array(PROOF, limit=40)}),
    query={'before': ID}, summary='Page readable project issues and exact owner and evidence choices')
def register(request, case_id):
    case = project(request.user, case_id)
    issues = public_current_issues(case).select_related('current').order_by('-pk')
    before = request.GET.get('before')
    if before:
        if not before.isascii() or not before.isdecimal() or len(before) > 19 or not 1 <= int(before) <= ID['maximum']:
            raise ValidationError('Choose the previous issue page.')
        issues = issues.filter(pk__lt=int(before))
    rows = list(issues[:51])
    owners = get_user_model().objects.filter(is_active=True, grant__case=case, grant__action='issue.own',
                                             grant__active=True).distinct().order_by('pk')[:100]
    evidence = public_evidence(case.evidence.all()).only('id', 'kind', 'version').order_by('-pk')[:40]
    return {'case_revision': case.revision, 'issues': [state(issue) for issue in rows[:50]],
            'next_before': rows[49].pk if len(rows) > 50 else None, 'proofs': proof_rows(evidence),
            'owners': [{'id': owner.pk, 'name': owner.get_full_name() or owner.username} for owner in owners]}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'reference': {**TEXT, 'maxLength': 160},
    'title': {**TEXT, 'maxLength': 240}, 'kind': {**TEXT, 'maxLength': 100}, 'owner_id': ID, 'next_action': NEXT,
    'evidence_id': ID, 'note': NOTE, 'severity': SEVERITY, 'external_links': array(LINK, limit=20)}),
    response=RECORD, status=201, summary='Record an authoritative project issue and responsible owner')
def capture(request, case_id, *, body):
    actor = request.user
    case = project(actor, case_id)
    row = native.log_issue(actor, case.pk, body['reference'], body['title'], body['kind'], body['owner_id'],
                           body['next_action'], body['evidence_id'], body['note'], body['case_revision'],
                           body['severity'], body['external_links'])
    return record(case, row)


TEAM = obj({'mode': choice('team', 'internal'), 'status': TEXT, 'assignment_id': nullable(ID), 'label': TEXT,
            'can_record': BOOLEAN, 'can_resolve': BOOLEAN, 'finding': {'type': 'string'}})


def team_projection(actor, issue):
    team = issue_teams.projection(actor, issue)
    return {'mode': team['mode'], 'status': team['status'], 'label': team['label'], 'can_record': team['can_record'],
            'assignment_id': team['assignment'].pk if team['assignment'] else None,
            'can_resolve': team.get('can_resolve', False), 'finding': team.get('finding', '')}


@endpoint(response=obj({'case_revision': REVISION, 'issue': STATE, 'team': TEAM,
    'acknowledgement': obj({'status': TEXT, 'at': nullable(DATETIME), 'basis': nullable(TEXT), 'reply_id': nullable(ID)})}),
    summary='Read the exact current issue and source-bound owner acknowledgement without changing the issue')
def detail(request, case_id, issue_id):
    case = project(request.user, case_id)
    issue = get_object_or_404(public_current_issues(case).select_related('case', 'current__owner'), pk=issue_id)
    clock = issue_teams.acknowledgement_clock(issue)
    return {'case_revision': case.revision, 'issue': state(issue), 'team': team_projection(request.user, issue),
            'acknowledgement': {key: clock[key] for key in ('status', 'at', 'basis', 'reply_id')}}


COMMANDS = {
    'update': {'operation': ACTION, 'next_action': nullable(NEXT), 'owner_id': nullable(ID), 'severity': SEVERITY,
               'fix_id': nullable(ID), 'root_cause_id': nullable(ID)},
    'close_log': {'role': choice('QA', 'PM')},
    'reopen': {'role': choice('QA', 'PM'), 'next_action': NEXT},
}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': action}, 'case_revision': REVISION, 'state_id': ID, 'evidence_id': ID, 'note': NOTE, **fields})
    for action, fields in COMMANDS.items()
]}, response=RECORD, status=201, summary='Record the exact issue update, closure log or authorised reopening')
def command(request, case_id, issue_id, *, body):
    case = project(request.user, case_id)
    get_object_or_404(public_current_issues(case), pk=issue_id)
    values = (request.user, case.pk, issue_id, body['state_id'])
    proof = (body['evidence_id'], body['note'], body['case_revision'])
    if body['action'] == 'update':
        row = native.update_issue(*values, body['operation'], *proof, body['next_action'], body['owner_id'],
                                  body['severity'], body['fix_id'], body['root_cause_id'])
    elif body['action'] == 'close_log':
        native.close_issue_log(*values, body['role'], *proof)
        row = native.Issue.objects.select_related('current').get(case=case, pk=issue_id).current
    else:
        row = native.reopen_issue(*values, body['role'], *proof, body['next_action'])
    return record(case, row)


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'state_id': ID, 'mode': choice('team', 'internal'),
    'team_key': {'type': 'string', 'maxLength': 100}, 'recorder_id': ID, 'recorder_role': ROLE, 'evidence_id': ID,
    'reason': REASON, 'work_id': nullable(ID), 'source_id': nullable(ID)}, optional=('work_id', 'source_id')),
    response=obj({'id': ID, 'case_revision': REVISION}), status=201,
    summary='Assign the issue to an internal owner or external team with its exact active recorder')
def assign(request, case_id, issue_id, *, body):
    case = project(request.user, case_id)
    row = issue_teams.assign(request.user, case.pk, issue_id, body['state_id'], body['mode'], body['team_key'],
                             body['recorder_id'], body['recorder_role'], body['evidence_id'], body['reason'],
                             body['case_revision'], work_id=body.get('work_id'), source_id=body.get('source_id'))
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'case_revision': case.revision}


def team_reply_fields():
    return {'assignment_id': ID, 'operation_key': UUID, 'party': {**TEXT, 'maxLength': 160},
            'channel': choice(*CHANNELS), 'responded_at': nullable(DATETIME), 'source_ref': {**TEXT, 'maxLength': 240}}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'state_id': ID, **team_reply_fields(),
    'operation': choice('acknowledge', 'start', 'progress', 'resolve'), 'evidence_id': ID, 'note': NOTE,
    'next_action': NEXT, 'fix_id': nullable(ID), 'root_cause_id': nullable(ID), 'resolution_role': nullable(ROLE)}),
    response=RECORD, status=201, summary='Record a source-attested external team reply and requested issue transition')
def team_reply(request, case_id, issue_id, *, body):
    case = project(request.user, case_id)
    at = datetime.fromisoformat(body['responded_at']) if body['responded_at'] else None
    row = issue_teams.record_reply(request.user, case.pk, issue_id, body['state_id'], body['assignment_id'],
                                   body['operation_key'], body['operation'], body['evidence_id'], body['note'],
                                   body['next_action'], body['party'], body['channel'], at, body['source_ref'],
                                   body['case_revision'], fix_id=body['fix_id'], root_cause_id=body['root_cause_id'],
                                   resolution_role=body['resolution_role'])
    return record(case, row.state)


@endpoint(response=obj({**VERSIONS, 'issue': STATE, 'team': TEAM, 'source_id': ID, 'can_request_update': BOOLEAN,
                        'response_task': nullable(obj({'id': ID, 'revision': REVISION})),
                        'next_action': TEXT, 'finding': {'type': 'string'}}),
    summary='Read the exact issue investigation and source-scoped owner response task')
def work_detail(request, work_id):
    work = require_line(request.user, work_id, flow.DEFINITION)
    row = presentation(request.user, work)
    panel = row['issues']
    if not panel:
        raise PermissionDenied
    task = next((task for task in row['tasks'] if task.status == 'open'), None) if panel['can_respond'] else None
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'issue': state(panel['issue']),
            'team': team_projection(request.user, panel['issue']), 'source_id': work.source_head_id,
            'can_request_update': row['can_request_update'], 'next_action': row['next_action'], 'finding': row['blocker'],
            'response_task': {'id': task.pk, 'revision': task.revision} if task else None}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'request_update'}, **VERSIONS, 'background': BOOLEAN}),
    obj({'action': {'const': 'respond'}, **VERSIONS, 'task_id': ID, 'task_revision': REVISION,
         'operation': choice('acknowledge', 'start', 'progress'), 'evidence_id': ID, 'note': NOTE, 'next_action': NEXT,
         'team_reply': nullable(obj(team_reply_fields()))}),
    obj({'action': choice('refresh', 'restart'), **VERSIONS, 'reason': REASON}),
]}, response=WORK_RESULT, summary='Continue issue investigation with the exact assigned response or follow-up')
def work_command(request, work_id, *, body):
    work = require_line(request.user, work_id, flow.DEFINITION)
    values = (request.user, work.pk, body['expected_revision'], body['case_revision'])
    if body['action'] == 'respond':
        team = body['team_reply']
        if team and team['responded_at'] is not None:
            team = dict(team, responded_at=datetime.fromisoformat(team['responded_at']))
        flow.respond(*values, body['task_id'], body['task_revision'], body['operation'], body['evidence_id'],
                     body['note'], body['next_action'], team_reply=team)
    elif body['action'] == 'request_update':
        flow.request_update(*values, body['background'])
    else:
        flow.refresh(*values, body['reason'], restart=body['action'] == 'restart')
    work.refresh_from_db()
    return result(work)
