"""A guarded observation of the exact native invoice-draft claim."""

import json
import os
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory
from apps.workflows.factory_invoice_information import handoff_for
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork, HumanTask
from tests import factory_helpers
from tests.billing_helpers import policy
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_live_steps_seed import LEASE_SECONDS, ObserveExactly
from tests.railway_invoice_milestone_proof_seed import WORKER_ACTIONS


TENANT = 'design-invoice-processing-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE invoice draft being prepared'
PREPARED = 'sample.invoice_processing_prepared'
OBSERVATION = 'sample.invoice_processing_observation'
TRIAL = 'psl-agent-trial'
WORKER = 'sample-invoice-processing-worker'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_REVIEWER = 'sample-correction-preparer-20261120'
READ_ACTIONS = {'case.read', 'factory.read', 'finance.read'}
REVIEW_ACTIONS = READ_ACTIONS | {'finance.invoice.review'}
STEP = 'ACT08'


def accounts(invitation_id, user_id, hosted):
    reader = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, reviewer = admitted_user(invitation_id, user_id, reader)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or reviewer.username != HOSTED_REVIEWER):
        raise RuntimeError('Use the original admitted synthetic Finance reviewer.')
    return reader, reviewer, {'admission': admission.pk, 'invitation': invitation_id,
                              'reader': reader.pk, 'reviewer': reviewer.pk}


def create_work(case, reader, reviewer):
    worker = get_user_model().objects.create_user(username=WORKER)
    for actor, actions in [(worker, WORKER_ACTIONS), (reader, READ_ACTIONS), (reviewer, REVIEW_ACTIONS)]:
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in sorted(actions)])
    with patch.object(factory_helpers, 'setup_case', return_value=(worker, case)):
        data = factory_helpers.fixture(max_age_seconds=7 * 86400, information_resolver_id=None,
                                       lease_seconds=LEASE_SECONDS)
    proof = add_evidence(worker, case.pk, 'policy_decision',
        'SAMPLE only the separate admitted Finance reviewer may decide whether the eventual invoice can be issued.',
        'synthetic:invoice-processing-review-authority')
    assignment = role_assignments.draft(worker, case.pk, [{'role': 'Finance', 'user_id': reviewer.pk}],
                                        proof.pk, timezone.now())
    transition(worker, assignment.pk, 'validated')
    transition(worker, assignment.pk, 'active')
    component = 'D05.decision_action_matrix'
    matrix = reference_values(active_component(component, case))[0]
    for rule in matrix['finance']:
        if rule['purpose'] == 'invoice' and rule['role'] == 'Finance':
            rule['allow_preparer_review'] = False
    policy(worker, case, component, matrix)
    work = data['work']
    for step in ('ACT04', 'ACT06'):
        advanced = factory.run_once(work.pk)
        work.refresh_from_db()
        if not advanced or not work.activities.filter(kind=step, status='succeeded').exists():
            raise RuntimeError(f'The sample did not complete the expected preliminary step {step}: {work.finding}')
    handoff = handoff_for(work)
    return work, {'work': work.pk, 'handoff': handoff.pk, 'completion': handoff.milestone.evidence_id,
                  'completion_sha256': handoff.milestone.evidence.sha256, 'profile': work.policy_id,
                  'review_proof': data['proof'].pk}


def guarded_work(case, marker, reader, reviewer, *, lock=False):
    worker = marker.actor
    query = FactoryWork.objects.select_related('case', 'actor').filter(
        pk=marker.data['work'], case=case, definition='pmo-finance/v1', actor=worker)
    work = (query.select_for_update(of=('self',)) if lock else query).get()
    if (worker.username != WORKER or not worker.is_active or worker.is_staff or worker.is_superuser
            or worker.has_usable_password() or Grant.objects.filter(user=worker).exclude(case=case).exists()):
        raise RuntimeError('This sample requires its original non-interactive case-only worker.')
    for actor, actions in [(worker, WORKER_ACTIONS), (reader, READ_ACTIONS), (reviewer, REVIEW_ACTIONS)]:
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve the originally scoped sample principals.')
    handoff = handoff_for(work)
    if (handoff.pk, handoff.milestone.evidence_id, handoff.milestone.evidence.sha256, work.policy_id) != tuple(
            marker.data[key] for key in ('handoff', 'completion', 'completion_sha256', 'profile')):
        raise RuntimeError('The prepared invoice sources and approved execution profile must be preserved.')
    if InvoiceJob.objects.filter(invoice__case=case).exists() or InvoiceIssue.objects.filter(invoice__case=case).exists():
        raise RuntimeError('This synthetic work cannot issue or send an invoice.')
    return work


def expect_only_draft(work):
    if (work.status != 'ready' or work.invoice_id is not None or work.preparation_id is not None
            or work.cancel_requested or work.lease_until or work.execution_binding_id
            or (work.plan_revision, work.fence) != (2, 2)
            or FactoryProgress.objects.filter(work=work).exists()
            or FactoryAttempt.objects.filter(activity__work=work, activity__kind=STEP).exists()
            or Invoice.objects.filter(case=work.case).exists()):
        raise RuntimeError('Use only the untouched sample immediately before its exact draft action.')
    _, value = factory.profile(work)
    choices, _ = factory.eligible(work, value, *factory.snapshot(work, value))
    if (choices != [STEP] or value['lease_seconds'] != LEASE_SECONDS
            or value['provider'] != 'synthetic_factory_v1'):
        raise RuntimeError('Only the exact permitted native invoice draft under the synthetic profile can be observed.')


def fixture_case(case):
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve all cases beyond the named synthetic invoice processing fixture.')


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    reader, reviewer, identities = accounts(invitation_id, user_id, hosted)
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    fixture_case(case)
    if created:
        work, records = create_work(case, reader, reviewer)
        expect_only_draft(work)
        marker = event(work.actor, case, PREPARED, **identities, **records)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=PREPARED)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('The originally prepared reader and independent reviewer must be preserved.')
    work = guarded_work(case, marker, reader, reviewer)
    return {'case': str(case.pk), **marker.data, 'preserved': not created,
            'path': reverse('factory_detail', args=[work.pk]),
            'decision': reverse('factory_invoice_decision', args=[work.pk]),
            'invoice': work.invoice_id, 'step': STEP}


def observe(invitation_id, user_id, work_id, *, hosted=False):
    if type(work_id) is not int or work_id < 1:
        raise RuntimeError('Choose the exact prepared work from the guarded fixture.')
    with transaction.atomic():
        reader, reviewer, identities = accounts(invitation_id, user_id, hosted)
        case = Case.objects.get(pk=CASE_ID)
        fixture_case(case)
        marker = Audit.objects.get(case=case, action=PREPARED, data__work=work_id)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve the original scoped test accounts and exact work.')
        work = guarded_work(case, marker, reader, reviewer, lock=True)
        if Audit.objects.filter(case=case, action=OBSERVATION).exists():
            raise RuntimeError('The original observation is preserved. Do not replay its worker claim.')
        expect_only_draft(work)
        event(work.actor, case, OBSERVATION, work=work.pk, step=STEP, handoff=marker.data['handoff'])
    if not factory.run_once(work.pk, provider=ObserveExactly(work.pk, STEP)):
        raise RuntimeError('The real native invoice draft did not finish after the observation window.')
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind=STEP, phase='observed')
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    task = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_review', status='open')
    if (work.invoice_id != attempt.result.get('invoice') or task.context['packet']['invoice'] != work.invoice_id
            or task.context['routing_at_creation']['eligible_principals'] != [reviewer.pk]
            or task.claimed_by_id is not None or InvoiceReview.objects.filter(invoice=work.invoice).exists()
            or InvoiceJob.objects.filter(invoice__case=case).exists()):
        raise RuntimeError('Preserve the separate unclaimed Finance decision and unsent native draft.')
    return {'work': work.pk, 'step': STEP, 'attempt': attempt.pk, 'invoice': work.invoice_id, 'review_task': task.pk}


def run(action, work_id=None):
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_INVOICE_PROCESSING_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and explicit processing fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    if action == 'prepare' and work_id is None:
        result = prepare(*HOSTED_ADMISSION, hosted=True)
    elif action == 'observe':
        result = observe(*HOSTED_ADMISSION, work_id, hosted=True)
    else:
        raise RuntimeError('Choose prepare or the exact new work to observe.')
    print('PSL_INVOICE_PROCESSING_FIXTURE=' + json.dumps(result), flush=True)
