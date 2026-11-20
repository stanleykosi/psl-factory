"""Prepare one role-separated fictional cash correction with its original receipt intact."""

import json
import os
from functools import partial
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from adapters.invoices import InternalInvoiceAdapter
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import cash, cash_successors, invoice_delivery
from apps.finance.models import CashSuccessor, InvoiceIssue, InvoiceJob
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.role_assignments import draft
from apps.policy.services import active_component, reference_values, transition
from tests import correction_helpers, settlement_helpers
from tests.billing_helpers import policy
from tests.helpers import rev
from tests.obligation_helpers import issue_identified
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_ADMITTED_CASH_SUCCESSOR_WALKTHROUGH'
TENANT = 'design-admitted-cash-successor-walkthrough'
MARKER = 'sample.cash_successor_ready_for_review'
REFERENCE = 'SAMPLE-CASH-CORRECTION'
ALLOCATION_KEY = 'sample-successor-allocation'
ALLOCATION_AMOUNT = '25.00'
REVIEW_REASON = 'Compared the two fictional source records and the full reversal of the original lot.'
APPROVAL_ACTIONS = ('case.read', 'finance.read', 'finance.correction.review')
MAKER_ACTIONS = ('case.read', 'finance.read', 'finance.cash.successor.apply', 'finance.cash.verify', 'finance.cash.allocate')


def baseline(case, owner, maker, reviewer):
    with patch.object(settlement_helpers, 'setup_case', return_value=(owner, case)):
        _, _, coverage, preparation, proofs = settlement_helpers.fixture()
    correction_helpers.configure(owner, case)
    proof = add_evidence(owner, case.pk, 'policy_decision', 'Synthetic cash correction with a separate source holder, '
                         'reviewer and executor for this case only.', 'synthetic:cash-successor-roles')
    assignment = draft(owner, case.pk, [{'role': 'Finance', 'user_id': actor.pk} for actor in (owner, maker, reviewer)],
                       proof.pk, timezone.now())
    transition(owner, assignment.pk, 'validated')
    transition(owner, assignment.pk, 'active')
    matrix = reference_values(active_component('D05.decision_action_matrix', case))[0]
    for rule in matrix['finance']:
        if rule['purpose'] == 'cash_successor':
            rule['allow_preparer_review'] = False
    policy(owner, case, 'D05.decision_action_matrix', matrix)
    component = 'D14.adjustment_correction_rule_refs'
    rules = reference_values(active_component(component, case))
    for rule in rules:
        if rule['target'] == 'cash_successor':
            rule['require_distinct_preparer'] = True
    policy(owner, case, component, rules)
    original_dispatch = invoice_delivery.run_once
    with patch.object(invoice_delivery, 'run_once', side_effect=partial(
            original_dispatch, InternalInvoiceAdapter(), case_id=case.pk)):
        invoice = settlement_helpers.draft(owner, case, preparation, REFERENCE)
        issue = issue_identified(owner, case, invoice, proofs)
    receipt, lot = settlement_helpers.receipt(owner, case, ref='sample-cash-original-transaction')
    settlement_helpers.assign(owner, case, receipt, coverage, proofs)
    allocation = settlement_helpers.allocate(owner, case, lot, issue, '20.00', proofs)
    reversal = cash.reverse(owner, case.pk, 'lot', lot.pk, 'Finance', proofs['cash_correction'].pk,
                            'The fictional bank confirmed a different amount for this original transaction.', rev(case))
    amount = '40.00'
    body = json.dumps(dict(cash.lot_payload(lot), amount=amount))
    report = add_evidence(owner, case.pk, 'cash_report', body, 'synthetic:corrected-cash-statement')
    verification = add_evidence(owner, case.pk, 'cash_verification', body, 'synthetic:independent-cash-statement-check')
    review = add_evidence(owner, case.pk, 'financial_correction_review', 'Synthetic proof for independent review of the '
                          'same original bank transaction and its corrected amount.', 'synthetic:cash-successor-review')
    successor = cash_successors.capture(owner, case.pk, lot.pk, report.pk, verification.pk, proofs['cash_correction'].pk,
                                        'Use the supplied corrected bank amount for this same transaction.', rev(case))
    if cash_successors.review_snapshot(successor)['reversal'] != reversal.pk:
        raise RuntimeError('Use only the original full reversal in this synthetic cash correction.')
    return {'invoice': invoice.pk, 'issue': issue.pk, 'coverage': coverage.pk, 'receipt': receipt.pk,
            'original_lot': lot.pk, 'original_allocation': allocation.pk, 'original_reversal': reversal.pk,
            'request': successor.pk, 'report': report.pk, 'verification': verification.pk,
            'legal': proofs['cash_correction'].pk, 'review_proof': review.pk,
            'allocation_proof': proofs['cash_allocation'].pk, 'transaction': receipt.transaction_ref,
            'invoice_amount': str(invoice.amount), 'corrected_amount': amount, 'next_allocation': ALLOCATION_AMOUNT}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit opt-in for this isolated cash correction is required.')
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    attributes = {'tenant': TENANT, 'title': f'SAMPLE original receipt and corrected cash {invitation_id}',
                  'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, f'{TENANT}:{invitation_id}'), defaults=attributes)
    if any(getattr(case, key) != value for key, value in attributes.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Preserve any workspace outside this exact synthetic receipt case.')
    identities = {'admission': admission.pk, 'invitation': invitation_id, 'maker': maker.pk, 'reviewer': reviewer.pk}
    username = f'sample-cash-successor-source-holder-{invitation_id}'
    if created:
        owner = get_user_model().objects.create_user(username)
        for person, actions in ((owner, ACTIONS), (maker, MAKER_ACTIONS), (reviewer, APPROVAL_ACTIONS)):
            Grant.objects.bulk_create([Grant(case=case, user=person, action=action) for action in dict.fromkeys(actions)])
        marker = event(owner, case, MARKER, **identities, **baseline(case, owner, maker, reviewer))
    else:
        marker = Audit.objects.get(case=case, actor__username=username, action=MARKER)
    if any(marker.data.get(key) != value for key, value in identities.items()):
        raise RuntimeError('Preserve the exact admission, source and assigned Finance roles.')
    for person, actions in ((maker, MAKER_ACTIONS), (reviewer, APPROVAL_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=person, active=True).values_list('action', flat=True)) != set(actions):
            raise RuntimeError('Keep the synthetic Finance reviewer and executor separate.')

    successor = CashSuccessor.objects.get(case=case, pk=marker.data['request'], parent_id=marker.data['original_lot'],
                                          actor=marker.actor)
    issue = InvoiceIssue.objects.get(invoice__case=case, pk=marker.data['issue'], invoice_id=marker.data['invoice'])
    if successor.parent.receipt_id != marker.data['receipt'] or InvoiceJob.objects.filter(invoice__case=case).exclude(
            kind='issue').exists():
        raise RuntimeError('Preserve the original supplied bank transaction and internal invoice register only.')
    keys = {key: value for key, value in marker.data.items() if key not in identities}
    return {'case': str(case.pk), **keys, 'reviewer': reviewer.username, 'preparer': maker.username,
            'settlement_path': reverse('finance_settlement', args=[case.pk]),
            'corrections_path': reverse('finance_corrections', args=[case.pk]),
            'money_path': reverse('design_project_tab', args=[case.pk, 'money']) + f'?figure=invoice-{issue.invoice_id}'}


def run(invitation_id, user_id):
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_'):
        raise RuntimeError('Select the existing isolated preview database.')
    print('PSL_ADMITTED_CASH_SUCCESSOR_FIXTURE=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
