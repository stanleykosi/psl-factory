"""One synthetic signed milestone, part-payment and a current change to link in the browser."""
import json
import os
from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import invoice_delivery, invoices
from apps.finance.models import CashAllocation, Handoff, InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo.change_execution import record_execution
from apps.pmo.change_stage_links import MANAGE_ACTIONS, current_plans, plan_proof
from apps.pmo.changes import CONTRIBUTORS, assess_change, authorize_change, decide_change, log_change
from apps.pmo.models import Baseline, ChangeMilestoneLink
from apps.pmo.services import complete_milestone
from apps.policy.services import register_reference
from apps.workflows.services import run_once as handoff_once
from tests import settlement_helpers as settlement
from tests.billing_helpers import coverage, evidence, policy, prepare as prepare_billing, stage_policy
from tests.helpers import activate, rev, signed
from tests.obligation_helpers import identified
from tests.railway_independent_commercial_seed import PROJECT
from tests.signature_helpers import reaffirm_for
from tests.test_commercial_changes import impact_fixture


TENANT = 'design-signed-milestone-payment'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE Harbour Hub signed milestone and change'
TRIAL = 'psl-agent-trial'
PREPARER = 'sample-signed-milestone-payment-fixture'
MARKER = 'sample.signed_milestone_payment_prepared'
MILESTONE = 'SAMPLE Harbour Hub go-live'
REFERENCE = 'SAMPLE-SIGNED-MILESTONE-INVOICE'
CHANGE_REFERENCE = 'SAMPLE-CR-001'
CHANGE_SCOPE = 'Add sample message reminders to go-live'
SIGNED_AMOUNT = Decimal('42.50')
PART_PAYMENT = Decimal('20.00')


def setup_terms(owner, case, proof):
    settlement.configured(owner, case)
    # Both role families must remain current after the Finance fixture installs its own role.
    refs = ['settlement-finance']
    for role in ('PM', 'Head of PMO', 'CEO', 'PMO Lead', 'Product', 'Engineering'):
        entry = register_reference(owner, case.pk, f'sample-stage:{role}', 'schema:psl/role-assignment/v1',
                                   {'role': role, 'user_id': owner.pk}, proof['policy_decision'].pk)
        refs.append(entry.ref)
    activate(owner, case, 'D05.role_principal_assignments', refs, proof['policy_decision'])
    reaffirm_for(owner, case)
    milestone = complete_milestone(owner, case.pk, MILESTONE, proof['completion'].pk, rev(case))
    if not handoff_once(case_id=case.pk):
        raise RuntimeError('The exact synthetic milestone must reach the internal Finance handoff.')
    handoff = Handoff.objects.get(case=case, milestone=milestone)
    scope = coverage(owner, case, amount_basis='gross_including_tax', reference='sample-signed-milestone')
    stage_policy(owner, case, scope, proof['signature'])
    due = timezone.localdate() + timedelta(days=7)
    terms = policy(owner, case, 'D12.stage_terms', [
        {'coverage_id': scope.pk, 'stage': 'completion', 'amount': str(SIGNED_AMOUNT), 'due_date': due.isoformat()},
    ])
    policy(owner, case, 'D12.completion_billing_predicate_ref', {
        'coverage_id': scope.pk, 'stage': 'completion', 'milestone_name': MILESTONE,
    })
    return handoff, scope, terms, due


def setup_part_payment(owner, case, handoff, scope, due):
    preparation = prepare_billing(owner, case, scope, kind='completion', h=handoff)
    draft = invoices.draft(owner, case.pk, preparation.pk, REFERENCE, due, rev(case))
    identified(owner, case, draft)
    proof = {kind: evidence(owner, case, kind, f'Synthetic signed milestone {kind}')
             for kind in ('invoice_review', 'cash_correction', 'cash_allocation')}
    settlement.approve(owner, case, draft, proof)
    reserved = invoices.reserve(owner, case.pk, draft.pk, 'issue', 'Finance', rev(case))
    # The canonical internal adapter uses this exact job and writes the local issue only.
    if not invoice_delivery.run_once(case_id=case.pk, job_id=reserved.pk):
        raise RuntimeError('The exact synthetic internal issue was not processed.')
    issue = InvoiceIssue.objects.get(invoice=draft, job=reserved)
    receipt, lot = settlement.receipt(owner, case, str(PART_PAYMENT), 'sample-signed-milestone-cash')
    settlement.assign(owner, case, receipt, scope, proof)
    allocation = settlement.allocate(owner, case, lot, issue, str(PART_PAYMENT), proof, key='sample-signed-milestone')
    return issue, receipt, allocation


def setup_change(owner, case):
    request = add_evidence(owner, case.pk, 'change_request', CHANGE_SCOPE, 'synthetic:stage-change-request')
    version = log_change(owner, case.pk, CHANGE_REFERENCE, 'Normal', 'Delivery', CHANGE_SCOPE,
                         'Fictional written request', request.pk, rev(case))
    for team in CONTRIBUTORS:
        impact = impact_fixture(team)
        if team == 'Engineering':
            impact['scope_items'] = [f'{CHANGE_REFERENCE}/reminders']
        assess_change(owner, case.pk, version.pk, team, False, False, False, request.pk,
                      'Engineering preparation on an isolated synthetic project', rev(case), **impact)
    for role in ('Product', 'Engineering'):
        decide_change(owner, case.pk, version.pk, role, 'approve', request.pk, 'Synthetic request reviewed', rev(case))
    authority = authorize_change(owner, case.pk, version.pk, None, rev(case))
    original = add_evidence(owner, case.pk, 'plan', CHANGE_SCOPE, 'synthetic:stage-change-owner-plan')
    plan = record_execution(owner, case.pk, authority.pk, 'plan_updated', original.pk,
                            'Original approved scope recorded in the owner plan', rev(case))
    return version, plan, original


@transaction.atomic
def prepare():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE_ID).exists():
        raise RuntimeError('Preserve all workspaces outside the exact signed milestone specimen.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    case = Case.objects.select_for_update().get(pk=case.pk)
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Use only the exact synthetic signed milestone specimen.')
    identity = {'trial': trial.pk}
    if created:
        owner = get_user_model().objects.create_user(PREPARER)
        Grant.objects.bulk_create([
            *[Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(user=trial, case=case, action=action) for action in sorted(MANAGE_ACTIONS)],
        ])
        proof = signed(owner, case)
        handoff, scope, terms, due = setup_terms(owner, case, proof)
        issue, receipt, allocation = setup_part_payment(owner, case, handoff, scope, due)
        version, plan, original = setup_change(owner, case)
        marker = event(owner, case, MARKER, **identity, signed=proof['signature'].pk, terms=terms.pk,
                       coverage=scope.pk, milestone=handoff.milestone_id, handoff=handoff.pk,
                       issue=issue.pk, receipt=receipt.pk, allocation=allocation.pk,
                       change=version.pk, plan=plan.pk, original_plan=original.pk)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER)
    if (marker.data['trial'] != trial.pk or marker.actor.username != PREPARER or marker.actor.has_usable_password()
            or marker.actor.is_staff or marker.actor.is_superuser or not marker.actor.is_active):
        raise RuntimeError('Preserve the separate synthetic preparer and Trial account.')
    if set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)) != MANAGE_ACTIONS:
        raise RuntimeError('Preserve the exact case-local Trial permissions.')
    data = marker.data
    baseline = Baseline.objects.get(case=case, signed_id=data['signed'])
    issue = InvoiceIssue.objects.get(pk=data['issue'], invoice__case=case, invoice__reference=REFERENCE,
        invoice__amount=SIGNED_AMOUNT, invoice__preparation__kind='completion',
        invoice__preparation__handoff_id=data['handoff'], invoice__preparation__coverage_id=data['coverage'],
        job__kind='issue', job__status='confirmed')
    allocation = CashAllocation.objects.get(pk=data['allocation'], issue=issue, lot__receipt_id=data['receipt'],
                                            amount=PART_PAYMENT)
    if InvoiceJob.objects.filter(invoice__case=case).exclude(pk=issue.job_id).exists() or InvoiceDelivery.objects.filter(invoice__case=case).exists():
        raise RuntimeError('Only the original internal synthetic issue may exist in this sample.')
    plan = current_plans(case).get(pk=data['plan'], authorization__version_id=data['change'])
    if plan_proof(case, plan) != data['original_plan']:
        raise RuntimeError('Preserve the exact original recorded owner plan.')
    linked = ChangeMilestoneLink.objects.filter(case=case).first()
    if linked and (linked.actor_id != trial.pk or linked.version_id != data['change'] or linked.stage != 'completion'
                   or linked.signed_id != baseline.signed_id or linked.plan_event_id != plan.pk):
        raise RuntimeError('Preserve only the exact authorized milestone link for this specimen.')
    return {**data, 'case': str(case.pk), 'preparer': marker.actor_id, 'invoice': issue.invoice_id,
            'paid': str(allocation.amount), 'reference': REFERENCE, 'milestone_name': MILESTONE,
            'change_reference': CHANGE_REFERENCE, 'change_scope': CHANGE_SCOPE,
            'linked': linked.pk if linked else None, 'preserved': not created,
            'milestones': reverse('design_project_tab', args=[case.pk, 'milestones']),
            'money': reverse('design_project_tab', args=[case.pk, 'money']) + '?figure=completion',
            'form': reverse('design_change_milestone_link', args=[case.pk])}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_SIGNED_MILESTONE_PAYMENT_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway test project and signed milestone fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicit acceptance preview database before preparing the specimen.')
    print('PSL_SIGNED_MILESTONE_PAYMENT_FIXTURE=' + json.dumps(prepare()), flush=True)
