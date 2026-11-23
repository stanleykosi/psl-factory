"""Source-backed meetings, retrospectives and project commitments."""
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.pmo import meetings
from apps.pmo.models import ActionItem, Meeting, MeetingActionLink, MeetingVersion

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .intake_sources import positive_id
from .project_operations import ACTION, OPTION, action_payload, next_page
from .work import PAGE, page_number


REF = {**TEXT, 'maxLength': 160}
NOTE = {**TEXT, 'maxLength': 4000}
KIND = choice(*meetings.MEETING_KINDS)
IDS = {**array(ID, limit=50), 'uniqueItems': True}
DECISION = obj({'text': {**TEXT, 'maxLength': 2000}, 'evidence_id': ID, 'change_evidence_id': nullable(ID)},
               optional=('change_evidence_id',))
MEETING = obj({'id': ID, 'version_id': ID, 'version': REVISION, 'reference': REF, 'kind': KIND,
               'occurred_at': DATETIME, 'purpose': {**TEXT, 'maxLength': 240}})


def workspace(actor, case_id, *, write=None):
    case = accessible_case(actor, case_id, source_action='meeting.read')
    require(actor, case, 'meeting.read')
    if case.kind != 'project':
        raise Problem(404, 'not_found', 'Choose a project workspace.')
    if write:
        require(actor, case, write)
    return case


def meeting_payload(version):
    return {'id': version.meeting_id, 'version_id': version.pk, 'version': version.number,
            'reference': version.meeting.reference, 'kind': version.kind,
            'occurred_at': version.occurred_at, 'purpose': version.purpose}


def public_ids(case, ids, *, kind=None):
    query = public_evidence(case.evidence.filter(pk__in=ids))
    if kind:
        query = query.filter(kind=kind)
    if set(query.values_list('pk', flat=True)) != ids:
        raise Problem(422, 'invalid_evidence', 'Choose available supporting evidence from this project.')


def people(case, action):
    return get_user_model().objects.filter(is_active=True, grant__case=case, grant__active=True, grant__action=action
                                           ).order_by('username', 'pk').distinct()


def choices(rows):
    return [{'id': person.pk, 'label': person.get_full_name() or person.username} for person in rows]


def visible_meetings(case):
    sources = public_evidence(case.evidence.all()).values('pk')
    return Meeting.objects.filter(case=case, current__evidence_id__in=sources).select_related('current__meeting')


@endpoint(response=obj({
    'revision': REVISION, 'items': array(MEETING, limit=25), 'next_page': nullable(PAGE),
    'can_record': BOOLEAN, 'can_manage_actions': BOOLEAN,
}), query={'kind': KIND, 'page': PAGE}, summary='Browse current meetings and retrospectives with available authoring controls')
def collection(http, case_id):
    case = workspace(http.user, case_id)
    grants = {action for _, action in active_case_grants(http.user, [case.pk])}
    rows = visible_meetings(case).order_by('-current__occurred_at', '-pk')
    kind = http.GET.get('kind')
    if kind is not None:
        if kind not in meetings.MEETING_KINDS:
            raise Problem(422, 'invalid_filter', 'Choose an available meeting kind.')
        rows = rows.filter(current__kind=kind)
    page = Paginator(rows, 25).get_page(page_number(http))
    return {'revision': case.revision, 'items': [meeting_payload(row.current) for row in page],
            'next_page': next_page(page), 'can_record': 'meeting.record' in grants,
            'can_manage_actions': 'action.manage' in grants}


@endpoint(response=obj({'revision': REVISION, 'participants': array(OPTION, limit=50), 'owners': array(OPTION, limit=50),
                        'proofs': array(OPTION, limit=50), 'more_participants': BOOLEAN, 'more_owners': BOOLEAN,
                        'more_proofs': BOOLEAN}), query={'page': PAGE},
          summary='Read selectable meeting participants, action owners and public proof')
def options(http, case_id):
    case = workspace(http.user, case_id)
    grants = {action for _, action in active_case_grants(http.user, [case.pk])}
    if not {'meeting.record', 'action.manage'}.intersection(grants):
        raise Problem(403, 'forbidden', 'Meeting or action recording authority is required.')
    number = page_number(http)
    participants = Paginator(people(case, 'meeting.participate') if 'meeting.record' in grants else [], 50).get_page(number)
    owners = Paginator(people(case, 'action.own') if 'action.manage' in grants else [], 50).get_page(number)
    proof = Paginator(public_evidence(case.evidence.all()).only('kind', 'version', 'source').order_by('-pk'), 50).get_page(number)
    return {'revision': case.revision, 'participants': choices(participants), 'owners': choices(owners),
            'proofs': [{'id': row.pk, 'label': f'{row.kind.replace("_", " ")} · v{row.version} · {row.source[:120]}'}
                       for row in proof], 'more_participants': participants.has_next(),
            'more_owners': owners.has_next(), 'more_proofs': proof.has_next()}


@endpoint(method='POST', request=obj({
    'revision': REVISION, 'reference': REF, 'kind': KIND, 'occurred_at': DATETIME,
    'purpose': {**TEXT, 'maxLength': 240}, 'summary': {**TEXT, 'maxLength': 16000},
    'participant_ids': IDS, 'decisions': array(DECISION, limit=50), 'evidence_id': ID, 'meeting_id': nullable(ID),
}, optional=('meeting_id',)), response=obj(MEETING['properties'] | {'revision': REVISION}), status=201,
          summary='Record an observed meeting or append a source-backed retrospective revision')
def record(http, case_id, *, body):
    actor = http.user
    case = workspace(actor, case_id, write='meeting.record')
    if body.get('meeting_id') is not None:
        get_object_or_404(visible_meetings(case), pk=body['meeting_id'])
    public_ids(case, {body['evidence_id'], *(row['evidence_id'] for row in body['decisions'])})
    public_ids(case, {row['change_evidence_id'] for row in body['decisions'] if row.get('change_evidence_id')},
               kind='change_request')
    version = meetings.record_meeting(
        actor, case.pk, body['reference'], body['kind'], body['occurred_at'], body['purpose'], body['summary'],
        body['participant_ids'], body['decisions'], body['evidence_id'], body['revision'], body.get('meeting_id'),
    )
    case.refresh_from_db(fields=['revision'])
    return meeting_payload(version) | {'revision': case.revision}


@endpoint(response=obj(MEETING['properties'] | {
    'revision': REVISION, 'summary': TEXT, 'participants': array(OPTION, limit=50), 'decisions': array(DECISION, limit=50),
    'evidence_id': ID, 'actions': array(ACTION, limit=25), 'next_page': nullable(PAGE),
    'current': BOOLEAN,
}), query={'page': PAGE, 'version_id': ID},
    summary='Read an exact meeting version, its source-backed decisions and current linked action states')
def detail(http, case_id, meeting_id):
    case = workspace(http.user, case_id)
    meeting = get_object_or_404(visible_meetings(case), pk=meeting_id)
    version = meeting.current
    sources = public_evidence(case.evidence.all()).values('pk')
    version_id = positive_id(http, 'version_id')
    if version_id is not None and version_id != version.pk:
        version = get_object_or_404(MeetingVersion, meeting=meeting, pk=version_id, evidence_id__in=sources)
    current = version.pk == meeting.current_id
    public_ids(case, {row['evidence_id'] for row in version.decisions})
    public_ids(case, {row['change_evidence_id'] for row in version.decisions if row.get('change_evidence_id')},
               kind='change_request')
    linked = MeetingActionLink.objects.filter(meeting=meeting, evidence_id__in=sources).values('item_id')
    actions = ActionItem.objects.filter(case=case, pk__in=linked, current__evidence_id__in=sources).select_related(
        'current__owner').order_by('pk')
    page = Paginator(actions if current else actions.none(), 25).get_page(page_number(http))
    return meeting_payload(version) | {'revision': case.revision, 'summary': version.summary,
        'participants': choices(people(case, 'meeting.participate').filter(pk__in=version.participant_ids)),
        'decisions': version.decisions, 'evidence_id': version.evidence_id,
        'actions': [action_payload(case, item, item.current) for item in page], 'next_page': next_page(page),
        'current': current}


@endpoint(method='POST', request=obj({
    'revision': REVISION, 'reference': REF, 'description': {**TEXT, 'maxLength': 1000}, 'owner_id': nullable(ID),
    'due_at': nullable(DATETIME), 'evidence_id': ID, 'reason': NOTE, 'meeting_id': nullable(ID),
    'calculated': BOOLEAN, 'change_evidence_id': nullable(ID),
}, optional=('owner_id', 'due_at', 'meeting_id', 'calculated', 'change_evidence_id')), response=ACTION, status=201,
          summary='Create a project action with a recorded owner, deadline basis and exact evidence')
def create_action(http, case_id, *, body):
    actor = http.user
    case = workspace(actor, case_id, write='action.manage')
    if body.get('meeting_id') is not None:
        get_object_or_404(visible_meetings(case), pk=body['meeting_id'])
    public_ids(case, {body['evidence_id']})
    if body.get('change_evidence_id') is not None:
        public_ids(case, {body['change_evidence_id']}, kind='change_request')
    item = meetings.create_action(actor, case.pk, body['reference'], body['description'], body.get('owner_id'),
        body.get('due_at'), body['evidence_id'], body['reason'], body['revision'], body.get('meeting_id'),
        body.get('calculated', False), body.get('change_evidence_id'))
    case.refresh_from_db(fields=['revision'])
    return action_payload(case, item, item.current)


@endpoint(method='POST', request=obj({'revision': REVISION, 'action_id': ID, 'evidence_id': ID}),
          response=obj({'link_id': ID, 'revision': REVISION}), status=201,
          summary='Link a current project action to a meeting using exact supporting evidence')
def link_action(http, case_id, meeting_id, *, body):
    actor = http.user
    case = workspace(actor, case_id, write='meeting.record')
    get_object_or_404(visible_meetings(case), pk=meeting_id)
    sources = public_evidence(case.evidence.all()).values('pk')
    get_object_or_404(ActionItem.objects.filter(case=case, current__evidence_id__in=sources), pk=body['action_id'])
    public_ids(case, {body['evidence_id']})
    link = meetings.link_action(actor, case.pk, meeting_id, body['action_id'], body['evidence_id'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'link_id': link.pk, 'revision': case.revision}
