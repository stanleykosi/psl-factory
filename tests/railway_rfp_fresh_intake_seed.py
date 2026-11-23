"""Guarded creation authority for a browser to record the first sample bid."""

import json
import os
from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZipInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.identity import intake
from apps.identity.intake_models import TenantAuthority
from apps.pmo import rfp_fresh_intake
from apps.pmo.models import RFPIntake
from tests.railway_independent_commercial_seed import PROJECT
from tests.railway_rfp_intake_upload_seed import sample_document as word_package


TENANT = 'design-fresh-bid-start-walkthrough'
BOOTSTRAP = 'sample-fresh-bid-start-bootstrap'
RECORDER = 'psl-agent-trial'
REFERENCE = 'SAMPLE-RECEIVED-BID-START-BROWSER'
FILENAME = f'{REFERENCE}.docx'
PROSPECT = 'Sample Reconciliation Team'
SUBMISSION_TARGET = 'fresh-bid-intake@example.invalid'
DEADLINE = '2026-12-04T17:00:00+01:00'
REASON = ('SAMPLE approved creation of synthetic bid workspaces from Start work. '
          'Only the five native intake actions are delegated to the ordinary trial recorder.')


def scope():
    actions = sorted(rfp_fresh_intake.GRANTS)
    return {'format': 'psl.tenant-access/v1', 'create_cases': True, 'manage_access': False,
            'kinds': ['project'], 'allowed_actions': actions, 'initial_actions': actions, 'classification': 'synthetic'}


def sample_document():
    paragraphs = [REFERENCE, f'Client or prospect: {PROSPECT}.',
                  'Fictional request for a sample reconciliation report.',
                  f'Submission deadline: {DEADLINE}.', f'Submit by email to {SUBMISSION_TARGET}.']
    content = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    content += ''.join(f'<w:p><w:r><w:t>{escape(item)}</w:t></w:r></w:p>' for item in paragraphs)
    content += '</w:body></w:document>'
    result = BytesIO()
    with ZipFile(BytesIO(word_package())) as original, ZipFile(result, 'w') as output:
        for name in original.namelist():
            output.writestr(ZipInfo(name), content.encode() if name == 'word/document.xml' else original.read(name))
    return result.getvalue()


@transaction.atomic
def prepare(recorder):
    intake.lock_users([recorder.pk])
    users = get_user_model().objects
    if not users.filter(pk=recorder.pk, username=RECORDER, is_active=True, is_staff=False, is_superuser=False).exists():
        raise RuntimeError('Use only the ordinary active trial recorder.')
    authorities = TenantAuthority.objects.filter(tenant=TENANT).select_related('actor').defer('actor__password')
    authority = authorities.first()
    created = authority is None
    if created:
        if Case.objects.filter(tenant=TENANT).exists() or users.filter(username=BOOTSTRAP).exists():
            raise RuntimeError('The new sample organization already contains an unrelated setup record.')
        bootstrap = users.create_superuser(BOOTSTRAP)
        authority = intake.provision(bootstrap, recorder, TENANT, scope(), timezone.now() + timedelta(days=1), True, REASON)
        bootstrap.is_active = bootstrap.is_staff = bootstrap.is_superuser = False
        bootstrap.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
    else:
        bootstrap = authority.actor
        if (authorities.count() != 1 or authority.user_id != recorder.pk or authority.value != scope()
                or authority.reason != REASON or not authority.enabled or authority.expires_at <= timezone.now()
                or bootstrap.username != BOOTSTRAP or bootstrap.is_active or bootstrap.is_staff or bootstrap.is_superuser):
            raise RuntimeError('Preserve the existing synthetic scope and use only its original current authority.')
    if bootstrap.has_usable_password():
        raise RuntimeError('The dedicated sample bootstrap must be unusable.')

    original = RFPIntake.objects.filter(rfp__tenant=TENANT, rfp__reference=REFERENCE, actor=recorder, number=1).first()
    if Case.objects.filter(tenant=TENANT).count() != (1 if original else 0):
        raise RuntimeError('Preserve records outside the one exact fresh bid walkthrough.')
    return {'organization': TENANT, 'authority': authority.pk, 'expires_at': authority.expires_at.isoformat(),
            'entry': f"{reverse('factory_create')}?definition={rfp_fresh_intake.LINE}", 'file_name': FILENAME,
            'reference': REFERENCE, 'prospect': PROSPECT, 'submission_method': 'Email',
            'submission_target': SUBMISSION_TARGET, 'deadline': DEADLINE, 'existing_receipt': original.pk if original else None,
            'preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_RFP_FRESH_INTAKE_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit fresh bid fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username=RECORDER, is_active=True, is_staff=False, is_superuser=False)
    print('PSL_RFP_FRESH_INTAKE_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
