"""Record a human's evidence of an upload to a configured client portal."""
import json
import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.evidence_access import restricted
from apps.core.services import bump, event, lock_case
from apps.documents.controlled import current_version, validate_review
from apps.documents.models import Publication
from apps.identity.services import require

from .models import RFPDocumentBinding, RFPPortalReceipt, RFPSubmission
from .rfp import ensure_open, note
from .rfp_documents import inputs, sender
from .rfp_submission_artifacts import approved_format, metadata
from .rfp_submission_pack import bound_pack, requirements
from .services import subject


METHOD = 'manual_client_portal'
SCHEMA = 'psl/rfp-portal-receipt/v1'
PDF_SCHEMA = 'psl/rfp-portal-receipt/v2'
FIELDS = {'schema', 'version', 'sha256', 'destination', 'reference', 'received_at'}


def exact_file(binding, *, new=False):
    pack = bound_pack(binding)
    if pack is None:
        return None
    artifact = metadata(binding=binding)
    if artifact:
        approved_format(binding, artifact)
    elif new and requirements(pack):
        raise ValidationError('Prepare a verified client file before recording its portal receipt.')
    return artifact


def proof(evidence, version, route, *, artifact=None, historical=False):
    try:
        value = json.loads(evidence.body)
        if historical and isinstance(value, dict) and value.get('schema') == SCHEMA:
            artifact = None
        expected_fields = FIELDS | {'artifact_sha256'} if artifact else FIELDS
        if (not isinstance(value, dict) or set(value) != expected_fields or
                value['schema'] != (PDF_SCHEMA if artifact else SCHEMA) or
                (artifact and value['artifact_sha256'] != artifact.sha256) or
                type(value['version']) is not int or value['version'] != version.pk or
                value['sha256'] != version.payload_sha256 or value['destination'] != route['destination_ref'] or
                not isinstance(value['reference'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,159}', value['reference'])):
            raise ValueError
        observed = datetime.fromisoformat(value['received_at'])
        if timezone.is_naive(observed):
            raise ValueError
    except (TypeError, ValueError) as exc:
        detail = ('Supply a portal receipt matching the exact approved pack, PDF fingerprint, destination and actual receipt time.'
                  if artifact else 'Supply a portal receipt matching the exact approved pack, destination and actual receipt time.')
        raise ValidationError(detail) from exc
    return value['reference'], observed


@transaction.atomic
def record(actor, case_id, version_id, evidence_id, attestation, expected):
    case = lock_case(actor, case_id, 'rfp.submit', expected)
    require(actor, case, 'case.read')
    require(actor, case, 'rfp.read')
    require(actor, case, 'document.read')
    binding = RFPDocumentBinding.objects.select_related('version','response__rfp','response__intake').filter(
        version_id=version_id, response__rfp__case=case).first()
    if binding is None or binding.snapshot['route']['method'] != METHOD:
        raise ValidationError('Choose the exact reviewed pack for the configured client portal.')
    version = binding.version
    note(attestation)
    evidence = subject(case, evidence_id, 'rfp_portal_receipt')
    if restricted(evidence):
        raise ValidationError('Choose available client portal receipt evidence.')
    original = RFPPortalReceipt.objects.filter(submission__version=version).first()
    artifact = exact_file(binding, new=original is None)
    reference, received = proof(evidence, version, binding.snapshot['route'], artifact=artifact,
                                historical=original is not None)
    if original:
        if original.evidence_id == evidence.pk and original.actor_id == actor.pk and original.note == attestation:
            return original.submission
        raise ValidationError('This version already has an original portal receipt.')
    ensure_open(binding.response.rfp)
    current_version(case, version.pk)
    sender(actor, version)
    if binding.snapshot != inputs(binding.response, binding.snapshot['route']['key']):
        raise ValidationError('The reviewed response or route changed. Check the original pack before recording a receipt.')
    review = validate_review(case, version)
    if not review or version.audience != 'client' or received < review.created_at or received > timezone.now():
        raise ValidationError('The actual portal receipt must follow exact client pack approval.')
    if Publication.objects.filter(version=version).exists() or RFPSubmission.objects.filter(version=version).exists() or (
            RFPPortalReceipt.objects.filter(evidence=evidence).exists()):
        raise ValidationError('This pack or evidence already belongs to a recorded submission.')
    deadline = binding.response.intake.deadline_at
    submission = RFPSubmission.objects.create(response=binding.response, version=version, snapshot=binding.snapshot,
        receipt_ids=[], submitted_at=received, late=bool(deadline and received>deadline), actor=actor)
    receipt = RFPPortalReceipt.objects.create(submission=submission, review=review, evidence=evidence,
                                             reference=reference, note=attestation, actor=actor)
    details = {'submission': submission.pk, 'receipt': receipt.pk}
    if artifact:
        details['artifact'] = artifact.pk
    event(actor, case, 'rfp.portal_receipt_recorded', **details)
    bump(case)
    return submission
