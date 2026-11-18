"""Evidenced external replies preserve the recorder and the actual recipient separately."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef

from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case
from apps.core.read_observation import read_observation
from apps.documents.controlled import current_version
from apps.documents.models import PublicationReceipt
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.handover_reply_validators import COMPONENT, VALUE
from apps.policy.services import active_component, decision_authority, reference_values
from apps.documents.contracts import validate
from . import delivery, delivery_closure
from .clocks import aware
from .rfp import past
from .services import subject

ACTION = 'delivery.record_support_reply'


def rules(case):
    try:
        configuration = active_component(COMPONENT, case)
    except ValidationError:
        raise ValidationError('Review who may record Support replies and the accepted reply channels.') from None
    value = reference_values(configuration)[0]
    validate(VALUE, value)
    return configuration, value


def authority(actor, case, role):
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('An active recorder is required.')
    require(actor, case, 'case.read')
    require(actor, case, 'delivery.read')
    require(actor, case, ACTION)
    configuration, value = rules(case)
    if role not in value['recorder_roles']:
        raise PermissionDenied('This role cannot record Support replies under the current rule.')
    return configuration, value, decision_authority(actor, case, role)


@read_observation
def current_receipt(case, dossier, receipt_id):
    if type(receipt_id) is not int or receipt_id < 1:
        raise ValidationError('Choose an exact handover receipt reference.')
    receipt = PublicationReceipt.objects.select_related('publication__version', 'recipient').filter(
        pk=receipt_id, publication__version__document__case=case,
        publication__version__audience='internal',
        publication__version__deliverydocumentbinding__dossier=dossier,
        publication__version__deliverydocumentbinding__purpose='handover').first()
    if receipt is None:
        raise ValidationError('Choose the exact delivered Support handover receipt.')
    current_version(case, receipt.publication.version_id)
    binding = receipt.publication.version.deliverydocumentbinding
    if binding.snapshot != delivery_closure.handover_inputs(dossier, binding.data):
        raise ValidationError('The handover changed. Publish and review the current package first.')
    return receipt, binding


@transaction.atomic
def record_reply(actor, case_id, dossier_id, receipt_id, status, evidence_id, note,
                 party, channel, responded_at, role, predecessor, expected):
    if any(type(value) is not int or value < 1 for value in [dossier_id, evidence_id, expected]):
        raise ValidationError('Choose exact current handover and source references.')
    case = lock_case(actor, case_id, ACTION, expected)
    dossier = delivery.dossier_for(case, dossier_id)
    delivery.ensure_open(dossier)
    list(Grant.objects.select_for_update().filter(case=case, user=actor).order_by('pk'))
    configuration, value, auth = authority(actor, case, role)
    if status not in ['received', 'gaps'] or channel not in value['channels']:
        raise ValidationError('Choose the actual reply status and a configured channel.')
    if not isinstance(party, str) or not party.strip() or len(party) > 200:
        raise ValidationError('Name the person who sent the Support reply.')
    delivery.note_required(note)
    responded_at = aware(responded_at)
    past(responded_at)
    receipt, binding = current_receipt(case, dossier, receipt_id)
    if responded_at < receipt.created_at:
        raise ValidationError('The reply must follow the exact recorded handover delivery.')
    previous = dossier.records.filter(kind='handover', data__receipt_id=receipt.pk).order_by('-pk').first()
    if type(predecessor) is not int or predecessor != (previous.pk if previous else 0):
        raise ValidationError('A newer Support reply is available. Refresh before recording another.')
    proof = subject(case, evidence_id)
    if not public_evidence(case.evidence.filter(pk=proof.pk)).exists():
        raise ValidationError('Select currently available proof of the Support reply.')
    require(proof.created_by, case, 'evidence.add')
    attestation = {'configuration': configuration.pk, 'role': role, 'authority': auth,
        'party': party.strip(), 'channel': channel, 'responded_at': responded_at.isoformat(),
        'proof_sha256': proof.sha256, 'predecessor': predecessor}
    result = delivery.record(actor, case, dossier, 'handover', proof,
        {'receipt_id': receipt.pk, 'recipient_id': receipt.recipient_id, 'status': status,
         'note': note, 'attestation': attestation}, binding.snapshot, parent=previous)
    from apps.workflows.factory_progress import wake_waiting
    work_id = receipt.publication.factory_work_id
    if work_id:
        wake_waiting(work_id)
    return result


def validate_record(record, receipt):
    case = record.dossier.case
    data = record.data['attestation']
    fields = {'configuration', 'role', 'authority', 'party', 'channel', 'responded_at', 'proof_sha256', 'predecessor'}
    if not isinstance(data, dict) or set(data) != fields or not isinstance(data['party'], str) or not data['party'].strip():
        raise ValidationError('The Support reply needs its exact recorded facts and authority.')
    actor = get_user_model().objects.get(pk=record.actor_id)
    configuration, value, auth = authority(actor, case, data['role'])
    proof = subject(case, record.evidence_id)
    if (configuration.pk != data['configuration'] or auth != data['authority'] or
            data['channel'] not in value['channels'] or data['proof_sha256'] != proof.sha256 or
            record.data['recipient_id'] != receipt.recipient_id or
            aware(data['responded_at']) < receipt.created_at or
            not public_evidence(case.evidence.filter(pk=proof.pk)).exists()):
        raise ValidationError('Review the current recorder authority, exact delivery and Support reply proof.')
    require(proof.created_by, case, 'evidence.add')
    past(aware(data['responded_at']))


def available_roles(actor, case):
    try:
        _, value = rules(case)
        result = []
        for role in value['recorder_roles']:
            try:
                authority(actor, case, role)
                result.append(role)
            except (PermissionDenied, ValidationError):
                continue
        return result
    except (PermissionDenied, ValidationError):
        return []


def decorate_receipts(case, receipts):
    """Load source visibility once and keep copied reply text behind that boundary."""
    source_ids = [item['ack'].evidence_id for item in receipts if item['ack']]
    owner = Grant.objects.filter(case=case, user_id=OuterRef('created_by_id'),
        user__is_active=True, action='evidence.add', active=True)
    source_access = dict(public_evidence(case.evidence.filter(pk__in=source_ids)).annotate(
        owner_current=Exists(owner)).values_list('pk', 'owner_current'))
    for item in receipts:
        ack = item['ack']
        attestation = ack.data.get('attestation') if ack else None
        readable = bool(ack and ack.evidence_id in source_access and
            (attestation is None or source_access[ack.evidence_id]))
        item['reply_source_available'] = readable
        item['reply_note'] = ack.data['note'] if readable else ''
        item['reply_party'] = attestation.get('party', '') if readable and isinstance(attestation, dict) else ''
        item['reply_channel'] = attestation.get('channel', '') if item['reply_party'] else ''
        item['reply_time'] = None
        if item['reply_party']:
            try:
                item['reply_time'] = aware(attestation['responded_at'])
            except (KeyError, ValidationError):
                pass
