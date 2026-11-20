"""Prepare isolated source records for a grouped browser walkthrough."""
import json
import os
from functools import partial
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, reference_values, register_reference, transition
from apps.workflows import factory, factory_accounting_intake, factory_change, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import test_commercial_changes, test_delivery, test_factory_hypercare, test_project_archive_files, test_standard_changes
from tests.helpers import rev
from tests.signature_helpers import reaffirm_for


PREVIEW_PROJECT = 'f957481b-c6f7-43af-bc66-449a330a9d53'
TENANT = 'design-composed-delivery-walkthrough'
PREPARATION = {
    'stability': ('delivery-hypercare/v1', 'SAMPLE release stability walkthrough'),
    'stability_active': ('delivery-hypercare/v1', 'SAMPLE active stability evaluation'),
    'client_testing_wait': ('delivery-release/v1', 'SAMPLE client testing request walkthrough'),
    'archive': ('delivery-archive/v1', 'SAMPLE file archive walkthrough'),
    'archive_active': ('delivery-archive/v1', 'SAMPLE active archive copy'),
    'standard': ('pmo-change/v1', 'SAMPLE standard change walkthrough'),
    'normal_change_refusal': ('pmo-change/v1', 'SAMPLE Normal Change refusal walkthrough'),
    'emergency': ('pmo-emergency/v1', 'SAMPLE emergency walkthrough'),
    'emergency_authorized': ('pmo-emergency/v1', 'SAMPLE emergency authorized outcome walkthrough'),
    'emergency_refused': ('pmo-emergency/v1', 'SAMPLE emergency refusal walkthrough'),
    'escalation': ('pmo-escalation/v1', 'SAMPLE escalation walkthrough'),
    'invoice_release': ('pmo-finance/v1', 'SAMPLE invoice release walkthrough'),
    'bid_final_costing': ('rfp-response/v1', 'SAMPLE bid final costing review'),
    'leadership': ('pmo-leadership-report/v1', 'SAMPLE leadership report walkthrough'),
    'tuesday': ('pmo-leadership-report/v1', 'SAMPLE Tuesday report walkthrough'),
    'accounts': ('finance-accounts/v1', 'SAMPLE accounts close walkthrough'),
    'accounts_continuation': ('finance-accounts/v1', 'SAMPLE accounts continuation walkthrough'),
    'accounts_reviewer_needed': ('finance-accounts/v1', 'SAMPLE accounts allocation reviewer needed'),
    'accounts_uncertain_receipt': ('finance-accounts/v1', 'SAMPLE accounts original delivery receipt'),
    'assets': ('finance-ppe/v1', 'SAMPLE fixed asset walkthrough'),
    'schedules': ('finance-schedules/v1', 'SAMPLE schedules walkthrough'),
    'schedule_duplicates': ('finance-schedules/v1', 'SAMPLE duplicate income detail walkthrough'),
    'forecast': ('finance-forecast/v1', 'SAMPLE cash forecast walkthrough'),
}
INTERNAL_EMERGENCY_REF = 'sample:emergency-internal'
INVOICE_DECISION_PREPARATION = {
    'invoice_maker': 'SAMPLE invoice waiting for an independent reviewer',
    'invoice_other_reviewer': 'SAMPLE invoice assigned to another reviewer',
    'invoice_replaced': 'SAMPLE invoice replaced while awaiting review',
}
INDEPENDENT_FINANCE_PREPARATION = {
    'asset_review': ('finance-ppe/v1', 'SAMPLE independent asset schedule review'),
    'income_review': ('finance-schedules/v1', 'SAMPLE independent income schedule review'),
}
SHORT_PAYMENT_PREPARATION = {
    'short_payment_unconfigured': 'SAMPLE short payment awaiting a review rule',
    'short_payment_configured': 'SAMPLE short payment for an exact Finance decision',
}
PROGRESS_PREPARATION = {
    'accounts_live': ('accounts', 'SAMPLE accounts investigation and report progress'),
    'assets_live': ('assets', 'SAMPLE asset register investigation progress'),
    'schedules_live': ('schedules', 'SAMPLE income source investigation progress'),
    'forecast_live': ('forecast', 'SAMPLE cash forecast investigation progress'),
    'archive_live': ('archive', 'SAMPLE active archive file receipts'),
}
ORIGINAL_WORK_KEYS = {
    'standard': 'SAMPLE-BATCH-STANDARD',
    'escalation': 'P44-1',
    'leadership': 'LEADERSHIP-1',
    'tuesday': 'LEADERSHIP-1',
}


def pause_existing_background(actor, work):
    work.refresh_from_db()
    if FactoryProgress.objects.filter(work=work, status__in=factory_progress.ACTIVE).exists():
        factory_progress.set_progress(actor, work.pk, work.revision, False)


def prepare_stability(actor, case):
    with patch.object(test_delivery, 'setup_case', return_value=(actor, case)):
        entry = test_factory_hypercare.setup()
        entry.accepted()
        entry.criteria()
        entry.observations()
    return entry.work


def prepare_client_testing_wait(actor, case):
    from apps.core import client_contacts
    from apps.workflows import factory_delivery

    entry = test_delivery.DeliveryFixture()
    entry.setup_delivery(context=(actor, case))
    entry.plan()
    entry.gates(['qa_exit', 'uat_product_manager', 'uat_product_owner', 'engineering_go'])
    profile = json.loads(Path('fixtures/factory-delivery.json').read_text())
    profile.pop('classification')
    config = draft_operator_policy(actor, case.pk, 'OPS.factory_delivery_execution', profile,
                                   entry.e['policy_decision'].pk, timezone.now())
    transition(actor, config.pk, 'validated')
    transition(actor, config.pk, 'active')
    client_contacts.save(actor, case, 'project', {
        'customer': '', 'client_name': 'SAMPLE Client', 'name': 'SAMPLE Client Test Witness',
        'email': 'sample-client-test@example.invalid', 'role': 'SAMPLE test contact',
        'evidence': entry.e['policy_decision'], 'revision': rev(case),
    })
    return factory_delivery.start(actor, case.pk, 'SAMPLE-BATCH-CLIENT-WAIT', entry.d.pk,
                                  'SAMPLE client testing and response', rev(case))


def prepare_archive(actor, case):
    with patch.object(test_delivery, 'setup_case', return_value=(actor, case)):
        entry = test_project_archive_files.configured()
    return entry.work


def prepare_standard(actor, case):
    with patch.object(test_standard_changes, 'fixture', side_effect=lambda *, existing:
                      test_commercial_changes.fixture(existing=existing, context=(actor, case))):
        entry = test_standard_changes.StandardChangeTests()
        entry.setUp()
    reaffirm_for(actor, case)
    entry.bound()
    template = entry.change_template()
    profile = json.loads(Path('fixtures/factory-change.json').read_text())
    profile.pop('classification')
    profile.update(preparer_id=actor.pk, executor_id=actor.pk)
    config = draft_operator_policy(actor, case.pk, 'OPS.factory_change_execution', profile,
                                   entry.e['policy_decision'].pk, timezone.now())
    transition(actor, config.pk, 'validated')
    transition(actor, config.pk, 'active')
    work = factory_change.start(actor, case.pk, 'SAMPLE-BATCH-STANDARD', entry.cv.pk,
                                {'template_id': template.pk, 'authorization_id': None},
                                'SAMPLE standard change with recorded procedure', rev(case))
    return work


def prepare_normal_change_refusal(actor, case):
    from tests import test_factory_change
    from tests.document_helpers import artifact

    fixture = test_commercial_changes.fixture
    with patch.object(test_commercial_changes, 'fixture', side_effect=lambda *, existing:
                      fixture(existing=existing, context=(actor, case))):
        entry = test_factory_change.FactoryChangeTests()
        entry.setUp()
    entry.assessments(cost=False, timeline=True, client=True)
    artifact(actor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
             {'rules': [{'role': 'Client', 'actions': ['reject']}]}, entry.e['policy_decision'])
    add_evidence(actor, case.pk, 'document', 'The fictional client declined the sample change for this phase.',
                 'synthetic:design-batch-normal-change-refusal')
    return entry.start()


def prepare_emergency(actor, case, *, verified_sources=False, refusal=False):
    from tests import test_emergencies, test_factory_emergency

    with patch.object(test_emergencies, 'fixture', side_effect=lambda *, existing:
                      test_commercial_changes.fixture(existing=existing, context=(actor, case))):
        entry = test_factory_emergency.FactoryEmergencyTests()
        entry.setUp()
    entry.policies()
    entry.clocks()
    if verified_sources:
        entry.glpi()
    if refusal:
        from tests.document_helpers import artifact
        artifact(actor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'CTO', 'actions': ['reject']}]}, entry.e['policy_decision'])
    return entry.start_work()


def prepare_internal_emergency_recipient(actor, case):
    """Extend only the named synthetic fixture while retaining earlier review records."""
    from tests.helpers import activate

    if (case.tenant != TENANT or not case.synthetic or case.title != PREPARATION['emergency_authorized'][1]
            or not Grant.objects.filter(case=case, user=actor, action='document.receive:internal', active=True).exists()):
        raise RuntimeError('The exact sample workspace and existing internal access are required')
    component = 'D11.recipient_grant_refs'
    config = active_component(component, case)
    recipients = reference_values(config)
    if any(row['audience'] == 'internal' for row in recipients):
        if any(row['audience'] == 'internal' and row['user_id'] != actor.pk for row in recipients):
            raise RuntimeError('A different internal recipient is configured on this sample')
        return
    if recipients != [{'audience': 'client', 'user_id': actor.pk}]:
        raise RuntimeError('Expected the original synthetic delivery configuration')
    evidence = case.evidence.get(kind='policy_decision', source='synthetic:test')
    reference = register_reference(actor, case.pk, INTERNAL_EMERGENCY_REF, 'schema:psl/document-recipient/v1',
                                   {'audience': 'internal', 'user_id': actor.pk}, evidence.pk)
    activate(actor, case, component, [*config.envelope['value'], reference.ref], evidence)


def prepare_escalation(actor, case):
    from tests import document_helpers, test_factory_escalation

    with patch.object(document_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_escalation.FactoryEscalationTests()
        entry.setUp()
    return entry.start()


def prepare_invoice_release(actor, case):
    from tests import factory_helpers
    from tests.obligation_helpers import factory_identified

    with patch.object(factory_helpers, 'setup_case', return_value=(actor, case)):
        entry = factory_helpers.fixture(max_age_seconds=7 * 86400)
    factory.run_until_wait(entry['work'].pk)
    return factory_identified(entry)


def prepare_final_costing(actor, case):
    from tests.factory_rfp_helpers import final_costing_wait

    work, _, _ = final_costing_wait(context=(actor, case))
    return work


def prepare_independent_invoice_reviewer(actor, case, work):
    from tests.billing_helpers import policy
    from tests.helpers import activate

    reviewer = get_user_model().objects.create_user('batch-invoice-independent-reviewer')
    Grant.objects.bulk_create([Grant(case=case, user=reviewer, action=action) for action in
                               ('case.read', 'factory.read', 'finance.read', 'finance.invoice.review')])
    proof = case.evidence.filter(kind='policy_decision', source='synthetic:billing-tests').order_by('pk').first()
    reference = register_reference(actor, case.pk, 'sample:invoice-independent-reviewer',
                                   'schema:psl/role-assignment/v1', {'role': 'Finance', 'user_id': reviewer.pk}, proof.pk)
    activate(actor, case, 'D05.role_principal_assignments', [reference.ref], proof)
    matrix = reference_values(active_component('D05.decision_action_matrix', case))[0]
    for rule in matrix['finance']:
        if rule['purpose'] == 'invoice' and rule['role'] == 'Finance':
            rule['allow_preparer_review'] = False
    policy(actor, case, 'D05.decision_action_matrix', matrix)
    factory.run_until_wait(work.pk)


@transaction.atomic
def prepare_invoice_decision_variant(actor, key):
    from apps.finance import invoices

    case, created = Case.objects.get_or_create(tenant=TENANT, title=INVOICE_DECISION_PREPARATION[key],
                                               kind='project', synthetic=True)
    if created:
        maker = (get_user_model().objects.create_user('batch-invoice-other-maker')
                 if key == 'invoice_other_reviewer' else actor)
        Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        if maker != actor:
            Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in
                                       ('case.read', 'factory.read', 'finance.read')])
        work = prepare_invoice_release(maker, case)
        pause_existing_background(maker, work)
        if key == 'invoice_maker':
            prepare_independent_invoice_reviewer(actor, case, work)
        if key == 'invoice_replaced':
            old = work.invoice
            invoices.draft(actor, case.pk, old.preparation_id, old.reference, old.due_date, rev(case))
    else:
        work = FactoryWork.objects.get(case=case, definition='pmo-finance/v1', key='FACTORY-EXAMPLE')
    return {'case': str(case.pk), 'work': work.pk, 'path': reverse('factory_invoice_decision', args=[work.pk]),
            'existing_work_preserved': not created}


def prepare_leadership(actor, case, *, tuesday=False):
    from tests import document_helpers, test_factory_leadership

    with patch.object(document_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_leadership.FactoryLeadershipTests()
        entry.setUp()
    if tuesday:
        entry.tuesday()
    return entry.start_work()


def prepare_accounts(actor, case, *, independent_allocation=False):
    from tests import factory_accounting_helpers, finance_analysis_helpers as source

    with patch.object(source, 'setup_case', return_value=(actor, case)):
        _, _, evidence, values, _, ledger, template, _ = source.fixture()
    if independent_allocation:
        for rule in values['authority']['finance']:
            if rule['purpose'] == 'allocation':
                rule['allow_preparer_review'] = False
        source.policy(actor, case, 'D05.decision_action_matrix', values['authority'], evidence['policy_decision'])
    return factory_accounting_helpers.configured(actor, case, evidence, ledger, template, source.METRICS)['work']


def prepare_accounts_uncertain_receipt(actor, case):
    from adapters.publications import PublicationTimeoutAfterAccept
    from apps.documents.models import PublicationJob
    from apps.workflows import factory_accounting
    from apps.workflows.models import HumanTask

    work = prepare_accounts(actor, case)
    factory.run_until_wait(work.pk)
    task = HumanTask.objects.get(case=case, kind='factory_accounting_review', status='open', context__purpose='output')
    task = factory_accounting.claim(actor, task.pk, task.revision)
    evidence = case.evidence.get(kind='finance_review', source='synthetic:finance')
    factory_accounting.decide(actor, task.pk, task.revision, 'approve', evidence.pk,
                              'The synthetic setup simulates an exact Finance review before the response is lost.')
    for _ in range(25):
        factory.run_once(work.pk, adapter=PublicationTimeoutAfterAccept())
        if PublicationJob.objects.filter(publication__factory_work=work, status='unknown').exists():
            return work
    raise RuntimeError('The sample must retain an original accepted report with its response still uncertain')


def prepare_assets(actor, case):
    from tests import finance_analysis_helpers, test_factory_ppe

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_ppe.FactoryPPETests()
        entry.setUp()
    return entry.start()


def prepare_schedules(actor, case, *, check_duplicates=False):
    from tests import finance_analysis_helpers, schedule_helpers, test_factory_schedules

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_schedules.FactorySchedulesTests()
        entry.setUp()
    if check_duplicates:
        for label, amount in [('SAMPLE training fee', '20.00'), ('SAMPLE support fee', '15.00')]:
            item = schedule_helpers.row(entry.f, label.replace(' ', '-'), amount, 'additive')
            entry.payload['rows'].append(dict(item, duplicate_state='not_assessed'))
    return entry.start()


@transaction.atomic
def prepare_independent_finance_review(actor, key):
    from tests import finance_analysis_helpers, ppe_helpers, schedule_helpers, test_factory_ppe, test_factory_schedules

    definition, title = INDEPENDENT_FINANCE_PREPARATION[key]
    case, created = Case.objects.get_or_create(tenant=TENANT, title=title, kind='project', synthetic=True)
    if created:
        maker = get_user_model().objects.create_user(f'batch-{key}-maker')
        Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        module, test_class, fixture = ((test_factory_ppe, test_factory_ppe.FactoryPPETests, ppe_helpers.fixture)
                                       if key == 'asset_review' else
                                       (test_factory_schedules, test_factory_schedules.FactorySchedulesTests, schedule_helpers.fixture))
        with (patch.object(finance_analysis_helpers, 'setup_case', return_value=(maker, case)),
              patch.object(module, 'fixture', side_effect=partial(fixture, reviewer=actor, recipient_username=f'batch-{key}-recipient'))):
            entry = test_class()
            entry.setUp()
        work = entry.start()
        factory.run_until_wait(work.pk)
        pause_existing_background(maker, work)
    else:
        work = FactoryWork.objects.get(case=case, definition=definition, actor__username=f'batch-{key}-maker')
    return {'case': str(case.pk), 'work': work.pk, 'path': reverse('factory_invoice_decision', args=[work.pk]),
            'existing_work_preserved': not created}


@transaction.atomic
def prepare_short_payment(actor, key):
    from apps.finance import invoice_delivery, invoices
    from apps.finance.models import InvoiceIssue
    from apps.policy.short_payment_validators import COMPONENT
    from tests import settlement_helpers as settlement
    from tests.obligation_helpers import approve_identified

    case, created = Case.objects.get_or_create(tenant=TENANT, title=SHORT_PAYMENT_PREPARATION[key],
                                               kind='project', synthetic=True)
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        with patch.object(settlement, 'setup_case', return_value=(actor, case)):
            _, _, coverage, prep, evidence = settlement.fixture()
        invoice = settlement.draft(actor, case, prep, reference='SAMPLE-SHORT-PAYMENT')
        approve_identified(actor, case, invoice, evidence)
        job = invoices.reserve(actor, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
        invoice_delivery.run_once(case_id=case.pk, job_id=job.pk)
        issue = InvoiceIssue.objects.get(invoice=invoice)
        receipt, lot = settlement.receipt(actor, case, amount='2.00', ref=f'sample-{key}')
        settlement.assign(actor, case, receipt, coverage, evidence)
        settlement.allocate(actor, case, lot, issue, '2.00', evidence, key=f'sample-{key}')
        if key == 'short_payment_configured':
            proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic short-payment review only.', 'synthetic:test')
            config = draft_operator_policy(actor, case.pk, COMPONENT, {
                'reviewer_id': actor.pk, 'treatments': ['request_proof', 'record_exception', 'reject_exception'],
            }, proof.pk, timezone.now())
            transition(actor, config.pk, 'validated')
            transition(actor, config.pk, 'active')
    else:
        issue = InvoiceIssue.objects.get(invoice__case=case, invoice__reference='SAMPLE-SHORT-PAYMENT')
    return {'case': str(case.pk), 'issue': issue.pk,
            'path': reverse('invoice_short_payment', args=[case.pk, issue.pk]), 'existing_work_preserved': not created}


def prepare_forecast(actor, case):
    from tests import forecast_helpers, test_factory_forecast

    with patch.object(forecast_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_forecast.ForecastFactoryTests()
        entry.setUp()
    return entry.start()


@transaction.atomic
def prepare_project(actor, key):
    template_key = key
    if key in PROGRESS_PREPARATION:
        template_key, title = PROGRESS_PREPARATION[key]
        definition = PREPARATION[template_key][0]
    else:
        definition, title = PREPARATION[key]
    case, created = Case.objects.get_or_create(tenant=TENANT, title=title, kind='project', synthetic=True)
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        prepare = {'stability': prepare_stability, 'stability_active': prepare_stability,
                   'client_testing_wait': prepare_client_testing_wait, 'archive': prepare_archive,
                   'archive_active': prepare_archive, 'standard': prepare_standard,
                   'normal_change_refusal': prepare_normal_change_refusal,
                   'emergency': prepare_emergency,
                   'emergency_authorized': partial(prepare_emergency, verified_sources=True),
                   'emergency_refused': partial(prepare_emergency, refusal=True), 'escalation': prepare_escalation,
                   'invoice_release': prepare_invoice_release,
                   'bid_final_costing': prepare_final_costing,
                   'leadership': prepare_leadership, 'tuesday': prepare_leadership,
                   'accounts': prepare_accounts, 'accounts_continuation': prepare_accounts,
                   'accounts_reviewer_needed': partial(prepare_accounts, independent_allocation=True),
                   'accounts_uncertain_receipt': prepare_accounts_uncertain_receipt, 'assets': prepare_assets,
                   'schedules': prepare_schedules,
                   'schedule_duplicates': partial(prepare_schedules, check_duplicates=True),
                   'forecast': prepare_forecast}[template_key]
        users = get_user_model().objects
        create_user = users.create_user
        with patch.object(users, 'create_user', side_effect=lambda username, **values:
                          create_user(username=f'batch-{key}-{username}', **values)):
            work = prepare(actor, case, tuesday=True) if key == 'tuesday' else prepare(actor, case)
        pause_existing_background(actor, work)
    else:
        candidates = FactoryWork.objects.filter(case=case, actor=actor, definition=definition)
        if key in ORIGINAL_WORK_KEYS:
            candidates = candidates.filter(key=ORIGINAL_WORK_KEYS[key])
        work = candidates.get()
    if key == 'emergency_authorized':
        prepare_internal_emergency_recipient(actor, case)
    return {'case': str(case.pk), 'work': work.pk, 'path': reverse('factory_detail', args=[work.pk]),
            'existing_work_preserved': not created}


@transaction.atomic
def prepare_accounting_intake(actor, *, missing_units):
    from tests import finance_analysis_helpers

    title, key = ('SAMPLE trial balance waiting for units', 'units') if missing_units else (
        'SAMPLE trial balance held at intake', 'quarantined')
    case, created = Case.objects.get_or_create(tenant=TENANT, title=title, kind='project', synthetic=True)
    reference = f'batch-intake-{key}'
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
            _, _, _, values, _, old_source, _, _ = finance_analysis_helpers.fixture(recipient_username=reference)
        body = values['csv'] + '\n' if missing_units else 'unsupported,columns\n1,2'
        source = add_evidence(actor, case.pk, 'financial_input', body, 'synthetic:design-batch-intake', rev(case))
        context = {'entity': old_source.entity, 'period': old_source.batch.rows[0]['period'],
                   'currency': old_source.batch.rows[0]['currency'], 'accounting_basis': old_source.accounting_basis,
                   'extracted_at': old_source.extracted_at, 'completeness': old_source.completeness,
                   'control_total': old_source.control_total, 'source_evidence_id': old_source.evidence_id}
        result = factory_accounting_intake.submit(actor, case.pk, reference, source.pk, context, title, rev(case))
        expected_status = 'source_units_needed' if missing_units else 'quarantined'
        if result['status'] != expected_status:
            raise RuntimeError('Sample trial balance did not reach its intended intake state.')
    else:
        receipt = case.audit.get(actor=actor, action=factory_accounting_intake.RECEIPT, data__key=reference)
        result = factory_accounting_intake.latest(receipt)
    return {'case': str(case.pk), 'intake_receipt': result['receipt'],
            'path': f"{reverse('factory_create')}?definition=finance-accounts/v1&case={case.pk}",
            'existing_work_preserved': not created}


@transaction.atomic
def prepare_hr_payroll_correction(actor):
    from apps.finance import payroll
    from apps.finance.payroll_models import PayrollHRFollowup
    from tests.payroll_helpers import approve, combined, fixture

    case, created = Case.objects.get_or_create(tenant=TENANT, title='SAMPLE HR payroll correction walkthrough',
                                               kind='project', synthetic=True)
    request_source = 'synthetic:design-batch-payroll-correction'
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        users = get_user_model().objects
        sample = fixture(context=(actor, case),
                         principal=lambda role: users.create_user(username=f'batch-payroll-correction-{role}'))
        combination = combined(sample, 'walkthrough-combination')
        approve(sample, combination)
        matching = payroll.match(sample['preparer'], case.pk, combination.pk, sample['hr'].pk,
                                 'walkthrough-matching', rev(case))
        proof = add_evidence(actor, case.pk, 'hr_correction_request', 'Synthetic request to check the BU assignment.', request_source)
        link = payroll.hr_correction(sample['preparer'], case.pk, matching.pk, 'walkthrough-hr-correction', proof.pk, rev(case))
        add_evidence(actor, case.pk, 'hr_correction_response', 'Synthetic HR check of the exact correction request.',
                     'synthetic:design-batch-payroll-decision-proof')
    else:
        link = PayrollHRFollowup.objects.get(run__request__case=case, record__evidence__source=request_source)
    return {'case': str(case.pk), 'correction': link.pk, 'finance_preparer': link.actor_id,
            'path': reverse('design_hr_payroll_correction', args=[case.pk, link.pk]),
            'existing_work_preserved': not created}


@transaction.atomic
def prepare_unreadable_invoice():
    users = get_user_model().objects
    username = 'batch-isolated-invoice-owner'
    case, created = Case.objects.get_or_create(tenant=TENANT, title='SAMPLE separate Finance workspace',
                                               kind='project', synthetic=True)
    if created:
        owner = users.create_user(username)
        Grant.objects.bulk_create([Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        work = prepare_invoice_release(owner, case)
    else:
        work = FactoryWork.objects.get(case=case, actor__username=username, definition='pmo-finance/v1')
    return {'case': str(case.pk), 'work': work.pk, 'path': reverse('factory_detail', args=[work.pk]),
            'existing_work_preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_COMPOSED_WALKTHROUGH')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('Exact Railway acceptance environment and explicit fixture guard required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    from tests.railway_commercial_client_seed import prepare_rework

    sessions = {key: lambda key=key: prepare_project(actor, key) for key in PREPARATION}
    sessions.update({key: lambda key=key: prepare_project(actor, key) for key in PROGRESS_PREPARATION})
    sessions.update({key: lambda key=key: prepare_invoice_decision_variant(actor, key)
                     for key in INVOICE_DECISION_PREPARATION})
    sessions.update({key: lambda key=key: prepare_independent_finance_review(actor, key)
                     for key in INDEPENDENT_FINANCE_PREPARATION})
    sessions.update({key: lambda key=key: prepare_short_payment(actor, key) for key in SHORT_PAYMENT_PREPARATION})
    sessions['rework'] = prepare_rework
    sessions['units'] = lambda: prepare_accounting_intake(actor, missing_units=True)
    sessions['quarantined'] = lambda: prepare_accounting_intake(actor, missing_units=False)
    sessions['hr_payroll_correction'] = lambda: prepare_hr_payroll_correction(actor)
    sessions['unreadable_invoice'] = prepare_unreadable_invoice
    failed = False
    for key, prepare in sessions.items():
        try:
            result = prepare()
        except Exception as exc:
            failed = True
            print(f'PSL_BATCH_FIXTURE_ERROR={key}: {type(exc).__name__}: {str(exc)[:240]}', flush=True)
        else:
            if key == 'rework':
                result['path'] = reverse('commercial_client_response', args=[result['case']])
            print('PSL_BATCH_FIXTURE=' + json.dumps({'journey': key, **result}), flush=True)
    if failed:
        raise RuntimeError('A sample preparation failed. Successful cases remain available.')
