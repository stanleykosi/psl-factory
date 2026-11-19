"""Read-only original-source, model, human-edit and downstream receipt checks."""
import json
import os

from django.contrib.auth import get_user_model

from apps.agents.file_draft_reviews import reviewed_output
from apps.agents.models import AgentJob
from apps.agents.upload_jobs import authorize
from apps.core.models import Audit, Case
from apps.documents.validation import source_current
from apps.documents.validation_models import DiscoverySource
from apps.identity.services import require


def inspect():
    if os.getenv('PSL_UPLOAD_RECOVERY_PROBE') != '1':
        raise RuntimeError('Explicit SAMPLE recovery read-only probe guard required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    case = Case.objects.get(tenant='design-upload-agent-recovery', synthetic=True)
    require(actor, case, 'case.read')
    require(actor, case, 'agent.extract')
    job = AgentJob.objects.select_related('upload__case', 'file_review__evidence').get(upload__case=case, actor=actor, role='A02')
    authorize(actor, job.upload)
    review = job.file_review
    result = reviewed_output(job, review.evidence)
    require(actor, case, 'validation.read')
    downstream = DiscoverySource.objects.get(case=case, pk=job.result['workflow_record'], evidence=review.evidence)
    source_current(downstream)
    if (job.status != 'reviewed' or result['source_sha256'] != job.upload.sha256
            or job.claim_token != job.settled_token or job.attempt < 2):
        raise RuntimeError('Recovery result does not match the original source and reviewed attempt')
    return {'read_only': True, 'case': str(case.pk), 'job': job.pk, 'attempt': job.attempt,
            'model': result['model'], 'source_hash_matches': True, 'reviewed_evidence': review.evidence_id,
            'validation_source': downstream.pk, 'native_current_source': True,
            'recovery_requests': Audit.objects.filter(case=case, actor=actor,
                action='file_agent.recovery_requested', data__job=job.pk).count(),
            'human_edits_used_by_downstream': result['summary'] in downstream.evidence.body,
            'raw_source_or_model_text_exported': False}


if os.getenv('PSL_UPLOAD_RECOVERY_PROBE') == '1':
    print('PSL_UPLOAD_RECOVERY_PROVENANCE=' + json.dumps(inspect()))
