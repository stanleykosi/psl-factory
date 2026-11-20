"""Prepare only the exact unsupplied milestone proof request for a browser walkthrough."""

import json
import os
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import CaseUpload
from apps.core.evidence_access import INVOICE_MILESTONE_PROOF
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.factory_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, decision_authority, reference_values, transition
from apps.workflows import factory, factory_progress
from apps.workflows.factory_invoice_information import handoff_for, request_matches, supplier as authorize_supplier
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask, InvoiceMilestoneProof
from tests import factory_helpers
from tests.billing_helpers import policy
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


TENANT = 'design-invoice-milestone-proof-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE invoice waiting for a private milestone PDF'
MARKER = 'sample.invoice_milestone_proof_waiting'
TRIAL = 'psl-agent-trial'
WORKER = 'sample-invoice-milestone-proof-worker'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_SUPPLIER = 'sample-correction-preparer-20261120'
FILENAME = 'sample-milestone-proof.pdf'
NOTE = 'SAMPLE signed testing evidence supplied for the recorded milestone.'
APPROVAL_REASON = 'The original private milestone proof and the exact sample invoice amount were checked.'
CASE_READ = {'case.read', 'factory.read', 'finance.read'}
SUPPLIER_ACTIONS = CASE_READ | {'factory.information', 'evidence.add'}
REVIEWER_ACTIONS = CASE_READ | {'finance.invoice.review'}
WORKER_ACTIONS = CASE_READ | {
    'evidence.add', 'policy.configure', 'policy.activate', 'baseline.prepare', 'baseline.sign',
    'decision.record', 'commercial.response', 'milestone.complete', 'finance.billing.register',
    'finance.billing.prepare', 'finance.invoice.draft', 'finance.invoice.receive',
    'factory.start', 'factory.execute', 'agent.extract',
}


def prepare_work(case, source_owner, reviewer):
    worker = get_user_model().objects.create_user(username=WORKER)
    for actor, actions in [(worker, WORKER_ACTIONS), (source_owner, SUPPLIER_ACTIONS), (reviewer, REVIEWER_ACTIONS)]:
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in sorted(actions)])
    with patch.object(factory_helpers, 'setup_case', return_value=(worker, case)):
        data = factory_helpers.fixture(configure=False, max_age_seconds=7 * 86400,
                                       required_evidence_kinds=['completion', INVOICE_MILESTONE_PROOF])
    matrix_component = 'D05.decision_action_matrix'
    matrix = reference_values(active_component(matrix_component, case))[0]
    for rule in matrix['finance']:
        if rule['purpose'] == 'invoice' and rule['role'] == 'Finance':
            rule['allow_preparer_review'] = False
    policy(worker, case, matrix_component, matrix)
    decision = add_evidence(worker, case.pk, 'policy_decision',
        'SAMPLE proof may be supplied only by the named admitted evidence owner. A separate Finance reviewer decides '
        'the exact later invoice. Background work can prepare the draft and has no authority to issue it.',
        'synthetic:invoice-milestone-proof-authority')
    assignment = role_assignments.draft(worker, case.pk, [{'role': 'Finance', 'user_id': reviewer.pk}],
                                        decision.pk, timezone.now())
    value = dict(data['value'], information_resolver_id=source_owner.pk)
    config = draft_operator_policy(worker, case.pk, COMPONENT, value, decision.pk, timezone.now())
    for configuration in (assignment, config):
        transition(worker, configuration.pk, 'validated')
        transition(worker, configuration.pk, 'active')
    work = data['work']
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'waiting' or work.invoice_id is not None:
        raise RuntimeError(f'The sample must wait before drafting ({work.status}): {work.finding}')
    task = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_information', status='open')
    if (task.claimed_by_id is not None or task.context.get('missing') != [INVOICE_MILESTONE_PROOF]
            or not request_matches(work, task, source_owner)):
        raise RuntimeError('No initial claim or evidence can be created by this setup.')
    job = factory_progress.set_progress(worker, work.pk, work.revision, True)
    handoff = handoff_for(work)
    return worker, {'work': work.pk, 'task': task.pk, 'profile': config.pk, 'progress': job.pk,
                    'handoff': handoff.pk, 'milestone': handoff.milestone_id,
                    'completion': handoff.milestone.evidence_id,
                    'completion_sha256': handoff.milestone.evidence.sha256, 'review_proof': data['proof'].pk}


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    accounts = get_user_model().objects
    reviewer = accounts.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, source_owner = admitted_user(invitation_id, user_id, reviewer)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or source_owner.username != HOSTED_SUPPLIER):
        raise RuntimeError('Use the original accepted synthetic evidence supplier.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve every workspace outside the exact milestone proof fixture.')
    actors = {'admission': admission.pk, 'invitation': invitation_id, 'supplier': source_owner.pk, 'reviewer': reviewer.pk}
    if created:
        worker, records = prepare_work(case, source_owner, reviewer)
        marker = event(worker, case, MARKER, **actors, **records)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER)
        worker = marker.actor
        if any(marker.data.get(key) != value for key, value in actors.items()):
            raise RuntimeError('Preserve the original sample’s approved identities and source.')
    if (worker.username != WORKER or not worker.is_active or worker.is_superuser or worker.is_staff
            or worker.has_usable_password() or Grant.objects.filter(user=worker).exclude(case=case).exists()):
        raise RuntimeError('The test worker must be non-interactive and restricted to the sample.')
    for actor, actions in [(worker, WORKER_ACTIONS), (source_owner, SUPPLIER_ACTIONS), (reviewer, REVIEWER_ACTIONS)]:
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve this sample’s exact case-only access.')
    work = FactoryWork.objects.get(pk=marker.data['work'], case=case, definition='pmo-finance/v1', actor=worker)
    config, value = factory.profile(work, recovery=True)
    task = HumanTask.objects.get(pk=marker.data['task'], case=case, kind='factory_information')
    job = FactoryProgress.objects.get(pk=marker.data['progress'], work=work, requested_by=worker)
    handoff = handoff_for(work)
    authorize_supplier(source_owner, work, value)
    decision_authority(reviewer, case, 'Finance', 'approve')
    if (config.pk != marker.data['profile'] or not request_matches(work, task, source_owner)
            or (handoff.pk, handoff.milestone_id, handoff.milestone.evidence_id, handoff.milestone.evidence.sha256)
            != tuple(marker.data[key] for key in ('handoff', 'milestone', 'completion', 'completion_sha256'))):
        raise RuntimeError('The exact milestone, original completion and request must be preserved.')
    if InvoiceJob.objects.filter(invoice__case=case).exists() or InvoiceIssue.objects.filter(invoice__case=case).exists():
        raise RuntimeError('This synthetic journey must not issue or send an invoice.')
    proofs = InvoiceMilestoneProof.objects.filter(work=work, task=task)
    if created and (Invoice.objects.filter(case=case).exists() or proofs.exists()
                    or CaseUpload.objects.filter(case=case).exists() or InvoiceReview.objects.filter(invoice__case=case).exists()):
        raise RuntimeError('Present an unsupplied milestone request. Leave proof and Finance decisions to the browser.')
    return {'case': str(case.pk), **marker.data, 'worker': worker.pk, 'preserved': not created,
            'status': task.status, 'claimed_by': task.claimed_by_id, 'proof_count': proofs.count(),
            'invoice': work.invoice_id, 'background_status': job.status,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'overview_path': reverse('factory_detail', args=[work.pk]), 'file_path': reverse('case_uploads', args=[case.pk]),
            'filename': FILENAME, 'note': NOTE, 'approval_reason': APPROVAL_REASON}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_INVOICE_MILESTONE_PROOF_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and explicit invoice proof fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_INVOICE_MILESTONE_PROOF_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
