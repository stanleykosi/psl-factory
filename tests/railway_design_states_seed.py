"""Prepare named synthetic cases for the state acceptance walkthrough."""
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from adapters.publications import InternalPublicationAdapter
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import review_version
from apps.documents.models import PublicationJob
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import resolve, transition
from apps.workflows import factory, factory_minutes
from apps.workflows.models import FactoryWork
from tests import document_helpers, planning_helpers, test_commercial_changes
from tests.billing_helpers import coverage, stage_policy
from tests.helpers import rev, signed
from tests.test_change_impacts import ChangeImpactTests
from tests.test_factory_minutes import FactoryMinutesTests
from tests.test_factory_reporting import FactoryReportingTests, artifact


class InterruptedMinutesDelivery(InternalPublicationAdapter):
    def deliver(self, job, fence):
        raise TimeoutError('Synthetic receipt unavailable after original dispatch')


@transaction.atomic
def prepare(key, operator):
    case, created = Case.objects.get_or_create(tenant='design-state-walkthrough', kind='project', synthetic=True,
                                               title='Browser design states · ' + key)
    if key == 'delegation':
        if created:
            Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
        second, _ = get_user_model().objects.get_or_create(username='state-check-delegation-recipient')
        Grant.objects.get_or_create(case=case, user=second, action='case.read')
        proof = case.evidence.filter(kind='policy_decision', source='synthetic:state-walkthrough').first()
        if proof is None:
            proof = add_evidence(operator, case.pk, 'policy_decision', 'Synthetic draft-only verification decision',
                                 'synthetic:state-walkthrough')
        if resolve('D05.role_principal_assignments', case).status != 'ACTIVE':
            policy = draft_roles(operator, case.pk, [{'role': 'PM', 'user_id': operator.pk},
                {'role': 'PM', 'user_id': second.pk}], proof.pk, timezone.now())
            transition(operator, policy.pk, 'validated')
            transition(operator, policy.pk, 'active')
        return {'case': str(case.pk), 'evidence': proof.pk, 'delegate': second.pk}
    if not created:
        existing = FactoryWork.objects.filter(case=case).first()
        return {'case': str(case.pk), 'work': existing.pk if existing else None}
    Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
    if key == 'assistant-draft':
        with patch.object(planning_helpers, 'setup_case', return_value=(operator, case)):
            planning = planning_helpers.fixture(configured=True, username='state-assistant-draft')
        return {'case': str(case.pk), 'packet': planning['packet'].pk}
    if key == 'signed-money':
        agreement = signed(operator, case)['signature']
        stage_policy(operator, case, coverage(operator, case), agreement)
        return {'case': str(case.pk), 'agreement': agreement.pk}
    users = get_user_model().objects
    create_user = users.create_user
    if key == 'changed-milestone':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            entry = ChangeImpactTests()
            entry.setUp()
        entry.approved_report()
        return {'case': str(case.pk), 'work': None}
    is_minutes = key in {'minutes', 'outward-minutes', 'minutes-uncertain'}
    entry = FactoryMinutesTests() if is_minutes else FactoryReportingTests()
    with (
        patch.object(document_helpers, 'setup_case', return_value=(operator, case)),
        patch.object(users, 'create_user', side_effect=lambda username: create_user(username=f'state-check-{key}-{username}')),
    ):
        entry.setUp()
    if is_minutes:
        outward = key != 'minutes'
        entry.start(outward=outward)
        entry.advance()
        if outward:
            entry.confirm()
            entry.advance()
        if key == 'minutes-uncertain':
            binding = factory_minutes.document(entry.work)
            review_version(operator, case.pk, binding.version_id, 'approve', 'Exact synthetic receipt review', rev(case))
            factory.run_until_wait(entry.work.pk, adapter=InterruptedMinutesDelivery())
            job = PublicationJob.objects.get(publication__factory_work=entry.work)
            if job.status != 'unknown':
                raise ValueError('Expected the original synthetic transmission to remain uncertain')
            return {'case': str(case.pk), 'work': entry.work.pk, 'job': job.pk}
    else:
        artifact(operator, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, entry.owner)
        entry.start_work()
        entry.advance()
        entry.review('return')
    return {'case': str(case.pk), 'work': entry.work.pk}


if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
    raise SystemExit('Exact isolated acceptance environment required')

trial = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
for fixture in ('delegation', 'minutes', 'weekly', 'outward-minutes', 'changed-milestone', 'assistant-draft', 'signed-money', 'minutes-uncertain'):
    try:
        result = prepare(fixture, trial)
    except Exception as exc:
        print(f'PSL_STATE_ERROR={fixture}: {type(exc).__name__}: {str(exc)[:240]}', flush=True)
    else:
        print('PSL_STATE_FIXTURE=' + json.dumps({'fixture': fixture, **result}), flush=True)
