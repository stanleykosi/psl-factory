"""Prepare a synthetic go-live with Hypercare criteria still awaiting review."""

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import resolve, transition
from apps.workflows import factory, factory_hypercare
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_delivery import CRITERIA, DeliveryFixture


TENANT = 'design-hypercare-stability-walkthrough'
TITLE = 'SAMPLE Hypercare stability criteria and corrected observations'
KEY = 'SAMPLE-HYPERCARE-STABILITY-WALKTHROUGH'
PRIMARY_CONTINUE = 'primary-continue'
PRIMARY_CASE_ID = uuid5(NAMESPACE_URL, 'psl-factory:design-acceptance:hypercare:primary-continue')
COMPONENT = 'D11.hypercare_criteria_ref'
CRITERIA_PROOF = 'synthetic:hypercare-stability-walkthrough-criteria'
INFRASTRUCTURE_PROOF = 'synthetic:hypercare-stability-walkthrough-infrastructure'
ENGINEERING_PROOFS = {
    'not_met': 'SAMPLE-HYPERCARE-ENGINEERING-ERRORS-2',
    'qualified': 'SAMPLE-HYPERCARE-ENGINEERING-ERRORS-0',
}
OPERATOR_ACTIONS = ('case.read', 'factory.read', 'factory.start', 'factory.execute', 'factory.manage',
                    'delivery.read', 'delivery.manage', 'delivery.source', 'delivery.verify', 'evidence.add',
                    'policy.read', 'policy.configure', 'policy.activate')


def grant_case(actor, case, actions):
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(actions)])


def create_sample(operator, case, key, actor_suffix):
    users = get_user_model().objects
    maker = users.create_user(f'sample-hypercare-release-maker{actor_suffix}')
    infrastructure = users.create_user(f'sample-hypercare-infrastructure-source{actor_suffix}')
    grant_case(maker, case, ACTIONS)
    grant_case(infrastructure, case, ('case.read', 'delivery.read', 'delivery.source', 'delivery.verify', 'evidence.add'))
    grant_case(operator, case, OPERATOR_ACTIONS)

    sample = DeliveryFixture()
    sample.setup_delivery(context=(maker, case))
    sample.accepted()
    infra_proof = add_evidence(infrastructure, case.pk, 'test_results',
                              'Fictional Infrastructure confirmation and 100 percent availability.', INFRASTRUCTURE_PROOF)
    infra = delivery.capture_source(infrastructure, case.pk, sample.d.pk, 'hypercare_infrastructure',
                                    'SAMPLE-HYPERCARE-INFRASTRUCTURE-100', infra_proof.pk,
                                    {'observed_at': timezone.now().isoformat(), 'confirmed': True,
                                     'metrics': {'availability': {'value': 100, 'unit': 'percent'}}}, rev(case))
    delivery.verify_source(infrastructure, case.pk, infra.pk, rev(case))
    for name, reference in ENGINEERING_PROOFS.items():
        value = 2 if name == 'not_met' else 0
        add_evidence(maker, case.pk, 'test_results', f'Fictional Engineering report of {value} errors.', reference)

    proof = add_evidence(maker, case.pk, 'policy_decision',
                         'Fictional nomination of the existing test stability criteria for this sample only.', CRITERIA_PROOF)
    draft_standard_policy(maker, case.pk, COMPONENT, CRITERIA, proof.pk, timezone.now())
    profile = json.loads(Path('fixtures/factory-hypercare.json').read_text())
    profile.pop('classification')
    configuration = draft_operator_policy(maker, case.pk, 'OPS.factory_hypercare_execution', profile,
                                           sample.e['policy_decision'].pk, timezone.now())
    transition(maker, configuration.pk, 'validated')
    transition(maker, configuration.pk, 'active')

    work = factory_hypercare.start(operator, case.pk, key, sample.d.pk, case.title, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if (work.status != 'configuration_needed' or resolve(COMPONENT, case).status == 'ACTIVE'
            or sample.d.records.filter(kind='hypercare').exists()
            or sample.d.sources.filter(kind='hypercare_engineering').exists()):
        raise RuntimeError('The Hypercare fixture must stop before criteria activation and Engineering evidence.')
    return work


@transaction.atomic
def prepare(operator, *, scenario='initial'):
    if not operator.is_active or operator.is_staff or operator.is_superuser:
        raise RuntimeError('A current ordinary acceptance operator is required.')
    if scenario not in ('initial', PRIMARY_CONTINUE):
        raise RuntimeError('Choose a registered synthetic Hypercare walkthrough.')
    suffix = f'-{PRIMARY_CONTINUE}' if scenario == PRIMARY_CONTINUE else ''
    title = 'SAMPLE Hypercare primary continuation after reviewed observations' if suffix else TITLE
    key = f'{KEY}{suffix.upper()}'
    identity = {'pk': PRIMARY_CASE_ID} if scenario == PRIMARY_CONTINUE else {}
    case, created = Case.objects.get_or_create(tenant=f'{TENANT}{suffix}', kind='project', synthetic=True, title=title,
                                               **identity)
    work = (create_sample(operator, case, key, suffix) if created else FactoryWork.objects.get(
        case=case, actor=operator, definition=factory_hypercare.DEFINITION, key=key))
    dossier = delivery.dossier_for(case, work.request['dossier'], current=False)
    release = dossier.records.get(kind='release_outcome')
    accepted = dossier.records.get(kind='go_live')
    infra = dossier.sources.get(kind='hypercare_infrastructure', evidence__source=INFRASTRUCTURE_PROOF)
    criteria_proof = case.evidence.get(kind='policy_decision', source=CRITERIA_PROOF)
    criteria = Configuration.objects.get(case=case, component=COMPONENT,
                                         envelope__human_decision_ref=f'evidence:{criteria_proof.pk}')
    proofs = {name: {'id': case.evidence.get(kind='test_results', source=source).pk, 'ref': source}
              for name, source in ENGINEERING_PROOFS.items()}
    return {'work': work.pk, 'case': str(case.pk), 'dossier': dossier.pk, 'candidate': dossier.candidate_id,
            'release': release.pk, 'released_at': release.data['released_at'], 'acceptance': accepted.pk,
            'receipt': accepted.data['receipt_id'], 'infrastructure_source': infra.pk,
            'infrastructure_recorder': infra.actor_id, 'criteria_draft': criteria.pk, 'criteria_proof': criteria_proof.pk,
            'engineering_proofs': proofs, 'path': reverse('factory_detail', args=[work.pk]),
            'case_policy_path': reverse('policy', args=[case.pk]), 'existing_work_preserved': not created}


def run():
    opt_in = os.getenv('PSL_HYPERCARE_WALKTHROUGH_FIXTURE')
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID')) != ('design-acceptance', PREVIEW_PROJECT) or (
            opt_in not in ('1', PRIMARY_CONTINUE)):
        raise RuntimeError('Use only the guarded Railway design acceptance environment.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('An explicitly configured Railway preview database is required.')
    operator = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    scenario = PRIMARY_CONTINUE if opt_in == PRIMARY_CONTINUE else 'initial'
    print('PSL_HYPERCARE_WALKTHROUGH_FIXTURE=' + json.dumps(prepare(operator, scenario=scenario)), flush=True)
