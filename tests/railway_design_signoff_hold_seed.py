"""Prepare one native Planning exit with an outstanding Design Lead sign-off."""

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery, planning
from apps.pmo.models import DeliveryRecord
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_delivery
from apps.workflows.models import FactoryWork
from tests import planning_helpers
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PROJECT
from tests.ui_artifact_helpers import target_payload


GUARD = 'PSL_DESIGN_SIGNOFF_HOLD_FIXTURE'
TENANT = 'design-planning-signoff-hold'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}/planning-exit')
TITLE = 'SAMPLE Harbor Clinics appointment screen plan'
REFERENCE = 'SAMPLE-PLANNING-DESIGN-SIGNOFF'
AUTHOR = 'sample-appointment-design-planning-source'
TRIAL = 'psl-agent-trial'
MARKER = 'sample.design_signoff_hold_prepared'
TRIAL_ACTIONS = ('case.read', 'delivery.read', 'factory.start', 'factory.read', 'factory.execute',
                 'evidence.add', 'policy.read', 'planning.read')


def populate(case, trial):
    author = get_user_model().objects.create_user(AUTHOR, first_name='SAMPLE Planning Lead')
    Grant.objects.bulk_create(Grant(case=case, user=user, action=action)
        for user, actions in ((author, dict.fromkeys(ACTIONS)), (trial, TRIAL_ACTIONS)) for action in actions)
    sample = planning_helpers.fixture(username=AUTHOR, context=(author, case))
    planning_helpers.observe(sample)
    packet = sample['packet']
    upstream = planning.prepare(author, case.pk, packet.pk)
    dossier = delivery.open_dossier(author, case.pk, sample['pair']['candidate_id'], sample['e']['plan'].pk,
        'Fictional appointment planning with reviewed requirements and Engineering estimate.', rev(case))
    scope = planning.bridge(author, case.pk, upstream.pk, dossier.pk)
    delivery.verify_source(author, case.pk, scope.pk, rev(case))
    for kind in delivery.PLANNING:
        if kind == 'scope_baseline':
            continue
        applicability = kind == 'ui_applicability'
        proof = add_evidence(author, case.pk, 'ui_applicability_statement' if applicability else 'plan',
            'Product/Design recorded an appointment booking UI and no separate client sign-off for this fictional case.'
            if applicability else f'Owned synthetic source for the current appointment plan and {kind}.',
            f'synthetic:appointment-design/{kind}')
        source = delivery.capture_source(author, case.pk, dossier.pk, kind, f'synthetic:appointment-design/{kind}',
            proof.pk, {'requires_ui': True, 'client_signoff_required': False} if applicability else {}, rev(case))
        delivery.verify_source(author, case.pk, source.pk, rev(case))

    design = add_evidence(author, case.pk, 'ui_design_artifact', 'Sample appointment booking view, revision v1.',
                          'synthetic:appointment-design/target-artifact')
    ownership = add_evidence(author, case.pk, 'ui_target_statement', 'Product/Design declares this exact design target.',
                             'synthetic:appointment-design/target-owner')
    target = delivery.capture_source(author, case.pk, dossier.pk, 'ui_target', 'synthetic:appointment-design/exact-target',
        ownership.pk, target_payload(design, 'v1', 'synthetic:appointment-design/view'), rev(case))
    delivery.verify_source(author, case.pk, target.pk, rev(case))

    profile = json.loads(Path('fixtures/factory-delivery.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    configuration = draft_operator_policy(author, case.pk, 'OPS.factory_delivery_execution', profile,
                                          sample['e']['policy_decision'].pk, timezone.now())
    transition(author, configuration.pk, 'validated')
    transition(author, configuration.pk, 'active')
    work = factory_delivery.start(trial, case.pk, REFERENCE, dossier.pk, REFERENCE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    panel = factory_delivery.projection(trial, work)
    hold = panel['design_signoff_hold']
    if (work.status != 'waiting' or work.policy_id != configuration.pk or panel['can_decide'] or not hold or not hold['estimate']
            or hold['requirements'].pk != sample['e']['requirements'].pk
            or hold['estimate'].pk != sample['e']['engineering_estimate'].pk or not hold['can_read_setup']
            or dossier.sources.filter(kind='ui_design').exists() or dossier.records.exists()):
        raise RuntimeError('Stop at the evidenced Design Lead sign-off hold with the original planning inputs intact.')
    return event(author, case, MARKER, work=work.pk, trial=trial.pk, dossier=dossier.pk, profile=configuration.pk,
        packet=packet.pk, upstream=upstream.pk, scope=scope.pk, target=target.pk, target_version='v1',
        requirements=hold['requirements'].pk, requirements_version=hold['requirements'].version,
        estimate=hold['estimate'].pk, estimate_version=hold['estimate'].version).data


@transaction.atomic
def prepare():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE,
                                                                     'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Only the exact synthetic UI design sign-off workspace may be used.')
    if created:
        data = populate(case, trial)
    else:
        data = Audit.objects.get(case=case, actor__username=AUTHOR, action=MARKER).data
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=trial, key=REFERENCE,
                                   definition=factory_delivery.DEFINITION)
    if data['trial'] != trial.pk or work.request['dossier'] != data['dossier']:
        raise RuntimeError('The choice must remain the exact prepared Trial work and dossier.')
    if DeliveryRecord.objects.filter(dossier_id=data['dossier'], kind__in=('release_ready', 'release_outcome')).exists():
        raise RuntimeError('The specimen has moved beyond the sign-off hold. Preserve its later history.')
    return {**data, 'case': str(case.pk), 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created,
            'setup': reverse('workspace_settings', args=[case.pk]) + '?area=roles#ui-design-signoff'}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(GUARD)) != (
            'design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and design sign-off guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicitly configured preview sample database.')
    print(GUARD + '=' + json.dumps(prepare()), flush=True)
