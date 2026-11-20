"""Prepare isolated BU result correction and live investigation browser stations."""

import json
import os
from functools import partial
from pathlib import Path
from time import sleep
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance import bu as native
from apps.finance.bu_models import BUWork
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_bu as bu, factory_progress
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests import bu_helpers, payroll_helpers
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


TENANT = 'design-business-unit-correction-walkthrough'
TITLES = {
    'return': 'SAMPLE staff totals require independent correction and approval',
    'live': 'SAMPLE live investigation of staff business-unit inputs',
}
WORK_KEY = 'SAMPLE-BU-STAFF-WALKTHROUGH'
RULE_KEY = 'sample-bu-corrected-exception'
OBSERVATION_SECONDS = 20


def require_sample_account():
    environment = (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
                   os.getenv('PSL_COMPOSED_WALKTHROUGH'))
    if environment != (PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('Exact Railway acceptance project and fixture guard required')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True,
                                        is_staff=False, is_superuser=False)


def exact_work(work_id, station, *, lock=False):
    works = FactoryWork.objects.select_related('actor', 'case', 'source_head')
    if lock:
        works = works.select_for_update(of=('self',))
    return works.get(pk=work_id, key=WORK_KEY, definition=bu.DEFINITION, case__tenant=TENANT,
                     case__title=TITLES[station], case__synthetic=True, request__mode='staff',
                     actor__username=f'batch-bu-browser-{station}-preparer')


@transaction.atomic
def prepare(station):
    reviewer = require_sample_account()
    case, created = Case.objects.get_or_create(tenant=TENANT, title=TITLES[station], kind='project', synthetic=True)
    if created:
        users = get_user_model().objects
        owner = users.create_user(f'batch-bu-browser-{station}-owner')
        Grant.objects.bulk_create([Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)])

        def principal(role):
            return reviewer if role == 'reviewer' else users.create_user(f'batch-bu-browser-{station}-{role}')

        with patch.object(bu_helpers, 'payroll_fixture', side_effect=partial(
                payroll_helpers.fixture, context=(owner, case), principal=principal)):
            data = bu_helpers.fixture()
        preparer = data['preparer']
        profile = json.loads(Path('fixtures/factory-bu.json').read_text(encoding='utf-8'))
        profile.pop('classification')
        config = draft_operator_policy(preparer, case.pk, 'OPS.factory_bu_execution', profile,
                                       data['e']['policy_decision'].pk, timezone.now())
        transition(preparer, config.pk, 'validated')
        transition(preparer, config.pk, 'active')
        original = bu_helpers.rule(data)
        bu_helpers.review(data, original)
        inputs = {'mode': 'staff', 'payroll_id': data['match'].pk, 'source_id': None,
                  'rule_ids': [original.pk], 'comparison': None}
        work = bu.start(preparer, case.pk, WORK_KEY, inputs, TITLES[station], rev(case))
        if station == 'return':
            factory.run_until_wait(work.pk)
            work.refresh_from_db()
            result = bu.result(work)
            if not result or result.metadata['status'] != 'complete' or result.reviews.exists():
                raise RuntimeError('Expected untouched staff result for the independent browser reviewer')
            factory_progress.set_progress(preparer, work.pk, work.revision, True)
    else:
        work = FactoryWork.objects.get(case=case, key=WORK_KEY, definition=bu.DEFINITION)
    return {'station': station, 'case': str(case.pk), 'work': work.pk, 'preserved': not created,
            'path': reverse('factory_detail' if station == 'live' else 'factory_invoice_decision', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk])}


@transaction.atomic
def prepare_replacement(work_id):
    reviewer = require_sample_account()
    work = exact_work(work_id, 'return', lock=True)
    existing = BUWork.objects.filter(case=work.case, operation_key=RULE_KEY, kind='rule', actor=work.actor).first()
    if existing:
        return {'work': work.pk, 'replacement': existing.pk, 'proof': existing.payload['rationale_evidence_id'],
                'preserved': True}
    result = bu.result(work)
    returned = result.reviews.filter(purpose='staff').order_by('-pk').first() if result else None
    if not returned or returned.verdict != 'return' or returned.actor_id != reviewer.pk or bu.publication(work):
        raise RuntimeError('The exact current result needs its independent browser return before preparing its rule successor')
    match, rules, _ = bu.source(work, work.actor)
    if len(rules) != 1 or rules[0].version != 1:
        raise RuntimeError('Expected one exact original payroll exception')
    original = rules[0]
    proof = add_evidence(work.actor, work.case_id, 'bu_review',
                         'Synthetic source owner supplied corrected allocation weights for this exact exception.',
                         'synthetic:business-unit-correction', rev(work.case))
    payload = dict(original.payload, rationale_evidence_id=proof.pk,
                   weights=[{'bu': 'BU-A', 'weight': '40'}, {'bu': 'BU-B', 'weight': '60'}])
    replacement = native.rule(work.actor, work.case_id, match.pk, original.reference, RULE_KEY, payload, rev(work.case))
    if replacement.version != 2 or replacement.reviews.exists():
        raise RuntimeError('Expected a distinct replacement awaiting an actual independent decision')
    return {'work': work.pk, 'returned_result': result.pk, 'original_rule': original.pk,
            'replacement': replacement.pk, 'proof': proof.pk, 'preserved': False}


class ObservableInvestigation(SyntheticFactoryCoordinator):
    def __init__(self, work_id):
        self.work_id = work_id

    def choose(self, context):
        if context['eligible'] == ['ACT04']:
            print(f'PSL_BU_LIVE_INVESTIGATION={self.work_id}', flush=True)
            sleep(OBSERVATION_SECONDS)
        return super().choose(context)


def observe(work_id):
    require_sample_account()
    work = exact_work(work_id, 'live')
    if FactoryProgress.objects.filter(work=work).exists() or work.plan_revision or work.lease_until:
        raise RuntimeError('The one-shot observation needs the fresh sample without an ordinary background request')
    _, profile = factory.profile(work)
    choices, _ = bu.eligible(work, profile, *bu.snapshot(work, profile))
    if choices != ['ACT04'] or profile['provider'] != 'synthetic_factory_v1':
        raise RuntimeError('Only the exact synthetic investigation can open an observation window')
    if not factory.run_once(work.pk, provider=ObservableInvestigation(work.pk)):
        raise RuntimeError('No native investigation settled')
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT04', phase='observed')
    return {'work': work.pk, 'investigation_attempt': attempt.pk, 'private_payloads': attempt.result['private_payloads_in_result']}


def run():
    for station in TITLES:
        print('PSL_BU_BROWSER_FIXTURE=' + json.dumps(prepare(station)), flush=True)
