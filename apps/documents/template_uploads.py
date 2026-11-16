"""Private file provenance for native controlled template versions."""
import hashlib
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction

from adapters.case_uploads import LIMIT
from apps.agents.upload_views import upload_file
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadBudget
from apps.core.services import lock_case
from apps.identity.services import require

from .controlled import register_template
from .contracts import PMO_DOCUMENT_TYPES, validate_template
from .models import Template, TemplateFile
from .template_access import visible_templates


def fingerprint(file):
    if not 0 < file.size <= LIMIT or len(file.name) > 160:
        raise ValidationError('Choose a file up to 5 MiB with a filename up to 160 characters.')
    suffix = PurePath(file.name).suffix.lower()
    try:
        if suffix == '.pdf' and file.read(5) == b'%PDF-':
            pass
        elif suffix in {'.docx', '.xlsx'}:
            member = 'word/document.xml' if suffix == '.docx' else 'xl/workbook.xml'
            with ZipFile(file) as archive:
                if '[Content_Types].xml' not in archive.namelist() or member not in archive.namelist():
                    raise ValidationError('The file does not match its Word or Excel format.')
        else:
            raise ValidationError('Choose a Word, Excel or PDF file.')
    except BadZipFile as exc:
        raise ValidationError('The file does not match its Word or Excel format.') from exc
    finally:
        file.seek(0)
    digest = hashlib.sha256(file.read(LIMIT + 1)).hexdigest()
    file.seek(0)
    return digest


def proofs(case):
    return public_evidence(case.evidence.filter(kind='policy_decision')).defer('body')


def replay(actor, case, request_key, previous_id, name, definition, proof, sha256, filename):
    old = TemplateFile.objects.filter(case=case, request_key=request_key).select_related('template', 'upload').first()
    if old and (old.template.case_id != case.pk or old.template.created_by_id != actor.pk
                or old.previous_id != previous_id or old.template.evidence_id != proof.pk
                or old.template.name != name or old.template.definition != definition
                or old.upload.sha256 != sha256 or old.filename != filename):
        raise ValidationError('The upload request is already in use. Open a new form.')
    return old


def submit(actor, case, proof, file, request_key, revision, *, previous=None, name=None, definition=None):
    for action in ('case.read', 'document.read', 'document.template', 'evidence.add'):
        require(actor, case, action)
    if previous is not None:
        if not visible_templates(actor, case, candidate_ids=[previous.pk], budget=ReadBudget()).exists():
            raise ValidationError('Choose a template available to you in this workspace.')
        name, definition = previous.name, previous.definition
    else:
        validate_template(definition, case=case)
        if definition['document_type'] not in PMO_DOCUMENT_TYPES or not name or len(name) > 160:
            raise ValidationError('Choose a project template type and enter a name of up to 160 characters.')
    if not proofs(case).filter(pk=proof.pk).exists():
        raise ValidationError('Choose owner evidence from this workspace.')
    sha256 = fingerprint(file)
    previous_id = previous.pk if previous else None
    old = replay(actor, case, request_key, previous_id, name, definition, proof, sha256, file.name)
    if old:
        return old.template
    if revision != case.revision:
        raise ValidationError('The workspace changed. Reload before uploading.')
    upload = upload_file(actor, case, file)
    with transaction.atomic():
        case = lock_case(actor, case.pk, 'document.template')
        require(actor, case, 'case.read')
        require(actor, case, 'evidence.add')
        require(actor, case, 'document.read')
        if previous_id and not visible_templates(actor, case, candidate_ids=[previous_id], budget=ReadBudget()).exists():
            raise ValidationError('The selected template is no longer available.')
        old = replay(actor, case, request_key, previous_id, name, definition, proof, sha256, file.name)
        if old:
            return old.template
        head = Template.objects.filter(case=case, name=name).order_by('-version').values_list('pk', flat=True).first()
        if head != previous_id:
            raise ValidationError('A newer template version exists. Select the latest version before uploading.')
        version = register_template(actor, case.pk, name, definition, proof.pk, revision)
        TemplateFile.objects.create(case=case, template=version, previous=previous, upload=upload,
                                    request_key=request_key, filename=file.name)
        return version
