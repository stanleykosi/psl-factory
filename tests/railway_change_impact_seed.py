"""Prepare a separate Normal change and a private synthetic Security estimate."""
import json
import os
from io import BytesIO
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from apps.agents.upload_views import upload_file
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from tests import test_commercial_changes
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_factory_change import FactoryChangeTests


GUARD = 'PSL_NORMAL_CHANGE_IMPACT_WALKTHROUGH'
TENANT = 'design-normal-change-impact-walkthrough'
TITLE = 'SAMPLE Normal change with a Security effort assessment'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
MARKER = 'sample.change_impact_prepared'
FILE = 'sample-security-assessment.pdf'
DISCIPLINE = 'The fallback uses the existing provider. No new personal data is stored.'
EFFORT = '0.5'
EDIT_GRANTS = ('case.read', 'factory.read', 'change.read', 'change.assess:Security', 'evidence.add')


def pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=440, height=200)
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): DictionaryObject({
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica'),
            }),
        }),
    })
    content = DecodedStreamObject()
    content.set_data(
        b'BT /F1 12 Tf 25 160 Td (SAMPLE Security assessment) Tj '
        b'0 -24 Td (Recorded effort: 0.5 person-days.) Tj '
        b'0 -24 Td (Use the existing provider. No new personal data is stored.) Tj ET'
    )
    page.replace_contents(content)
    writer.add_metadata({'/Title': 'Synthetic Security assessment: 0.5 person-days', '/Subject': DISCIPLINE})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@transaction.atomic
def prepare(viewer):
    if viewer.username != 'psl-agent-trial' or not viewer.is_active or viewer.is_staff or viewer.is_superuser:
        raise RuntimeError('The existing ordinary Trial account must record the synthetic assessment.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the workspace occupying the sample assessment identifier.')
    if created:
        owner = get_user_model().objects.create_user('sample-normal-change-impact-source')
        Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in dict.fromkeys(ACTIONS)])
        Grant.objects.bulk_create([Grant(case=case, user=viewer, action=action) for action in EDIT_GRANTS])
        original_fixture = test_commercial_changes.fixture
        with patch.object(test_commercial_changes, 'fixture', side_effect=lambda *, existing:
                          original_fixture(existing=existing, context=(owner, case))):
            entry = FactoryChangeTests()
            entry.setUp()
        entry.assessments(cost=False, timeline=False, client=False)
        work = entry.start()
        evidence = add_evidence(owner, case.pk, 'change_assessment',
            f'Sample Security owner statement. {DISCIPLINE} Confirmed effort: {EFFORT} person-days.',
            'synthetic:normal-change-impact-statement')
        attachment = upload_file(viewer, case, ContentFile(pdf(), name=FILE))
        saved = event(owner, case, MARKER, operator=viewer.pk, owner=owner.pk, work=work.pk, version=entry.cv.pk,
                      initial=list(entry.cv.assessments.order_by('pk').values_list('pk', flat=True)),
                      evidence=evidence.pk, upload=attachment.pk)
    else:
        saved = Audit.objects.get(case=case, action=MARKER)
    if saved.data['operator'] != viewer.pk:
        raise RuntimeError('Preserve the original Trial assessment scope.')
    return {**saved.data, 'case': str(case.pk), 'path': reverse('factory_detail', args=[saved.data['work']]),
            'file': FILE, 'discipline': DISCIPLINE, 'effort': EFFORT, 'preserved': not created}


def run():
    actual = os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)
    database = os.getenv('PGDATABASE', '')
    if actual != (PREVIEW_PROJECT, 'design-acceptance', '1') or not database or database.startswith('test_'):
        raise RuntimeError('The isolated Railway preview and Normal change impact fixture guard are required.')
    viewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print(GUARD + '=' + json.dumps(prepare(viewer), sort_keys=True), flush=True)
