"""Current Planning packet, received facts and scoped Delivery handoff."""
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from adapters.planning_packet import INPUT, PURPOSES
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.services import lock_case
from apps.identity.services import active_case_grants, visible_cases
from apps.pmo import planning as domain, planning_inputs, planning_sources
from apps.pmo.models import ActionItem
from apps.pmo.models import DeliveryDossier, DeliverySource
from apps.policy.services import decision_authority
from apps.workflows import factory_planning
from apps.workflows.factory_progress import wake_waiting

from .commands import require_line
from .delivery import PROOF, RESPONSE, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj


DEPARTMENT = choice(*planning_inputs.DEPARTMENTS)
EFFORT = choice('known', 'unknown', 'not_applicable')
DAYS = {'type': 'string', 'pattern': r'^[0-9]{1,9}(?:\.[0-9]{1,3})?$'}
NOTE = {**TEXT, 'maxLength': 4000}
EMPTY_TEXT = {'type': 'string'}
FACT = obj({'id': ID, 'version': REVISION, 'source_id': ID, 'source_party': TEXT, 'received_at': DATETIME,
    'summary': TEXT, 'effort_state': EFFORT, 'person_days': nullable(DAYS), 'changed_effort': BOOLEAN})
RECORDED = obj({'revision': REVISION, 'record_id': ID})


@endpoint(response=obj({
    'revision': REVISION, 'packet_id': nullable(ID), 'packet': nullable(INPUT), 'finding': EMPTY_TEXT,
    'can_record_input': BOOLEAN, 'review_roles': array(TEXT), 'effort_reviewed': BOOLEAN,
    'departments': array(obj({'department': DEPARTMENT, 'input': nullable(FACT)})),
    'readiness': nullable(obj({'evidence_id': ID, 'delivery_dossiers': array(obj({'id': ID, 'label': TEXT}), limit=25),
        'source_ids': array(ID, limit=25)})),
}), summary='Read the current Planning packet, received department input, readiness and exact Delivery handoff')
@read_observation
def detail(request, case_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    domain.readable(actor, case)
    with limit_queries(1400, deadline=monotonic() + 10):
        grants = {action for _, action in active_case_grants(actor, [case.pk])}
        head = domain.latest(case, 'packet')
        packet_value = None
        collection = {}
        finding = ''
        if head:
            try:
                packet, data = domain.packet(case, head.pk)
            except (ValidationError, PermissionDenied):
                finding = 'Review the current scope, packet sources and recording authority.'
            else:
                packet_value = data['payload']
                collection = planning_inputs.received_projection(case, packet, packet_value) or {}
        records = [row['record'] for row in collection.get('rows', []) if row['record']]
        visible_ids = set(public_evidence(case.evidence.filter(pk__in=[row['source'] for row in records]))
                          .values_list('pk', flat=True))
        visible_facts = {row['department']: {**{key: row[key] for key in FACT['properties'] if key != 'source_id'},
                         'source_id': row['source']} for row in records if row['source'] in visible_ids}
        review_roles = []
        if collection.get('changed') and {'planning.coordinate', 'commercial.read', 'costing.read', 'costing.source.read'} <= grants:
            try:
                _, criteria = domain.criteria(case)
            except (ValidationError, PermissionDenied):
                criteria = {}
            for role in criteria.get('department_inputs', {}).get('reviewer_roles', []):
                try:
                    decision_authority(actor, case, role)
                except (ValidationError, PermissionDenied):
                    continue
                review_roles.append(role)
        readiness = None
        if packet_value is not None and 'delivery.read' in grants:
            ready = domain.latest(case, 'ready')
            if ready:
                try:
                    pinned = domain.current_readiness(case, ready.pk)
                except (ValidationError, PermissionDenied):
                    finding = 'The recorded readiness needs review against the current sources.'
                else:
                    dossiers = DeliveryDossier.objects.filter(case=case, candidate_id=pinned['inputs']['candidate_id'])
                    handoffs = DeliverySource.objects.filter(dossier__in=dossiers, kind='scope_baseline', evidence=ready)
                    readiness = {'evidence_id': ready.pk, 'delivery_dossiers': [
                        {'id': pk, 'label': label} for pk, label in dossiers.order_by('-pk').values_list('pk', 'candidate__reference')[:25]],
                        'source_ids': list(handoffs.order_by('-pk').values_list('pk', flat=True)[:25])}
    return {'revision': case.revision, 'packet_id': head.pk if head else None, 'packet': packet_value,
            'finding': finding or collection.get('finding') or '', 'review_roles': review_roles,
            'can_record_input': bool(collection) and 'planning.coordinate' in grants,
            'effort_reviewed': collection.get('effort_reviewed', False),
            'departments': [{'department': row['department'], 'input': visible_facts.get(row['department'])}
                            for row in collection.get('rows', [])], 'readiness': readiness}


COMMAND = {'oneOf': [
    obj({'action': {'const': 'capture'}, 'revision': REVISION, 'previous_id': nullable(ID), 'packet': INPUT}),
    obj({'action': {'const': 'align'}, 'revision': REVISION, 'packet_id': ID,
         'purpose': choice(*PURPOSES), 'meeting_version_id': ID}),
    obj({'action': {'const': 'prepare_readiness'}, 'revision': REVISION, 'packet_id': ID}),
    obj({'action': {'const': 'handoff'}, 'revision': REVISION, 'readiness_id': ID, 'dossier_id': ID}),
]}


@endpoint(method='POST', request=COMMAND, response=RECORDED,
          summary='Capture exact Planning sources, align a meeting, prepare readiness or hand it off to Delivery')
@transaction.atomic
def command(request, case_id, *, body):
    actor = request.user
    action = body['action']
    case = lock_case(actor, case_id, 'planning.coordinate' if action in ('capture', 'align') else 'planning.prepare',
                     body['revision'])
    domain.readable(actor, case)
    if action == 'capture':
        saved = domain.capture(actor, case.pk, body['packet'], body['previous_id'])
    elif action == 'align':
        saved = domain.align(actor, case.pk, body['packet_id'], body['purpose'], body['meeting_version_id'])
    elif action == 'prepare_readiness':
        saved = domain.prepare(actor, case.pk, body['packet_id'])
    else:
        saved = domain.bridge(actor, case.pk, body['readiness_id'], body['dossier_id'])
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'record_id': saved.pk}


@endpoint(method='POST', request=obj({
    'revision': REVISION, 'packet_id': ID, 'department': DEPARTMENT, 'previous_id': nullable(ID), 'source_id': ID,
    'source_party': {**TEXT, 'maxLength': 160}, 'received_at': DATETIME,
    'summary': NOTE, 'effort_state': EFFORT, 'person_days': nullable(DAYS),
}), response=RECORDED, status=201, summary='Record exact received department input or its explicit successor')
def record_input(request, case_id, *, body):
    values = dict(body)
    values['expected'] = values.pop('revision')
    values['received_at'] = parse_datetime(values['received_at'])
    row = planning_inputs.record(request.user, case_id, **values)
    return {'revision': row.case.revision, 'record_id': row.pk}


@endpoint(method='POST', request=obj({'revision': REVISION, 'packet_id': ID, 'role': {**TEXT, 'maxLength': 100},
    'disposition': choice('retain_costing', 'new_costing'), 'evidence_id': ID, 'reason': {**TEXT, 'maxLength': 2000}}),
    response=RECORDED, status=201, summary='Review changed department effort against its exact costing and commercial sources')
def review_effort(request, case_id, *, body):
    values = dict(body)
    values['expected'] = values.pop('revision')
    review = planning_inputs.review(request.user, case_id, **values)
    return {'revision': review.case.revision, 'record_id': review.pk}


@endpoint(response=obj({'expected_revision': REVISION, 'requests': array(obj({'request_id': ID,
    'receipt_id': ID, 'role': TEXT, 'proofs': array(PROOF, limit=100)}), limit=2)}),
          summary='Read only the current department-owned request and matching supplied proof choices')
def owner_requests(request, work_id):
    work = require_line(request.user, work_id, factory_planning.DEFINITION)
    with limit_queries(650, deadline=monotonic() + 8):
        available = factory_planning.owner_panels(request.user, work)
    return {'expected_revision': work.revision, 'requests': [
        {'request_id': row['request'].pk, 'receipt_id': row['receipt'].pk, 'role': row['owner_role'],
         'proofs': proof_rows(row['evidence'])} for row in available]}


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'request_id': ID, 'receipt_id': ID, 'evidence_id': ID}),
          response=RESPONSE, status=201, summary='Record the current department owner’s exact source observation')
@transaction.atomic
def observe(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_planning.DEFINITION)
    observation = factory_planning.observe_department(request.user, work.pk, body['expected_revision'], body['request_id'],
                                                     body['receipt_id'], body['evidence_id'])
    wake_waiting(work.pk)
    return recorded(work, observation)


CORRELATION = obj({'key': TEXT, 'code': TEXT, 'detail': TEXT, 'source_ids': array(ID)})
CLARIFICATION = obj({'key': TEXT, 'action_id': ID, 'action_version': REVISION, 'owner_id': nullable(ID),
    'owner_status': choice('unassigned', 'assigned', 'source_access_held'), 'status': TEXT, 'response_id': nullable(ID),
    'approval_granted': {'const': False}})
COST = obj({'disposition': TEXT, 'proposal': REVISION, 'previous': REVISION}, optional=('proposal', 'previous'))


@endpoint(response=obj({'revision': REVISION, 'packet_id': nullable(ID), 'findings': array(CORRELATION),
    'clarifications': array(CLARIFICATION), 'reviewed_costing': nullable(COST), 'can_assign': BOOLEAN}),
    summary='Read exact Planning source gaps, owner responses and current reviewed costing')
@read_observation
def sources(request, case_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    domain.readable(actor, case)
    with limit_queries(1450, deadline=monotonic() + 12):
        facts = domain.report(actor, case.pk)
        grants = {action for _, action in active_case_grants(actor, [case.pk])}
        findings = facts.get('source_correlation', {}).get('findings', [])
        ids = {pk for finding in findings for pk in finding['source_ids']}
        readable = set(public_evidence(case.evidence.filter(pk__in=ids)).values_list('pk', flat=True))
        collection = (facts.get('readiness_inputs') or {}).get('department_inputs') or {}
        costing = factory_planning.reviewed_costing(actor, case, collection)
    return {'revision': case.revision, 'packet_id': facts.get('packet_id'),
            'findings': [{**{key: finding[key] for key in ('key', 'code', 'detail')},
                          'source_ids': [pk for pk in finding['source_ids'] if pk in readable]} for finding in findings],
            'clarifications': facts.get('source_clarifications', []), 'reviewed_costing': costing,
            'can_assign': {'planning.coordinate', 'action.manage'} <= grants}


CLARIFICATION_ACTION = {'oneOf': [
    obj({'action': {'const': 'assign'}, 'revision': REVISION, 'packet_id': ID, 'key': {**TEXT, 'maxLength': 100},
         'owner_id': nullable(ID)}),
    obj({'action': {'const': 'respond'}, 'revision': REVISION, 'packet_id': ID, 'key': {**TEXT, 'maxLength': 100},
         'action_id': ID, 'expected_action': REVISION, 'disposition': choice('source_correction_required', 'exclude_in_successor'),
         'evidence_id': ID, 'replacement_source_id': nullable(ID), 'target_prd_id': nullable(ID), 'target_scope_id': nullable(ID)}),
]}


@endpoint(method='POST', request=CLARIFICATION_ACTION, response=RECORDED, status=201,
    summary='Assign an exact Planning source clarification or record the currently assigned owner’s evidenced response')
@transaction.atomic
def clarify(request, case_id, *, body):
    actor = request.user
    action = body['action']
    case = lock_case(actor, case_id, 'planning.coordinate' if action == 'assign' else 'planning.participate', body['revision'])
    domain.readable(actor, case)
    values = {key: value for key, value in body.items() if key not in ('action', 'revision')}
    if action == 'assign':
        record = planning_sources.clarify(actor, case.pk, **values)
    else:
        get_object_or_404(ActionItem, case=case, pk=body['action_id'])
        record = planning_sources.resolve(actor, case.pk, **values)
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'record_id': record.pk}
