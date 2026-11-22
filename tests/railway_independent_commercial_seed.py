"""One guarded synthetic portal receipt and outcome with separate human authority."""

import json
import os

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_portal
from apps.pmo.models import RFPDocumentBinding, RFPSubmission
from apps.policy.role_assignments import COMPONENT, draft
from apps.policy.services import active_component, reference_values, register_reference, transition
from apps.workflows import factory
from apps.workflows.factory_progress import set_progress
from apps.workflows.models import FactoryWork
from tests import factory_rfp_helpers
from tests.helpers import activate, rev


PROJECT = 'f957481b-c6f7-43af-bc66-449a330a9d53'
TENANT = 'design-independent-commercial-walkthrough'
TITLE = 'SAMPLE commercial portal with independent receipt and outcome recorder'
KEY = 'SAMPLE-INDEPENDENT-BID-RECORDING'
MAKER_USERNAME = 'sample-independent-bid-maker'
PORTAL_REFERENCE = 'SAMPLE-PORTAL-INDEPENDENT'
RECORDER_ACTIONS = {'case.read', 'factory.read', 'rfp.read', 'rfp.submit', 'rfp.outcome', 'document.read'}
SOURCES = {
    'portal': 'synthetic:independent-bid-exact-portal-receipt',
    'wrong_portal': 'synthetic:independent-bid-mismatched-portal-receipt',
    'award': 'synthetic:independent-bid-customer-award',
}


def bind_recorder(maker, case, recorder, data):
    proof = data['evidence']['policy_decision']
    current = reference_values(active_component(COMPONENT, case))
    roles = [entry for entry in current if entry['role'] != 'Client']
    roles.append({'role': 'Client', 'user_id': recorder.pk})
    profile = draft(maker, case.pk, roles, proof.pk, timezone.now())
    transition(maker, profile.pk, 'validated')
    transition(maker, profile.pk, 'active')
    rfp.assign(maker, case.pk, maker, 'CEO', proof.pk, 'Synthetic maker remains the assigned project manager.', rev(case))

    route = {**data['route'], 'sender_roles': ['PM', 'Client']}
    registered = register_reference(maker, case.pk, 'rfp:sample-independent-portal-route',
        'schema:psl/rfp-submission-route/v1', route, proof.pk)
    activate(maker, case, 'D11.adapter_configuration_refs', [registered.ref], proof)
    return route


@transaction.atomic
def prepare(recorder):
    case, created = Case.objects.get_or_create(tenant=TENANT, kind='project', synthetic=True, title=TITLE)
    if created:
        maker = get_user_model().objects.create_user(username=MAKER_USERNAME)
        Grant.objects.bulk_create([
            *[Grant(case=case, user=maker, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(case=case, user=recorder, action=action) for action in sorted(RECORDER_ACTIONS)],
        ])
        data = factory_rfp_helpers.configured(KEY, portal=True, context=(maker, case))
        route = bind_recorder(maker, case, recorder, data)
        work = factory_rfp_helpers.start(data, key=KEY)
        _, version = factory_rfp_helpers.reviewed_document(data, work)
        factory.run_until_wait(work.pk)
        receipt = {'schema': rfp_portal.SCHEMA, 'version': version.pk, 'sha256': version.payload_sha256,
            'destination': route['destination_ref'], 'reference': PORTAL_REFERENCE, 'received_at': timezone.now().isoformat()}
        add_evidence(maker, case.pk, 'rfp_portal_receipt', json.dumps(receipt), SOURCES['portal'])
        add_evidence(maker, case.pk, 'rfp_portal_receipt', json.dumps({**receipt, 'sha256': '0' * 64}), SOURCES['wrong_portal'])
        add_evidence(maker, case.pk, 'rfp_outcome',
            f'Fictional customer awarded the exact pack version {version.pk} under portal reference {PORTAL_REFERENCE}. Price was not stated.',
            SOURCES['award'])
        work.refresh_from_db()
        set_progress(maker, work.pk, work.revision, True)
    else:
        work = FactoryWork.objects.get(case=case, actor__username=MAKER_USERNAME, definition='rfp-response/v1', key=KEY)
        maker = work.actor
    binding = RFPDocumentBinding.objects.select_related('version').get(response__rfp__case=case)
    version = binding.version
    submission = RFPSubmission.objects.filter(version=version).first()
    sources = dict(case.evidence.filter(source__in=SOURCES.values()).values_list('source', 'pk'))
    return {'case': str(case.pk), 'work': work.pk, 'version': version.pk, 'maker': maker.pk, 'recorder': recorder.pk,
        'review': version.reviews.latest('pk').pk, 'reference': PORTAL_REFERENCE,
        'sources': {key: sources[value] for key, value in SOURCES.items()},
        'submission': submission.pk if submission else None, 'path': reverse('factory_work_response', args=[work.pk]),
        'existing_work_preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_INDEPENDENT_COMMERCIAL_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit independent Commercial fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print('PSL_INDEPENDENT_COMMERCIAL_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
