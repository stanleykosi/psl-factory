"""A guarded reviewed sample statement of work, awaiting its first release and reply."""

import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Case
from apps.documents.controlled import guard_reserve_publication, request_review, review_version
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import commercial
from apps.pmo.models import CommercialDocumentBinding
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PROJECT
from tests.test_commercial_changes import approvals, fixture, proposal


TENANT = 'design-sow-decline-correction-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE statement of work decline and correction'
RECORDER = 'psl-agent-trial'
REFERENCE = 'SAMPLE-SOW-DECLINE-CORRECTION'
CLIENT_NAMES = {'initial': 'Sample procurement contact', 'corrected': 'Sample procurement lead'}
PROOF_NAMES = {'initial': f'{REFERENCE}-response.txt', 'corrected': f'{REFERENCE}-correction.txt'}
ACTIONS = {
    'case.read', 'evidence.add', 'policy.configure', 'policy.activate',
    'commercial.read', 'commercial.prepare', 'commercial.decide', 'commercial.submit', 'commercial.response',
    'document.read', 'document.template', 'document.draft', 'document.request_review', 'document.review_controlled',
    'document.publish', 'document.receive:client',
}


def sample_proof(sample, receipt, variant):
    qualifier = ('The corrected fictional reply confirms the responder is the named procurement lead. '
                 'The original decision remains a decline. ' if variant == 'corrected' else '')
    return (f'{REFERENCE}\nFictional sample reply from {CLIENT_NAMES[variant]}. '
            f'The client declines the exact statement of work, proposal {sample["proposal"]}, '
            f'delivered document version record {sample["version"]}, sample receipt {receipt}. '
            f'{qualifier}Reviewed document fingerprint: {sample["document_sha256"]}.\n').encode()


@transaction.atomic
def prepare(recorder):
    users = get_user_model().objects
    if not users.filter(pk=recorder.pk, username=RECORDER, is_active=True, is_staff=False, is_superuser=False).exists():
        raise RuntimeError('Use the ordinary active trial recorder.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'kind': 'project', 'title': TITLE, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('The original isolated sample workspace must stay intact.')
    if created:
        Grant.objects.bulk_create([Grant(case=case, user=recorder, action=action) for action in sorted(ACTIONS)])
        _, _, evidence, template = fixture(context=(recorder, case))
        revision = proposal(recorder, case, evidence)
        approvals(recorder, case, revision)
        version = commercial.draft_submission(recorder, case.pk, revision.pk, template.pk, rev(case))
        request_review(recorder, case.pk, version.pk, rev(case))
        review_version(recorder, case.pk, version.pk, 'approve', 'SAMPLE human approval of the exact internal test pack.', rev(case))
    else:
        binding = CommercialDocumentBinding.objects.select_related('version', 'revision').get(
            revision__dossier__case=case, revision__number=1, version__number=1)
        revision, version = binding.revision, binding.version
    if set(Grant.objects.filter(case=case, user=recorder, active=True).values_list('action', flat=True)) != ACTIONS:
        raise RuntimeError('Preserve the original sample permissions and separate actual roles.')
    delivery = Publication.objects.filter(version=version).first()
    if delivery:
        recipients = delivery.recipient_ids
    else:
        _, ready, _ = guard_reserve_publication(recorder, case, version.pk)
        recipients = ready['recipients']
    if recipients != [recorder.pk]:
        raise RuntimeError('Only the exact isolated application inbox may receive the sample.')
    return {'case': str(case.pk), 'proposal': revision.pk, 'version': version.pk, 'document_sha256': version.payload_sha256,
            'documents': reverse('documents', args=[case.pk]), 'response': reverse('commercial_client_response', args=[case.pk]),
            'proof_names': PROOF_NAMES, 'responder_names': CLIENT_NAMES, 'preserved': not created,
            'existing_delivery': delivery.pk if delivery else None, 'existing_responses': revision.responses.count()}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_SOW_DECLINE_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit statement-of-work decline fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username=RECORDER, is_active=True, is_staff=False, is_superuser=False)
    print('PSL_SOW_DECLINE_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
