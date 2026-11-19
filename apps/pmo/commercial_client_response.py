"""Exact delivered-document witness flow over existing commercial and signature services.

Private proof is kept outside generic evidence views. Recording the client response
does not sign a contract, approve a baseline, decide billing or bypass dual proof.
"""
import json
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from adapters import case_uploads
from adapters import commercial_client_response as contract
from apps.agents.models import CaseUpload
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence, event, lock_case
from apps.documents.contracts import digest
from apps.documents.models import PublicationReceipt
from apps.identity.services import require
from apps.policy.services import active_component, decision_authority, reference_values
from . import commercial
from .clocks import aware


def readable(actor, case):
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('Current active commercial reader required.')
    for action in ['case.read', 'commercial.read']:
        require(actor, case, action)
    if case.kind != 'project':
        raise PermissionDenied('Statement-of-work responses belong to project workspaces.')


def witness(actor, case):
    readable(actor, case)
    require(actor, case, 'commercial.response')
    return decision_authority(actor, case, 'PM')


def latest(case):
    return Evidence.objects.filter(case=case, kind=contract.KIND).defer('body').select_related('created_by').order_by('-version').first()


def receipt_for(case, revision_id, receipt_id):
    from .models import CommercialRevision, RFPResponse
    revision = CommercialRevision.objects.filter(pk=revision_id, dossier__case=case).first()
    if not revision or RFPResponse.objects.filter(commercial=revision).exists():
        raise ValidationError('Choose a delivered project statement of work; a bid response is separate.')
    receipt = PublicationReceipt.objects.select_related('publication__version__document').filter(
        pk=receipt_id, publication__version__commercialdocumentbinding__revision=revision,
        publication__version__audience='client').first()
    if not receipt or receipt.payload_sha256 != receipt.publication.version.payload_sha256:
        raise ValidationError('Select the exact client delivery receipt for this statement of work.')
    return revision, receipt


def read(actor, case, evidence):
    readable(actor, case)
    if not evidence or evidence.case_id != case.pk or evidence.kind != contract.KIND:
        raise ValidationError('Select this project’s exact client response.')
    if actor.pk != evidence.created_by_id:
        require(actor, case, 'commercial.proof.read')
    if not get_user_model().objects.filter(pk=evidence.created_by_id, is_active=True).exists():
        raise PermissionDenied('The original response recorder no longer has current authority.')
    witness(evidence.created_by, case)
    try:
        value = contract.read(json.loads(evidence.body))
    except (ValueError, TypeError):
        raise ValidationError('The retained client response is not a supported typed record.') from None
    if (evidence.sha256 != digest_text(evidence.body)
            or evidence.source != contract.PREFIX + value['operation_key']
            or not Audit.objects.filter(case=case, actor=evidence.created_by, action='commercial.client_witness',
                data={'evidence': evidence.pk, 'sha256': evidence.sha256, 'response': value['response']}).exists()):
        raise ValidationError('The original client response authority or provenance changed; record a reviewed correction.')
    revision, receipt = receipt_for(case, value['revision'], value['receipt'])
    if (receipt.publication.version_id, receipt.payload_sha256) != (value['document_version'], value['document_sha256']):
        raise ValidationError('The client response identifies a different delivered document.')
    from .models import ClientResponse
    response = ClientResponse.objects.filter(pk=value['response'], revision=revision, receipt=receipt,
        evidence_id=value['evidence'], actor_id=evidence.created_by_id,
        kind='feedback' if value['outcome'] == 'changes_requested' else value['outcome']).first()
    if not response or response.evidence.source != evidence.source:
        raise ValidationError('The response has no exact native commercial record.')
    return value, response


def digest_text(body):
    import hashlib
    return hashlib.sha256(body.encode()).hexdigest()


def proof_rows(actor, case, evidence):
    value, _ = read(actor, case, evidence)
    rows = {row.pk: row for row in CaseUpload.objects.filter(case=case, pk__in=[p['id'] for p in value['proofs']])}
    for pin in value['proofs']:
        row = rows.get(pin['id'])
        if not row or (row.actor_id, row.sha256, row.size, row.name) != (pin['actor'], pin['sha256'], pin['size'], pin['name']):
            raise ValidationError('The private response proof no longer matches its recorded source.')
    return [rows[pin['id']] for pin in value['proofs']]


def source_note_visible(actor, case, source):
    """Legacy pages must authorise new private notes before loading their text."""
    if not source.startswith(contract.PREFIX):
        return True  # The existing legacy commercial-read contract is unchanged.
    metadata = Evidence.objects.filter(case=case, kind=contract.KIND, source=source).defer('body').first()
    try:
        read(actor, case, metadata)
    except (PermissionDenied, ValidationError):
        return False
    return True


@transaction.atomic
def record(actor, case_id, revision_id, receipt_id, client_name, responded_at, outcome, genuine,
           proof_ids, note, operation_key, expected, predecessor=None, party_ref=None):
    case = lock_case(actor, case_id, 'commercial.response', expected)
    authority = witness(actor, case)
    require(actor, case, 'evidence.add')
    if not isinstance(client_name, str) or not client_name.strip() or len(client_name) > 160:
        raise ValidationError('Name the person who actually responded.')
    if genuine is not True or outcome not in ['signed', 'changes_requested', 'declined']:
        raise ValidationError('Record the actual response and confirm it came from the named client.')
    try:
        key = str(UUID(str(operation_key)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Reload this response form before recording it.') from None
    commercial.note_required(note)
    revision, receipt = receipt_for(case, revision_id, receipt_id)
    commercial.current_revision(case, revision.pk)
    instant = aware(responded_at, 'Actual client response time')
    if not receipt.created_at <= instant <= timezone.now():
        raise ValidationError('The actual response must be after this delivery and cannot be in the future.')
    if (not isinstance(proof_ids, list) or not 1 <= len(proof_ids) <= 12
            or any(type(pk) is not int for pk in proof_ids) or len(set(proof_ids)) != len(proof_ids)):
        raise ValidationError('Select one to twelve distinct private proof files.')
    uploads = list(CaseUpload.objects.filter(case=case, actor=actor, pk__in=proof_ids).order_by('pk'))
    if len(uploads) != len(proof_ids):
        raise PermissionDenied('Only your own exact project files can support this response.')
    pins = [{'id': row.pk, 'actor': row.actor_id, 'sha256': row.sha256, 'size': row.size, 'name': row.name} for row in uploads]
    policy_id, identity_id = None, None
    if party_ref is not None:
        policy = active_component('D11.client_signature_contract', case)
        rules = reference_values(policy)[0]
        party = next((p for p in rules['parties'] if p['party_ref'] == party_ref and 'sow' in p['documents']), None)
        if party is None:
            raise ValidationError('Select a currently owner-confirmed statement-of-work signer or leave their eligibility undecided.')
        policy_id, identity_id = policy.pk, party['identity_evidence_id']
    command = digest({'revision': revision.pk, 'receipt': receipt.pk, 'client_name': client_name.strip(),
        'responded_at': instant.isoformat(), 'outcome': outcome, 'proofs': pins, 'note': note,
        'predecessor': predecessor, 'actor': actor.pk, 'party_ref': party_ref,
        'party_identity_evidence': identity_id, 'signature_policy': policy_id})
    old = Evidence.objects.filter(case=case, kind=contract.KIND, source=contract.PREFIX + key).defer('body').first()
    if old:
        value, response = read(actor, case, old)
        if value['command_sha256'] != command or old.created_by_id != actor.pk:
            raise ValidationError('This response reference already identifies different details.')
        return old, response
    prior = latest(case)
    if (prior.pk if prior else None) != predecessor:
        raise ValidationError('This response changed. Review the current record before correcting it.')
    for upload in uploads:
        case_uploads.read(upload)  # Native bounded integrity check; no model transmission.
    public = add_evidence(actor, case.pk, 'signature' if outcome == 'signed' else 'client_feedback',
        'A human recorded the client’s ' + outcome.replace('_', ' ') + ' response to the exact delivered statement of work.',
        contract.PREFIX + key)
    case.refresh_from_db(fields=['revision'])
    response = commercial.capture_response(actor, case.pk, revision.pk, receipt.pk,
        'feedback' if outcome == 'changes_requested' else outcome, public.pk, note, case.revision)
    value = {'protocol': contract.PROTOCOL, 'operation_key': key, 'command_sha256': command,
        'predecessor': predecessor, 'revision': revision.pk, 'receipt': receipt.pk,
        'document_version': receipt.publication.version_id, 'document_sha256': receipt.payload_sha256,
        'response': response.pk, 'evidence': public.pk, 'client_name': client_name.strip(),
        'responded_at': instant.isoformat(), 'outcome': outcome, 'genuine': True, 'proofs': pins,
        'party_ref': party_ref, 'party_identity_evidence': identity_id, 'signature_policy': policy_id,
        'authority': authority, 'assurance': 'human_witness_only_not_signature_provider_authentication'}
    contract.read(value)
    metadata = add_evidence(actor, case.pk, contract.KIND, json.dumps(value, sort_keys=True), contract.PREFIX + key)
    event(actor, case, 'commercial.client_witness', evidence=metadata.pk, sha256=metadata.sha256, response=response.pk)
    from apps.workflows.models import FactoryWork
    from apps.workflows.factory_progress import wake_waiting
    ids = list(FactoryWork.objects.filter(case=case, definition='commercial/v1').values_list('pk', flat=True)[:100])
    transaction.on_commit(lambda: [wake_waiting(pk) for pk in ids])
    return metadata, response


_UNSPECIFIED_REVISION = object()


def current_for_signature(actor, case, signature, revision_id=_UNSPECIFIED_REVISION):
    """Legacy native evidence stays on its existing contract; new witnesses are exact."""
    if not signature.source.startswith(contract.PREFIX):
        return None
    metadata = Evidence.objects.filter(case=case, kind=contract.KIND, source=signature.source).defer('body').first()
    value, response = read(actor, case, metadata)
    proof_rows(actor, case, metadata)
    if (value['outcome'] != 'signed' or value['evidence'] != signature.pk
            or revision_id is not _UNSPECIFIED_REVISION and value['revision'] != revision_id
            or response.revision.responses.order_by('-pk').first().pk != response.pk):
        raise ValidationError('The current client response does not confirm this exact statement of work signature.')
    return metadata


def qualify_signature_packet(packet, rules):
    from .services import subject
    metadata = current_for_signature(packet.actor, packet.case,
        subject(packet.case, packet.signatures['sow']['evidence_id'], 'signature'), packet.revision_id)
    if metadata is None:
        return  # Existing native legacy evidence retains its existing contract.
    value, _ = read(packet.actor, packet.case, metadata)
    party = next(p for p in rules['parties'] if p['party_ref'] == packet.signatures['sow']['party_ref'] and 'sow' in p['documents'])
    # The witness is a historical fact. Fresh native signature packets enforce
    # today's exact role/policy versions; unchanged identity can be reaffirmed.
    if (value['signature_policy'] is None or (value['party_ref'], value['party_identity_evidence']) != (
            party['party_ref'], party['identity_evidence_id'])):
        raise ValidationError('Confirm the owner-eligible signer on the current client response before using it as a signed baseline.')


def ask_agent(actor, case, metadata):
    from apps.agents.upload_views import queue_draft
    rows = proof_rows(actor, case, metadata)
    if metadata.created_by_id != actor.pk:
        raise PermissionDenied('Only the original witness may send their own files to the test model.')
    return [queue_draft(actor, row, 'A07') for row in rows]
