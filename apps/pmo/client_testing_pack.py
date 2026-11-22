"""Review delivery of exact client test files and track the response window."""
import json
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from adapters import case_uploads, client_uat as contract
from adapters.forecast import obj
from apps.agents.models import CaseUpload
from apps.core.models import Audit
from apps.core.services import add_evidence, bump, event, lock_case
from apps.documents.contracts import digest, validate
from apps.identity.services import require

from . import client_uat, delivery
from .clocks import aware
from .models import DeliverySource, DeliverySourceVerification


PACK = 'client_test_pack_delivery'
REMINDER = 'client_test_reply_reminder'
REVIEW = 'human-client-test-pack-receipt/v1'
PACK_SCHEMA = obj({'format': {'const': 'psl.client-test-pack/v1'}, 'target_id': contract.ID,
                   'target_sha256': contract.HASH, 'pack': contract.PROOF, 'receipt_file': contract.PROOF,
                   'reference': {'type': 'string', 'minLength': 1, 'maxLength': 160},
                   'received_at': {'type': 'string'}, 'authority': contract.AUTH})
REMINDER_SCHEMA = obj({'format': {'const': 'psl.client-test-reminder/v1'}, 'pack': contract.ID,
                       'review': contract.ID, 'previous': contract.NULL_ID, 'reply_due_at': {'type': 'string'},
                       'remind_at': {'type': ['string', 'null']}, 'reason': contract.TEXT, 'authority': contract.AUTH})


def pinned_file(file):
    return {'id': file.pk, 'sha256': file.sha256, 'size': file.size, 'actor_id': file.actor_id}


def files_for(row):
    pins = [row.payload['pack'], row.payload['receipt_file']]
    files = CaseUpload.objects.filter(pk__in=[pin['id'] for pin in pins], case_id=row.dossier.case_id, actor=row.actor).in_bulk()
    if any(pin['id'] not in files or pinned_file(files[pin['id']]) != pin for pin in pins):
        raise ValidationError('The original test pack or delivery proof changed.')
    return [files[pin['id']] for pin in pins]


def append(actor, case, dossier, kind, key, data, schema):
    validate(schema, data)
    if not isinstance(key, UUID):
        raise ValidationError('Refresh the form before recording the next step.')
    reference = f'psl:{kind}:{key}'
    previous = dossier.sources.filter(kind=kind, external_ref=reference).first()
    if previous:
        if previous.actor_id != actor.pk or previous.payload != data:
            raise ValidationError('This request already identifies different evidence.')
        return previous
    proof = add_evidence(actor, case.pk, 'agent_private_client_test_pack_metadata', metadata(data), reference)
    row = DeliverySource.objects.create(dossier=dossier, kind=kind, external_ref=reference,
                                         payload=data, evidence=proof, actor=actor)
    event(actor, case, kind + '.recorded', row=row.pk, sha256=digest(data))
    return row


def metadata(data):
    return json.dumps({'format': data['format'], 'payload_sha256': digest(data)})


def check_provenance(row, schema):
    validate(schema, row.payload)
    case_id = row.dossier.case_id
    proof = row.evidence
    if (proof.case_id != case_id or proof.source != row.external_ref or proof.created_by_id != row.actor_id
            or proof.body != metadata(row.payload) or not Audit.objects.filter(
                case_id=case_id, actor_id=row.actor_id, action=row.kind + '.recorded',
                data={'row': row.pk, 'sha256': digest(row.payload)}).exists()):
        raise ValidationError('Check the original recorded evidence for this work.')


def fresh_target(actor, case, dossier_id, target_id):
    dossier = delivery.dossier_for(case, dossier_id)
    delivery.ensure_open(dossier)
    target = client_uat.head(dossier, contract.TARGET)
    if not target or target.pk != target_id:
        raise ValidationError('Review the current request for this client and version.')
    client_uat.current_target(actor, target)
    return dossier, target


@transaction.atomic
def record_pack(actor, case_id, dossier_id, expected, target_id, key, pack_id, receipt_file_id, reference, received_at):
    case = lock_case(actor, case_id, 'client_uat.record', expected)
    authority = client_uat.witness(actor, case)
    dossier, target = fresh_target(actor, case, dossier_id, target_id)
    if client_uat.head(dossier, contract.RESPONSE, target.pk):
        raise ValidationError('This client has already replied. Preserve the current response history.')
    if pack_id == receipt_file_id:
        raise ValidationError('Choose separate files for the test pack and proof of delivery.')
    files = CaseUpload.objects.filter(pk__in=[pack_id, receipt_file_id], case=case, actor=actor).in_bulk()
    if set(files) != {pack_id, receipt_file_id}:
        raise PermissionDenied('Choose your own uploaded files in this project.')
    instant = aware(received_at)
    if not aware(target.payload['sent_at']) <= instant <= timezone.now():
        raise ValidationError('Use the actual delivery time at or after the send time.')
    data = {'format': 'psl.client-test-pack/v1', 'target_id': target.pk, 'target_sha256': digest(target.payload),
            'pack': pinned_file(files[pack_id]), 'receipt_file': pinned_file(files[receipt_file_id]),
            'reference': reference, 'received_at': instant.isoformat(), 'authority': authority}
    return append(actor, case, dossier, PACK, key, data, PACK_SCHEMA)


def current_pack(actor, dossier, target):
    row = client_uat.head(dossier, PACK, target.pk)
    if row is None:
        return None
    return checked_pack(actor, dossier, target, row)


def checked_pack(actor, dossier, target, row):
    client_uat.current_target(actor, target)
    check_provenance(row, PACK_SCHEMA)
    if row.payload['target_sha256'] != digest(target.payload):
        raise ValidationError('The test pack needs a fresh check against the current client request.')
    if row.payload['authority'] != client_uat.witness(row.actor, dossier.case):
        raise ValidationError('The original test pack recorder needs a fresh authority check.')
    files_for(row)
    return row


def review_context(actor, row):
    cfg, value, authority = client_uat.reviewer(actor, row.dossier.case)
    if value['independent_review'] is None:
        raise ValidationError('Choose whether a separate pack reviewer is required in the proof review settings.')
    if value['independent_review'] and actor.pk == row.actor_id:
        raise PermissionDenied('A separate configured reviewer must check the delivery proof.')
    return {'configuration': cfg.pk, 'authority': authority, 'sha256': digest(row.payload)}


@transaction.atomic
def confirm_pack(actor, case_id, dossier_id, expected, target_id, row_id, note):
    case = lock_case(actor, case_id, 'client_uat.review', expected)
    dossier, target = fresh_target(actor, case, dossier_id, target_id)
    row = current_pack(actor, dossier, target)
    if row is None or row.pk != row_id:
        raise ValidationError('Choose the current test pack and delivery proof.')
    validate(contract.TEXT, note)
    context = review_context(actor, row)
    last = current_review(row)
    if last and last.actor_id == actor.pk:
        return last
    try:
        for file in files_for(row):
            case_uploads.read(file)
    except OSError as exc:
        raise ValidationError('The original files are temporarily unavailable.') from exc
    checked = DeliverySourceVerification.objects.create(source=row, adapter=REVIEW, actor=actor,
                                                         result={**context, 'note': note})
    event(actor, case, 'client_test_pack.delivery_confirmed', row=row.pk, check=checked.pk)
    bump(case)
    return checked


def current_review(row):
    last = row.verifications.filter(adapter=REVIEW).select_related('actor').order_by('-pk').first()
    if not last:
        return None
    try:
        context = review_context(last.actor, row)
    except (PermissionDenied, ValidationError):
        return None
    if not Audit.objects.filter(case_id=row.dossier.case_id, actor_id=last.actor_id,
                                action='client_test_pack.delivery_confirmed',
                                data={'row': row.pk, 'check': last.pk}).exists():
        return None
    return last if all(last.result.get(key) == value for key, value in context.items()) else None


def latest_reminder(dossier, pack):
    return dossier.sources.filter(kind=REMINDER, payload__pack=pack.pk).order_by('-pk').first()


@transaction.atomic
def schedule(actor, case_id, dossier_id, expected, target_id, pack_id, previous, key, reply_due_at, remind_at, reason):
    case = lock_case(actor, case_id, 'client_uat.record', expected)
    authority = client_uat.witness(actor, case)
    dossier, target = fresh_target(actor, case, dossier_id, target_id)
    pack = current_pack(actor, dossier, target)
    if pack is None or pack.pk != pack_id or not (review := current_review(pack)):
        raise ValidationError('Review the exact delivery receipt before changing the reminder.')
    if client_uat.head(dossier, contract.RESPONSE, target.pk):
        raise ValidationError('The client already replied. The earlier reminder stays in history.')
    current = latest_reminder(dossier, pack)
    if previous != (current.pk if current else None):
        raise ValidationError('The response window changed. Review the latest dates.')
    due = aware(reply_due_at)
    remind = aware(remind_at) if remind_at else None
    if due <= aware(pack.payload['received_at']) or (remind and remind <= timezone.now()):
        raise ValidationError('The deadline must follow delivery. Choose a future time for a new reminder.')
    data = {'format': 'psl.client-test-reminder/v1', 'pack': pack.pk, 'review': review.pk, 'previous': previous,
            'reply_due_at': due.isoformat(), 'remind_at': remind.isoformat() if remind else None, 'reason': reason,
            'authority': authority}
    return append(actor, case, dossier, REMINDER, key, data, REMINDER_SCHEMA)


def projection(actor, dossier, target):
    if not target:
        return {}
    try:
        pack = current_pack(actor, dossier, target)
        review = current_review(pack) if pack else None
    except (PermissionDenied, ValidationError):
        return {'stale': True}
    recorded = latest_reminder(dossier, pack) if review else None
    timing = None
    if recorded:
        try:
            check_provenance(recorded, REMINDER_SCHEMA)
            if (recorded.payload['review'] == review.pk
                    and recorded.payload['authority'] == client_uat.witness(recorded.actor, dossier.case)):
                timing = recorded
        except (PermissionDenied, ValidationError):
            pass
    return {'pack': pack, 'review': review, 'timing': timing, 'previous': recorded.pk if recorded else None,
            'client_replied': bool(client_uat.head(dossier, contract.RESPONSE, target.pk)),
            'reminder_due': bool(timing and timing.payload['remind_at'] and aware(timing.payload['remind_at']) <= timezone.now())}
