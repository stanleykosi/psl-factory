"""An exact bid prepared by the trial actor for an already admitted reviewer."""

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp
from apps.pmo.models import RFPResponse, RFPSubmission
from apps.policy import role_assignments
from apps.policy.factory_rfp_validators import COMPONENT as EXECUTION_COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, decision_authority, reference_values, transition
from apps.workflows import factory, factory_rfp
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_independent_commercial_seed import PROJECT
from tests.test_rfp import fixture as rfp_sources


TENANT = 'design-admitted-bid-response-return'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE bid response with independent Engineering review'
REFERENCE = 'SAMPLE-ADMITTED-BID-RETURN'
MARKER = 'sample.admitted_bid_awaits_review'
TRIAL = 'psl-agent-trial'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_REVIEWER = 'sample-correction-preparer-20261120'
ROLE = 'Engineering Lead'
REVIEW_ACTIONS = {'case.read', 'factory.read', 'rfp.read', 'rfp.review'}
PREPARER_ACTIONS = {
    'case.read', 'factory.read', 'factory.start', 'factory.execute', 'factory.manage', 'evidence.add',
    'rfp.read', 'rfp.intake', 'rfp.assign', 'rfp.prepare', 'agent.rfp', 'commercial.prepare',
    'document.read', 'document.template', 'document.receive:client', 'policy.configure', 'policy.activate',
} | {f'rfp.contribute:{team}' for team in rfp.TEAMS}
REQUIREMENT = 'SAMPLE R1: Show the count of received items and a separate total for unresolved exceptions.'
INITIAL_ANSWER = 'The reconciliation report lists the count of received items.'
RETURN_REASON = 'Explain how the report will show a separate total for unresolved exceptions, as required by R1.'
CORRECTED_ANSWER = 'The report lists the count of received items and separately totals unresolved exceptions.'
APPROVE_REASON = 'The new response covers both totals stated in R1.'


def prepared_bid(trial, reviewer, case):
    Grant.objects.bulk_create([
        *[Grant(case=case, user=trial, action=action) for action in sorted(PREPARER_ACTIONS)],
        *[Grant(case=case, user=reviewer, action=action) for action in sorted(REVIEW_ACTIONS)],
    ])
    _, _, sources, _, _ = rfp_sources(reference=REFERENCE, portal=True, context=(trial, case))
    proof = add_evidence(trial, case.pk, 'policy_decision',
        'SAMPLE decision appoints the admitted reviewer to the Engineering Lead review only. '
        'The trial remains responsible for preparing the cited response and any corrections.', 'synthetic:admitted-bid-review-role')
    assigned = reference_values(active_component(role_assignments.COMPONENT, case))
    roles = [entry for entry in assigned if entry['role'] != ROLE]
    roles.append({'role': ROLE, 'user_id': reviewer.pk})
    profile = role_assignments.draft(trial, case.pk, roles, proof.pk, timezone.now())
    transition(trial, profile.pk, 'validated')
    transition(trial, profile.pk, 'active')
    rfp.assign(trial, case.pk, trial, 'CEO', proof.pk, 'SAMPLE original preparer remains the project manager.', rev(case))

    execution = json.loads(Path('fixtures/factory-rfp.json').read_text())
    execution.pop('classification')
    settings = draft_operator_policy(trial, case.pk, EXECUTION_COMPONENT, execution, proof.pk, timezone.now())
    transition(trial, settings.pk, 'validated')
    transition(trial, settings.pk, 'active')
    requirement = add_evidence(trial, case.pk, 'requirements', REQUIREMENT, 'synthetic:admitted-bid-requirement-r1')
    wording = add_evidence(trial, case.pk, 'rfp_response', INITIAL_ANSWER, 'synthetic:admitted-bid-initial-answer')
    payload = {'response_evidence': wording.pk, 'public_terms': sources['rfp_commercial_terms'].pk,
               'sources': {'requirements': requirement.pk, 'plan': sources['plan'].pk, 'costing': sources['costing'].pk},
               'matrix': [{'key': 'R1', 'evidence_id': requirement.pk,
                           'response': INITIAL_ANSWER, 'disposition': 'addressed'}],
               'lessons': sources['rfp_lessons'].pk}
    work = factory_rfp.start(trial, case.pk, REFERENCE, payload, REFERENCE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    initial = factory_rfp.response_for(work)
    if initial is None or initial.actor_id != trial.pk or initial.reviews.exists():
        raise RuntimeError('The cited response must wait before any Engineering decision.')
    return work, initial, requirement, proof


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, reviewer = admitted_user(invitation_id, user_id, trial)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or reviewer.username != HOSTED_REVIEWER):
        raise RuntimeError('The accepted sample invitation does not belong to the original hosted reviewer.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'kind': 'project', 'title': TITLE, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('Preserve all workspaces outside this exact synthetic bid fixture.')
    identities = {'admission': admission.pk, 'invitation': invitation_id, 'reviewer': reviewer.pk, 'preparer': trial.pk}
    if created:
        work, initial, requirement, proof = prepared_bid(trial, reviewer, case)
        marker = event(trial, case, MARKER, **identities, work=work.pk, response=initial.pk,
                       requirement=requirement.pk, proof=proof.pk)
    else:
        marker = Audit.objects.get(case=case, action=MARKER, actor=trial)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve the original bid and its separate accepted reviewer.')
        work = FactoryWork.objects.get(pk=marker.data['work'], case=case, definition=factory_rfp.DEFINITION,
                                       key=REFERENCE, actor=trial)
        initial = RFPResponse.objects.get(pk=marker.data['response'], rfp__case=case, actor=trial)
    for actor, actions in ((trial, PREPARER_ACTIONS), (reviewer, REVIEW_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('The bid must retain its exact original case-local permissions.')
    decision_authority(reviewer, case, ROLE, 'return')
    if RFPSubmission.objects.filter(response__rfp__case=case).exists() or Publication.objects.filter(
            version__document__case=case).exists():
        raise RuntimeError('No client delivery is part of this bid review sample.')
    current = factory_rfp.response_for(work)
    return {'case': str(case.pk), 'work': work.pk, 'reference': REFERENCE, **identities, 'role': ROLE,
            'original_response': initial.pk, 'current_response': current.pk if current else None,
            'review_proof': marker.data['proof'], 'requirement': marker.data['requirement'],
            'decision': reverse('factory_invoice_decision', args=[work.pk]),
            'correction': reverse('factory_detail', args=[work.pk]) + '#correct-response',
            'return_reason': RETURN_REASON, 'corrected_answer': CORRECTED_ANSWER, 'approve_reason': APPROVE_REASON,
            'existing_decisions': initial.reviews.count(), 'preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_RFP_ADMITTED_RETURN_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit admitted bid reviewer fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_RFP_ADMITTED_RETURN_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
