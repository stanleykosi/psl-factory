"""Exact client response witnesses and controlled signed-baseline adoption."""

from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from adapters import case_uploads
from adapters.commercial_rework import SOURCE_KINDS
from apps.agents.upload_views import upload_file
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.services import lock_case
from apps.identity.services import require, visible_cases
from apps.pmo import commercial as native, commercial_client_response as witness, commercial_rework, signatures
from apps.pmo.commercial_client_views import ResponseForm, revision_context, signature_form
from apps.pmo.commercial_models import BaselineAdoption, ClientResponse, CommercialCase
from apps.pmo.models import CommercialSignaturePacket
from apps.pmo.signature_exemptions import record_exemption
from apps.policy.signature_validators import SIGNATURES, VALUE

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


NOTE = {**TEXT, 'maxLength': 4000}
KEY = {**TEXT, 'maxLength': 100}
OPTION = obj({'id': ID, 'label': TEXT})
FILE = obj({'id': ID, 'name': TEXT, 'size': ID, 'sha256': TEXT})
OUTCOME = choice('signed', 'changes_requested', 'declined')
RESPONSE = obj({'id': ID, 'evidence_id': ID, 'revision_id': ID, 'receipt_id': ID, 'kind': TEXT})
WITNESS = obj({'id': ID, 'response_id': ID, 'client_name': TEXT, 'outcome': OUTCOME, 'responded_at': DATETIME})
ADOPTION = obj({'id': ID, 'revision_id': ID, 'finance_intake_id': nullable(ID), 'current': BOOLEAN})
PACKET = obj({'id': ID, 'revision_id': nullable(ID), 'sow': TEXT, 'prd': TEXT, 'contract': TEXT, 'authenticity': TEXT})
RESULT = obj({'case_revision': REVISION, 'record_ids': array(ID, limit=50)})


def project(actor, case_id):
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    witness.readable(actor, case)
    return case


def file_value(row):
    return {'id': row.pk, 'name': row.name, 'size': row.size, 'sha256': row.sha256}


def current_response(actor, case, response_id, *, signed=False):
    response = get_object_or_404(ClientResponse.objects.select_related('evidence', 'revision__dossier'),
                                 revision__dossier__case=case, pk=response_id)
    if response.revision.dossier.current_id != response.revision_id:
        raise Problem(409, 'stale_version', 'Choose the response to the current statement of work.')
    if signed and response.kind != 'signed':
        raise Problem(422, 'invalid_input', 'Select the actual signed client response.')
    witness.current_for_signature(actor, case, response.evidence, response.revision_id)
    return response


@endpoint(response=obj({'case_revision': REVISION, 'current_revision_id': nullable(ID), 'can_record': BOOLEAN,
    'receipts': array(OPTION, limit=50), 'owned_files': array(FILE, limit=50),
    'witness': nullable(WITNESS), 'witness_files': array(FILE, limit=50),
    'parties': array(obj({'reference': TEXT, 'label': TEXT})), 'responses': array(RESPONSE, limit=25),
    'packet': nullable(PACKET), 'signature_proofs': array(PROOF, limit=50), 'requirements': array(PROOF, limit=50),
    'adoption': nullable(ADOPTION), 'revision_drafts': array(OPTION, limit=25)}),
    summary='Read current delivered versions, private witness proof, signature choices and verified baseline handoff')
def desk(request, case_id):
    actor = request.user
    case = project(actor, case_id)
    with limit_queries(1400):
        dossier = CommercialCase.objects.select_related('current').filter(case=case).first()
        revision = dossier.current if dossier else None
        try:
            witness.witness(actor, case)
        except (PermissionDenied, ValidationError):
            can_record = False
        else:
            can_record = True
        form = ResponseForm(actor=actor, case=case, revision=revision) if can_record else None
        receipts = [{'id': row.pk, 'label': form.fields['receipt'].label_from_instance(row)}
                    for row in form.fields['receipt'].queryset] if form else []
        owned_files = [file_value(row) for row in form.fields['proofs'].queryset] if form else []
        parties = [{'reference': key, 'label': label} for key, label in form.fields['party_ref'].choices if key] if form else []
        metadata = witness.latest(case)
        observed, files, revisions = None, [], []
        if metadata:
            try:
                value, response = witness.read(actor, case, metadata)
                files = witness.proof_rows(actor, case, metadata)
            except (PermissionDenied, ValidationError):
                pass
            else:
                observed = {'id': metadata.pk, 'response_id': response.pk, **{
                    key: value[key] for key in ('client_name', 'outcome', 'responded_at')}}
                if can_record and value['outcome'] == 'changes_requested' and metadata.created_by_id == actor.pk and case.synthetic:
                    form_data = revision_context(actor, case, metadata, files)
                    draft_form = form_data.get('form')
                    if draft_form:
                        revisions = [{'id': int(pk), 'label': label} for pk, label in draft_form.fields['job'].choices if pk][:25]
        current_rows = ClientResponse.objects.filter(revision=revision).select_related('evidence').defer('note', 'evidence__body').order_by('-pk')[:25]
        responses = [{'id': row.pk, 'evidence_id': row.evidence_id, 'revision_id': row.revision_id,
                      'receipt_id': row.receipt_id, 'kind': row.kind} for row in current_rows
                     if witness.source_note_visible(actor, case, row.evidence.source)]
        adoption = BaselineAdoption.objects.filter(revision=revision).select_related('signedbaselineintake').first()
        adoption_value, packet_value, proof_choices, requirement_choices = None, None, [], []
        if adoption and any(row['id'] == adoption.response_id for row in responses):
            current = False
            try:
                signatures.assert_current_signed_baseline(case)
            except (PermissionDenied, ValidationError):
                pass
            else:
                current = True
            intake = getattr(adoption, 'signedbaselineintake', None)
            adoption_value = {'id': adoption.pk, 'revision_id': adoption.revision_id,
                              'finance_intake_id': intake.pk if intake else None, 'current': current}
        if can_record:
            try:
                require(actor, case, 'baseline.sign')
            except PermissionDenied:
                pass
            else:
                packet = signatures.latest(case)
                if packet:
                    packet_value = {'id': packet.pk, 'revision_id': packet.revision_id, **signatures.packet_status(packet)}
                signed = next((row for row in responses if row['kind'] == 'signed'), None)
                if signed:
                    controls = signature_form(case, ClientResponse.objects.get(pk=signed['id']))
                    proof_choices = proof_rows(public_evidence(controls.fields['prd_signature'].queryset).order_by('-pk')[:50])
                    requirement_choices = proof_rows(public_evidence(controls.fields['prd'].queryset).order_by('-pk')[:50])
    return {'case_revision': case.revision, 'current_revision_id': revision.pk if revision else None, 'can_record': can_record,
            'receipts': receipts, 'owned_files': owned_files, 'witness': observed, 'witness_files': list(map(file_value, files)),
            'parties': parties, 'responses': responses, 'packet': packet_value, 'signature_proofs': proof_choices,
            'requirements': requirement_choices, 'adoption': adoption_value, 'revision_drafts': revisions}


FIELDS = {
    'witness': {'revision_id': ID, 'receipt_id': ID, 'client_name': {**TEXT, 'maxLength': 160}, 'responded_at': DATETIME,
                'outcome': OUTCOME, 'genuine': {'const': True}, 'proof_ids': array(ID, limit=50), 'note': NOTE,
                'operation_key': UUID, 'predecessor_id': nullable(ID), 'party_ref': nullable(KEY)},
    'signatures': {'response_id': ID, 'prd_id': ID, 'signatures': SIGNATURES, 'note': NOTE,
                   'operation_key': KEY, 'predecessor_id': nullable(ID)},
    'adopt': {'response_id': ID},
    'reaffirm': {'packet_id': ID},
    'internal_exemption': {'prd_id': ID, 'note': NOTE, 'operation_key': KEY, 'predecessor_id': nullable(ID)},
    'signature_policy': {'value': VALUE, 'evidence_id': ID, 'effective_from': DATETIME},
    'review_changes': {'witness_id': ID},
    'save_revision': {'witness_id': ID, 'job_id': ID, 'sources': obj(dict.fromkeys(SOURCE_KINDS, nullable(ID))),
                      'scope': {**TEXT, 'maxLength': 20000}, 'note': NOTE, 'confirmed': {'const': True},
                      'operation_key': UUID, 'predecessor_id': nullable(ID)},
    'prepare_revision': {'draft_id': ID},
}
ACTIONS = {'oneOf': [obj({'action': {'const': key}, 'case_revision': REVISION, **fields})
                     for key, fields in FIELDS.items()]}


@endpoint(method='POST', request=ACTIONS, response=RESULT, status=201,
    summary='Capture actual commercial response, review changes, record separate signatures, or adopt the exact signed baseline')
@transaction.atomic
def command(request, case_id, *, body):
    actor = request.user
    case = project(actor, case_id)
    expected = body['case_revision']
    action = body['action']
    if action == 'witness':
        row, _ = witness.record(actor, case.pk, body['revision_id'], body['receipt_id'], body['client_name'],
            parse_datetime(body['responded_at']), body['outcome'], body['genuine'], body['proof_ids'], body['note'],
            body['operation_key'], expected, body['predecessor_id'], body['party_ref'])
    elif action in ('signatures', 'adopt'):
        case = lock_case(actor, case.pk, 'commercial.response', expected)
        response = current_response(actor, case, body['response_id'], signed=True)
        if action == 'signatures':
            supplied = body['signatures']
            if supplied.get('sow', {}).get('evidence_id', response.evidence_id) != response.evidence_id:
                raise Problem(422, 'invalid_input', 'Use the exact statement-of-work signature from the selected response.')
            row = signatures.capture_packet(actor, case.pk, body['prd_id'], supplied, body['note'],
                body['operation_key'], expected, response.revision_id, body['predecessor_id'])
        else:
            row = native.adopt_signed(actor, case.pk, response.revision_id, response.pk, expected)
    elif action == 'reaffirm':
        get_object_or_404(CommercialSignaturePacket, case=case, pk=body['packet_id'])
        row = signatures.reaffirm_baseline(actor, case.pk, body['packet_id'], expected)
    elif action == 'internal_exemption':
        row = record_exemption(actor, case.pk, body['prd_id'], body['note'], body['operation_key'], expected, body['predecessor_id'])
    elif action == 'signature_policy':
        row = signatures.draft_contract(actor, case.pk, body['value'], body['evidence_id'],
                                        parse_datetime(body['effective_from']), expected)
    elif action == 'review_changes':
        jobs = commercial_rework.ask_agent(actor, case.pk, body['witness_id'], expected)
        return {'case_revision': case.revision, 'record_ids': [job.pk for job in jobs]}
    elif action == 'save_revision':
        row = commercial_rework.capture(actor, case.pk, body['witness_id'], body['job_id'], body['sources'], body['scope'],
            body['note'], body['confirmed'], body['operation_key'], expected, body['predecessor_id'])
    else:
        row = commercial_rework.prepare_revision(actor, case.pk, body['draft_id'], expected)
    case.refresh_from_db(fields=['revision'])
    return {'case_revision': case.revision, 'record_ids': [row.pk]}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'file': {'type': 'string', 'format': 'binary'}}),
    response=FILE, status=201, multipart=True, summary='Upload private evidence for a witnessed client response')
@transaction.atomic
def upload(request, case_id):
    actor = request.user
    case = project(actor, case_id)
    witness.witness(actor, case)
    try:
        expected = int(request.POST['case_revision'])
    except (ValueError, TypeError):
        raise Problem(422, 'invalid_input', 'Use the current project revision.') from None
    lock_case(actor, case.pk, 'commercial.response', expected)
    return file_value(upload_file(actor, case, request.FILES['file']))


@endpoint(response={'type': 'string', 'format': 'binary'}, media_type='application/octet-stream',
    summary='Download only a private file cited by this exact authorised client response')
def download(request, case_id, evidence_id, upload_id):
    case = project(request.user, case_id)
    evidence = get_object_or_404(case.evidence.defer('body'), pk=evidence_id)
    rows = witness.proof_rows(request.user, case, evidence)
    file = next((row for row in rows if row.pk == upload_id), None)
    if file is None:
        raise PermissionDenied
    try:
        body = case_uploads.read(file)
    except OSError:
        raise Problem(503, 'source_unavailable', 'The private file is temporarily unavailable.') from None
    return FileResponse(BytesIO(body), as_attachment=True, filename=file.name, content_type='application/octet-stream')
