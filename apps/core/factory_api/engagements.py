"""Source-owned engagement, assignment and exact Planning registration handoff."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.models import ClientContactRevision
from apps.core.read_budget import limit_queries
from apps.identity.services import active_case_grants, require
from apps.pmo import engagement, engagement_details
from apps.pmo.engagement_forms import PROOFS
from apps.pmo.models import RFPDisposition
from apps.policy.document_validators import ROLES
from apps.workflows import factory_engagement as workflow

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows, recorded
from .http import BOOLEAN, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .intake import KEY, start_projects
from .intake_sources import positive_id
from .reviews import VERSIONS
from .work import WORK_RESULT


ROUTE = choice('A', 'B', 'C')
REFERENCE = {**TEXT, 'maxLength': 120}
ROLE = choice(*ROLES)
DATE = {'type': 'string', 'format': 'date'}
CAPTURE = obj({'id': ID, 'route': ROUTE, 'reference': TEXT, 'evidence_id': ID, 'rfp_disposition_id': nullable(ID)})
SHARED = {'key': KEY, 'evidence_id': ID}
COMMANDS = {
    'assign': {**SHARED, 'role': ROLE, 'pm_id': ID},
    'details': {**SHARED, 'capture_id': ID, 'reference': REFERENCE, 'plan_id': ID, 'checked': {'const': True},
                'planned_start': nullable(DATE), 'contact_id': nullable(ID)},
    'register': {**SHARED, 'role': ROLE, 'value': REFERENCE, 'plan_id': ID, 'details_id': nullable(ID)},
    'reassess': {'capture_id': nullable(ID), 'reason': {**NOTE, 'maxLength': 2000}},
}
DETAILS = obj({'id': ID, 'reference': TEXT, 'plan_id': ID, 'evidence_id': ID, 'planned_start': nullable(DATE),
               'contact_id': nullable(ID)})


def capture_projection(case, pk=None):
    try:
        capture = workflow.capture_current(case, pk)
    except (PermissionDenied, ValidationError):
        return None
    return {'id': capture.pk, 'route': capture.data['route'], 'reference': capture.data['reference'],
            'rfp_disposition_id': capture.data['rfp_disposition'], 'evidence_id': capture.evidence_id}


@endpoint(response=obj({'revision': REVISION, 'capture': nullable(CAPTURE), 'sources': array(PROOF, limit=30),
                        'won_dispositions': array(ID, limit=30), 'next_before': nullable(ID)}), query={'before': ID},
          summary='Read exact engagement source options and the current captured original')
def options(request, case_id):
    actor = request.user
    case = get_object_or_404(start_projects(actor, workflow.DEFINITION), pk=case_id)
    workflow.readable(actor, case, 'factory.start')
    before = positive_id(request, 'before')
    evidence = public_evidence(case.evidence.filter(kind__in=['engagement_source', 'product_input', 'rfp_outcome']))
    if before:
        evidence = evidence.filter(pk__lt=before)
    rows = list(evidence.only('id', 'kind', 'version').order_by('-pk')[:31])
    won = []
    if active_case_grants(actor, [case.pk], actions=['rfp.read']):
        won = list(RFPDisposition.objects.filter(rfp__case=case, kind='route_a', outcome__result='won')
                   .order_by('-pk').values_list('pk', flat=True)[:30])
    return {'revision': case.revision, 'capture': capture_projection(case), 'sources': proof_rows(rows[:30]),
            'won_dispositions': won, 'next_before': rows[29].pk if len(rows) > 30 else None}


@endpoint(response=obj({**VERSIONS, 'capture': nullable(CAPTURE), 'assignment_id': nullable(ID),
    'registration_id': nullable(ID), 'planning_work_id': nullable(ID), 'planning_receipt_id': nullable(ID),
    'planning_packet_id': nullable(ID), 'finding': {'type': 'string'}, 'actions': array(choice(*COMMANDS)),
    'assignment_roles': array(ROLE), 'registration_roles': array(ROLE),
    'managers': array(obj({'id': ID, 'name': TEXT}), limit=30), 'source_proofs': array(PROOF, limit=35),
    'details': nullable(DETAILS), 'project_contact_id': nullable(ID)}),
    summary='Read the exact engagement assignment, registration inputs and Planning handoff')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, workflow.DEFINITION)
    case = work.case
    with limit_queries(900):
        native = workflow.projection(actor, work)
        capture = capture_projection(case, native['capture']) if native['capture'] else None
        grants = {action for _, action in active_case_grants(actor, [case.pk])}
        live = not (work.cancel_requested or work.status in ('verified', 'cancelled', 'followup_needed'))
        assign = workflow.human_roles(actor, case, 'assign') if live and capture else []
        register = workflow.human_roles(actor, case, 'register') if live and capture else []
        manage = live and capture and 'engagement.capture' in grants
        actions = [name for name, allowed in [('assign', assign), ('details', manage), ('register', register),
                   ('reassess', 'factory.manage' in grants and native['changed'])] if allowed]
        managers = [{'id': user.pk, 'name': user.get_full_name() or user.username}
                    for user in engagement.pm_candidates(case)[:30]] if assign else []
        saved = None
        current = engagement_details.Details.objects.filter(case=case, capture_id=native['capture']).order_by('-pk').first()
        if current:
            try:
                details, contact = engagement_details.current(case, current.pk)
            except (ValidationError, PermissionDenied):
                pass
            else:
                saved = {'id': details.pk, 'reference': details.reference, 'plan_id': details.plan_id,
                         'evidence_id': details.evidence_id, 'planned_start': details.planned_start,
                         'contact_id': contact.pk if contact else None}
        candidates = public_evidence(case.evidence.filter(kind__in=PROOFS)).only('id', 'kind', 'version').order_by('-pk')
        contact_id = None
        if manage:
            contact_id = ClientContactRevision.objects.filter(case=case, purpose='project', customer='').order_by('-number')
            contact_id = contact_id.values_list('pk', flat=True).first()
    return {'expected_revision': work.revision, 'case_revision': case.revision, 'capture': capture,
            'assignment_id': native['assignment'], 'registration_id': native['registration'], 'planning_work_id': native['planning_work'],
            'planning_receipt_id': native.get('receipt'), 'planning_packet_id': native.get('planning_packet'), 'finding': native['finding'],
            'actions': actions, 'assignment_roles': assign, 'registration_roles': register, 'managers': managers,
            'source_proofs': proof_rows(candidates[:35]) if actions else [], 'details': saved, 'project_contact_id': contact_id}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, **VERSIONS, **fields})
    for action, fields in COMMANDS.items()]}, response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Assign the PM, attest planning details or register the exact source-owned project identity')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, workflow.DEFINITION)
    require(actor, work.case, 'engagement.read')
    action = body['action']
    args = (actor, work.pk, body['expected_revision'])
    if action == 'reassess':
        current = workflow.reassess(*args, body['reason'], body['capture_id'], case_expected=body['case_revision'])
    else:
        fields = {key: body[key] for key in COMMANDS[action]}
        current = workflow.human(*args, body['case_revision'], action, fields)
    return recorded(work, current)
