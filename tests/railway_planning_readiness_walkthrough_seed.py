"""Prepare one source-bound Planning readiness claim for the native browser."""

import json
import os
from decimal import Decimal
from time import sleep
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.core.models import Audit, Case
from apps.core.services import event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import commercial, planning, planning_inputs
from apps.pmo.models import DeliverySource
from apps.workflows import factory, factory_planning
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests import planning_helpers, test_factory_planning
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_planning_department_inputs import enhanced, record


GUARD = 'PSL_PLANNING_READINESS_WALKTHROUGH'
TENANT = 'design-planning-readiness-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
TITLE = 'SAMPLE Planning readiness from five department inputs'
MAKER = 'sample-planning-readiness-recorder'
PREPARED = 'sample.planning_readiness_prepared'
OBSERVATION = 'sample.planning_readiness_observation_requested'
STEP = 'ACT08'
WINDOW_SECONDS = 40
READ = ('case.read', 'factory.read', 'planning.read', 'approval.read', 'approval.source.read:synthetic-planning-scope',
        'approval.source.read:synthetic-planning-estimates', 'commercial.read', 'costing.read', 'costing.source.read')


def trial_reader():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and Planning readiness fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def choices(work):
    _, value = factory.profile(work)
    options, _ = factory_planning.eligible(work, value, *factory_planning.snapshot(work, value))
    return value, options


def prepare_sample(case, reader):
    maker = get_user_model().objects.create_user(MAKER)
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action)
        for user, actions in ((maker, dict.fromkeys(ACTIONS)), (reader, READ)) for action in actions])

    def native_fixture(configured, username):
        return planning_helpers.fixture(configured=configured, username=MAKER)

    with (patch.object(planning_helpers, 'setup_case', return_value=(maker, case)),
          patch.object(test_factory_planning, 'fixture', side_effect=native_fixture)):
        sample = enhanced()
    work = sample['work']
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'waiting':
        raise RuntimeError('The exact native Planning requests must be waiting for their source owners.')
    planning_helpers.observe(sample)

    sources = {key: sample['e'][key].pk for key in commercial.SOURCE_KINDS}
    first = commercial.propose(maker, case.pk, sources, sample['e']['requirements'].pk,
                               'Fictional earlier recorded costing.', rev(case))
    for role in commercial.ROLES:
        commercial.decide_proposal(maker, case.pk, first.pk, role, 'approve', 'Synthetic previous exact approval.', rev(case))
    baseline = record(sample, 'Engineering', days=Decimal('1'))
    current = record(sample, 'Engineering', previous=baseline, days=Decimal('2.500'))
    inputs = [current, record(sample, 'QA', state='unknown', days=None), record(sample, 'Security'),
              record(sample, 'Product', state='not_applicable', days=None), record(sample, 'Infrastructure', days=Decimal('1'))]
    source = planning_helpers.evidence(sample, 'costing', 'Fictional supplied costing reviewed after the Engineering input changed.')
    proposal = commercial.propose(maker, case.pk, {**sources, 'costing': source.pk}, sample['e']['requirements'].pk,
                                  'Fix the sample costing source against the current department inputs.', rev(case))
    for role in commercial.ROLES:
        commercial.decide_proposal(maker, case.pk, proposal.pk, role, 'approve', 'Synthetic current exact approval.', rev(case))
    review = planning_inputs.review(maker, case.pk, sample['packet'].pk, 'PM', 'retain_costing', sample['e']['policy_decision'].pk,
                                    'Use the later reviewed supplied sample costing for these exact inputs.', rev(case))

    work.refresh_from_db()
    _, options = choices(work)
    if options != ['ACT04'] or not factory.run_once(work.pk):
        raise RuntimeError('Run only the fresh native investigation before observing preparation.')
    work.refresh_from_db()
    _, options = choices(work)
    if (options != [STEP] or work.source_head_id != sample['packet'].pk or planning.latest(case, 'ready')
            or FactoryProgress.objects.filter(work=work).exists()):
        raise RuntimeError('The specimen must stop at the first exact readiness preparation step.')
    return event(maker, case, PREPARED, work=work.pk, packet=sample['packet'].pk, reader=reader.pk,
        inputs={item.department: item.pk for item in inputs}, review=review.pk, proposal=proposal.pk,
        proposal_version=proposal.number, previous_proposal=first.pk, previous_version=first.number).data


def pinned(reader, work_id=None, *, lock=False):
    case = Case.objects.get(pk=CASE_ID, tenant=TENANT, kind='project', title=TITLE, synthetic=True)
    data = Audit.objects.get(case=case, action=PREPARED).data
    if data['reader'] != reader.pk or work_id is not None and data['work'] != work_id:
        raise RuntimeError('Match the exact guarded preview specimen and Trial reader.')
    works = FactoryWork.objects.select_related('case', 'actor', 'source_head')
    if lock:
        works = works.select_for_update(of=('self',))
    work = works.get(pk=data['work'], case=case, actor__username=MAKER, definition=factory_planning.DEFINITION)
    if work.source_head_id != data['packet'] or not Grant.objects.filter(case=case, user=reader, action='planning.read', active=True).exists():
        raise RuntimeError('The original packet and current Trial read scope are required.')
    return work, data


@transaction.atomic
def prepare():
    reader = trial_reader()
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying this sample identifier.')
    if created:
        prepare_sample(case, reader)
    work, data = pinned(reader)
    return {**data, 'case': str(CASE_ID), 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created}


class ObserveReadiness(SyntheticFactoryCoordinator):
    def __init__(self, work_id):
        self.work_id = work_id

    def choose(self, context):
        if context['eligible'] != [STEP]:
            raise RuntimeError('The exact native readiness step must remain eligible.')
        print(f'{GUARD}_ACTIVE={self.work_id}:{STEP}', flush=True)
        sleep(WINDOW_SECONDS)
        return super().choose(context)


def observe(work_id):
    reader = trial_reader()
    if type(work_id) is not int or not 0 < work_id <= 9223372036854775807:
        raise RuntimeError('Supply the exact prepared Planning work identifier.')
    with transaction.atomic():
        work, data = pinned(reader, work_id, lock=True)
        value, options = choices(work)
        if (options != [STEP] or value['provider'] != 'synthetic_factory_v1' or value['lease_seconds'] < 2 * WINDOW_SECONDS
                or work.cancel_requested or work.lease_until or planning.latest(work.case, 'ready')
                or FactoryProgress.objects.filter(work=work).exists() or work.activities.filter(kind=STEP).exists()
                or Audit.objects.filter(case=work.case, action=OBSERVATION).exists()):
            raise RuntimeError('Observe only the fresh exact readiness claim without other active work.')
        event(work.actor, work.case, OBSERVATION, work=work.pk, packet=work.source_head_id, step=STEP)
    if not factory.run_once(work.pk, provider=ObserveReadiness(work.pk)):
        raise RuntimeError('The native readiness preparation did not settle.')
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind=STEP, phase='observed')
    readiness = planning.latest(work.case, 'ready')
    current = planning.current_readiness(work.case, readiness.pk)
    collection = current['inputs']['department_inputs']
    if (attempt.result['readiness'] != readiness.pk or collection['review_id'] != data['review']
            or {row['department']: row['id'] for row in collection['inputs']} != data['inputs']
            or DeliverySource.objects.filter(dossier__case=work.case, kind='scope_baseline').exists()):
        raise RuntimeError('Retain the exact readiness output before the independent delivery handoff.')
    return {'work': work.pk, 'attempt': attempt.pk, 'packet': work.source_head_id, 'readiness': readiness.pk}


def run():
    print(GUARD + '=' + json.dumps(prepare()), flush=True)
