"""Guarded independent escalation investigation and human decision sample."""
import json
import os
from datetime import timedelta
from pathlib import Path
from time import sleep
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import escalations
from apps.pmo.issues import log_issue
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from apps.workflows import factory, factory_escalation
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PROJECT
from tests.test_escalations import clocks


GUARD = 'PSL_ESCALATION_INVESTIGATION_FIXTURE'
TENANT = 'design-escalation-investigation-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE Harbor Clinics dependency investigation'
MAKER = 'sample-escalation-investigation-preparer'
TRIAL = 'psl-agent-trial'
TRIAL_ACTIONS = {'case.read', 'factory.read', 'issue.read', 'issue.escalation_decide'}
REFERENCE = 'SAMPLE-DEPENDENCY-TIMING'
OTHER_REFERENCE = 'SAMPLE-UNRELATED-DEPENDENCY'
ROLE = 'Head of PMO'
PREPARED = 'sample.escalation_investigation_prepared'
OBSERVATION = 'sample.escalation_investigation_observation_requested'
STEP = 'ACT04'
WINDOW_SECONDS = 45
PROFILE = Path(__file__).resolve().parent.parent / 'fixtures' / 'factory-escalation.json'


def trial_reviewer():
    return get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)


def populate(case, reviewer):
    maker = get_user_model().objects.create_user(MAKER)
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action)
        for actor, actions in ((maker, dict.fromkeys(ACTIONS)), (reviewer, sorted(TRIAL_ACTIONS))) for action in actions])
    owner = add_evidence(maker, case.pk, 'policy_decision', 'Fictional scope, acknowledgement method and reviewer.',
                         'synthetic:escalation-investigation-owner')
    role = draft_roles(maker, case.pk, [{'role': 'PM', 'user_id': maker.pk}, {'role': ROLE, 'user_id': reviewer.pk}],
                       owner.pk, timezone.now())
    transition(maker, role.pk, 'validated')
    transition(maker, role.pk, 'active')
    decision_rule = artifact(maker, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                             {'rules': [{'role': ROLE, 'actions': ['reject']}]}, owner)
    clock, deadline = clocks(maker, case, owner, anchor='trigger_at', routes=False)
    settings = json.loads(PROFILE.read_text(encoding='utf-8'))
    settings.pop('classification')
    settings.update(preparer_id=maker.pk, executor_id=maker.pk)
    config = draft_operator_policy(maker, case.pk, 'OPS.factory_escalation_execution', settings, owner.pk, timezone.now())
    transition(maker, config.pk, 'validated')
    transition(maker, config.pk, 'active')
    trigger = timezone.now() - timedelta(hours=41)
    source = add_evidence(maker, case.pk, 'completion',
        f'Fictional dependency first recorded at {trigger.isoformat()}. No acknowledgement was captured.',
        'synthetic:escalation-investigation-trigger')
    selected = log_issue(maker, case.pk, REFERENCE, 'SAMPLE acceptance data has not arrived', 'Delivery', maker.pk,
                         'Confirm when the test data is expected.', source.pk, 'Exact specimen for investigation.', rev(case), 'High')
    other = log_issue(maker, case.pk, OTHER_REFERENCE, 'SAMPLE unrelated documentation update', 'Documentation',
                      maker.pk, 'Check the internal update.', source.pk, 'Separate issue outside this request.', rev(case))
    profile = escalations.capture_profile(maker, case.pk, selected.issue_id, selected.pk, 'client_dependent', True,
        trigger, source.pk, 'Fictional timing and exact selected issue state.', rev(case))
    request = escalations.request_escalation(maker, case.pk, profile.pk, 'escalate', 'Client', source.pk,
        'Review the timing before deciding whether to contact the client.', rev(case))
    other_profile = escalations.capture_profile(maker, case.pk, other.issue_id, other.pk, 'internal', False, None,
        source.pk, 'Separate dependency outside the selected investigation.', rev(case))
    other_request = escalations.request_escalation(maker, case.pk, other_profile.pk, 'escalate', 'Client', source.pk,
        'Separate request for a different issue.', rev(case))
    work = factory_escalation.start(maker, case.pk, 'SAMPLE-ESCALATION-INVESTIGATING', request.pk, None,
                                    'SAMPLE investigate the acceptance data delay', rev(case))
    return event(maker, case, PREPARED, work=work.pk, packet=work.source_head_id, reviewer=reviewer.pk,
        maker=maker.pk, profile=profile.pk, request=request.pk, issue=selected.issue_id, issue_state=selected.pk,
        other_issue=other.issue_id, other_request=other_request.pk, evidence=source.pk, trigger=trigger.isoformat(),
        clock=clock.pk, deadline=deadline.pk,
        decision_rule=decision_rule.pk, authority=role.pk, execution=config.pk)


def pinned(reviewer, work_id=None, *, lock=False):
    case = Case.objects.get(pk=CASE_ID, tenant=TENANT, title=TITLE, kind='project', synthetic=True)
    marker = Audit.objects.select_related('actor').get(case=case, action=PREPARED)
    data = marker.data
    if (data['reviewer'] != reviewer.pk or work_id is not None and data['work'] != work_id
            or marker.actor_id != data['maker'] or marker.actor.username != MAKER or marker.actor.has_usable_password()):
        raise RuntimeError('Preserve the exact distinct Trial reviewer and synthetic escalation specimen.')
    if set(Grant.objects.filter(case=case, user=reviewer, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS:
        raise RuntimeError('Preserve the original case-local Trial escalation authority.')
    query = FactoryWork.objects.select_related('case', 'actor', 'source_head')
    if lock:
        query = query.select_for_update(of=('self',))
    work = query.get(case=case, pk=data['work'], actor=marker.actor, definition=factory_escalation.DEFINITION)
    native, _ = factory_escalation.source(work, reviewer)
    if (work.source_head_id, native.pk, native.profile_id, native.profile.state_id, native.profile.state.issue_id) != (
            data['packet'], data['request'], data['profile'], data['issue_state'], data['issue']):
        raise RuntimeError('Preserve the exact original escalation request and issue input.')
    if (native.profile.state.issue.reference != REFERENCE or native.profile.evidence_id != data['evidence']
            or native.profile.trigger_at.isoformat() != data['trigger']):
        raise RuntimeError('Use only the original native issue clock evidence for this specimen.')
    if factory_escalation.document(work) or Publication.objects.filter(factory_work=work).exists():
        raise RuntimeError('No escalation communication or delivery belongs to this investigation-only sample.')
    return work, native, data


@transaction.atomic
def prepare():
    reviewer = trial_reviewer()
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE_ID).exists():
        raise RuntimeError('Preserve other work outside the exact escalation specimen.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    case = Case.objects.select_for_update().get(pk=case.pk)
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('This setup is limited to the exact synthetic escalation specimen.')
    if created:
        populate(case, reviewer)
    work, _, data = pinned(reviewer)
    return {**data, 'case': str(case.pk), 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created}


class ObserveInvestigation(SyntheticFactoryCoordinator):
    def __init__(self, work_id):
        self.work_id = work_id

    def choose(self, context):
        if context['eligible'] != [STEP]:
            raise RuntimeError('Only the exact native escalation investigation may be observed.')
        print(f'{GUARD}_ACTIVE={self.work_id}:{STEP}', flush=True)
        sleep(WINDOW_SECONDS)
        return super().choose(context)


def observe(work_id):
    if type(work_id) is not int or not 0 < work_id <= 9223372036854775807:
        raise RuntimeError('Supply the exact prepared escalation work identifier.')
    reviewer = trial_reviewer()
    with transaction.atomic():
        work, request, data = pinned(reviewer, work_id, lock=True)
        _, settings = factory.profile(work)
        state, *sources = factory_escalation.snapshot(work, settings)
        options, _ = factory_escalation.eligible(work, settings, state, *sources)
        if (options != [STEP] or settings['provider'] != 'synthetic_factory_v1' or settings['lease_seconds'] < 2 * WINDOW_SECONDS
                or request.decisions.exists() or work.cancel_requested or work.lease_until or work.activities.exists()
                or FactoryProgress.objects.filter(work=work).exists()
                or Audit.objects.filter(case=work.case, action=OBSERVATION).exists()):
            raise RuntimeError('Observe only the fresh exact escalation claim before the human decision.')
        event(work.actor, work.case, OBSERVATION, work=work.pk, packet=work.source_head_id, step=STEP)
    if not factory.run_once(work.pk, provider=ObserveInvestigation(work.pk)):
        raise RuntimeError('The native escalation investigation did not settle.')
    factory.run_until_wait(work.pk)
    work, request, data = pinned(reviewer, work_id)
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind=STEP, phase='observed')
    [finding] = attempt.result['investigation']['findings']
    if (attempt.result['head'] != data['packet'] or finding['profile_id'] != data['profile']
            or finding['state_id'] != data['issue_state'] or finding['evidence_id'] != data['evidence']
            or finding['timing']['acknowledgement_status'] != 'OVERDUE' or finding['timing']['client_24h'] is not True
            or attempt.result['communications_dispatched'] or request.decisions.exists()
            or PublicationReceipt.objects.filter(publication__factory_work=work).exists() or work.status != 'waiting'):
        raise RuntimeError('Retain the selected investigation and stop at the separate human decision.')
    return {'work': work.pk, 'attempt': attempt.pk, 'run': attempt.result['investigation_run'], 'issue': data['issue'],
            'request': data['request'], 'acknowledgement': 'OVERDUE', 'client_threshold_reached': True}


def run(action='prepare', work_id=None):
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv(GUARD)) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and escalation investigation guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicitly configured preview sample database.')
    if action == 'prepare' and work_id is None:
        result = prepare()
    elif action == 'observe':
        result = observe(work_id)
    else:
        raise RuntimeError('Choose preparation or observation of the one exact specimen.')
    print(GUARD + '=' + json.dumps(result), flush=True)
