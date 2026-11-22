"""A guarded signed sample whose exact facts await a current human reaffirmation."""

import json
import os
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.upload_views import upload_file
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import commercial, commercial_client_response, signatures
from apps.policy.services import active_component, reference_values
from apps.policy.signature_validators import COMPONENT as SIGNATURE_COMPONENT
from tests.helpers import activate, rev
from tests.railway_independent_commercial_seed import PROJECT
from tests.railway_sow_decline_seed import ACTIONS as RESPONSE_ACTIONS
from tests.signature_helpers import contract, packet_for
from tests.test_commercial_changes import approvals, delivered, fixture, proposal


TENANT = 'design-sow-same-identity-reaffirmation'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE unchanged signed documents with renewed authority'
RECORDER = 'psl-agent-trial'
PROOF = 'SAMPLE-SOW-ORIGINAL-SIGNATURE.txt'
ROLE_COMPONENT = 'D05.role_principal_assignments'
ACTIONS = RESPONSE_ACTIONS | {'baseline.sign'}


def prepare_original(recorder, case):
    _, _, sources, template = fixture(context=(recorder, case))
    revision = proposal(recorder, case, sources)
    approvals(recorder, case, revision)
    receipt = delivered(recorder, case, revision, template, scoped=True)
    original_contract = contract(recorder, case, sources['policy_decision'])
    proof = upload_file(recorder, case, SimpleUploadedFile(PROOF, (
        'Fictional client signature witnessed for the synthetic statement of work.\n'
        f'Original proposal {revision.pk}, document version {receipt.publication.version_id}, internal receipt {receipt.pk}.\n'
        f'Document fingerprint {receipt.payload_sha256}.\n'
        'This sample contains no real identity or signature information.\n').encode()))
    _, response = commercial_client_response.record(recorder, case.pk, revision.pk, receipt.pk,
        'Synthetic client representative', timezone.now(), 'signed', True, [proof.pk],
        'SAMPLE original human witness to the exact synthetic statement of work.', uuid4(), rev(case),
        party_ref='synthetic-client')
    packet = packet_for(recorder, case, {**sources, 'signature': response.evidence}, revision, configure=False)
    commercial.adopt_signed(recorder, case.pk, revision.pk, response.pk, rev(case))
    if signatures.assert_current_signed_baseline(case).pk != packet.pk or packet.policy_id != original_contract.pk:
        raise RuntimeError('The original sample must retain the exact native dual signature checks.')

    renewal = add_evidence(recorder, case.pk, 'policy_decision',
        'SAMPLE review renews the existing project manager and client identity rules without changing '
        'the human principals, client identity evidence, signature method or signed documents.',
        'synthetic:sow-same-identity-authority-renewal')
    role = active_component(ROLE_COMPONENT, case)
    activate(recorder, case, ROLE_COMPONENT, role.envelope['value'], renewal)
    contract(recorder, case, renewal)


@transaction.atomic
def prepare(recorder):
    if not get_user_model().objects.filter(pk=recorder.pk, username=RECORDER, is_active=True,
                                           is_staff=False, is_superuser=False).exists():
        raise RuntimeError('Use the ordinary active trial recorder.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'kind': 'project', 'title': TITLE, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('Preserve the original isolated synthetic sample.')
    if created:
        Grant.objects.bulk_create([Grant(case=case, user=recorder, action=action) for action in sorted(ACTIONS)])
        prepare_original(recorder, case)
    if set(Grant.objects.filter(case=case, user=recorder, active=True).values_list('action', flat=True)) != ACTIONS:
        raise RuntimeError('Keep the original ordinary recorder with its exact sample grants.')

    _, use = signatures.baseline_use(case)
    original = use.packet
    role = active_component(ROLE_COMPONENT, case)
    contract_version = active_component(SIGNATURE_COMPONENT, case)
    if (original.actor_id != recorder.pk or role.pk == original.authority_id or contract_version.pk == original.policy_id
            or reference_values(role) != reference_values(original.authority)
            or reference_values(contract_version) != reference_values(original.policy)):
        raise RuntimeError('Only an authority renewal for the same witness and exact client identity may be exercised.')
    witness = commercial_client_response.latest(case)
    value, response = commercial_client_response.read(recorder, case, witness)
    if (response.pk != use.adoption.response_id or value['evidence'] != original.signatures['sow']['evidence_id']
            or commercial_client_response.proof_rows(recorder, case, witness)[0].name != PROOF):
        raise RuntimeError('The original signed witness and private proof must remain the same.')
    finance = use.adoption.signedbaselineintake
    try:
        confirmed = signatures.assert_current_signed_baseline(case)
    except ValidationError:
        confirmed = None
    if created and (confirmed or use.reaffirmations.exists()):
        raise RuntimeError('Leave the current human signature decision for the browser.')
    return {'case': str(case.pk), 'path': reverse('commercial_client_response', args=[case.pk]),
            'proposal': response.revision_id, 'document_version': value['document_version'],
            'delivery_receipt': response.receipt_id, 'response': response.pk, 'original_packet': original.pk,
            'original_role': original.authority_id, 'renewed_role': role.pk, 'original_contract': original.policy_id,
            'renewed_contract': contract_version.pk, 'adoption': use.adoption_id, 'finance_intake': finance.pk,
            'prd': original.sources['prd']['id'], 'signature_checks': original.signatures,
            'confirmed_packet': confirmed.pk if confirmed else None, 'preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_SOW_REAFFIRMATION_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit signature reaffirmation fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username=RECORDER, is_active=True, is_staff=False, is_superuser=False)
    print('PSL_SOW_REAFFIRMATION_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
