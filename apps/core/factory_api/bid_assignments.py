"""Received bid assignment with current appointment and source checks."""
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.services import add_evidence
from apps.identity.factory_access import project_cases
from apps.pmo import rfp_assignment_queue as queue
from apps.pmo.rfp_assignment_views import AssignmentForm

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, endpoint, nullable, obj
from .work_proofs import owned_pdf


CURSOR = {**TEXT, 'maxLength': 1024}
CHOICE = obj({'id': ID, 'label': TEXT})
BID = obj({
    'case_id': UUID, 'intake_id': ID, 'revision': REVISION, 'reference': TEXT,
    'received_at': DATETIME, 'deadline_status': TEXT, 'deadline': nullable(DATETIME),
    'owner_access_required': BOOLEAN,
})
ASSIGNMENT = obj({'id': ID, 'person_id': ID, 'role': TEXT, 'intake_id': ID})
ASSIGNMENT_SCREEN = obj({
    'bid': BID, 'setup_required': BOOLEAN, 'assignment': nullable(ASSIGNMENT),
    'roles': array(TEXT), 'nominees': array(CHOICE), 'proofs': array(CHOICE, limit=26),
    'next_steps': array(obj({'key': TEXT, 'label': TEXT, 'api_url': nullable(TEXT)})),
})


def bid_payload(bid, access_required):
    intake = bid.current_intake
    return {'case_id': bid.case_id, 'intake_id': intake.pk, 'revision': bid.case.revision,
            'reference': bid.reference, 'received_at': intake.received_at, 'deadline_status': intake.deadline_status,
            'deadline': intake.deadline_at, 'owner_access_required': access_required}


def assignment_payload(record):
    return {'id': record.pk, 'person_id': record.pm_id, 'role': record.role, 'intake_id': record.intake_id}


@endpoint(response=obj({'items': array(BID, limit=queue.PAGE_SIZE), 'cursor': nullable(CURSOR),
                        'checked': {'type': 'integer', 'minimum': 0, 'maximum': queue.PAGE_SIZE}}),
          query={'cursor': CURSOR}, summary='List received bids that need current project manager assignments')
def pending(http):
    data = queue.page(http.user, http.GET.get('cursor'))
    return {'items': [bid_payload(bid, bid.owner_access_required) for bid in data['rows']],
            'cursor': data['next_cursor'], 'checked': data['checked']}


@endpoint(response=ASSIGNMENT_SCREEN, summary='Read current bid, assignment and eligible nominees and evidence')
def detail(http, case_id):
    actor = http.user
    case = get_object_or_404(project_cases(actor), pk=case_id)
    try:
        roles, records = queue.assignment_scope(actor, case)
    except ValidationError as exc:
        raise Problem(422, 'setup_required', exc.messages[0]) from exc
    bid = get_object_or_404(queue.bids(), case=case)
    current, access_required = queue.assignment_state(bid)
    people = [] if current else queue.nominees(case, records)
    proofs = [] if current else queue.source_choices(bid)
    if current:
        path = f'/api/v1/received-bids/{case.pk}/receipts/{bid.current_intake_id}'
        steps = [{'key': 'inspect_bid', 'label': 'Review the original bid and its submission instructions.', 'api_url': path}]
    elif access_required:
        steps = [{'key': 'grant_access', 'label': 'Arrange project manager access to this bid.', 'api_url': None}]
    else:
        steps = [{'key': 'assign_pm', 'label': 'Choose the responsible project manager and record the assignment.', 'api_url': None}]
    return {'bid': bid_payload(bid, access_required), 'setup_required': False,
            'next_steps': steps,
            'assignment': assignment_payload(current) if current else None, 'roles': roles if not current else [],
            'nominees': [{'id': person.pk, 'label': person.get_full_name() or person.username} for person in people],
            'proofs': [{'id': proof.pk, 'label': f'{proof.kind.replace("_", " ").capitalize()} · version {proof.version}'}
                       for proof in proofs]}


ASSIGN_FIELDS = {'intake': ID, 'revision': REVISION, 'candidate': ID, 'role': TEXT, 'reason': {**TEXT, 'maxLength': 4000}}


@endpoint(method='POST', request={'oneOf': [
    obj({**ASSIGN_FIELDS, 'evidence': ID}),
    obj({**ASSIGN_FIELDS, 'upload_id': ID, 'checked': {'const': True}}),
]},
          response=ASSIGNMENT, status=201, summary='Assign an eligible project manager to an exact received bid')
@transaction.atomic
def assign(http, case_id, *, body):
    actor = http.user
    case = get_object_or_404(project_cases(actor), pk=case_id)
    roles, records = queue.assignment_scope(actor, case)
    bid = get_object_or_404(queue.bids(), case=case)
    if case.revision != body['revision'] or bid.current_intake_id != body['intake'] or queue.assignment_state(bid)[0]:
        raise Problem(409, 'stale_version', 'The received bid or its assignment changed. Reload it.')
    people = queue.nominees(case, records)
    if 'upload_id' in body:
        proof = owned_pdf(actor, case, body['upload_id'])
        evidence = add_evidence(actor, case.pk, 'rfp_assignment_proof_copy',
            json.dumps({**proof, 'intake': bid.current_intake_id, 'candidate': body['candidate'],
                        'checked': body['checked']}, sort_keys=True),
            f"bid-assignment-copy/v1:{proof['upload_id']}", case.revision)
        body = {**body, 'evidence': evidence.pk, 'revision': case.revision + 1}
    form = AssignmentForm(bid, roles, people, body)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the assignment fields.',
                      fields=[{'name': key, 'message': messages[0]} for key, messages in form.errors.items()])
    data = form.cleaned_data
    candidate = next(person for person in people if person.pk == data['candidate'])
    try:
        result = queue.assign(actor, case.pk, data['intake'], candidate, data['role'], data['evidence'],
                              data['reason'], data['revision'])
    except queue.StaleAssignment as exc:
        raise Problem(409, 'stale_version', exc.messages[0]) from exc
    return assignment_payload(result)
