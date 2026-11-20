"""Source-bound preparation for the native RFP controlled document."""

import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import restricted
from apps.core.services import bump, event, lock_case
from apps.documents.models import Publication
from apps.identity.services import require
from apps.pmo.services import subject

from . import rfp
from .models import RFPSubmission, RFPSubmissionPack


SIZE_RULES = {'less_than': 'Under', 'at_most': 'At most'}
FIELDS = ('cover_note', 'file_extension', 'file_count', 'file_size_rule', 'file_size_bytes')


def normalized(values):
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise ValidationError('Supply the complete cover note and file requirements form.')
    note, extension, count, rule, size = (values[key] for key in FIELDS)
    if not isinstance(note, str) or len(note) > 4000 or '\x00' in note:
        raise ValidationError('Enter a cover note of up to 4,000 characters.')
    if not isinstance(extension, str) or (extension and not re.fullmatch(r'[a-zA-Z0-9]{1,16}', extension)):
        raise ValidationError('Enter a file extension such as PDF, or leave it blank if unknown.')
    if count is not None and (type(count) is not int or not 1 <= count <= 2_147_483_647):
        raise ValidationError('The stated number of files must be a positive whole number.')
    if not isinstance(rule, str) or (size is None and rule) or (
            size is not None and (type(size) is not int or not 1 <= size <= 9_223_372_036_854_775_807
                                  or rule not in SIZE_RULES)):
        raise ValidationError('Enter both the stated byte limit and how it applies, or leave both blank.')
    return dict(zip(FIELDS, (note.strip(), extension.lower(), count, rule, size)))


def current(response):
    return RFPSubmissionPack.objects.filter(response=response).order_by('-number').first()


def read(actor, case, response):
    for permission in ('case.read', 'rfp.read', 'document.read'):
        require(actor, case, permission)
    if response.rfp.case_id != case.pk:
        raise PermissionDenied('This draft is outside the current bid.')
    return current(response)


def can_edit(actor, case, response):
    try:
        for permission in ('case.read', 'rfp.read', 'document.read', 'rfp.prepare'):
            require(actor, case, permission)
        if response.actor_id != actor.pk:
            return False
        rfp.current_response(case, response.pk)
    except (PermissionDenied, ValidationError):
        return False
    return not release_started(response)


def release_started(response):
    return RFPSubmission.objects.filter(response=response).exists() or Publication.objects.filter(
        version__rfpdocumentbinding__response=response).exclude(job__status='cancelled').exists()


@transaction.atomic
def record(actor, case_id, response_id, base_id, expected, values):
    case = lock_case(actor, case_id, 'rfp.prepare', expected)
    for permission in ('case.read', 'rfp.read', 'document.read'):
        require(actor, case, permission)
    response = rfp.current_response(case, response_id)
    if actor.pk != response.actor_id:
        raise PermissionDenied('Only the assigned response preparer can revise this pack.')
    if release_started(response):
        raise ValidationError('Resolve the original submission before changing this pack.')
    if type(base_id) is not int:
        raise ValidationError('Select the current submission pack revision.')
    previous = current(response)
    if (previous.pk if previous else 0) != base_id:
        raise ValidationError('The submission pack changed. Refresh it before saving.')
    values = normalized(values)
    if previous and all(getattr(previous, key) == value for key, value in values.items()):
        return previous
    source = subject(case, response.intake.evidence_id, 'rfp_intake', metadata_only=True)
    if restricted(source):
        raise ValidationError('The received bid proof must be available to the controlled client pack.')
    pack = RFPSubmissionPack.objects.create(response=response, number=previous.number + 1 if previous else 1,
                                            supersedes=previous, source=source, actor=actor, **values)
    event(actor, case, 'rfp.submission_pack_drafted', response=response.pk, pack=pack.pk,
          previous=previous.pk if previous else None, source=source.pk)
    bump(case)
    return pack


def requirements(pack):
    parts = []
    if pack.file_extension:
        parts.append(f'Format {pack.file_extension.upper()}')
    if pack.file_count is not None:
        parts.append(f'Number of files {pack.file_count}')
    if pack.file_size_bytes is not None:
        parts.append(f'{SIZE_RULES[pack.file_size_rule]} {pack.file_size_bytes:,} bytes per file')
    return parts


def summary(pack, introduction):
    cover = pack.cover_note or 'Not supplied.'
    stated = '\n'.join(requirements(pack)) or 'Not recorded.'
    return f'{introduction}\n\nCover note\n{cover}\n\nClient file requirements\n{stated}'


def bound_pack(binding):
    pack_id = binding.snapshot.get('submission_pack')
    if pack_id is None:
        return None
    return RFPSubmissionPack.objects.get(pk=pack_id, response_id=binding.response_id)


def require_verified_files(binding):
    pack = bound_pack(binding)
    if pack and requirements(pack):
        raise ValidationError('Verify that the client files meet the stated requirements before sending from the factory.')


def require_independent_review(actor, version):
    from .models import RFPDocumentBinding

    if version.audience != 'client' or version.template.definition['document_type'] not in ('rfp_response', 'project_artifact'):
        return
    binding = RFPDocumentBinding.objects.filter(version=version, snapshot__has_key='submission_pack').first()
    if binding:
        require(actor, version.document.case, 'rfp.read')
        require(actor, version.document.case, 'document.read')
        if bound_pack(binding).actor_id == actor.pk:
            raise PermissionDenied('A different authorised person must review this exact submission pack.')
