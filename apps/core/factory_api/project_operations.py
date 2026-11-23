"""Project actions and exact signed-stage evidence."""
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.services import add_evidence
from apps.identity.services import active_case_grants, require, visible_cases
from apps.pmo import change_stage_links
from apps.pmo.meetings import action_timing, change_action
from apps.pmo.models import ChangeMilestoneLink, Milestone
from apps.pmo.project_action_views import ActionForm, action_options, load_action
from apps.pmo.services import complete_milestone
from apps.pmo.signature_exemptions import assert_current_baseline_assurance

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work_proofs import owned_pdf


LABEL = {'type': 'string'}
OPTION = obj({'id': ID, 'label': TEXT})
STATE = obj({
    'id': ID, 'revision': REVISION, 'status': choice('open', 'in_progress', 'paused', 'completed', 'cancelled'),
    'description': LABEL, 'owner': nullable(OPTION), 'deadline': nullable(DATETIME),
    'timing': choice('CLOSED', 'UNKNOWN', 'PAUSED', 'OVERDUE', 'NOT_DUE'), 'recorded_at': DATETIME,
})
OPERATIONS = choice('assign', 'reassign', 'cancel', 'reopen', 'start', 'complete')
ACTION = obj({'case_id': UUID, 'revision': REVISION, 'id': ID, 'reference': LABEL, 'current': STATE})
ACTION_DETAIL = obj(ACTION['properties'] | {
    'operations': array(OPERATIONS), 'owners': array(OPTION, limit=50), 'evidence': array(OPTION, limit=50),
    'owner_page': nullable(ID), 'evidence_page': nullable(ID),
    'history': array(STATE, limit=20), 'next_page': nullable(ID),
    'can_attach_pdf': BOOLEAN,
})
ACTION_FIELDS = {
    'revision': REVISION, 'action_revision': REVISION, 'operation': OPERATIONS,
    'owner': nullable(ID), 'due_at': nullable(DATETIME),
    'reason': {**TEXT, 'maxLength': 4000},
}
ACTION_WRITE = {'oneOf': [
    obj({**ACTION_FIELDS, 'evidence': ID}, optional=('owner', 'due_at')),
    obj({**ACTION_FIELDS, 'upload_id': ID, 'checked': {'const': True}}, optional=('owner', 'due_at')),
]}


def state_payload(state):
    owner = state.owner
    return {
        'id': state.pk, 'revision': state.number, 'status': state.status, 'description': state.description,
        'owner': {'id': owner.pk, 'label': owner.get_full_name() or owner.username} if owner else None,
        'deadline': state.due_at, 'timing': action_timing(state), 'recorded_at': state.created_at,
    }


def action_payload(case, item, state):
    return {'case_id': str(case.pk), 'revision': case.revision, 'id': item.pk, 'reference': item.reference,
            'current': state_payload(state)}


def next_page(page):
    return page.next_page_number() if page.has_next() else None


@endpoint(response=ACTION_DETAIL, query={'page': ID, 'owner_page': ID, 'evidence_page': ID},
          summary='Read a project action, permitted transitions, selectable owners and supporting records')
def action(http, case_id, item_id):
    case, item = load_action(http.user, case_id, item_id)
    state = item.current
    choices, manages, has_open_owner = action_options(http.user, case, state)
    form = ActionForm(case, state, choices)
    owners = form.fields['owner'].queryset if 'owner' in form.fields else None
    if manages and has_open_owner and owners is not None and owners.exclude(pk=state.owner_id).exists():
        choices.append(('reassign', 'Change owner'))
    owner_page = Paginator(owners if owners is not None else [], 50).get_page(http.GET.get('owner_page'))
    evidence_page = Paginator(form.fields['evidence'].queryset if choices else [], 50).get_page(
        http.GET.get('evidence_page'))
    history = Paginator(item.states.select_related('owner').order_by('-number'), 20).get_page(http.GET.get('page'))
    return action_payload(case, item, state) | {
        'operations': [operation for operation, _ in choices],
        'can_attach_pdf': bool(choices and active_case_grants(http.user, [case.pk], actions=['evidence.add'])),
        'owners': [{'id': owner.pk, 'label': owner.get_full_name() or owner.username} for owner in owner_page],
        'evidence': [{'id': source.pk, 'label': f'{source.kind.replace("_", " ").capitalize()} · version {source.version}'}
                     for source in evidence_page],
        'owner_page': next_page(owner_page), 'evidence_page': next_page(evidence_page),
        'history': [state_payload(prior) for prior in history], 'next_page': next_page(history),
    }


@endpoint(method='POST', request=ACTION_WRITE, response=ACTION, summary='Apply a permitted project action transition')
@transaction.atomic
def update_action(http, case_id, item_id, *, body):
    actor = http.user
    case, item = load_action(actor, case_id, item_id)
    if body['revision'] != case.revision or body['action_revision'] != item.current.number:
        raise Problem(409, 'stale_version', 'The action changed. Reload it before continuing.')
    choices, manages, has_open_owner = action_options(actor, case, item.current)
    reassign = body['operation'] == 'reassign'
    if reassign and manages and has_open_owner:
        choices = [('reassign', 'Change owner')]
    if body['operation'] not in dict(choices):
        raise PermissionDenied()
    if 'upload_id' in body:
        proof = owned_pdf(actor, case, body['upload_id'])
        evidence = add_evidence(actor, case.pk, 'action_proof_copy',
            json.dumps({**proof, 'action': item.pk, 'action_version': item.current.number,
                        'operation': body['operation'], 'checked': body['checked']}, sort_keys=True),
            f"project-action-copy/v1:{proof['upload_id']}", case.revision)
        body = {**body, 'evidence': evidence.pk, 'revision': case.revision + 1}
    form = ActionForm(case, item.current, choices, body, owner_only=reassign)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the action fields.',
                      fields=[{'name': key, 'message': messages[0]} for key, messages in form.errors.items()])
    values = form.cleaned_data
    owner = values.get('owner')
    state = change_action(actor, case.pk, item.pk, values['operation'], values['evidence'].pk, values['reason'],
                          values['revision'], values['action_revision'], owner.pk if owner else None,
                          values.get('due_at'))
    case.refresh_from_db(fields=['revision'])
    return action_payload(case, item, state)


def project(actor, case_id):
    return get_object_or_404(visible_cases(actor), pk=case_id, kind='project')


STAGE = choice(*ChangeMilestoneLink.Stage.values)
LINK_OPTIONS = obj({
    'revision': REVISION, 'can_link': BOOLEAN, 'limited': BOOLEAN, 'plans': array(OPTION),
    'stages': array(obj({'value': STAGE, 'label': TEXT})),
})


@endpoint(response=LINK_OPTIONS, summary='Read eligible change plans and their signed milestone choices')
def stage_options(http, case_id):
    actor = http.user
    case = project(actor, case_id)
    change_stage_links.require_access(actor, case, change_stage_links.READ_ACTIONS)
    try:
        change_stage_links.require_access(actor, case, change_stage_links.MANAGE_ACTIONS)
    except PermissionDenied:
        return {'revision': case.revision, 'can_link': False, 'limited': False, 'plans': [], 'stages': []}
    stages, plans, limited = change_stage_links.options(case)
    return {'revision': case.revision, 'can_link': bool(plans and stages), 'limited': limited,
            'stages': [{'value': value, 'label': label} for value, label in stages],
            'plans': [{'id': key, 'label': label} for key, label in plans]}


@endpoint(method='POST', request=obj({'revision': REVISION, 'stage': STAGE, 'plan_event_id': ID,
                                     'scope_note': {**TEXT, 'maxLength': 240}}),
          response=obj({'id': ID, 'stage': STAGE, 'plan_event_id': ID, 'revision': REVISION}),
          summary='Link an approved change plan to a signed milestone')
def link_stage(http, case_id, *, body):
    result = change_stage_links.record(http.user, case_id, stage=body['stage'], plan_id=body['plan_event_id'],
                                       scope_note=body['scope_note'], expected=body['revision'])
    result.case.refresh_from_db(fields=['revision'])
    return {'id': result.pk, 'stage': result.stage, 'plan_event_id': result.plan_event_id,
            'revision': result.case.revision}


MILESTONE_INPUT = {'revision': REVISION, 'name': {**TEXT, 'maxLength': 200}}


@endpoint(method='POST', request={'oneOf': [
    obj({**MILESTONE_INPUT, 'evidence_id': ID}),
    obj({**MILESTONE_INPUT, 'upload_id': ID, 'checked': {'const': True}}),
]},
          response=obj({'id': ID, 'revision': REVISION, 'name': TEXT, 'evidence_id': ID}), status=201,
          summary='Complete a milestone with exact evidence and queue its Finance handoff')
@transaction.atomic
def record_milestone(http, case_id, *, body):
    case = project(http.user, case_id)
    require(http.user, case, 'milestone.complete')
    revision = body['revision']
    if 'upload_id' in body:
        proof = owned_pdf(http.user, case, body['upload_id'])
        evidence = add_evidence(http.user, case.pk, 'completion',
            json.dumps({**proof, 'milestone': body['name'], 'checked': body['checked']}, sort_keys=True),
            f"milestone-completion-copy/v1:{proof['upload_id']}", revision)
        revision += 1
    else:
        evidence = get_object_or_404(public_evidence(case.evidence.filter(kind='completion')), pk=body['evidence_id'])
    milestone = complete_milestone(http.user, case.pk, body['name'], evidence.pk, revision)
    case.refresh_from_db(fields=['revision'])
    return {'id': milestone.pk, 'revision': case.revision, 'name': milestone.name, 'evidence_id': milestone.evidence_id}


@endpoint(response=obj({'revision': REVISION, 'proofs': array(OPTION, limit=50), 'next_page': nullable(ID),
    'can_complete': BOOLEAN, 'can_attach_pdf': BOOLEAN,
    'hold': nullable(choice('baseline_required', 'proof_required', 'name_in_use'))}),
          query={'page': ID, 'name': {**TEXT, 'maxLength': 200}}, summary='Read exact supporting records for milestone completion')
def milestone_options(http, case_id):
    case = project(http.user, case_id)
    require(http.user, case, 'milestone.complete')
    proofs = public_evidence(case.evidence.filter(kind='completion')).only('version').order_by('-pk')
    page = Paginator(proofs, 50).get_page(http.GET.get('page'))
    attach = bool(active_case_grants(http.user, [case.pk], actions=['evidence.add']))
    hold = None
    try:
        assert_current_baseline_assurance(case)
    except (ValidationError, PermissionDenied):
        hold = 'baseline_required'
    name = http.GET.get('name')
    if hold is None and name and Milestone.objects.filter(case=case, name=name).exists():
        hold = 'name_in_use'
    if hold is None and not (page.paginator.count or attach):
        hold = 'proof_required'
    return {'revision': case.revision, 'proofs': [{'id': source.pk, 'label': f'Completion evidence · version {source.version}'}
                                                for source in page], 'next_page': next_page(page),
            'can_complete': hold is None, 'can_attach_pdf': attach, 'hold': hold}


@endpoint(response=obj({'id': ID, 'name': TEXT, 'completed_at': DATETIME, 'evidence_id': ID, 'proof_version': REVISION}),
    summary='Read current permitted completion evidence for a directly selected project milestone')
def milestone(http, case_id, milestone_id):
    from apps.core.project_journey import MILESTONE_RECORD_ACTIONS
    from apps.identity.factory_access import project_actions

    case = project(http.user, case_id)
    if not MILESTONE_RECORD_ACTIONS.intersection(project_actions(http.user, case)):
        raise PermissionDenied
    row = get_object_or_404(Milestone.objects.select_related('evidence').filter(case=case,
                            evidence_id__in=public_evidence(case.evidence.all()).values('pk')), pk=milestone_id)
    return {'id': row.pk, 'name': row.name, 'completed_at': row.completed_at,
            'evidence_id': row.evidence_id, 'proof_version': row.evidence.version}
