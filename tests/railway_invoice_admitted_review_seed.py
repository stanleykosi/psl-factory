"""Prepare a synthetic invoice and a separate accepted-account reviewer journey."""

import json
import os
from datetime import timedelta
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import invoices, usage_intake
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.services import transition
from apps.workflows import factory, factory_invoice_intake, factory_routing
from apps.workflows.models import FactoryWork, HumanTask
from tests import usage_intake_helpers
from tests.billing_helpers import policy, prepare as prepare_billing
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.settlement_helpers import configured as configure_settlement
from tests.test_factory_invoice_intake import configuration


TENANT = 'design-admitted-invoice-review'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE usage invoice with separate Finance review'
REFERENCE = 'SAMPLE-INVOICE-INDEPENDENT'
MARKER = 'sample.admitted_invoice_awaits_review'
TRIAL = 'psl-agent-trial'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_MAKER = 'sample-correction-preparer-20261120'
DELIVERY = 'sample-usage-correction-delivery'
OPERATION = 'sample-usage-correction-receive'
COMMENT = 'Please verify the count against the fictional usage control before it is approved.'
RETURN_REASON = 'The reported usage is incomplete. Reconcile the amended report and submit a new packet.'
CORRECTION_REASON = 'Reconciled the corrected report and its control. The charge changes from NGN 20.00 to NGN 24.00.'
APPROVE_REASON = 'I checked the corrected usage report, reconciled total, and current invoice amount.'
REVIEW_ACTIONS = {'case.read', 'factory.read', 'finance.read', 'finance.invoice.review'}
MAKER_ACTIONS = {
    'case.read', 'factory.read', 'factory.start', 'factory.execute', 'factory.manage', 'factory.information', 'evidence.add',
    'finance.read', 'finance.billing.register', 'finance.billing.capture', 'finance.billing.prepare',
    'agent.billing', 'finance.invoice.draft', 'finance.invoice.receive', 'policy.read', 'policy.configure', 'policy.activate',
}


def prepared_invoice(maker, reviewer, case):
    Grant.objects.bulk_create([
        Grant(case=case, user=actor, action=action)
        for actor, actions in ((maker, MAKER_ACTIONS), (reviewer, REVIEW_ACTIONS))
        for action in sorted(actions)
    ])
    with patch.object(usage_intake_helpers, 'setup_case', return_value=(maker, case)):
        _, _, coverages, source, control = usage_intake_helpers.fixture()
    coverage = coverages[0]
    receipt = usage_intake_helpers.receive(maker, case, source, control)
    accepted = usage_intake.accept(maker, case.pk, receipt.source_id, rev(case))
    usage_intake_helpers.prices(maker, case, coverages)
    prep = prepare_billing(maker, case, coverage, u=accepted.partitions.get(coverage=coverage))

    settlement = configure_settlement(maker, case)
    for rule in settlement['review']['finance']:
        if rule['purpose'] == 'invoice' and rule['role'] == 'Finance':
            rule['allow_preparer_review'] = False
    policy(maker, case, 'D05.decision_action_matrix', settlement['review'])
    assignment = add_evidence(maker, case.pk, 'policy_decision',
        'SAMPLE Finance review belongs to the separate test reviewer. The admitted preparer owns the usage and correction.',
        'synthetic:admitted-invoice-review-role')
    role = role_assignments.draft(maker, case.pk, [{'role': 'Finance', 'user_id': reviewer.pk}],
                                  assignment.pk, timezone.now())
    transition(maker, role.pk, 'validated')
    transition(maker, role.pk, 'active')
    review_proof = configuration(maker, case)

    source, control = usage_intake_helpers.correction(source, control)
    corrected_source = add_evidence(maker, case.pk, 'usage_intake_source', json.dumps(source),
                                    'synthetic:invoice-corrected-usage')
    corrected_control = add_evidence(maker, case.pk, 'usage_intake_controls', json.dumps(control),
                                     'synthetic:invoice-corrected-controls')
    due_date = timezone.localdate() + timedelta(days=7)
    work = factory_invoice_intake.start(maker, case.pk, REFERENCE, prep.pk, REFERENCE, due_date, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'waiting' or work.invoice_id is None:
        raise RuntimeError(f'The fictional invoice did not reach review ({work.status}): {work.finding}')
    task = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_review', status='open')
    if (work.invoice.actor_id, task.claimed_by_id) != (maker.pk, None):
        raise RuntimeError('Prepare only an unclaimed exact review of the original fictional invoice.')
    if factory_routing.require_ready(work)['eligible_principals'] != [reviewer.pk]:
        raise RuntimeError('The trial must be the only current Finance reviewer.')
    return {
        'work': work.pk, 'invoice': work.invoice_id, 'task': task.pk, 'review_proof': review_proof.pk,
        'source_evidence': corrected_source.pk, 'control_evidence': corrected_control.pk,
        'predecessor': receipt.source_id, 'coverage': coverage.pk, 'due_date': due_date.isoformat(),
    }


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    reviewer = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or maker.username != HOSTED_MAKER):
        raise RuntimeError('Use only the original accepted sample preparer.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve every workspace outside the exact fictional invoice fixture.')
    identities = {'admission': admission.pk, 'invitation': invitation_id, 'reviewer': reviewer.pk, 'maker': maker.pk}
    if created:
        marker = event(maker, case, MARKER, **identities, **prepared_invoice(maker, reviewer, case))
    else:
        marker = Audit.objects.get(case=case, actor=maker, action=MARKER)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve this fixture’s original roles and preparer admission.')
    for actor, actions in ((maker, MAKER_ACTIONS), (reviewer, REVIEW_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('The original exact fixture access must remain bounded to one case.')
    work = FactoryWork.objects.get(pk=marker.data['work'], case=case, key=REFERENCE,
                                   definition='pmo-finance/v1', actor=maker)
    original = Invoice.objects.get(pk=marker.data['invoice'], case=case, actor=maker)
    invoices.review_authority(reviewer, case, 'invoice', 'Finance', 'return', original.actor_id, invoice=original)
    if InvoiceJob.objects.filter(invoice__case=case).exists() or InvoiceIssue.objects.filter(invoice__case=case).exists():
        raise RuntimeError('Preserve this prepared sample without any invoice dispatch.')
    return {'case': str(case.pk), 'reference': REFERENCE, **marker.data, 'current_invoice': work.invoice_id,
            'original_decisions': InvoiceReview.objects.filter(invoice=original).count(), 'preserved': not created,
            'decision': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery': reverse('factory_invoice_recovery', args=[work.pk]),
            'overview': reverse('factory_detail', args=[work.pk]),
            'usage_intake': reverse('finance_usage_intake', args=[case.pk]),
            'billing': reverse('finance_billing', args=[case.pk]),
            'settlement': reverse('finance_settlement', args=[case.pk]),
            'delivery': DELIVERY, 'operation': OPERATION, 'comment': COMMENT, 'return_reason': RETURN_REASON,
            'correction_reason': CORRECTION_REASON, 'approve_reason': APPROVE_REASON}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_INVOICE_ADMITTED_REVIEW_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and explicit invoice fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_INVOICE_ADMITTED_REVIEW_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
