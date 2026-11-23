"""Private source proof for a specific invoice's recorded milestone handoff."""

import hashlib
import json
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from adapters import case_uploads
from apps.agents.models import CaseUpload
from apps.core.evidence_access import INVOICE_MILESTONE_PROOF
from apps.core.services import add_evidence, lock_case
from apps.finance.models import Handoff
from apps.identity.services import require

from . import factory, factory_routing
from .models import FactoryWork, HumanTask, InvoiceMilestoneProof, TaskEvent


SOURCE = 'psl:invoice-milestone-proof/v1'
ATTACHED = 'factory.invoice_proof_attached'


def handoff_for(work):
    handoff_id = work.request.get('handoff')
    if work.definition != 'pmo-finance/v1' or type(handoff_id) is not int:
        raise ValidationError('This proof requires the original milestone handoff.')
    handoff = Handoff.objects.filter(case_id=work.case_id, pk=handoff_id).select_related('milestone__evidence').first()
    if handoff is None:
        raise ValidationError('The exact milestone handoff is unavailable.')
    milestone = handoff.milestone
    if (milestone.case_id != work.case_id or milestone.evidence.case_id != work.case_id
            or handoff.payload.get('milestone_id') != milestone.pk
            or handoff.payload.get('name') != milestone.name
            or handoff.payload.get('evidence_id') != milestone.evidence_id
            or handoff.payload.get('evidence_sha256') != milestone.evidence.sha256):
        raise ValidationError('The recorded milestone differs from its handoff.')
    return handoff


def supplier(actor, work, value):
    factory.access(actor, work.case)
    factory.access(actor, work.case, 'factory.information')
    require(actor, work.case, 'evidence.add')
    if actor.pk != value['information_resolver_id'] or INVOICE_MILESTONE_PROOF not in value['required_evidence_kinds']:
        raise PermissionDenied('The configured evidence owner for this request must supply this proof.')


def request_matches(work, task, actor):
    return (task.kind == 'factory_information' and task.case_id == work.case_id
            and (task.factory_key or '').startswith(f'factory:{work.pk}:')
            and task.context.get('work') == work.pk and task.context.get('profile') == work.policy_id
            and task.context.get('resolver') == actor.pk and INVOICE_MILESTONE_PROOF in task.context.get('missing', []))


def pin(work, task, handoff, upload, previous):
    return {'work': work.pk, 'task': task.pk, 'handoff': handoff.pk, 'milestone': handoff.milestone_id,
            'upload': upload.pk, 'sha256': upload.sha256, 'size': upload.size, 'previous': previous}


def current(work, value):
    """Use just the exact source bound to this workflow, with its current original owner."""
    if INVOICE_MILESTONE_PROOF not in value['required_evidence_kinds']:
        return None
    proof = (InvoiceMilestoneProof.objects.filter(work=work)
             .select_related('actor', 'task', 'upload', 'evidence').defer('note', 'upload__key', 'upload__name')
             .order_by('-pk').first())
    if proof is None:
        return None
    try:
        handoff = handoff_for(work)
        supplier(proof.actor, work, value)
    except (ValidationError, PermissionDenied):
        return None
    expected = pin(work, proof.task, handoff, proof.upload, proof.previous_id)
    body = json.dumps(expected, sort_keys=True)
    if (proof.handoff_id != handoff.pk or not request_matches(work, proof.task, proof.actor)
            or proof.upload.actor_id != proof.actor_id or proof.upload.case_id != work.case_id
            or proof.evidence.case_id != work.case_id or proof.evidence.created_by_id != proof.actor_id
            or proof.evidence.kind != INVOICE_MILESTONE_PROOF or proof.evidence.source != SOURCE
            or proof.evidence.body != body or proof.evidence.sha256 != hashlib.sha256(body.encode()).hexdigest()):
        return None
    return proof


def available_files(actor, work):
    return CaseUpload.objects.filter(case_id=work.case_id, actor=actor, name__iendswith='.pdf',
                                     size__gte=1, size__lte=case_uploads.LIMIT).order_by('-pk')


def authorize(actor, work, task):
    _, value = factory.profile(work, recovery=True)
    supplier(actor, work, value)
    if not request_matches(work, task, actor):
        raise PermissionDenied('Use your exact invoice evidence request.')
    return handoff_for(work)


def attach(actor, work_id, task_id, expected, case_expected, upload_id, operation, previous_id, note):
    from .factory_ppe_opening import pdf_bytes

    if (any(type(value) is not int or value < 1 for value in (work_id, task_id, expected, case_expected, upload_id))
            or type(operation) is not UUID or (previous_id is not None and (type(previous_id) is not int or previous_id < 1))
            or not isinstance(note, str) or len(note.strip()) > 2000 or '\x00' in note):
        raise ValidationError('Choose the current invoice request, the original PDF and a note of up to 2,000 characters.')
    note = note.strip()
    work = FactoryWork.objects.select_related('case').get(pk=work_id)
    factory.access(actor, work.case)
    task = HumanTask.objects.filter(pk=task_id, case_id=work.case_id).first()
    if task is None:
        raise PermissionDenied('Use your exact invoice evidence request.')
    authorize(actor, work, task)
    upload = available_files(actor, work).filter(pk=upload_id).first()
    if upload is None:
        raise ValidationError('Choose your original private PDF for this workspace.')
    receipt = InvoiceMilestoneProof.objects.filter(work=work, task=task, operation=operation).first()
    if receipt:
        return exact_receipt(receipt, actor, upload, previous_id, note)
    require_open(work, task, actor, expected, case_expected)
    try:
        pdf_bytes(ContentFile(case_uploads.read(upload), name=upload.name))
    except OSError as exc:
        raise ValidationError('The original private PDF is unavailable. No proof was recorded.') from exc

    # Read private storage before the database locks. Record only after rechecking the exact source and authority.
    with transaction.atomic():
        work = FactoryWork.objects.select_for_update().get(pk=work_id)
        task = HumanTask.objects.select_for_update().get(pk=task_id, case_id=work.case_id)
        work.case = lock_case(actor, work.case_id, 'evidence.add')
        handoff = authorize(actor, work, task)
        receipt = InvoiceMilestoneProof.objects.filter(work=work, task=task, operation=operation).first()
        if receipt:
            return exact_receipt(receipt, actor, upload, previous_id, note)
        require_open(work, task, actor, expected, case_expected)
        latest = InvoiceMilestoneProof.objects.filter(work=work, task=task).order_by('-pk').first()
        if (latest.pk if latest else None) != previous_id or (latest and latest.upload_id == upload.pk):
            raise ValidationError('Select the exact previous proof and a different original file for a correction.')
        original = available_files(actor, work).filter(pk=upload.pk, key=upload.key,
                                                        size=upload.size, sha256=upload.sha256, name=upload.name).first()
        if original is None:
            raise ValidationError('The original PDF changed before the evidence was recorded.')
        body = json.dumps(pin(work, task, handoff, original, previous_id), sort_keys=True)
        evidence = add_evidence(actor, work.case_id, INVOICE_MILESTONE_PROOF, body, SOURCE, work.case.revision)
        proof = InvoiceMilestoneProof.objects.create(work=work, task=task, handoff=handoff, upload=original,
            evidence=evidence, previous=latest, actor=actor, operation=operation, note=note)
        TaskEvent.objects.create(task=task, actor=actor, action=ATTACHED, data={'evidence': evidence.pk, 'proof': proof.pk})
        task.revision += 1
        task.save(update_fields=['revision'])
        from .factory_progress import wake_waiting
        wake_waiting(work.pk)
        return proof


def require_open(work, task, actor, expected, case_expected):
    if (task.status != 'open' or task.claimed_by_id != actor.pk or task.revision != expected
            or work.case.revision != case_expected or work.cancel_requested or work.status not in ('ready', 'waiting')):
        raise ValidationError('Open the current claimed evidence request before supplying proof.')


def exact_receipt(receipt, actor, upload, previous_id, note):
    if (receipt.actor_id, receipt.upload_id, receipt.previous_id, receipt.note) != (actor.pk, upload.pk, previous_id, note):
        raise ValidationError('This request already recorded different evidence. Use a new correction.')
    return receipt


def readable_proof(actor, work):
    factory.access(actor, work.case)
    _, value = factory.profile(work, recovery=True)
    proof = current(work, value)
    if proof is None:
        return None
    if actor.pk != proof.actor_id:
        if work.invoice_id is None:
            raise PermissionDenied('The private proof is available to its supplier and current Finance reviewers.')
        factory_routing.require_ready(work, actor)
    return proof
