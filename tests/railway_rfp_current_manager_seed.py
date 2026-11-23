"""Guarded synthetic submissions for independent bid follow-up walkthroughs."""

import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_portal
from apps.pmo.models import RFPFollowupDispatch, RFPSubmission
from apps.policy.role_assignments import COMPONENT, draft
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory
from apps.workflows.models import FactoryWork
from tests import factory_rfp_helpers
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PROJECT
from tests.test_rfp_messages import configured as configure_sample_mailbox


TENANT = 'design-rfp-current-manager-walkthrough'
TITLES = {
    'reminder': 'SAMPLE unconfirmed bid with a revised internal reminder',
    'message': 'SAMPLE unconfirmed bid with a separately reviewed follow-up',
}
MANAGER_ACTIONS = {'case.read', 'factory.read', 'rfp.read', 'rfp.prepare', 'rfp.outcome', 'document.read'}
MESSAGE_ACTIONS = {'agent.rfp', 'evidence.add', 'rfp.submit'}


def prepare_submission(maker, manager, case, scenario, reference):
    data = factory_rfp_helpers.configured(reference, portal=True, context=(maker, case))
    proof = data['evidence']['policy_decision']
    roles = [row for row in reference_values(active_component(COMPONENT, case)) if row['role'] != 'Client']
    roles.extend({'role': role, 'user_id': manager.pk} for role in ('PM', 'Client'))
    configuration = draft(maker, case.pk, roles, proof.pk, timezone.now())
    transition(maker, configuration.pk, 'validated')
    transition(maker, configuration.pk, 'active')
    rfp.assign(maker, case.pk, maker, 'CEO', proof.pk, 'Original preparer managed the synthetic response.', rev(case))
    if scenario == 'message':
        configure_sample_mailbox(data)

    work = factory_rfp_helpers.start(data, key=reference)
    _, version = factory_rfp_helpers.reviewed_document(data, work)
    factory.run_until_wait(work.pk)
    receipt = add_evidence(maker, case.pk, 'rfp_portal_receipt', json.dumps({
        'schema': rfp_portal.SCHEMA,
        'version': version.pk,
        'sha256': version.payload_sha256,
        'destination': data['route']['destination_ref'],
        'reference': f'SAMPLE-PORTAL-CURRENT-MANAGER-{scenario.upper()}',
        'received_at': timezone.now().isoformat(),
    }), 'synthetic:current-manager-portal-receipt')
    rfp_portal.record(maker, case.pk, version.pk, receipt.pk,
                      'Verified the exact previously approved fictional portal pack.', rev(case))
    handoff = add_evidence(maker, case.pk, 'policy_decision',
        'The separately nominated sample manager will check this exact submitted bid for the preview exercise.',
        'synthetic:current-manager-handoff')
    rfp.assign(maker, case.pk, manager, 'CEO', handoff.pk,
               'The current synthetic manager will check for a customer response.', rev(case))
    return work


@transaction.atomic
def prepare(manager, scenario):
    title = TITLES[scenario]
    maker_name = f'sample-bid-current-manager-{scenario}-maker'
    reference = f'SAMPLE-BID-CURRENT-MANAGER-{scenario.upper()}'
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, f'{TENANT}/{scenario}'),
        defaults={'tenant': TENANT, 'kind': 'project', 'title': title, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', title, True):
        raise RuntimeError('Choose only the exact synthetic bid workspace.')
    actions = MANAGER_ACTIONS | (MESSAGE_ACTIONS if scenario == 'message' else set())
    if created:
        maker = get_user_model().objects.create_user(username=maker_name)
        Grant.objects.bulk_create([
            *[Grant(user=maker, case=case, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(user=manager, case=case, action=action) for action in sorted(actions)],
        ])
        work = prepare_submission(maker, manager, case, scenario, reference)
    else:
        work = FactoryWork.objects.get(case=case, actor__username=maker_name, definition='rfp-response/v1', key=reference)

    rfp_root = rfp.root(case)
    assignment = rfp.current_assignment(rfp_root)
    grants = set(Grant.objects.filter(case=case, user=manager, active=True).values_list('action', flat=True))
    if manager.pk != assignment.pm_id or manager.pk == work.actor_id or grants != actions:
        raise RuntimeError('Use the original separate manager and exact sample permissions.')
    submission = RFPSubmission.objects.get(response__rfp=rfp_root)
    followups = RFPFollowupDispatch.objects.filter(outcome__submission=submission).order_by('pk')
    return {'scenario': scenario, 'case': str(case.pk), 'work': work.pk, 'reference': reference,
            'maker': work.actor_id, 'manager': manager.pk, 'assignment': assignment.pk,
            'submission': submission.pk, 'submitted_at': submission.submitted_at.isoformat(),
            'portal_reference': submission.portal_receipt.reference,
            'path': reverse('factory_work_response', args=[work.pk]), 'alerts': reverse('design_alerts'),
            'history': reverse('rfp', args=[case.pk]), 'outcomes': list(submission.outcomes.values_list('pk', flat=True)),
            'followups': list(followups.values_list('pk', flat=True)), 'preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_RFP_CURRENT_MANAGER_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit current-manager fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    manager = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    for scenario in TITLES:
        print('PSL_RFP_CURRENT_MANAGER_FIXTURE=' + json.dumps(prepare(manager, scenario)), flush=True)
