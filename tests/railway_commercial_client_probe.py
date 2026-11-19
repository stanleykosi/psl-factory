"""Read-only native readback of the manually completed SAMPLE client journey."""
import json
import os

from django.contrib.auth import get_user_model

from apps.agents.file_draft_reviews import reviewed_output
from apps.agents.models import AgentJob
from apps.core.models import Case
from apps.pmo import commercial_client_response as domain, signatures
from apps.pmo.models import BaselineAdoption, ClientResponse
from tests.railway_commercial_client_seed import TENANT


def inspect():
    if os.getenv('PSL_COMMERCIAL_CLIENT_PROBE') != '1':
        raise RuntimeError('Explicit read-only SAMPLE probe guard required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True)
    case = Case.objects.get(tenant=TENANT, synthetic=True)
    metadata = domain.latest(case)
    value, response = domain.read(actor, case, metadata)
    proof = domain.proof_rows(actor, case, metadata)
    adoption = BaselineAdoption.objects.get(response=response)
    packet = signatures.assert_current_signed_baseline(case)
    intake = adoption.signedbaselineintake
    job = AgentJob.objects.select_related('upload', 'file_review__evidence').get(
        upload__in=proof, actor=actor, role='A07', status='reviewed')
    review = reviewed_output(job, job.file_review.evidence)
    assert review['source_sha256'] == job.upload.sha256
    assert response.kind == 'signed' and value['outcome'] == 'signed'
    assert packet.signatures['sow']['evidence_id'] == response.evidence_id
    assert intake.payload['invoice_created'] is False
    return {'case': str(case.pk), 'metadata': metadata.pk, 'response': response.pk,
            'public_signature': response.evidence_id, 'signature_packet': packet.pk,
            'adoption': adoption.pk, 'finance_intake': intake.pk, 'invoice_created': False,
            'responses': ClientResponse.objects.filter(revision=response.revision).count(),
            'job': job.pk, 'attempt': job.attempt, 'model': job.result['model'],
            'reviewed_evidence': job.file_review.evidence_id, 'source_sha256': job.upload.sha256,
            'native_current_signature_checks': True, 'read_only': True}


if os.getenv('PSL_COMMERCIAL_CLIENT_PROBE') == '1':
    print('PSL_COMMERCIAL_CLIENT_PROBE=' + json.dumps(inspect(), sort_keys=True))
