"""An empty synthetic workspace for the native received-bid upload journey."""

import json
import os
from io import BytesIO
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.agents.models import CaseUpload
from apps.core.models import Case
from apps.identity.models import Grant
from apps.pmo.models import RFPCase
from tests.railway_independent_commercial_seed import PROJECT


TENANT = 'design-rfp-intake-private-upload-walkthrough'
TITLE = 'SAMPLE workspace to record an incoming bid document'
REFERENCE = 'SAMPLE-RFP-PRIVATE-INTAKE-BROWSER'
FILENAME = f'{REFERENCE}.docx'
ACTIONS = {'case.read', 'rfp.read', 'rfp.intake', 'evidence.add', 'document.read', 'agent.rfp'}


def sample_document():
    content_types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    relationships = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>')
    document = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body><w:p><w:r><w:t>{REFERENCE}</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Fictional request to document a test-system reconciliation process. '
        'No submission deadline, recipient, commercial value or production access is provided.</w:t></w:r></w:p>'
        '</w:body></w:document>')
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', relationships)
        archive.writestr('word/document.xml', document)
    return stream.getvalue()


@transaction.atomic
def prepare(recorder):
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, TENANT),
        defaults={'tenant': TENANT, 'kind': 'project', 'title': TITLE, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('Choose only the exact synthetic intake workspace.')
    if created:
        Grant.objects.bulk_create([Grant(case=case, user=recorder, action=action) for action in sorted(ACTIONS)])
    grants = set(Grant.objects.filter(case=case, user=recorder, active=True).values_list('action', flat=True))
    if grants != ACTIONS:
        raise RuntimeError('Use the original ordinary recorder with the exact sample access.')
    bid = RFPCase.objects.filter(case=case).first()
    if bid and bid.reference != REFERENCE:
        raise RuntimeError('The sample workspace already has a different bid. Preserve it.')
    return {'case': str(case.pk), 'reference': REFERENCE, 'file_name': FILENAME, 'recorder': recorder.pk,
            'path': reverse('rfp', args=[case.pk]), 'grants': sorted(grants), 'preserved': not created,
            'existing_intake': bid.current_intake_id if bid else None,
            'existing_uploads': CaseUpload.objects.filter(case=case).count()}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_RFP_INTAKE_UPLOAD_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit received-bid fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print('PSL_RFP_INTAKE_UPLOAD_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
