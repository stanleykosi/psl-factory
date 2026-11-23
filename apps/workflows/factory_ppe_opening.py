"""Attach private PDF opening proof to a returned, exactly selected asset register."""

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from adapters import case_uploads
from apps.core.evidence_access import PPE_OPENING_SOURCE
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence, event
from apps.finance import analysis, ppe
from apps.identity.services import require
from . import factory, factory_ppe as flow
from .models import FactoryWork


ATTACHED = 'factory.ppe_opening_proof_attached'
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpeningProof:
    name: str
    key: str
    size: int
    sha256: str


def returned_subject(work, register):
    for target, purpose in ((register, 'register'), (flow.schedule(work), 'schedule')):
        decision = ppe.latest(target, purpose) if target else None
        if decision and decision.verdict == 'return' and decision.snapshot == target.snapshot:
            return target, decision
    return None


def pdf_bytes(file):
    if file is None or not 0 < file.size <= case_uploads.LIMIT:
        raise ValidationError('Choose one PDF proof file up to 5 MiB.')
    name = file.name.replace('\\', '/').rsplit('/', 1)[-1]
    if not name.lower().endswith('.pdf') or len(name) > 160 or any(ord(character) < 32 for character in name):
        raise ValidationError('Choose a PDF proof file with a valid name.')
    data = file.read(case_uploads.LIMIT + 1)
    if len(data) != file.size or not data.startswith(b'%PDF-'):
        raise ValidationError('Choose a valid PDF proof file.')
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise ValidationError('PDF proof validation is unavailable.') from exc
    try:
        pdf = PdfReader(BytesIO(data), strict=True)
        if pdf.is_encrypted or pdf.trailer.get('/Root') is None:
            raise ValidationError('Choose a readable, unencrypted PDF proof file.')
    except (PdfReadError, ValueError, KeyError, IndexError, RecursionError) as exc:
        raise ValidationError('Choose a valid PDF proof file.') from exc
    return name, data


def authority(actor, work):
    if actor.pk != work.actor_id:
        raise PermissionDenied('The preparer records private proof for this returned asset work.')
    factory.access(actor, work.case, 'factory.manage', flow.DEFINITION)
    for action in ('ppe.capture', 'ppe.report', 'evidence.add'):
        require(actor, work.case, action)


def attach(actor, work_id, expected, case_expected, target_id, review_id, reason, uploaded):
    if any(type(value) is not int or value < 1 for value in (work_id, expected, case_expected, target_id, review_id)):
        raise ValidationError('Open the exact current return before submitting proof.')
    staged_key = None
    try:
        with transaction.atomic(durable=True):
            work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(
                pk=work_id, definition=flow.DEFINITION)
            authority(actor, work)
            case = ppe.locked(actor, work.case_id, 'ppe.capture', case_expected)
            work.case = case
            authority(actor, work)
            if work.revision != expected or work.cancel_requested or work.status in ('cancelled', 'followup_needed'):
                raise ValidationError('Open the exact current return before submitting proof.')
            flow.settled(work)
            analysis.note(reason)
            register, source = flow.source(work, actor)
            returned = returned_subject(work, register)
            if not returned or (returned[0].pk, returned[1].pk) != (target_id, review_id):
                raise ValidationError('Open the exact register or schedule that Finance returned.')
            ppe.current(returned[0])
            name, data = pdf_bytes(uploaded)
            sha256 = hashlib.sha256(data).hexdigest()
            key = 'ppe-opening-' + secrets.token_hex(32)
            proof = add_evidence(actor, case.pk, 'ppe_opening', 'Private opening proof retained for Finance review.',
                                 PPE_OPENING_SOURCE, case.revision)
            case.refresh_from_db(fields=['revision'])
            supplied = dict(register.payload, opening_evidence_id=proof.pk)
            corrected = add_evidence(actor, case.pk, 'ppe_register', json.dumps(supplied, sort_keys=True),
                                      PPE_OPENING_SOURCE, case.revision)
            case.refresh_from_db(fields=['revision'])
            successor = ppe.capture(actor, case.pk, register.reference, corrected.pk, case.revision)
            case.refresh_from_db(fields=['revision'])
            revised = flow.correct(actor, work.pk, expected, case.revision, successor.pk, source['prior_id'],
                                   source['ledger_id'], reason)
            event(actor, case, ATTACHED, work=work.pk, returned=target_id, review=review_id,
                  prior_register=register.pk, register=successor.pk, register_sha256=successor.sha256,
                  proof=proof.pk, proof_sha256=proof.sha256, storage_key=key, sha256=sha256, size=len(data), name=name)
            staged_key = key
            case_uploads.put(key, data)
        return revised
    except Exception as exc:
        if staged_key:
            try:
                if not Audit.objects.filter(action=ATTACHED, data__storage_key=staged_key).exists():
                    case_uploads.discard_unbound(staged_key)
            except (DatabaseError, OSError, ValidationError):
                LOGGER.warning('Private opening proof for asset work %s needs storage reconciliation', work_id)
        if isinstance(exc, OSError):
            raise ValidationError('Private storage is unavailable. Try again later.') from exc
        raise


def attachment_for(actor, work, register):
    factory.access(actor, work.case, 'factory.read', flow.DEFINITION)
    require(actor, work.case, 'ppe.report')
    if (register.case_id != work.case_id or register.kind != 'ppe_register'
            or register.reference != work.request['register_reference']):
        return None
    proof = Evidence.objects.filter(pk=register.payload['opening_evidence_id'], case=work.case, kind='ppe_opening',
                                   source=PPE_OPENING_SOURCE, created_by_id=register.actor_id).only('id', 'sha256').first()
    if proof is None:
        return None
    ppe.require_opening_owner(register.actor, work.case)
    receipt = Audit.objects.filter(case=work.case, action=ATTACHED, actor_id=register.actor_id,
        data__work=work.pk, data__register=register.pk, data__register_sha256=register.sha256,
        data__proof=proof.pk, data__proof_sha256=proof.sha256).first()
    if receipt is None:
        return None
    data = receipt.data
    return OpeningProof(data['name'], data['storage_key'], data['size'], data['sha256'])
