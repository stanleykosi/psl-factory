"""Explicit owner appointment drafts and exact policy lifecycle decisions."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils.dateparse import parse_datetime

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.services import lock_case
from apps.identity.services import active_case_grants, require
from apps.policy import impact, role_assignments
from apps.policy.models import Configuration, PolicyState, ScopeVersion
from apps.policy.registry import components
from apps.policy.services import transition

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


STATES = choice('draft', 'validated', 'active', 'revoked', 'superseded')
TRANSITIONS = {'validated': 'policy.configure', 'active': 'policy.activate', 'revoked': 'policy.activate'}
FROM_STATE = {'draft': 'validated', 'validated': 'active', 'active': 'revoked'}
COMPONENT = {**TEXT, 'maxLength': 100}
CONFIG = obj({'id': ID, 'component': COMPONENT, 'version': REVISION, 'state_id': ID, 'state': STATES,
              'actions': array(choice(*TRANSITIONS), limit=1)})
OPTION = obj({'id': ID, 'label': TEXT})


def states(records):
    last = PolicyState.objects.filter(configuration_id=OuterRef('pk')).order_by('-pk')
    return records.annotate(state_id=Subquery(last.values('pk')[:1]), current_state=Subquery(last.values('state')[:1]))


def config_payload(record, actions=()):
    return {'id': record.pk, 'component': record.component, 'version': record.revision,
            'state_id': record.state_id, 'state': record.current_state, 'actions': list(actions)}


@endpoint(response=obj({'case_revision': REVISION, 'items': array(CONFIG, limit=25), 'next_page': nullable(PAGE)}),
          query={'page': PAGE, 'component': COMPONENT}, summary='Read visible policy versions and the exact next review actions')
def versions(request, case_id):
    actor = request.user
    case = impact.context(actor, case_id)
    component = request.GET.get('component')
    if component is not None and (len(component) > COMPONENT['maxLength'] or component not in components()):
        raise Problem(422, 'invalid_filter', 'Choose a registered policy component.')
    records = Configuration.objects.filter(case=case).only('pk', 'component', 'revision')
    if component:
        records = records.filter(component=component)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    page = Paginator(states(records).order_by('-pk'), 25).get_page(page_number(request))
    items = []
    with limit_queries(250):
        frozen = set(ScopeVersion.objects.filter(configuration_id__in=[row.pk for row in page])
                     .values_list('configuration_id', flat=True))
        for row in page:
            try:
                impact.configuration(actor, case.pk, row.pk)
            except PermissionDenied:
                continue
            action = FROM_STATE.get(row.current_state)
            items.append(config_payload(row, [action] if action and TRANSITIONS[action] in grants and row.pk not in frozen else []))
    return {'case_revision': case.revision, 'items': items,
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'state_id': ID, 'transition': choice(*TRANSITIONS)}),
          response=CONFIG, summary='Validate, activate or revoke the exact reviewed policy version')
@transaction.atomic
def review(request, case_id, configuration_id, *, body):
    actor = request.user
    action = body['transition']
    case = lock_case(actor, case_id, TRANSITIONS[action], body['case_revision'])
    config = impact.configuration(actor, case.pk, configuration_id)
    if config.states.order_by('-pk').values_list('pk', flat=True).first() != body['state_id']:
        raise Problem(409, 'stale_version', 'Reload the current policy state before recording the decision.')
    transition(actor, config.pk, action)
    return config_payload(states(Configuration.objects.only('component', 'revision')).get(pk=config.pk))


APPOINTMENTS = {'type': 'array', 'minItems': 1, 'maxItems': 100,
                'items': {'oneOf': list(role_assignments.SCHEMAS.values())}}


def appointment_head(actor, case):
    head = Configuration.objects.filter(case=case, component=role_assignments.COMPONENT).order_by('-revision').only('pk').first()
    if head:
        impact.configuration(actor, case.pk, head.pk)
    return head.pk if head else None


@endpoint(response=obj({'case_revision': REVISION, 'latest_id': nullable(ID), 'active_id': nullable(ID),
    'people': array(OPTION, limit=50), 'proofs': array(ID, limit=50), 'can_draft': BOOLEAN,
    'appointments': array(obj({'user_id': ID, 'roles': array(TEXT), 'eligibility': TEXT})),
    'next_page': nullable(PAGE)}), query={'page': PAGE}, summary='Read current business appointments and eligible project principals')
def appointments(request, case_id):
    actor = request.user
    case = impact.context(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    with limit_queries(600):
        status = role_assignments.report(actor, case.pk)
        latest = appointment_head(actor, case)
    people = get_user_model().objects.filter(is_active=True, grant__case=case, grant__action='case.read', grant__active=True)
    can_draft = 'policy.configure' in grants
    page = Paginator(people.order_by('username', 'pk').distinct() if can_draft else [], 50).get_page(page_number(request))
    proofs = public_evidence(case.evidence.filter(kind='policy_decision')).order_by('-pk').values_list('pk', flat=True)
    return {'case_revision': case.revision, 'latest_id': latest, 'active_id': status.get('configuration'), 'can_draft': can_draft,
            'people': [{'id': person.pk, 'label': person.get_full_name() or person.username} for person in page],
            'proofs': list(proofs[:50]) if can_draft else [], 'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None,
            'appointments': [{key: row[key] for key in ('user_id', 'roles', 'eligibility')} for row in status['assignments']]}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'latest_id': nullable(ID), 'assignments': APPOINTMENTS,
    'evidence_id': ID, 'effective_from': DATETIME}), response=CONFIG, status=201,
    summary='Draft exact named business decision appointments from recorded owner evidence')
@transaction.atomic
def draft_appointments(request, case_id, *, body):
    actor = request.user
    case = lock_case(actor, case_id, 'policy.configure', body['case_revision'])
    impact.context(actor, case.pk)
    if appointment_head(actor, case) != body['latest_id']:
        raise Problem(409, 'stale_version', 'Reload the latest appointment proposal before drafting another version.')
    require(actor, case, 'policy.read')
    if not public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='policy_decision')).exists():
        raise Problem(422, 'invalid_input', 'Choose an available owner decision from this project.')
    assignment_ids = {row['user_id'] for row in body['assignments']}
    eligible = set(get_user_model().objects.filter(pk__in=assignment_ids, is_active=True, grant__case=case,
        grant__action='case.read', grant__active=True).values_list('pk', flat=True))
    if eligible != assignment_ids:
        raise Problem(422, 'invalid_input', 'Choose active people with current access to this project.')
    draft = role_assignments.draft(actor, case.pk, body['assignments'], body['evidence_id'], parse_datetime(body['effective_from']))
    return config_payload(states(Configuration.objects.only('component', 'revision')).get(pk=draft.pk))
