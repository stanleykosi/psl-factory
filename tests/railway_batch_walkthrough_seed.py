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
from apps.policy.services import transition
from apps.workflows import factory, factory_accounting_intake, factory_change, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import test_commercial_changes, test_delivery, test_factory_hypercare, test_project_archive_files, test_standard_changes
from tests.helpers import rev
from tests.signature_helpers import reaffirm_for


PREVIEW_PROJECT = 'f957481b-c6f7-43af-bc66-449a330a9d53'
TENANT = 'design-composed-delivery-walkthrough'
PREPARATION = {
    'stability': ('delivery-hypercare/v1', 'SAMPLE release stability walkthrough'),
    'archive': ('delivery-archive/v1', 'SAMPLE file archive walkthrough'),
    'standard': ('pmo-change/v1', 'SAMPLE standard change walkthrough'),
    'normal_change_refusal': ('pmo-change/v1', 'SAMPLE Normal Change refusal walkthrough'),
    'emergency': ('pmo-emergency/v1', 'SAMPLE emergency walkthrough'),
    'emergency_authorized': ('pmo-emergency/v1', 'SAMPLE emergency authorized outcome walkthrough'),
    'emergency_refused': ('pmo-emergency/v1', 'SAMPLE emergency refusal walkthrough'),
    'escalation': ('pmo-escalation/v1', 'SAMPLE escalation walkthrough'),
    'invoice_release': ('pmo-finance/v1', 'SAMPLE invoice release walkthrough'),
    'leadership': ('pmo-leadership-report/v1', 'SAMPLE leadership report walkthrough'),
    'tuesday': ('pmo-leadership-report/v1', 'SAMPLE Tuesday report walkthrough'),
    'accounts': ('finance-accounts/v1', 'SAMPLE accounts close walkthrough'),
    'accounts_continuation': ('finance-accounts/v1', 'SAMPLE accounts continuation walkthrough'),
    'assets': ('finance-ppe/v1', 'SAMPLE fixed asset walkthrough'),
    'schedules': ('finance-schedules/v1', 'SAMPLE schedules walkthrough'),
    'forecast': ('finance-forecast/v1', 'SAMPLE cash forecast walkthrough'),
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

    with patch.object(test_commercial_changes, 'fixture', side_effect=lambda *, existing:
                      test_commercial_changes.fixture(existing=existing, context=(actor, case))):
        entry = test_factory_change.FactoryChangeTests()
        entry.setUp()
    entry.assessments(cost=False, timeline=True, client=True)
    artifact(actor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
             {'rules': [{'role': 'Client', 'actions': ['approve', 'reject']}]}, entry.e['policy_decision'])
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


def prepare_leadership(actor, case, *, tuesday=False):
    from tests import document_helpers, test_factory_leadership

    with patch.object(document_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_leadership.FactoryLeadershipTests()
        entry.setUp()
    if tuesday:
        entry.tuesday()
    return entry.start_work()


def prepare_accounts(actor, case):
    from tests import factory_accounting_helpers, finance_analysis_helpers as source

    with patch.object(source, 'setup_case', return_value=(actor, case)):
        _, _, evidence, _, _, ledger, template, _ = source.fixture()
    return factory_accounting_helpers.configured(actor, case, evidence, ledger, template, source.METRICS)['work']


def prepare_assets(actor, case):
    from tests import finance_analysis_helpers, test_factory_ppe

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_ppe.FactoryPPETests()
        entry.setUp()
    return entry.start()


def prepare_schedules(actor, case):
    from tests import finance_analysis_helpers, test_factory_schedules

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_schedules.FactorySchedulesTests()
        entry.setUp()
    return entry.start()


def prepare_forecast(actor, case):
    from tests import forecast_helpers, test_factory_forecast

    with patch.object(forecast_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_forecast.ForecastFactoryTests()
        entry.setUp()
    return entry.start()


@transaction.atomic
def prepare_project(actor, key):
    definition, title = PREPARATION[key]
    case, created = Case.objects.get_or_create(tenant=TENANT, title=title, kind='project', synthetic=True)
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        prepare = {'stability': prepare_stability, 'archive': prepare_archive, 'standard': prepare_standard,
                   'normal_change_refusal': prepare_normal_change_refusal,
                   'emergency': prepare_emergency,
                   'emergency_authorized': partial(prepare_emergency, verified_sources=True),
                   'emergency_refused': partial(prepare_emergency, refusal=True), 'escalation': prepare_escalation,
                   'invoice_release': prepare_invoice_release,
                   'leadership': prepare_leadership, 'tuesday': prepare_leadership,
                   'accounts': prepare_accounts, 'accounts_continuation': prepare_accounts, 'assets': prepare_assets,
                   'schedules': prepare_schedules, 'forecast': prepare_forecast}[key]
        users = get_user_model().objects
        create_user = users.create_user
        with patch.object(users, 'create_user', side_effect=lambda username, **values:
                          create_user(username=f'batch-{key}-{username}', **values)):
            work = prepare(actor, case, tuesday=True) if key == 'tuesday' else prepare(actor, case)
        pause_existing_background(actor, work)
    else:
        work = FactoryWork.objects.get(case=case, actor=actor, definition=definition)
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
