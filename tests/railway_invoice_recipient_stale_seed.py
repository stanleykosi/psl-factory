"""A guarded invoice whose draft is unchanged while the reviewed recipient changes."""

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
from apps.finance import invoices
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory
from apps.workflows.models import FactoryWork, HumanTask
from tests import factory_helpers
from tests.billing_helpers import policy
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


TENANT = 'design-invoice-recipient-stale-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE invoice with a changed billing recipient'
MARKER = 'sample.invoice_recipient_changed_review_open'
TRIAL = 'psl-agent-trial'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_MAKER = 'sample-correction-preparer-20261120'
EARLIER_LABEL, CURRENT_LABEL = 'Sample Previous Billing Inbox', 'Sample Updated Billing Inbox'
EARLIER_EMAIL, CURRENT_EMAIL = 'earlier-invoice-inbox@example.invalid', 'current-invoice-inbox@example.invalid'
APPROVAL_REASON = 'Checked the replacement Finance packet, the new sample recipient and the unchanged invoice amount.'
RECIPIENT_COMPONENT = 'D08.adapter_contract_ref'
READER_ACTIONS = {'case.read', 'factory.read', 'finance.read'}
REVIEWER_ACTIONS = READER_ACTIONS | {'finance.invoice.review'}
MAKER_ACTIONS = READER_ACTIONS | {
    'evidence.add', 'policy.configure', 'policy.activate', 'baseline.prepare', 'baseline.sign',
    'decision.record', 'commercial.response', 'milestone.complete', 'finance.billing.register',
    'finance.billing.prepare', 'finance.invoice.draft', 'finance.invoice.receive',
    'factory.start', 'factory.execute', 'factory.information', 'agent.extract',
}


def recipient(case, username, name, email):
    row = get_user_model().objects.create_user(username=username, first_name=name, email=email)
    Grant.objects.create(case=case, user=row, action='finance.invoice.receive')
    return row


def stale_decision(case, maker, reviewer):
    for actor, actions in [(maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)]:
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in sorted(actions)])
    earlier = recipient(case, 'sample-invoice-earlier-recipient', EARLIER_LABEL, EARLIER_EMAIL)
    current = recipient(case, 'sample-invoice-current-recipient', CURRENT_LABEL, CURRENT_EMAIL)
    with patch.object(factory_helpers, 'setup_case', return_value=(maker, case)):
        data = factory_helpers.fixture(max_age_seconds=7 * 86400)
    authority = add_evidence(maker, case.pk, 'policy_decision',
        'SAMPLE independent Finance reviewer remains the same across both exact governed recipient versions.',
        'synthetic:invoice-recipient-review-authority')
    assignment = role_assignments.draft(maker, case.pk, [{'role': 'Finance', 'user_id': reviewer.pk}],
                                        authority.pk, timezone.now())
    transition(maker, assignment.pk, 'validated')
    transition(maker, assignment.pk, 'active')
    component = 'D05.decision_action_matrix'
    matrix = reference_values(active_component(component, case))[0]
    for rule in matrix['finance']:
        if rule['purpose'] == 'invoice' and rule['role'] == 'Finance':
            rule['allow_preparer_review'] = False
    policy(maker, case, component, matrix)
    adapter = reference_values(active_component(RECIPIENT_COMPONENT, case))[0]
    earlier_route = policy(maker, case, RECIPIENT_COMPONENT, {**adapter, 'recipient_id': earlier.pk})
    work = data['work']
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'waiting' or work.invoice_id is None:
        raise RuntimeError(f'The sample must stop before an independent Finance decision ({work.status}): {work.finding}')
    task = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_review', status='open')
    if (task.context['packet']['recipient_id'] != earlier.pk or task.claimed_by_id is not None
            or task.context['routing_at_creation']['eligible_principals'] != [reviewer.pk]):
        raise RuntimeError('Preserve the exact captured earlier recipient and current separate reviewer.')
    current_route = policy(maker, case, RECIPIENT_COMPONENT, {**adapter, 'recipient_id': current.pk})
    if invoices.review_packet(work.invoice)['recipient_id'] != current.pk:
        raise RuntimeError('Expected the freshly configured recipient on the same invoice.')
    return {'work': work.pk, 'task': task.pk, 'invoice': work.invoice_id, 'invoice_sha256': work.invoice.sha256,
            'earlier': earlier.pk, 'earlier_route': earlier_route.pk, 'current': current.pk,
            'current_route': current_route.pk, 'review_proof': data['proof'].pk}


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    reviewer = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or maker.username != HOSTED_MAKER):
        raise RuntimeError('Use the original accepted synthetic invoice preparer.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('Preserve every workspace outside the exact stale invoice fixture.')
    identities = {'admission': admission.pk, 'invitation': invitation_id, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if created:
        marker = event(maker, case, MARKER, **identities, **stale_decision(case, maker, reviewer))
    else:
        marker = Audit.objects.get(case=case, actor=maker, action=MARKER)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve this sample’s original separate maker and Finance reviewer.')
    invoice = Invoice.objects.get(pk=marker.data['invoice'], case=case, actor=maker)
    work = FactoryWork.objects.get(pk=marker.data['work'], invoice=invoice, case=case, actor=maker)
    task = HumanTask.objects.get(pk=marker.data['task'], case=case, kind='factory_review', context__work=work.pk)
    for actor, actions in [(maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)]:
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve these exact case-local permissions.')
    if (invoice.sha256 != marker.data['invoice_sha256'] or task.context['packet']['recipient_id'] != marker.data['earlier']
            or invoices.review_packet(invoice)['recipient_id'] != marker.data['current']
            or active_component(RECIPIENT_COMPONENT, case).pk != marker.data['current_route']):
        raise RuntimeError('Preserve the original invoice and both evidenced recipient versions.')
    invoices.review_authority(reviewer, case, 'invoice', 'Finance', 'approve', maker.pk, invoice=invoice)
    if InvoiceIssue.objects.filter(obligation_key=invoice.obligation_key).exists() or InvoiceJob.objects.filter(
            invoice__obligation_key=invoice.obligation_key).exists():
        raise RuntimeError('This comparison cannot issue or send its synthetic invoice.')
    return {'case': str(case.pk), **marker.data, 'preserved': not created,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'overview_path': reverse('factory_detail', args=[work.pk]),
            'earlier_label': EARLIER_LABEL, 'current_label': CURRENT_LABEL, 'approval_reason': APPROVAL_REASON,
            'reviews': InvoiceReview.objects.filter(invoice=invoice).count()}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_INVOICE_RECIPIENT_STALE_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and explicit recipient fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_INVOICE_RECIPIENT_STALE_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
