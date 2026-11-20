"""Observe exact native worker steps in new synthetic preview cases."""

import os
from functools import partial
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
from apps.policy.operator_drafts import draft_operator_policy
from apps.workflows import factory, factory_ledger, factory_ppe
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests import finance_analysis_helpers, ledger_helpers, ppe_helpers, test_factory_ledger, test_factory_ppe
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


TENANT = 'design-finance-live-steps'
PREPARED = 'sample.finance_live_grant_fixture'
OBSERVATION = 'sample.finance_live_observation_requested'
WINDOW_SECONDS = 30
LEASE_SECONDS = 120
STEPS = {
    'asset-calculation': (factory_ppe, 'PPE-1', 'ACT08', 'SAMPLE live asset schedule calculation', ('ppe.read',)),
    'ledger-investigation': (factory_ledger, 'ledger-1', 'ACT04', 'SAMPLE live supplied ledger investigation',
                             ('ledger.read', 'ledger.private.read')),
}


def trial_reader():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
        os.getenv('PSL_FINANCE_LIVE_STEP_FIXTURE')) != (PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway acceptance environment and Finance live step guard are required.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def owner_name(station):
    return f'batch-finance-live-{station}-owner'


def case_id(station):
    return uuid5(NAMESPACE_URL, f'{TENANT}:{station}')


def observation_lease(actor, case_id, component, value, *args):
    return draft_operator_policy(actor, case_id, component, dict(value, lease_seconds=LEASE_SECONDS), *args)


def native_sample(station, owner, case):
    if station == 'asset-calculation':
        sample = test_factory_ppe.FactoryPPETests()
        with (patch.object(finance_analysis_helpers, 'setup_case', return_value=(owner, case)),
              patch.object(test_factory_ppe, 'fixture', partial(ppe_helpers.fixture,
                  reviewer_username='batch-finance-live-asset-reviewer', recipient_username='batch-finance-live-asset-inbox')),
              patch.object(test_factory_ppe, 'draft_operator_policy', observation_lease)):
            sample.setUp()
        work = sample.start()
        if not factory.run_once(work.pk) or not work.activities.filter(kind='ACT04', status='succeeded').exists():
            raise RuntimeError('The reviewed register must finish its initial native investigation first.')
    else:
        sample = test_factory_ledger.FactoryLedgerTests()
        with (patch.object(ledger_helpers, 'setup_case', return_value=(owner, case)),
              patch.object(test_factory_ledger, 'draft_operator_policy', observation_lease)):
            sample.fixture_factory = partial(ledger_helpers.fixture, reviewer_username='batch-finance-live-ledger-reviewer')
            sample.setUp()
        work = sample.start()
    work.refresh_from_db()
    return work


def pinned_work(station, reader, work_id=None, *, lock=False):
    domain, key, _, title, _ = STEPS[station]
    candidates = FactoryWork.objects.select_related('case', 'actor', 'source_head').filter(
        case_id=case_id(station), case__tenant=TENANT, case__title=title, case__synthetic=True, case__kind='project',
        actor__username=owner_name(station), actor__is_active=True, actor__is_staff=False,
        actor__is_superuser=False, source_head__case_id=case_id(station),
        key=key, definition=domain.DEFINITION)
    if lock:
        candidates = candidates.select_for_update(of=('self',))
    work = candidates.get(pk=work_id) if work_id is not None else candidates.get()
    if work.actor_id == reader.pk or not Audit.objects.filter(case=work.case, actor=work.actor, action=PREPARED,
            data={'work': work.pk, 'source': work.source_head_id, 'sha256': work.source_head.sha256,
                  'reader': reader.pk, 'station': station}).exists():
        raise RuntimeError('The exact distinct owner, trial reader and prepared source must match.')
    factory.access(reader, work.case, 'factory.read', work.definition)
    return work


@transaction.atomic
def prepare(station):
    reader = trial_reader()
    _, _, step, title, permissions = STEPS[station]
    case, created = Case.objects.get_or_create(pk=case_id(station), defaults={
        'tenant': TENANT, 'title': title, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, title, 'project', True):
        raise RuntimeError('Preserve the existing case if the synthetic identity differs.')
    if created:
        owner = get_user_model().objects.create_user(username=owner_name(station))
        Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in dict.fromkeys(ACTIONS)])
        Grant.objects.bulk_create([Grant(case=case, user=reader, action=action)
                                   for action in ('case.read', 'factory.read', 'finance.read', *permissions)])
        work = native_sample(station, owner, case)
        event(owner, case, PREPARED, work=work.pk, source=work.source_head_id, sha256=work.source_head.sha256,
              reader=reader.pk, station=station)
    work = pinned_work(station, reader)
    return {'station': station, 'case': str(case.pk), 'work': work.pk, 'source': work.source_head_id,
            'step': step, 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created}


class ObserveExactly(SyntheticFactoryCoordinator):
    def __init__(self, work_id, step):
        self.work_id = work_id
        self.step = step

    def choose(self, context):
        if context['eligible'] != [self.step]:
            raise RuntimeError('The worker must still be on the selected native observation step.')
        print(f'PSL_FINANCE_LIVE_STEP={self.work_id}:{self.step}', flush=True)
        sleep(WINDOW_SECONDS)
        return super().choose(context)


def observe(station, work_id):
    reader = trial_reader()
    domain, _, step, _, _ = STEPS[station]
    with transaction.atomic():
        work = pinned_work(station, reader, work_id, lock=True)
        marker = Audit.objects.filter(case=work.case, action=OBSERVATION, data__work=work.pk)
        result = factory_ppe.schedule(work) if domain is factory_ppe else factory_ledger.lineage(work)
        expected_plans = 1 if domain is factory_ppe else 0
        if (marker.exists() or result or work.cancel_requested or work.lease_until or work.execution_binding_id
                or (work.plan_revision, work.fence) != (expected_plans, expected_plans)
                or FactoryProgress.objects.filter(work=work).exists()
                or FactoryAttempt.objects.filter(activity__work=work, activity__kind=step).exists()):
            raise RuntimeError('Select the fresh synthetic sample with no earlier observation or worker request.')
        if (domain is factory_ppe) != work.activities.filter(kind='ACT04', status='succeeded').exists():
            raise RuntimeError('The fixture must still be at its exact initial step.')
        _, profile = factory.profile(work)
        eligible, _ = domain.eligible(work, profile, *domain.snapshot(work, profile))
        if (eligible != [step] or profile['provider'] != 'synthetic_factory_v1'
                or profile['lease_seconds'] != LEASE_SECONDS):
            raise RuntimeError('The exact native step and bounded synthetic worker profile must match.')
        event(work.actor, work.case, OBSERVATION, work=work.pk, source=work.source_head_id, step=step)
    if not factory.run_once(work.pk, provider=ObserveExactly(work.pk, step)):
        raise RuntimeError('The original native worker step did not settle.')
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind=step, phase='observed')
    return {'work': work.pk, 'step': step, 'attempt': attempt.pk}
