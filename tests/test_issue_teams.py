"""Real native issue states, external-party facts and current recorder authority."""
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import issue_teams
from apps.pmo.issue_team_models import IssueTeamAssignment, IssueTeamReply
from apps.policy.issue_team_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_issues, factory_progress
from apps.workflows.models import FactoryAttempt, HumanTask
from tests.helpers import roles, rev
from tests import test_factory_issues as issue_helpers


def configure(entry):
    roles(entry.a, entry.c, entry.e['policy_decision'])
    value = json.loads(Path('fixtures/issue-team-controls.json').read_text())['value']
    config = draft_operator_policy(entry.a, entry.c.pk, COMPONENT, value,
                                  entry.e['policy_decision'].pk, timezone.now())
    transition(entry.a, config.pk, 'validated')
    transition(entry.a, config.pk, 'active')
    return config, value


class IssueTeamTests(TestCase):
    def setUp(self):
        entry = issue_helpers.FactoryIssueTests()
        entry.setUp()
        self.a, self.c, self.e, self.work = entry.a, entry.c, entry.e, entry.work
        self.helper = entry
        self.issue = entry.state.issue
        self.config, self.value = configure(entry)

    def assign(self, **changes):
        self.issue.refresh_from_db()
        self.work.refresh_from_db()
        values = dict(actor=self.a, case_id=self.c.pk, issue_id=self.issue.pk,
            state_id=self.issue.current_id, mode='team', team_key='sample-engineering',
            recorder_id=self.a.pk, recorder_role='PM', evidence_id=self.e['requirements'].pk,
            reason='Synthetic owner decision', expected=rev(self.c),
            work_id=self.work.pk, source_id=self.work.source_head_id)
        values.update(changes)
        return issue_teams.assign(**values)

    def reply(self, assignment, **changes):
        self.issue.refresh_from_db()
        values = dict(actor=self.a, case_id=self.c.pk, issue_id=self.issue.pk,
            state_id=self.issue.current_id, assignment_id=assignment.pk, operation_key=uuid4(),
            operation='acknowledge', evidence_id=self.e['requirements'].pk,
            note='Engineering confirmed the source issue', next_action='Investigate sample cause',
            party='Sample engineer without an account', channel='email',
            responded_at=timezone.now()-timedelta(minutes=2), source_ref='synthetic:email:17', expected=rev(self.c))
        values.update(changes)
        return issue_teams.record_reply(**values)

    def test_external_owner_and_actual_recorder_survive_native_followup_to_verified_output(self):
        assignment = self.assign()
        self.assertTrue(factory_issues.sync_owner(self.work.pk))
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        task = factory_issues.tasks(self.work).get(status='open')
        result = factory_issues.respond(self.a, self.work.pk, self.work.revision, rev(self.c),
            task.pk, task.revision, 'acknowledge', self.e['requirements'].pk, 'Engineering acknowledges',
            'Investigate actual cause', team_reply={'assignment_id': assignment.pk,
            'operation_key': uuid4(), 'party': 'Sample Engineering responder', 'channel': 'email',
            'responded_at': timezone.now()-timedelta(minutes=3), 'source_ref': 'synthetic:team-email'})
        factory.run_until_wait(result.pk)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        proof = factory_issues.verify(self.work, self.a)
        self.assertFalse(proof['issue_resolution_verified'])
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.current.status, 'Open')
        reply = IssueTeamReply.objects.get()
        self.assertEqual(reply.party, 'Sample Engineering responder')
        self.assertEqual(reply.actor_id, self.a.pk)
        self.assertEqual(reply.state.actor_id, self.a.pk)
        self.assertLess(reply.responded_at, reply.state.acknowledged_at)
        observed = FactoryAttempt.objects.filter(activity__work=self.work,
            activity__kind='ACT04', phase='observed').last()
        self.assertEqual(observed.result['investigation']['owner_context']['label'], 'SAMPLE Engineering')
        self.client.force_login(self.a)
        page = self.client.get(reverse('factory_detail', args=[self.work.pk]))
        self.assertContains(page, 'Sample Engineering responder')
        self.assertContains(page, 'Follow-up coordinator')

    def test_missing_team_rules_hold_only_external_assignment_and_pending_owner_is_readable(self):
        transition(self.a, self.config.pk, 'revoked')
        with self.assertRaises(ValidationError):
            self.assign()
        assignment = self.assign(team_key='', recorder_role='')
        self.assertIsNone(assignment.policy_id)
        factory_issues.sync_owner(self.work.pk)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'waiting')
        self.assertFalse(factory_issues.tasks(self.work).filter(status='open').exists())
        self.assertEqual(factory_issues.projection(self.a, self.work)['team']['status'], 'unassigned')

    def test_existing_internal_account_owner_does_not_depend_on_external_team_rules(self):
        transition(self.a, self.config.pk, 'revoked')
        assignment = self.assign(mode='internal', team_key='', recorder_role='')
        self.assertIsNone(assignment.policy_id)
        self.assertTrue(factory_issues.sync_owner(self.work.pk))
        factory.run_until_wait(self.work.pk)
        self.assertTrue(factory_issues.tasks(self.work).filter(status='open').exists())

    def test_exact_source_refresh_is_idempotent_and_preserves_budget_and_human_pause(self):
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        used = self.work.budget_used
        job = factory_progress.set_progress(self.a, self.work.pk, self.work.revision, True)
        factory_progress.set_progress(self.a, self.work.pk, self.work.revision, False)
        self.assign()
        self.assertTrue(factory_issues.sync_owner(self.work.pk))
        self.assertFalse(factory_issues.sync_owner(self.work.pk))
        job.refresh_from_db()
        self.work.refresh_from_db()
        self.assertEqual(job.status, 'paused')
        self.assertEqual(self.work.budget_used, used)
        self.assertEqual(HumanTask.objects.get().status, 'returned')

    def test_live_worker_defers_exact_assignment_until_ready(self):
        assignment = self.assign()
        self.work.lease_until = timezone.now()+timedelta(minutes=1)
        self.work.save(update_fields=['lease_until'])
        self.assertFalse(factory_issues.sync_owner(self.work.pk))
        self.work.refresh_from_db()
        self.assertEqual(self.work.source_head_id, assignment.requested_source_id)
        self.work.lease_until = None
        self.work.save(update_fields=['lease_until'])
        self.assertTrue(factory_issues.sync_owner(self.work.pk))

    def test_later_unreviewed_source_change_is_not_adopted_by_assignment_intent(self):
        self.assign()
        self.issue.refresh_from_db()
        from apps.pmo.issues import update_issue
        update_issue(self.a, self.c.pk, self.issue.pk, self.issue.current_id, 'manage',
                     self.e['requirements'].pk, 'Later source change', rev(self.c), next_action='Different facts')
        self.assertFalse(factory_issues.sync_owner(self.work.pk))

    def test_unknown_planner_effect_blocks_assignment_source_sync(self):
        from unittest.mock import patch
        from tests.readiness_helpers import endpoint
        from apps.agents import factory_coordinator
        # Existing role fixtures are already active. Exercise the actual durable
        # provider request and receipt workflow against the synthetic endpoint.
        with endpoint() as state, patch('tests.helpers.roles'):
            self.helper.configure_planner(state)
            state['lose_planning_response'] = True
            factory.run_once(self.work.pk)
            self.work.refresh_from_db()
            self.assertEqual(self.work.status, 'waiting_effect')
            assignment = self.assign()
            self.assertFalse(factory_issues.sync_owner(self.work.pk))
            self.work.refresh_from_db()
            self.assertEqual(self.work.source_head_id, assignment.requested_source_id)
            factory_coordinator.reconcile(self.a, self.work.pk, self.work.revision)
            self.assertTrue(factory_issues.sync_owner(self.work.pk))
            self.assertEqual(state['planning_calls'], 1)

    def test_current_role_grants_and_team_rule_version_are_required_for_recording(self):
        assignment = self.assign()
        Grant.objects.filter(user=self.a, case=self.c, action='issue.work').update(active=False)
        with self.assertRaises(PermissionDenied):
            self.reply(assignment)
        Grant.objects.filter(user=self.a, case=self.c, action='issue.work').update(active=True)
        value = deepcopy(self.value)
        value['teams'][0]['label'] = 'Changed team'
        newer = draft_operator_policy(self.a, self.c.pk, COMPONENT, value,
            self.e['policy_decision'].pk, timezone.now())
        transition(self.a, newer.pk, 'validated')
        transition(self.a, newer.pk, 'active')
        with self.assertRaises(ValidationError):
            self.reply(assignment)
        self.assertFalse(IssueTeamReply.objects.exists())

    def test_actual_recorder_cannot_be_replaced_by_a_different_case_reader(self):
        assignment = self.assign()
        other = get_user_model().objects.create_user('other-team-recorder')
        for action in ['case.read', 'issue.read', 'issue.work', 'issue.own', 'evidence.add', 'factory.read']:
            Grant.objects.create(user=other, case=self.c, action=action)
        with self.assertRaises(PermissionDenied):
            self.reply(assignment, actor=other)

    def test_distinct_configured_coordinator_records_without_agent_execution_authority(self):
        from tests.helpers import activate
        from apps.policy.services import register_reference
        from apps.policy.models import RegisteredReference
        coordinator = get_user_model().objects.create_user('sample-team-coordinator')
        for action in ['case.read', 'issue.read', 'issue.work', 'issue.own', 'evidence.add', 'factory.read']:
            Grant.objects.create(user=coordinator, case=self.c, action=action)
        register_reference(self.a, self.c.pk, 'sample-second-pm', 'schema:psl/role-assignment/v1',
            {'role': 'PM', 'user_id': coordinator.pk}, self.e['policy_decision'].pk)
        references = list(RegisteredReference.objects.filter(case=self.c,
            schema_ref='schema:psl/role-assignment/v1').values_list('ref', flat=True))
        activate(self.a, self.c, 'D05.role_principal_assignments', references, self.e['policy_decision'])
        assignment = self.assign(recorder_id=coordinator.pk)
        factory_issues.sync_owner(self.work.pk)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        task = factory_issues.tasks(self.work).get(status='open')
        factory_issues.respond(coordinator, self.work.pk, self.work.revision, rev(self.c), task.pk,
            task.revision, 'acknowledge', self.e['requirements'].pk, 'Engineering response received',
            'Investigate sample issue', team_reply={'assignment_id': assignment.pk, 'operation_key': uuid4(),
            'party': 'External Engineering responder', 'channel': 'email',
            'responded_at': timezone.now()-timedelta(minutes=1), 'source_ref': 'synthetic:coordinator-email'})
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        self.assertEqual(IssueTeamReply.objects.get().actor_id, coordinator.pk)
        self.assertFalse(Grant.objects.filter(user=coordinator, case=self.c, action='factory.execute').exists())

    def test_closed_policy_contract_refuses_unknown_choices_duplicate_keys_and_clock_invention(self):
        for changes in [dict(channels=['unconfigured']), dict(recorder_roles=['Made up role']),
                        dict(clock_basis='assumed_send_time'), dict(extra_rule='invented'),
                        dict(teams=[self.value['teams'][0], self.value['teams'][0]])]:
            with self.subTest(changes=tuple(changes)):
                value = dict(self.value, **changes)
                with self.assertRaises(ValidationError):
                    proposed = draft_operator_policy(self.a, self.c.pk, COMPONENT, value,
                        self.e['policy_decision'].pk, timezone.now())
                    transition(self.a, proposed.pk, 'validated')

    def test_legacy_native_update_cannot_record_an_external_team_reply_without_source_facts(self):
        from apps.pmo.issues import update_issue
        self.assign()
        self.issue.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'actual external team response'):
            update_issue(self.a, self.c.pk, self.issue.pk, self.issue.current_id, 'acknowledge',
                self.e['requirements'].pk, 'Legacy generic owner claim', rev(self.c), next_action='Investigate')
        self.assertFalse(IssueTeamReply.objects.exists())
        self.client.force_login(self.a)
        page = self.client.get(reverse('issues', args=[self.c.pk]))
        self.assertContains(page, 'SAMPLE Engineering')
        self.assertNotContains(page, 'Owner acknowledges')
        source = self.client.get(reverse('factory_create')+'?definition=pmo-issues/v1&case='+
            str(self.c.pk)+'&issue='+str(self.issue.pk))
        self.assertEqual(source.context['form'].fields['issue'].initial.pk, self.issue.pk)

    def test_reply_idempotency_preserves_exact_source_intent_and_stale_variants_are_refused(self):
        assignment = self.assign()
        self.issue.refresh_from_db()
        original = dict(state_id=self.issue.current_id, expected=rev(self.c), operation_key=uuid4(),
                        responded_at=timezone.now()-timedelta(minutes=1))
        reply = self.reply(assignment, **original)
        self.assertEqual(self.reply(assignment, **original).pk, reply.pk)
        with self.assertRaises(ValidationError):
            self.reply(assignment, **original, party='Changed source claim')
        self.assertEqual(IssueTeamReply.objects.count(), 1)

    def test_future_time_unknown_channel_resolution_and_private_proof_are_refused(self):
        assignment = self.assign()
        private = add_evidence(self.a, self.c.pk, 'agent_private_hr_contract', 'Private sample', 'synthetic:private')
        for changes in [dict(responded_at=timezone.now()+timedelta(days=1)), dict(channel='unconfigured'),
                        dict(operation='resolve'), dict(evidence_id=private.pk), dict(party=' '), dict(next_action='')]:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaises(ValidationError):
                    self.reply(assignment, **changes)
        self.assertFalse(IssueTeamReply.objects.exists())

    def test_append_only_rows_and_cross_project_assignment_are_enforced_by_postgresql(self):
        assignment = self.assign()
        reply = self.reply(assignment)
        for model, pk in [(IssueTeamAssignment, assignment.pk), (IssueTeamReply, reply.pk)]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=pk).update(actor_id=self.a.pk)
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute('DELETE FROM '+model._meta.db_table+' WHERE id=%s', [pk])
        from tests.helpers import setup_case, project_evidence
        actor, case = setup_case(username='other-project')
        other_proof = project_evidence(actor, case)['requirements']
        self.issue.refresh_from_db()
        with self.assertRaises(DatabaseError), transaction.atomic():
            IssueTeamAssignment.objects.create(issue=self.issue, state=self.issue.current, number=2,
                mode='internal', recorder=self.a, evidence=other_proof, reason='Forged scope', actor=self.a)

    def test_owner_form_get_is_read_only_and_post_continues_exact_existing_work(self):
        self.client.force_login(self.a)
        url = reverse('issue_team_owner', args=[self.c.pk, self.issue.pk])+'?work='+str(self.work.pk)
        before = rev(self.c)
        page = self.client.get(url)
        self.assertContains(page, 'Team without a factory account')
        self.assertEqual(rev(self.c), before)
        posted = self.client.post(url, {'mode': 'team', 'team_key': 'sample-engineering',
            'recorder': self.a.pk, 'recorder_role': 'PM', 'evidence': self.e['requirements'].pk,
            'reason': 'Synthetic reviewed external owner', 'state': self.issue.current_id,
            'revision': rev(self.c), 'work': self.work.pk, 'source': self.work.source_head_id})
        self.assertRedirects(posted, reverse('factory_detail', args=[self.work.pk]), fetch_redirect_response=False)
        self.assertEqual(IssueTeamAssignment.objects.count(), 1)
        self.work.refresh_from_db()
        self.assertNotEqual(self.work.source_head_id, IssueTeamAssignment.objects.get().requested_source_id)

    def test_team_rule_editor_preserves_existing_team_identity_and_creates_only_draft(self):
        self.client.force_login(self.a)
        url = reverse('issue_team_configuration', args=[self.c.pk])
        page = self.client.get(url)
        self.assertContains(page, 'SAMPLE Engineering')
        posted = self.client.post(url, {'recorder_roles': ['PM'], 'teams': 'SAMPLE Engineering',
            'channels': ['email'], 'evidence': self.e['policy_decision'].pk, 'revision': rev(self.c)})
        self.assertRedirects(posted, url)
        from apps.policy.services import reference_values
        from apps.policy.models import Configuration
        latest = Configuration.objects.filter(case=self.c, component=COMPONENT).latest('pk')
        self.assertEqual(latest.states.order_by('-pk').first().state, 'draft')
        self.assertEqual(reference_values(latest)[0]['teams'][0]['key'], 'sample-engineering')


class IssueTeamConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.entry = issue_helpers.FactoryIssueTests()
        self.entry.setUp()
        configure(self.entry)
        self.issue = self.entry.state.issue

    def assign(self):
        e = self.entry
        return issue_teams.assign(e.a, e.c.pk, self.issue.pk, e.state.pk, 'team',
            'sample-engineering', e.a.pk, 'PM', e.e['requirements'].pk, 'Concurrent sample assignment',
            e.c.revision, work_id=e.work.pk, source_id=e.work.source_head_id)

    def test_competing_assignments_record_only_one_current_owner_intent(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        self.assertEqual(connection.vendor, 'postgresql')
        rev(self.entry.c)
        barrier = Barrier(2)

        def attempt():
            try:
                barrier.wait(timeout=10)
                try:
                    return ('saved', self.assign().pk)
                except ValidationError:
                    return ('refused', None)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual([row[0] for row in outcomes].count('saved'), 1, outcomes)
        self.assertEqual(IssueTeamAssignment.objects.count(), 1)
        self.assertTrue(factory_issues.sync_owner(self.entry.work.pk))

    def test_busy_work_row_refuses_without_waiting_on_its_case_lock(self):
        from threading import Event, Thread
        from apps.workflows.models import FactoryWork

        locked, release = Event(), Event()
        rev(self.entry.c)

        def own_work():
            try:
                with transaction.atomic():
                    FactoryWork.objects.select_for_update().get(pk=self.entry.work.pk)
                    locked.set()
                    release.wait(timeout=15)
            finally:
                connections.close_all()

        worker = Thread(target=own_work)
        worker.start()
        try:
            self.assertTrue(locked.wait(timeout=5))
            with self.assertRaisesMessage(ValidationError, 'busy or unavailable'):
                self.assign()
            self.assertFalse(IssueTeamAssignment.objects.exists())
        finally:
            release.set()
            worker.join(timeout=15)

    def test_competing_exact_external_replies_have_one_native_successor(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        rev(self.entry.c)
        assignment = self.assign()
        self.issue.refresh_from_db()
        expected = rev(self.entry.c)
        key, source_time, barrier = uuid4(), timezone.now()-timedelta(minutes=1), Barrier(2)

        def record():
            try:
                barrier.wait(timeout=10)
                return issue_teams.record_reply(self.entry.a, self.entry.c.pk, self.issue.pk,
                    self.issue.current_id, assignment.pk, key, 'acknowledge', self.entry.e['requirements'].pk,
                    'Synthetic concurrent team reply', 'Investigate cause', 'Sample Engineering', 'email',
                    source_time, 'synthetic:concurrent-email', expected).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: record(), range(2)))
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(IssueTeamReply.objects.count(), 1)
