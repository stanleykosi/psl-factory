"""Real PostgreSQL recovery contention; temporary discovery location during607 freeze."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.factory_recovery_validators import COMPONENT, METHOD
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_execution
from apps.workflows.models import FactoryExecutionBinding, FactoryWork
from apps.agents.models import AgentRun
from tests.factory_helpers import fixture


class ExecutionContentionTests(TransactionTestCase):
    def setUp(self):
        self.data = fixture(username='isolated-recovery-reviewer')
        self.worker = get_user_model().objects.create_user(username='isolated-recovery-worker')
        for action in ['case.read', 'finance.read', 'factory.read', 'factory.execute']:
            Grant.objects.create(case=self.data['case'], user=self.worker, action=action)

    def configure(self, until=None):
        f = self.data
        now = timezone.now()
        self.rule = dict(definition='pmo-finance/v1', method=METHOD, principal_id=self.worker.pk,
                         reviewer_id=f['actor'].pk, review_role='Finance', independent_of_worker=True,
                         valid_from=now.isoformat(), valid_until=(until or now + timedelta(hours=1)).isoformat())
        config = draft_operator_policy(f['actor'], f['case'].pk, COMPONENT, {'rules': [self.rule]}, f['evidence']['policy_decision'].pk, now)
        transition(f['actor'], config.pk, 'validated'); transition(f['actor'], config.pk, 'active')
        return config

    def bind(self):
        f = self.data
        return factory_execution.bind(f['actor'], f['work'].pk, f['work'].revision,
                                      f['evidence']['policy_decision'].pk, 'Synthetic real PostgreSQL contention review')

    def test_two_reviewers_cannot_fork_the_same_work_revision(self):
        self.configure(); barrier = Barrier(2)
        def review():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()'); pid = cursor.fetchone()[0]
                barrier.wait(timeout=30)
                try:
                    self.bind(); return pid, 'recorded'
                except ValidationError as exc:
                    if 'STALE_VERSION' not in str(exc): raise
                    return pid, 'stale'
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: review(), range(2)))
        self.assertEqual(len({pid for pid, _ in results}), 2)
        self.assertEqual(sorted(state for _, state in results), ['recorded', 'stale'])
        f = self.data; work = FactoryWork.objects.get(pk=f['work'].pk)
        self.assertEqual(FactoryExecutionBinding.objects.filter(work=work).count(), 1)
        self.assertEqual(work.actor_id, f['actor'].pk); self.assertEqual(work.execution_actor_id, self.worker.pk)
        self.assertEqual(work.budget_used, f['work'].budget_used)
        self.assertEqual(work.budget_limit, f['work'].budget_limit)
        self.assertFalse(AgentRun.objects.filter(case=f['case']).exists())

    def test_an_actual_worker_lease_blocks_review_on_another_connection(self):
        self.configure(); acquired = Event()
        def claim():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()'); pid = cursor.fetchone()[0]
                token = factory.claim(self.data['work'].pk)
                acquired.set(); return pid, token
            finally: close_old_connections()
        def review():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()'); pid = cursor.fetchone()[0]
                self.assertTrue(acquired.wait(timeout=30))
                with self.assertRaisesMessage(ValidationError, 'CONFLICT'):
                    self.bind()
                return pid
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            claiming = pool.submit(claim); reviewing = pool.submit(review)
            owner_pid, token = claiming.result(timeout=40); reviewer_pid = reviewing.result(timeout=40)
        self.assertNotEqual(owner_pid, reviewer_pid); self.assertIsNotNone(token)
        work = FactoryWork.objects.get(pk=self.data['work'].pk)
        self.assertGreater(work.lease_until, timezone.now())
        self.assertIsNone(work.execution_binding_id); self.assertEqual(work.budget_used, 0)

    def test_authority_really_expires_without_backdating_or_fallback(self):
        deadline = timezone.now() + timedelta(seconds=25)
        self.configure(until=deadline); binding = self.bind()
        work = FactoryWork.objects.get(pk=self.data['work'].pk)
        self.assertEqual(work.execution_actor_id, self.worker.pk)
        remaining = (deadline - timezone.now()).total_seconds()
        self.assertGreater(remaining, 0)
        Event().wait(remaining + 0.1)
        self.assertGreaterEqual(timezone.now(), deadline)
        with self.assertRaisesMessage(ValidationError, 'owner_needed'):
            factory_execution.execution_actor(work)
        work.refresh_from_db()
        self.assertEqual(work.execution_binding_id, binding.pk)
        self.assertEqual(work.actor_id, self.data['actor'].pk); self.assertEqual(work.budget_used, 0)
