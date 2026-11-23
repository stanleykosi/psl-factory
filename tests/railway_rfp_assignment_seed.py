"""A guarded received bid that awaits a separate human assignment."""

import json
import os
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.core.workbench import work
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_assignment_queue
from apps.policy.role_assignments import draft
from apps.policy.services import transition
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PROJECT


TENANT = 'design-rfp-assignment-walkthrough'
TITLE = 'SAMPLE incoming bid awaiting a project manager'
REFERENCE = 'SAMPLE-BID-ASSIGNMENT-BROWSER'
PREPARER = 'sample-bid-assignment-browser-preparer'
NOMINEE = 'sample-bid-assignment-browser-nominee'
ASSIGNER_ACTIONS = {'case.read', 'rfp.read', 'rfp.assign'}
PREPARER_ACTIONS = {'case.read', 'rfp.intake', 'evidence.add', 'policy.read', 'policy.configure', 'policy.activate'}
NOMINEE_ACTIONS = {'case.read', 'rfp.read', 'rfp.prepare'}


def grant(case, user, actions):
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for action in sorted(actions)])


def record_intake(assigner, preparer, nominee, case):
    proof = add_evidence(preparer, case.pk, 'policy_decision',
        'SAMPLE reviewed nomination of the synthetic trial assigner and a separate sample project manager.',
        'synthetic:bid-assignment-nominations')
    artifact(preparer, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v2', {
        'rfp': {'assignment_roles': ['CEO'], 'outcome_roles': ['Client']},
        'rules': [{'role': 'Engineering Lead', 'actions': ['return', 'reject']}],
    }, proof)
    profile = draft(preparer, case.pk, [{'role': 'CEO', 'user_id': assigner.pk}, {'role': 'PM', 'user_id': nominee.pk}],
                    proof.pk, timezone.now())
    transition(preparer, profile.pk, 'validated')
    transition(preparer, profile.pk, 'active')
    source = add_evidence(preparer, case.pk, 'rfp_intake',
        'SAMPLE fictional bid request about a test-system handoff. No actual deadline or destination was supplied.',
        'synthetic:bid-assignment-received-source')
    rfp.intake(preparer, case.pk, REFERENCE, source.pk, timezone.now() - timedelta(minutes=5),
               'not_stated', None, None, 'The isolated sample tender is ready for a human project manager assignment.', rev(case))


@transaction.atomic
def prepare(assigner):
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, TENANT),
        defaults={'tenant': TENANT, 'kind': 'project', 'title': TITLE, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('Choose only the exact synthetic bid assignment workspace.')
    users = get_user_model().objects
    if created:
        preparer = users.create_user(username=PREPARER)
        nominee = users.create_user(username=NOMINEE, first_name='Sample', last_name='Bid Manager')
        grant(case, preparer, PREPARER_ACTIONS)
        grant(case, assigner, ASSIGNER_ACTIONS)
        grant(case, nominee, NOMINEE_ACTIONS)
        record_intake(assigner, preparer, nominee, case)
    else:
        preparer = users.get(username=PREPARER, is_active=True)
        nominee = users.get(username=NOMINEE, is_active=True)

    roles, nominations = rfp_assignment_queue.assignment_scope(assigner, case)
    available = rfp_assignment_queue.nominees(case, nominations)
    actual_actions = set(Grant.objects.filter(case=case, user=assigner, active=True).values_list('action', flat=True))
    if roles != ['CEO'] or [user.pk for user in available] != [nominee.pk] or actual_actions != ASSIGNER_ACTIONS:
        raise RuntimeError('Keep the exact original synthetic assigner permissions and separate approved nominee.')
    bid = rfp_assignment_queue.bids().get(case=case, reference=REFERENCE, current_intake__actor=preparer)
    current, access_held = rfp_assignment_queue.assignment_state(bid)
    readback = []
    if current and current.pm_id == nominee.pk:
        readback = [row['record_id'] for row in work(nominee)['rows']
                    if row['kind'] == 'assigned_rfp' and row['case_id'] == str(case.pk)]
    return {'case': str(case.pk), 'reference': REFERENCE, 'queue': reverse('rfp_assignment_queue'),
            'assignment_form': reverse('rfp_assignment', args=[case.pk]), 'source': bid.current_intake.evidence_id,
            'intake': bid.current_intake_id, 'assigner': assigner.pk, 'preparer': preparer.pk,
            'nominee': nominee.pk, 'nominee_name': nominee.get_full_name(), 'role': roles[0], 'preserved': not created,
            'current_assignment': current.pk if current else None, 'access_held': access_held,
            'nominee_assigned_work_readback': readback}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_RFP_ASSIGNMENT_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit bid assignment fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    assigner = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print('PSL_RFP_ASSIGNMENT_FIXTURE=' + json.dumps(prepare(assigner)), flush=True)
