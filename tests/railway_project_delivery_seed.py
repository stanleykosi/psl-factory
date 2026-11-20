"""Add isolated Project samples that stop before the browser's human decisions."""

import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.pmo.gates import register_candidate
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import COMPONENT, draft as draft_roles
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_delivery
from apps.workflows.models import FactoryWork
from tests.helpers import prepared, rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_delivery import DeliveryFixture


TENANT = 'design-project-delivery-review-walkthrough'
CASES = {
    'planning': 'SAMPLE release waiting for an independent Planning reviewer',
    'glpi': 'SAMPLE readiness waiting for a distinct external approval',
}
REVIEWER_GRANTS = ('case.read', 'factory.read', 'delivery.read', 'delivery.planning_decide',
                   'policy.read', 'policy.configure', 'policy.activate')
RELEASE_REFERENCE = 'SAMPLE-GLPI-CEO-PENDING'
NOMINATION_SOURCE = 'synthetic:project-delivery-planning-nomination'


def grant_case(actor, case, actions):
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(actions)])


def start_release(entry, scenario):
    profile = json.loads(Path('fixtures/factory-delivery.json').read_text())
    profile.pop('classification')
    configuration = draft_operator_policy(entry.actor, entry.case.pk, 'OPS.factory_delivery_execution', profile,
                                           entry.e['policy_decision'].pk, timezone.now())
    transition(entry.actor, configuration.pk, 'validated')
    transition(entry.actor, configuration.pk, 'active')
    work = factory_delivery.start(entry.actor, entry.case.pk, f'SAMPLE-PROJECT-DELIVERY-{scenario.upper()}',
                                  entry.d.pk, CASES[scenario], rev(entry.case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    return work


def prepare_planning(case, reviewer):
    maker = get_user_model().objects.create_user('sample-project-delivery-planning-maker')
    grant_case(maker, case, ACTIONS)
    grant_case(reviewer, case, REVIEWER_GRANTS)

    entry = DeliveryFixture()
    entry.actor, entry.case = maker, case
    entry.e = prepared(maker, case)
    entry.candidate = register_candidate(maker, case.pk, 'sample-delivery-build', entry.e['requirements'].pk, rev(case))
    entry.d = delivery.open_dossier(maker, case.pk, entry.candidate.pk, entry.e['plan'].pk,
                                    'Fictional Planning scope for this candidate, without a signed agreement.', rev(case))
    for kind in delivery.PLANNING:
        payload = {'requires_ui': False, 'client_signoff_required': False} if kind == 'ui_applicability' else {}
        entry.source(kind, payload)

    standing = [role for role in reference_values(active_component(COMPONENT, case)) if role['role'] != 'PMO Lead']
    proof = add_evidence(maker, case.pk, 'policy_decision',
                         'Fictional preflight decision. The sample has no PMO Lead yet and can retain Planning evidence.',
                         'synthetic:project-delivery-empty-planning-owner')
    empty = draft_roles(maker, case.pk, standing, proof.pk, timezone.now())
    transition(maker, empty.pk, 'validated')
    transition(maker, empty.pk, 'active')

    nomination = add_evidence(maker, case.pk, 'policy_decision',
                               'Fictional nomination of the independent sample reviewer for this project only.',
                               NOMINATION_SOURCE)
    draft_roles(maker, case.pk, [*standing, {'role': 'PMO Lead', 'user_id': reviewer.pk}], nomination.pk, timezone.now())
    return start_release(entry, 'planning')


def prepare_glpi(case, actor):
    grant_case(actor, case, ACTIONS)
    entry = DeliveryFixture()
    entry.setup_delivery(context=(actor, case))
    entry.plan()
    entry.gates(delivery.UPSTREAM_GATES)
    delivery.record_release_request(actor, case.pk, entry.d.pk, RELEASE_REFERENCE, entry.e['requirements'].pk,
                                    'Recorded fictional external deployment request. No deployment is authorized.', rev(case))
    entry.gates([gate for gate in delivery.GLPI_GATES if gate != 'glpi_ceo'], RELEASE_REFERENCE)
    return start_release(entry, 'glpi')


@transaction.atomic
def prepare(actor, scenario):
    case, created = Case.objects.get_or_create(tenant=TENANT, kind='project', synthetic=True, title=CASES[scenario])
    if created:
        work = (prepare_planning if scenario == 'planning' else prepare_glpi)(case, actor)
    else:
        work = FactoryWork.objects.get(case=case, definition=factory_delivery.DEFINITION,
                                       key=f'SAMPLE-PROJECT-DELIVERY-{scenario.upper()}')
    dossier = delivery.dossier_for(case, work.request['dossier'], current=False)
    result = {'scenario': scenario, 'case': str(case.pk), 'work': work.pk, 'dossier': dossier.pk,
              'candidate': dossier.candidate_id, 'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
              'case_policy_path': reverse('policy', args=[case.pk]), 'delivery_path': reverse('delivery', args=[case.pk]),
              'existing_work_preserved': not created}
    if scenario == 'planning':
        nomination = case.evidence.get(source=NOMINATION_SOURCE)
        result['role_draft'] = Configuration.objects.get(case=case, component=COMPONENT,
            envelope__human_decision_ref=f'evidence:{nomination.pk}').pk
        result['planning_evidence'] = dossier.evidence_id
    else:
        result['release_reference'] = RELEASE_REFERENCE
        result['gate_evidence'] = dossier.candidate.requirements_id
    return result


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_PROJECT_DELIVERY_FIXTURES')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance environment and Project fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('An explicitly configured Railway preview sample database is required.')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    for scenario in CASES:
        print('PSL_PROJECT_DELIVERY_FIXTURE=' + json.dumps(prepare(actor, scenario)), flush=True)
