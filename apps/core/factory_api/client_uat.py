"""Client testing witness, independent proof review and exact gate evidence."""

from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from adapters import case_uploads, client_uat as contract
from apps.agents.models import CaseUpload
from apps.agents.upload_views import upload_file
from apps.core.models import ClientContactRevision
from apps.core.read_budget import limit_queries
from apps.core.services import lock_case
from apps.identity.services import require, visible_cases
from apps.pmo import client_uat as domain
from apps.pmo.client_uat_models import ClientUATGateBinding
from apps.pmo.client_uat_views import _contact_visible
from apps.pmo.models import DeliveryDossier

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


FILE = obj({'id': ID, 'name': TEXT, 'size': ID, 'sha256': TEXT})
RESULT = obj({'case_revision': REVISION, 'record_ids': array(ID, limit=50)})
NOTE = {**TEXT, 'maxLength': 2000}
OPTIONAL_NOTE = {'type': 'string', 'maxLength': 2000}
OUTCOME = choice(*contract.OUTCOMES)


def scope(actor, case_id, dossier_id):
    scope_case = get_object_or_404(visible_cases(actor), pk=case_id)
    domain.readable(actor, scope_case)
    return get_object_or_404(DeliveryDossier.objects.select_related('case', 'candidate'),
                             case=scope_case, pk=dossier_id)


def file_value(row):
    return {'id': row.pk, 'name': row.name, 'size': row.size, 'sha256': row.sha256}


@endpoint(response=obj({'case_revision': REVISION, 'target_id': nullable(ID), 'response_id': nullable(ID),
    'outcome': nullable(OUTCOME), 'inspection_id': nullable(ID), 'review_id': nullable(ID), 'binding_id': nullable(ID),
    'gate_id': nullable(ID), 'proof_current': BOOLEAN, 'binding_current': BOOLEAN,
    'contact_choices': array(obj({'id': ID, 'name': TEXT}), limit=1),
    'owned_files': array(FILE, limit=50), 'proof_files': array(FILE, limit=50)}),
    summary='Read the current client testing request, exact response, proof review and gate state')
def desk(request, case_id, dossier_id):
    actor = request.user
    dossier = scope(actor, case_id, dossier_id)
    case = dossier.case
    with limit_queries(1300):
        target = domain.head(dossier, contract.TARGET)
        response = domain.head(dossier, contract.RESPONSE, target.pk) if target else None
        if target:
            try:
                domain.current_target(actor, target)
            except (PermissionDenied, ValidationError):
                target = response = None
        proof_current, binding_current, inspected, reviewed, binding, files = False, False, None, None, None, []
        if response:
            try:
                domain.current_response(actor, response)
            except (PermissionDenied, ValidationError):
                response = None
        if response:
            inspected = response.verifications.filter(adapter=contract.INSPECTION).order_by('-pk').first()
            reviewed = response.verifications.filter(adapter=contract.REVIEW).order_by('-pk').first()
            binding = ClientUATGateBinding.objects.filter(review__source=response).order_by('-pk').first()
            try:
                files = domain.proof_rows(actor, response)
            except (PermissionDenied, ValidationError):
                pass
            try:
                domain.current_review(actor, response)
            except (PermissionDenied, ValidationError):
                pass
            else:
                proof_current = True
        gate = dossier.candidate.gates.filter(kind='uat_client').order_by('-pk').values_list('pk', flat=True).first()
        if binding:
            from apps.pmo.approvals import gate_current
            try:
                gate_current(dossier.candidate, 'uat_client', binding.verification)
            except (PermissionDenied, ValidationError):
                pass
            else:
                binding_current = True
        contacts = ClientContactRevision.objects.filter(case=case, purpose='project', customer='').order_by('-number')[:1]
        visible_contacts = [{'id': row.pk, 'name': row.name} for row in contacts if _contact_visible(actor, case, row.pk)]
        owned = CaseUpload.objects.filter(case=case, actor=actor).order_by('-pk')[:50]
        return {'case_revision': case.revision, 'target_id': target.pk if target else None,
                'response_id': response.pk if response else None, 'outcome': response.payload['outcome'] if response else None,
                'inspection_id': inspected.pk if inspected else None, 'review_id': reviewed.pk if reviewed else None,
                'binding_id': binding.pk if binding else None, 'gate_id': gate, 'proof_current': proof_current,
                'binding_current': binding_current, 'contact_choices': visible_contacts,
                'owned_files': list(map(file_value, owned)), 'proof_files': list(map(file_value, files))}


FIELDS = {
    'target': {'contact_id': ID, 'sent_at': DATETIME, 'previous_id': nullable(ID), 'gate_id': nullable(ID),
               'replace_existing': BOOLEAN, 'operation_key': UUID},
    'response': {'target_id': ID, 'responded_at': DATETIME, 'outcome': OUTCOME, 'genuine': {'const': True},
                 'note': OPTIONAL_NOTE, 'workaround': nullable(NOTE), 'source_reference': nullable({**TEXT, 'maxLength': 240}),
                 'proof_ids': array(ID, limit=50), 'previous_id': nullable(ID), 'operation_key': UUID},
    'inspect': {'response_id': ID},
    'agent': {'response_id': ID},
    'review': {'response_id': ID, 'inspection_id': ID, 'verdict': choice('confirm', 'return', 'withdraw'),
               'proof_confirmed': BOOLEAN, 'note': NOTE, 'operation_key': UUID},
    'export': {'response_id': ID, 'review_id': ID, 'previous_binding_id': nullable(ID), 'reason': nullable(NOTE)},
    'retract': {'response_id': ID, 'reason': NOTE, 'operation_key': UUID},
}
COMMAND = {'oneOf': [obj({'action': {'const': action}, 'case_revision': REVISION, **fields}) for action, fields in FIELDS.items()]}


@endpoint(method='POST', request=COMMAND, response=RESULT, status=201,
    summary='Record client testing evidence, request inspection, review proof or bind the confirmed decision to the exact gate')
@transaction.atomic
def command(request, case_id, dossier_id, *, body):
    actor = request.user
    dossier = scope(actor, case_id, dossier_id)
    case = dossier.case
    action, expected = body['action'], body['case_revision']
    response = None
    if 'response_id' in body:
        response = domain.exact(case, body['response_id'], contract.RESPONSE)
        if response.dossier_id != dossier.pk:
            raise PermissionDenied
    if action == 'target':
        row = domain.record_target(actor, case.pk, dossier.pk, body['contact_id'], parse_datetime(body['sent_at']),
            body['previous_id'], body['gate_id'], body['replace_existing'], body['operation_key'], expected)
    elif action == 'response':
        target = domain.exact(case, body['target_id'], contract.TARGET)
        if target.dossier_id != dossier.pk:
            raise PermissionDenied
        row = domain.record_response(actor, case.pk, target.pk, parse_datetime(body['responded_at']), body['outcome'],
            body['genuine'], body['note'], body['workaround'], body['source_reference'], body['proof_ids'],
            body['previous_id'], body['operation_key'], expected)
    elif action == 'inspect':
        row = domain.inspect_proof(actor, case.pk, response.pk, expected)
    elif action == 'agent':
        lock_case(actor, case.pk, 'client_uat.record', expected)
        jobs = domain.queue_checks(actor, response)
        return {'case_revision': case.revision, 'record_ids': [job.pk for job in jobs]}
    elif action == 'review':
        row = domain.review_proof(actor, case.pk, response.pk, body['inspection_id'], body['verdict'],
            body['proof_confirmed'], body['note'], body['operation_key'], expected)
    elif action == 'export':
        row = domain.export_gate(actor, case.pk, response.pk, body['review_id'], expected,
            previous_binding_id=body['previous_binding_id'], correction_reason=body['reason'])
    else:
        row = domain.withdraw_recording(actor, case.pk, response.pk, body['reason'], body['operation_key'], expected)
    case.refresh_from_db(fields=['revision'])
    return {'case_revision': case.revision, 'record_ids': [row.pk]}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'file': {'type': 'string', 'format': 'binary'}}),
    response=FILE, status=201, multipart=True, summary='Upload private evidence for the current client testing request')
@transaction.atomic
def upload(request, case_id, dossier_id):
    dossier = scope(request.user, case_id, dossier_id)
    require(request.user, dossier.case, 'evidence.add')
    try:
        expected = int(request.POST['case_revision'])
    except (ValueError, TypeError):
        raise Problem(422, 'invalid_input', 'Use the current project revision.') from None
    lock_case(request.user, case_id, 'case.read', expected)
    return file_value(upload_file(request.user, dossier.case, request.FILES['file']))


@endpoint(response={'type': 'string', 'format': 'binary'}, media_type='application/octet-stream',
    summary='Download an exact private file bound to the current recorded client testing response')
def download(request, case_id, dossier_id, response_id, upload_id):
    dossier = scope(request.user, case_id, dossier_id)
    response = domain.exact(dossier.case, response_id, contract.RESPONSE)
    if response.dossier_id != dossier.pk:
        raise PermissionDenied
    rows = domain.proof_rows(request.user, response)
    file = next((row for row in rows if row.pk == upload_id), None)
    if not file:
        raise PermissionDenied
    try:
        body = case_uploads.read(file)
    except OSError:
        raise Problem(503, 'source_unavailable', 'The private file is temporarily unavailable.') from None
    return FileResponse(BytesIO(body), as_attachment=True, filename=file.name, content_type='application/octet-stream')
