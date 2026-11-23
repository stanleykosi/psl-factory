"""Attach work-bound evidence without claiming that a PDF has been verified."""
import hashlib
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from adapters import case_uploads
from apps.agents.models import CaseUpload
from apps.core.services import add_evidence, lock_case
from apps.identity.factory_access import department_cases
from apps.identity.services import require
from apps.workflows.factory_ppe_opening import pdf_bytes

from .http import ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .work import observed_work


KIND = 'agent_private_work_proof_v1'
NOTE = {**TEXT, 'maxLength': 4000}
PROOF = obj({'evidence_id': ID, 'kind': choice('pdf_copy', 'pmo_lead_note'),
             'name': nullable(TEXT), 'sha256': nullable(TEXT), 'note': nullable(TEXT),
             'download_url': nullable(TEXT)})
INPUT = {'oneOf': [
    obj({'kind': {'const': 'pdf_copy'}, 'upload_id': ID, 'case_revision': REVISION}),
    obj({'kind': {'const': 'pmo_lead_note'}, 'note': NOTE, 'case_revision': REVISION}),
]}


def attached_work(actor, work_id):
    work, _, restricted = observed_work(actor, work_id)
    if restricted.get('recipient_only') or restricted.get('handoff'):
        raise Http404
    return work


def proof_data(row, actor):
    value = json.loads(row.body)
    upload_id = value.pop('upload_id', None)
    download = reverse('case_upload_download', args=[row.case_id, upload_id]) if (
        upload_id and row.created_by_id == actor.pk) else None
    return {'evidence_id': row.pk, 'download_url': download, **value}


@endpoint(response=obj({'items': array(PROOF, limit=50), 'case_revision': REVISION}),
          summary='Read the proof attached to this work')
def proofs(request, work_id):
    work = attached_work(request.user, work_id)
    source = f'work-proof/v1:{work.pk}'
    rows = work.case.evidence.filter(kind=KIND, source=source).order_by('-pk')[:50]
    return {'items': [proof_data(row, request.user) for row in rows], 'case_revision': work.case.revision}


@endpoint(method='POST', request=INPUT, response=PROOF, status=201,
          summary='Attach a private PDF copy or a current PMO Lead note to this work')
def attach(request, work_id, *, body):
    actor = request.user
    work = attached_work(actor, work_id)
    require(actor, work.case, 'evidence.add')
    source = f'work-proof/v1:{work.pk}'
    value = {'kind': body['kind'], 'name': None, 'sha256': None, 'note': None}
    if body['kind'] == 'pdf_copy':
        upload = get_object_or_404(CaseUpload, pk=body['upload_id'], case_id=work.case_id, actor=actor)
        data = case_uploads.read(upload)
        name, _ = pdf_bytes(SimpleUploadedFile(upload.name, data))
        value.update(name=name, sha256=upload.sha256, upload_id=upload.pk)
    else:
        if not body['note'].strip():
            raise ValidationError('Enter the PMO Lead’s proof note.')
        value['note'] = body['note'].strip()
    recorded = json.dumps(value, sort_keys=True)
    with transaction.atomic():
        case = lock_case(actor, work.case_id, 'evidence.add')
        if body['kind'] == 'pmo_lead_note' and not department_cases(actor, 'pmo-lead', heads_only=True).filter(
            pk=case.pk,
        ).exists():
            raise PermissionDenied('Only the current PMO Lead can provide a written proof note.')
        existing = case.evidence.filter(kind=KIND, source=source, created_by=actor,
                                        sha256=hashlib.sha256(recorded.encode()).hexdigest()).first()
        row = existing or add_evidence(actor, case.pk, KIND, recorded, source, body['case_revision'])
    return proof_data(row, actor)
