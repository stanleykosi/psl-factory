"""Guarded started-work handover before whole-account departure."""
import json
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents import controlled
from apps.documents.models import ControlledReview, Publication
from apps.finance.models import Handoff, InvoiceIssue, InvoiceJob
from apps.identity import intake
from apps.identity.actions import ACTIONS
from apps.identity.intake_models import CaseIntake
from apps.identity.models import Grant, StaffAccountChange, TenantAuthority
from apps.pmo.services import complete_milestone
from apps.policy.factory_recovery_validators import COMPONENT, METHOD
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from apps.workflows import factory, factory_execution
from apps.workflows.models import FactoryAttempt, FactoryWork
from apps.workflows.services import run_once as run_handoff
from tests.billing_helpers import coverage, policy, stage_policy
from tests.helpers import rev, signed
from tests.railway_independent_commercial_seed import PROJECT
from tests.settlement_helpers import configured
from tests.signature_helpers import reaffirm_for


GUARD = 'PSL_STAFF_WORK_DEPARTURE_FIXTURE'
TENANT = 'design-staff-worker-departure'
TITLE = 'SAMPLE Harbor Clinics work handover before departure'
CASE_KEY = 'sample-staff-work-departure'
TRIAL = 'psl-agent-trial'
DEPARTING = 'sample-original-recording-worker'
SUCCESSOR = 'sample-continuing-recording-worker'
KEEPER = 'sample-continued-signed-source-owner'
BOOTSTRAP = 'sample-work-departure-bootstrap'
WORK_REFERENCE = 'SAMPLE-STAFF-WORK-HANDOVER'
PREPARED = 'sample.started_work_departure_prepared'
FOLLOW_UP = 'sample.departure_successor_follow_up_observed'
DEFINITION = 'pmo-finance/v1'
COMMON = {'case.read', 'factory.read', 'factory.execute', 'finance.read', 'agent.extract'}
TARGET_ACTIONS = COMMON | {'factory.start', 'document.read', 'document.review_controlled'}
SUCCESSOR_ACTIONS = COMMON | {'finance.billing.prepare', 'finance.invoice.draft'}


def install(actor, case, component, value, proof):
    configuration = draft_operator_policy(actor, case.pk, component, value, proof.pk, timezone.now())
    transition(actor, configuration.pk, 'validated')
    transition(actor, configuration.pk, 'active')
    return configuration


def provision(trial):
    root = get_user_model().objects.create_superuser(BOOTSTRAP)
    value = {'format': 'psl.tenant-access/v3', 'create_cases': True, 'manage_access': True, 'kinds': ['project'],
             'allowed_actions': list(dict.fromkeys(ACTIONS)), 'initial_actions': list(dict.fromkeys(ACTIONS)),
             'classification': 'synthetic', 'staff_lifecycle': {'invite_minutes': 60, 'allow_invite': True,
                 'allow_deactivation': True, 'allow_roster': True, 'allow_account_deactivation': True}}
    authority = intake.provision(root, trial, TENANT, value, timezone.now() + timedelta(days=3), True,
                                'Fictional whole-account departure in this sample workspace only.')
    case = intake.create_case(trial, TENANT, CASE_KEY, TITLE, 'project')
    root.is_active = False
    root.save(update_fields=['is_active'])
    return case, authority


def populate(trial, case, authority):
    users = get_user_model().objects
    target = users.create_user(DEPARTING, first_name='SAMPLE Original Worker')
    successor = users.create_user(SUCCESSOR, first_name='SAMPLE Continuing Worker')
    keeper = users.create_user(KEEPER, first_name='SAMPLE Signed Source Owner')
    for user, actions in ((target, TARGET_ACTIONS), (successor, SUCCESSOR_ACTIONS)):
        for action in sorted(actions):
            intake.change_access(trial, case.pk, user.pk, action, True, 'Exact fictional sample workspace access')
    Grant.objects.bulk_create(Grant(case=case, user=keeper, action=action) for action in dict.fromkeys(ACTIONS))
    proof = signed(keeper, case)
    configured(keeper, case)
    roles = [{'role': role, 'user_id': keeper.pk} for role in ('PM', 'Head of PMO', 'CEO', 'PMO Lead', 'Finance')]
    roles += [{'role': 'Finance', 'user_id': user.pk} for user in (target, successor)]
    roles += [{'role': 'PMO Lead', 'user_id': target.pk}, {'role': 'Head of PMO', 'user_id': trial.pk}]
    assignment = draft_roles(keeper, case.pk, roles, proof['policy_decision'].pk, timezone.now())
    transition(keeper, assignment.pk, 'validated')
    transition(keeper, assignment.pk, 'active')
    reaffirm_for(keeper, case)

    milestone = complete_milestone(keeper, case.pk, 'SAMPLE recorded handover completion', proof['completion'].pk, rev(case))
    if not run_handoff(case_id=case.pk):
        raise RuntimeError('The exact synthetic PMO handoff must be available.')
    handoff = Handoff.objects.get(case=case, milestone=milestone)
    scope = coverage(keeper, case, reference='sample-staff-handoff-stage', amount_basis='gross_including_tax')
    stage_policy(keeper, case, scope, proof['signature'])
    policy(keeper, case, 'D12.stage_terms', [{'coverage_id': scope.pk, 'stage': 'completion', 'amount': '42.00',
        'due_date': (timezone.localdate() + timedelta(days=7)).isoformat()}])
    policy(keeper, case, 'D12.completion_billing_predicate_ref', {'coverage_id': scope.pk, 'stage': 'completion',
                                                                 'milestone_name': milestone.name})

    template = controlled.register_template(keeper, case.pk, 'SAMPLE internal progress record',
        {'document_type': 'status_report', 'required_fields': ['status'], 'audience_fields': {'internal': ['status']}},
        proof['policy_decision'].pk, rev(case))
    report = controlled.create_version(keeper, case.pk, template.pk, 'SAMPLE earlier progress decision', 'internal',
        {'status': {'text': 'The earlier project review was recorded.', 'evidence_ids': [proof['completion'].pk]}}, rev(case))
    controlled.request_review(keeper, case.pk, report.pk, rev(case))
    earlier_review = controlled.review_version(target, case.pk, report.pk, 'approve',
                                                'SAMPLE prior decision retained under the original worker.', rev(case))

    handover = add_evidence(trial, case.pk, 'policy_decision', 'Fictional same Finance responsibility handover.',
                            'synthetic:started-work-departure-review')
    execution = install(keeper, case, 'OPS.factory_execution', {'definition': DEFINITION, 'max_steps': 40,
        'max_tokens': 20000, 'tokens_per_call': 100, 'max_children': 100, 'max_depth': 1, 'lease_seconds': 120,
        'max_age_seconds': 86400, 'required_evidence_kinds': ['completion'], 'information_resolver_id': None,
        'executor_id': successor.pk, 'review_role': 'Finance', 'provider': 'synthetic_factory_v1', 'enabled': True}, handover)
    work = factory.start(target, case.pk, 'sample-started-finance-work-departure', scope.pk, handoff.pk,
                         WORK_REFERENCE, rev(case))
    if not factory.run_once(work.pk):
        raise RuntimeError('Original worker must complete the real initial investigation before handover.')
    work.refresh_from_db()
    original = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT04', phase='observed')
    if work.invoice_id or work.preparation_id or work.lease_until:
        raise RuntimeError('Stop before the replacement’s accounting work or any invoice effect.')
    now = timezone.now()
    recovery = install(trial, case, COMPONENT, {'rules': [{'definition': DEFINITION, 'method': METHOD,
        'principal_id': successor.pk, 'reviewer_id': trial.pk, 'review_role': 'Head of PMO',
        'independent_of_worker': True, 'valid_from': now.isoformat(), 'valid_until': (now + timedelta(days=2)).isoformat()}]}, handover)
    return event(trial, case, PREPARED, person=target.pk, successor=successor.pk, keeper=keeper.pk,
        trial=trial.pk, authority=authority.pk, work=work.pk, handoff=handoff.pk, coverage=scope.pk,
        older_version=report.pk, older_review=earlier_review.pk, original_attempt=original.pk,
        spent=work.budget_used, recovery_config=recovery.pk, proof=handover.pk, execution=execution.pk)


def read_sample(trial):
    intake_row = CaseIntake.objects.select_related('case').get(tenant=TENANT, reference=CASE_KEY, actor=trial)
    case = intake_row.case
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve unrelated workspaces and accounts.')
    marker = Audit.objects.get(case=case, action=PREPARED, actor=trial)
    data = marker.data
    people = get_user_model().objects
    for key, name in (('person', DEPARTING), ('successor', SUCCESSOR), ('keeper', KEEPER)):
        user = people.get(pk=data[key], username=name, is_staff=False, is_superuser=False)
        if user.has_usable_password():
            raise RuntimeError('This specimen can only use its original noninteractive sample users.')
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor_id=data['person'], definition=DEFINITION)
    ControlledReview.objects.get(pk=data['older_review'], version_id=data['older_version'],
                                 version__document__case=case, actor_id=data['person'], verdict='approve')
    FactoryAttempt.objects.get(pk=data['original_attempt'], activity__work=work, activity__kind='ACT04', phase='observed')
    if work.budget_used < data['spent'] or InvoiceJob.objects.filter(invoice__case=case).exists() or Publication.objects.filter(
            version__document__case=case).exists():
        raise RuntimeError('Preserve the original investigation and all separate invoice and publication effects.')
    return case, work, data


@transaction.atomic
def prepare():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    exists = CaseIntake.objects.filter(tenant=TENANT, reference=CASE_KEY).exists()
    if not exists:
        if Case.objects.filter(tenant=TENANT).exists() or TenantAuthority.objects.filter(tenant=TENANT).exists():
            raise RuntimeError('The exact guarded synthetic workspace is required for this specimen.')
        case, authority = provision(trial)
        populate(trial, case, authority)
    case, work, data = read_sample(trial)
    return {**data, 'case': str(case.pk), 'preserved': exists,
            'departure': reverse('staff_account_departure', args=[data['person']]),
            'worker_review': reverse('factory_execution_review', args=[work.pk]),
            'work_path': reverse('factory_detail', args=[work.pk]),
            'earlier_review': reverse('design_document_review', args=[case.pk, data['older_version']])}


def follow_up():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    case, work, data = read_sample(trial)
    departure = StaffAccountChange.objects.get(user_id=data['person'], kind='deactivated', actor=trial)
    worker = factory_execution.available_actor(work)
    if (work.actor.is_active or not worker or worker.pk != data['successor'] or work.execution_binding_id is None
            or work.execution_binding.reviewer_id != trial.pk or work.execution_binding.evidence_id != data['proof']):
        raise RuntimeError('Record the exact reviewed replacement and whole sample account departure first.')
    if not FactoryAttempt.objects.filter(activity__work=work, activity__kind='ACT06', phase='observed').exists():
        if not factory.run_once(work.pk):
            raise RuntimeError('The replacement worker must reconcile the exact PMO handoff.')
    if not work.invoice_id and not factory.run_once(work.pk):
        raise RuntimeError('The replacement worker must prepare a draft from the original billing scope.')
    work.refresh_from_db()
    prepared = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT08', phase='observed')
    if (not work.preparation_id or work.preparation.actor_id != worker.pk or work.preparation.handoff_id != data['handoff']
            or not work.invoice_id or work.invoice.actor_id != worker.pk or prepared.result['invoice'] != work.invoice_id
            or InvoiceIssue.objects.filter(invoice__case=case).exists() or InvoiceJob.objects.filter(invoice__case=case).exists()):
        raise RuntimeError('Retain the exact successor draft and stop before Finance approval or invoice effects.')
    return {'work': work.pk, 'departure': departure.pk, 'binding': work.execution_binding_id,
            'preparation': work.preparation_id, 'draft': work.invoice_id, 'attempt': prepared.pk, 'worker': worker.pk}


def run(action='prepare'):
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv(GUARD)) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and staff work fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicit preview database before preparing staff work.')
    commands = {'prepare': prepare, 'follow-up': follow_up}
    if action not in commands:
        raise RuntimeError('Choose preparation or follow-up of this exact fixture.')
    print(GUARD + '=' + json.dumps(commands[action]()), flush=True)
