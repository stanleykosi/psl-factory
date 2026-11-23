"""Prepare the first group disclosure for two existing synthetic browser actors."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.controlled import register_template
from apps.documents.models import Publication
from apps.finance import forecast, group_forecast
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, reference_values, register_reference, transition
from apps.workflows import factory, factory_forecast as flow
from apps.workflows.factory_forecast_sources import PROTOCOL
from apps.workflows.models import FactoryWork
from tests import forecast_helpers as samples
from tests.billing_helpers import evidence, policy
from tests.document_helpers import artifact
from tests.helpers import activate, rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_finance_schedule_seed import fixture_reviewer


TENANT = 'design-admitted-group-forecast'
MARKER = 'sample.group_forecast_initial_review'
MAKER_ACTIONS = ('case.read', 'factory.read', 'factory.start', 'factory.execute', 'factory.manage', 'finance.read',
                 'finance.forecast.capture', 'finance.forecast.calculate', 'finance.publish', 'document.draft',
                 'evidence.add', 'policy.configure', 'policy.read')
REVIEWER_ACTIONS = ('case.read', 'factory.read', 'factory.execute', 'finance.read',
                    'finance.forecast.review', 'finance.publish', 'document.review_controlled', 'document.publish',
                    'evidence.add', 'policy.configure', 'policy.activate', 'policy.read')


def first_disclosure(case, maker, reviewer, suffix, run, owner, decision):
    reader = get_user_model().objects.create_user(username=f'group-forecast-recipient-{suffix}')
    Grant.objects.create(user=reader, case=case, action='document.receive:group')
    fields = ['executive_summary', 'financial_metrics', 'bu_totals']
    template = register_template(owner, case.pk, 'Synthetic Plan group forecast',
        {'document_type': 'finance_group_report', 'required_fields': fields, 'audience_fields': {'group': fields},
         'internal_review_required': True}, decision.pk, rev(case))
    artifact(owner, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
        {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, decision)
    destination = register_reference(owner, case.pk, 'synthetic:group-forecast-recipient',
        'schema:psl/document-recipient/v1', {'audience': 'group', 'user_id': reader.pk}, decision.pk)
    activate(owner, case, 'D11.recipient_grant_refs', [destination.ref], decision)
    as_of = run.scenario.payload['as_of']
    expected = {'implementation': group_forecast.IMPLEMENTATION,
        'metadata': {'currency': 'NGN', 'basis': 'gross_cash', 'as_of': as_of},
        'rows': [{'kind': 'other_inflow', 'residual': '50', 'expected_on': as_of}],
        'scope': 'selected_assumptions_only_no_group_balances', 'execution_authorized': False}
    base = evidence(reviewer, case, 'forecast_group_oracle', json.dumps(expected, sort_keys=True))
    # Independently specified outputs. The new allowed fields are a real narrowing
    # from the earlier artifact, with no whole-workspace or extra recipient fixture.
    corrected = evidence(reviewer, case, 'forecast_group_oracle', json.dumps(
        dict(expected, rows=[{'kind': 'other_inflow', 'residual': '50'}]), sort_keys=True))
    projection = reference_values(active_component('D10.audience_projection_rules', case))[0]
    projection = dict(projection, group={'implementation': 'native_selected_items_v1', 'run_id': run.pk,
        'run_hash': run.sha256, 'rows': ['receipt-1'], 'fields': ['kind', 'residual', 'expected_on'],
        'metadata': ['currency', 'basis', 'as_of'], 'recipient_ids': [reader.pk], 'reviewer_roles': ['Finance'],
        'publisher_roles': ['Finance'], 'allow_preparer_review': False, 'oracle_evidence_id': base.pk})
    configuration = policy(owner, case, 'D10.audience_projection_rules', projection)
    profile = json.loads(Path('fixtures/factory-forecast.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    profile.update(preparer_id=maker.pk, executor_id=reviewer.pk)
    execution = draft_operator_policy(owner, case.pk, 'OPS.factory_forecast_execution', profile, decision.pk, timezone.now())
    transition(owner, execution.pk, 'validated')
    transition(owner, execution.pk, 'active')
    return template, reader, configuration, base, corrected


def seed(case, maker, reviewer, suffix, identity):
    owner = get_user_model().objects.create_user(username=f'group-forecast-setup-{suffix}')
    Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for actor, actions in (
        (owner, dict.fromkeys(ACTIONS)), (maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)) for action in actions])
    samples.configure(owner, case)
    decision = evidence(owner, case, 'policy_decision', 'Fictional group disclosure selection, reviewer and recipient.')
    assignments = [register_reference(owner, case.pk, f'synthetic:group-forecast-finance-{actor.pk}',
        'schema:psl/role-assignment/v1', {'role': 'Finance', 'user_id': actor.pk}, decision.pk).ref
        for actor in (maker, reviewer)]
    activate(owner, case, 'D05.role_principal_assignments', assignments, decision)
    matrix = reference_values(active_component('D05.decision_action_matrix', case))[0]
    rules = [dict(rule, allow_preparer_review=False) for rule in matrix['finance']]
    policy(owner, case, 'D05.decision_action_matrix', dict(matrix, finance=rules,
        rules=[*matrix.get('rules', []), {'role': 'Finance', 'actions': ['return', 'reject']}]))
    scenario = samples.scenario(maker, case, reference=f'GROUP-FORECAST-{suffix}')
    run = forecast.prepare(maker, case.pk, scenario.pk, rev(case))
    samples.review(reviewer, case, run)
    template, reader, config, base, corrected = first_disclosure(case, maker, reviewer, suffix, run, owner, decision)
    p = scenario.payload
    source = {'protocol': PROTOCOL, 'scenario_id': scenario.pk, 'as_of': p['as_of'], 'months': p['months'],
        'source_ids': sorted({scenario.evidence_id, *(row['evidence_id'] for row in p['items'] + p['openings'])}),
        'template_id': template.pk, 'audience': 'group'}
    work = flow.start(maker, case.pk, f'GROUP-FORECAST-{suffix}', source, case.title, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    binding = flow.document(work)
    if (not binding or binding.version.created_by_id != maker.pk or flow.report(work, reviewer)['stage'] != 'group_review'
            or binding.version.reviews.exists() or Publication.objects.filter(factory_work=work).exists()):
        raise RuntimeError('The first exact group disclosure must await its independent browser decision.')
    return event(owner, case, MARKER, **identity, work=work.pk, run=run.pk, initial_version=binding.version_id,
                 configuration=config.pk, base_oracle=base.pk, corrected_oracle=corrected.pk, decision=decision.pk,
                 recipient=reader.pk, selection=source)


@transaction.atomic
def prepare(invitation_id, user_id):
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    suffix = str(invitation_id)
    title = f'SAMPLE independently reviewed group forecast {suffix}'
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, TENANT + '-' + suffix),
        defaults={'tenant': TENANT, 'title': title, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, title, 'project', True):
        raise RuntimeError('The separate synthetic group forecast workspace must match.')
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    marker = seed(case, maker, reviewer, suffix, identity) if created else Audit.objects.get(
        case=case, action=MARKER, actor__username=f'group-forecast-setup-{suffix}')
    if any(marker.data.get(key) != value for key, value in identity.items()):
        raise RuntimeError('The existing fixture belongs to a different exact admission or reviewer.')
    work = FactoryWork.objects.get(pk=marker.data['work'], case=case, definition=flow.DEFINITION, actor=maker)
    return {**marker.data, 'case': str(case.pk), 'preserved': not created,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
            'policy_path': reverse('policy', args=[case.pk]), 'work_path': reverse('factory_detail', args=[work.pk])}
