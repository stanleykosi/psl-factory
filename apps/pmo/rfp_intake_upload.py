"""Capture a received bid document without publishing its content."""

import hashlib
from dataclasses import asdict
from datetime import timezone as datetime_timezone
from io import BytesIO
from pathlib import PurePath
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction

from adapters import case_uploads, upload_text
from apps.agents.models import CaseUpload
from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence, event, lock_case
from apps.documents.contracts import digest

from . import rfp, rfp_staged_uploads as staged
from .clocks import aware
from .models import RFPCase
from .rfp_intake_context import authorize_read as require_read, authorize_write, from_intake, validate as validate_context


SOURCE = 'psl:rfp-intake-private-attachment'
ADMISSION = 'rfp.intake_attachment_admitted'


def attachment_for(actor, case, intake):
    require_read(actor, case)
    return bound_attachment(case, intake, check_uploader=True)


def bound_attachment(case, intake, *, check_uploader):
    if intake.rfp.case_id != case.pk:
        return None
    evidence = Evidence.objects.filter(pk=intake.evidence_id, case=case, kind='rfp_intake', source=SOURCE,
                                       created_by_id=intake.actor_id).only('id', 'sha256').first()
    if not evidence:
        return None
    if check_uploader:
        authorize_write(intake.actor, case)
    binding = Audit.objects.filter(case=case, actor_id=intake.actor_id, action=ADMISSION,
        data__intake=intake.pk, data__evidence=evidence.pk, data__evidence_sha256=evidence.sha256).first()
    if binding is None or type(binding.data.get('upload')) is not int:
        return None
    return CaseUpload.objects.filter(pk=binding.data['upload'], case=case, actor_id=intake.actor_id,
                                     sha256=binding.data.get('file_sha256')).first()


def read_file(file):
    if (file is None or not 0 < file.size <= case_uploads.LIMIT
            or PurePath(file.name).suffix.lower() not in ('.docx', '.pdf')):
        raise ValidationError('Choose a readable Word or PDF file up to 5 MiB.')
    data = file.read(case_uploads.LIMIT + 1)
    if len(data) != file.size:
        raise ValidationError('The file changed while it was read. Choose it again.')
    return data


def validate_file(name, data):
    from pypdf.errors import PdfReadError

    try:
        if PurePath(name).suffix.lower() == '.docx':
            with ZipFile(BytesIO(data)) as archive:
                if not {'[Content_Types].xml', 'word/document.xml'}.issubset(archive.namelist()):
                    raise ValidationError('The file does not match its Word format.')
        upload_text.extract(name, data)
    except (BadZipFile, ParseError, PdfReadError, ValueError, KeyError, IndexError) as exc:
        raise ValidationError('The file could not be read as a Word or PDF document. Choose another copy.') from exc


def matches_receipt(intake, actor, facts, context):
    if intake is None or intake.actor_id != actor.pk:
        return False
    return ((intake.rfp.reference, intake.received_at, intake.deadline_status, intake.deadline_at,
             intake.deadline_evidence_id, intake.note) == facts and from_intake(intake) == context)


def persist(actor, case, facts, filename, data, intent, *, first, context, context_attested):
    reference, received_at, deadline_status, deadline_at, deadline_evidence_id, note = facts
    evidence = add_evidence(actor, case.pk, 'rfp_intake',
        'A private copy of the received bid document was retained with this intake.', SOURCE, case.revision)
    case.refresh_from_db(fields=['revision'])
    intake = rfp.intake(actor, case.pk, reference, evidence.pk, received_at, deadline_status,
                        deadline_at, deadline_evidence_id, note, case.revision,
                        source_context=context, context_attested=context_attested)
    upload = CaseUpload.objects.create(case=case, actor=actor, name=filename[:160], key=intent.key,
                                       sha256=intent.sha256, size=intent.size)
    event(actor, case, ADMISSION, intake=intake.pk, evidence=evidence.pk, evidence_sha256=evidence.sha256,
          upload=upload.pk, file_sha256=upload.sha256, intent=str(intent.pk))
    staged.put_or_verify(intent, data, first=first)
    intent.intake, intent.upload = intake, upload
    intent.save(update_fields=['intake', 'upload'])
    return intake


def current_receipt(actor, case, facts, context, fingerprint, size, expected):
    authorize_write(actor, case)
    bid = RFPCase.objects.filter(case=case).select_related('current_intake').first()
    current = bid.current_intake if bid else None
    if matches_receipt(current, actor, facts, context):
        original = attachment_for(actor, case, current)
        if original and (original.sha256, original.size) == (fingerprint, size):
            return current
    if case.revision != expected:
        raise ValidationError('Stale revision; refresh before retrying.')
    return None


def record(actor, case_id, reference, received_at, deadline_status, deadline_at, deadline_evidence_id, note, expected, file,
           *,source_context=None, context_attested=False):
    case = Case.objects.get(pk=case_id)
    authorize_write(actor, case)
    if type(expected) is not int or expected < 1 or not isinstance(reference, str) or not reference.strip() or len(reference.strip()) > 160:
        raise ValidationError('Choose the current workspace and enter the bid reference.')
    context = validate_context(source_context, context_attested)
    data = read_file(file)
    fingerprint = hashlib.sha256(data).hexdigest()
    received_at = aware(received_at, 'Received time').astimezone(datetime_timezone.utc)
    rfp.past(received_at)
    rfp.note(note)
    if deadline_at is not None:
        deadline_at = aware(deadline_at, 'Deadline').astimezone(datetime_timezone.utc)
    facts = (reference.strip(), received_at, deadline_status, deadline_at, deadline_evidence_id, note)
    payload = digest([[value.isoformat() if hasattr(value, 'isoformat') else value for value in facts],
                      asdict(context), fingerprint, len(data)])
    operation = digest(['existing-bid-intake', str(case.pk), actor.pk, expected, payload])
    with staged.serialized(operation):
        with transaction.atomic(durable=True):
            case = lock_case(actor, case_id, 'rfp.intake')
            old = current_receipt(actor, case, facts, context, fingerprint, len(data), expected)
            if old:
                return old
            validate_file(file.name, data)
            intent, first = staged.reserve(operation=operation, actor=actor, payload=payload,
                fingerprint=fingerprint, size=len(data), case=case, revision=expected)
        with transaction.atomic(durable=True):
            case = lock_case(actor, case_id, 'rfp.intake')
            old = current_receipt(actor, case, facts, context, fingerprint, len(data), expected)
            if old:
                return old
            return persist(actor, case, facts, file.name, data, intent, first=first,
                           context=context, context_attested=context_attested)
