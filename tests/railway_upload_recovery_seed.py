"""Additive SAMPLE file-agent recovery exercise; no real provider outage asserted."""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from apps.agents.models import AgentJob
from apps.agents.upload_jobs import run_once
from apps.agents.upload_views import queue_draft, upload_file
from apps.core.models import Case
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant

TENANT = 'design-upload-agent-recovery'
SOURCE = (b'SAMPLE isolated file review. The operator observed a fictional project evidence handoff.\n'
          b'The evidence still needs human review and source validation. No business approval is supplied.\n')


@transaction.atomic
def prepare():
    if os.getenv('PSL_UPLOAD_RECOVERY_FIXTURE') != '1':
        raise RuntimeError('Explicit SAMPLE upload-recovery fixture guard required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    old = Case.objects.filter(tenant=TENANT).first()
    if old:
        if not old.synthetic:
            raise RuntimeError('Unexpected operational workspace')
        job = AgentJob.objects.get(upload__case=old, actor=actor, role='A02')
        return {'already_prepared': True, 'case': str(old.pk), 'job': job.pk,
                'current_status': job.status, 'no_existing_records_reset': True}
    # Never consume another person's queued work or expire their running request.
    if AgentJob.objects.filter(status__in=['queued', 'running']).exists():
        raise RuntimeError('Wait for existing file reviews before preparing this isolated sample')
    case = Case.objects.create(tenant=TENANT, title='SAMPLE file-agent recovery', kind='project', synthetic=True)
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in ACTIONS])
    proof = upload_file(actor, case, SimpleUploadedFile('SAMPLE-recovery-evidence.txt', SOURCE))
    # Fault only the external model adapter. Storage, claim, validation and audit are native.
    # The isolated checks service deliberately has no real model credentials.
    with patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic/fault-injection',
                                'OPENROUTER_API_KEY': 'not-a-provider-credential'}), \
         patch('adapters.openrouter.review', side_effect=TimeoutError('SAMPLE injected provider timeout')):
        job = queue_draft(actor, proof, 'A02')
        if not run_once():
            raise RuntimeError('The sample needs the configured test-model worker')
    job.refresh_from_db()
    if job.status != 'held' or job.attempt != 1:
        # Also rolls back a competing claim if a new queued job won the race.
        raise RuntimeError('Isolated sample did not receive its own stopped native attempt')
    return {'case': str(case.pk), 'upload': proof.pk, 'job': job.pk, 'role': job.role,
            'initial_failure': 'Explicit injected external-adapter timeout, not an actual provider incident',
            'private_storage_upload_and_read': 'native', 'actual_model_request_sent': False,
            'human_recovery_review_or_handoff_recorded': False, 'owner_policy_values_adopted': False}
