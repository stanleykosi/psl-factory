"""Prepare an isolated invoice that still needs a named responsibility resolver."""

import json
import os
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance.models import InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.factory_routing_validators import COMPONENT
from apps.policy.models import Configuration
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_routing
from apps.workflows.models import FactoryWork, HumanTask
from tests import factory_helpers
from tests.billing_helpers import policy
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_invoice_milestone_proof_seed import WORKER_ACTIONS
from tests.test_factory_routing import configure


TENANT = 'design-invoice-owner-needed-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE invoice waiting for named responsibilities'
MARKER = 'sample.invoice_owner_needed'
TRIAL = 'psl-agent-trial'
WORKER = 'sample-invoice-owner-needed-preparer'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_READER = 'sample-correction-preparer-20261120'
RECHECK_REASON = 'The named sample invoice owner and resolver have current workspace access and the separate Finance review is ready.'
READER_ACTIONS = {'case.read', 'factory.read', 'finance.read'}
RESOLVER_ACTIONS = READER_ACTIONS | {'policy.read', 'policy.configure', 'policy.activate', 'finance.invoice.review'}


def prepare_draft(case, reader, resolver):
    worker = get_user_model().objects.create_user(username=WORKER)
    for actor, actions in [(worker, WORKER_ACTIONS), (reader, READER_ACTIONS), (resolver, RESOLVER_ACTIONS)]:
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in sorted(actions)])
    with patch.object(factory_helpers, 'setup_case', return_value=(worker, case)):
        data = factory_helpers.fixture(responsibility=False, max_age_seconds=7 * 86400, information_resolver_id=None)
    authority = add_evidence(worker, case.pk, 'policy_decision',
        'SAMPLE Finance reviewer has separate native review rights for this invoice. The sample process owner '
        'and responsibility resolver must still be explicitly named before a review can proceed.',
        'synthetic:invoice-owner-needed-authority')
    assignment = role_assignments.draft(worker, case.pk, [{'role': 'Finance', 'user_id': resolver.pk}],
                                        authority.pk, timezone.now())
    transition(worker, assignment.pk, 'validated')
    transition(worker, assignment.pk, 'active')
    decision_component = 'D05.decision_action_matrix'
    matrix = reference_values(active_component(decision_component, case))[0]
    for rule in matrix['finance']:
        if rule['purpose'] == 'invoice' and rule['role'] == 'Finance':
            rule['allow_preparer_review'] = False
    policy(worker, case, decision_component, matrix)
    initial = configure(data, process_owner_id=None, governance_resolver_id=None)
    nomination = add_evidence(worker, case.pk, 'policy_decision',
        'SAMPLE review of responsibility after the hold. The fictional invoice preparer remains accountable '
        'for the process, routing and review policy in this sample. The named trial account can resolve the '
        'hold separately from preparation. Record and activate the exact nominations before rechecking.',
        'synthetic:invoice-owner-needed-nominations')
    work = data['work']
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'owner_needed' or work.invoice_id is None:
        raise RuntimeError(f'Expect the exact drafted invoice held on its owners ({work.status}): {work.finding}')
    task = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_governance', status='open')
    routing = factory_routing.evaluate(work)
    if (task.claimed_by_id is not None or routing['missing'] != ['process_owner_id']
            or routing['governance_resolver_id'] is not None or routing['eligible_principals']):
        raise RuntimeError('Leave the missing owner, resolver nomination and recheck for the browser.')
    return worker, {'work': work.pk, 'invoice': work.invoice_id, 'invoice_sha256': work.invoice.sha256,
                    'task': task.pk, 'initial_configuration': initial.pk, 'nomination_evidence': nomination.pk,
                    'review_proof': data['proof'].pk}


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    resolver = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, reader = admitted_user(invitation_id, user_id, resolver)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or reader.username != HOSTED_READER):
        raise RuntimeError('Use the original accepted sample project reader.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve every workspace outside this exact invoice responsibility sample.')
    identities = {'admission': admission.pk, 'invitation': invitation_id, 'reader': reader.pk, 'resolver': resolver.pk}
    if created:
        worker, records = prepare_draft(case, reader, resolver)
        marker = event(worker, case, MARKER, **identities, **records)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER)
        worker = marker.actor
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve this sample’s original admitted viewer and separate resolver.')
    if (worker.username != WORKER or not worker.is_active or worker.is_staff or worker.is_superuser
            or worker.has_usable_password() or Grant.objects.filter(user=worker).exclude(case=case).exists()):
        raise RuntimeError('The original sample worker must remain non-interactive and case scoped.')
    for actor, actions in [(worker, WORKER_ACTIONS), (reader, READER_ACTIONS), (resolver, RESOLVER_ACTIONS)]:
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve the fixture’s original exact case-local rights.')
    work = FactoryWork.objects.get(pk=marker.data['work'], case=case, actor=worker, invoice_id=marker.data['invoice'])
    task = HumanTask.objects.get(pk=marker.data['task'], case=case, context__work=work.pk, kind='factory_governance')
    initial = Configuration.objects.get(pk=marker.data['initial_configuration'], case=case, component=COMPONENT)
    original = reference_values(initial)[0]
    if (work.invoice.sha256 != marker.data['invoice_sha256'] or original['process_owner_id'] is not None
            or original['governance_resolver_id'] is not None
            or task.context['routing']['binding']['configuration'] != initial.pk):
        raise RuntimeError('The original held responsibility and exact invoice must remain unchanged.')
    if InvoiceJob.objects.filter(invoice__case=case).exists() or InvoiceIssue.objects.filter(invoice__case=case).exists():
        raise RuntimeError('The sample has no authority to issue or deliver an invoice.')
    if created and InvoiceReview.objects.filter(invoice__case=case).exists():
        raise RuntimeError('Leave the separate native invoice decision to a later step.')
    fields = {'process_owner_id': worker.pk, 'activity_owner_id': worker.pk, 'policy_owner_id': worker.pk,
              'governance_resolver_id': resolver.pk, 'authority_mode': 'direct_only',
              'availability_mode': 'not_applied', 'evidence': marker.data['nomination_evidence']}
    return {'case': str(case.pk), **marker.data, 'worker': worker.pk, 'preserved': not created, 'status': work.status,
            'task_status': task.status, 'claimed_by': task.claimed_by_id, 'nomination_fields': fields,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'responsibility_path': reverse('factory_responsibility', args=[case.pk]) + '?' + urlencode({'work': work.pk}),
            'recheck_reason': RECHECK_REASON}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_INVOICE_OWNER_NEEDED_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and explicit owner-needed fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_INVOICE_OWNER_NEEDED_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
