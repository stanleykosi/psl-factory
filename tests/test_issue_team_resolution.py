"""External fix facts join native severity, closure, clocks and current authority."""
import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import issue_teams, issues
from apps.pmo.issue_team_models import IssueTeamReply
from apps.policy.issue_team_validators import COMPONENT, SCHEMA, SCHEMA_V2, validate_value
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition, register_reference, resolve
from tests.helpers import rev, activate
from tests import test_issue_teams as team_helpers


class IssueTeamResolutionTests(TestCase):
    setUp = team_helpers.IssueTeamTests.setUp
    assign = team_helpers.IssueTeamTests.assign
    reply = team_helpers.IssueTeamTests.reply

    def configure_resolution(self, **changes):
        value = json.loads(Path('fixtures/issue-team-resolution-controls.json').read_text())['value']
        value.update(changes)
        config = draft_operator_policy(self.a, self.c.pk, COMPONENT, value,
                                      self.e['policy_decision'].pk, timezone.now())
        transition(self.a, config.pk, 'validated')
        transition(self.a, config.pk, 'active')
        self.assertEqual(config.envelope['value']['schema_ref'], SCHEMA_V2)
        return config

    def prepared(self, **changes):
        self.configure_resolution(**changes)
        assignment = self.assign()
        self.reply(assignment)
        self.issue.refresh_from_db()
        issues.update_issue(self.a, self.c.pk, self.issue.pk, self.issue.current_id, 'manage',
            self.e['requirements'].pk, 'Project manager assessed severity', rev(self.c), severity='Critical')
        self.fix = add_evidence(self.a, self.c.pk, 'resolution', 'Synthetic documented fix', 'synthetic:team-fix')
        self.root = add_evidence(self.a, self.c.pk, 'root_cause', 'Synthetic documented cause', 'synthetic:team-cause')
        return assignment

    def resolve(self, assignment, **changes):
        return self.reply(assignment, operation='resolve', fix_id=self.fix.pk, root_cause_id=self.root.pk,
                          resolution_role='PM', **changes)

    def qa(self):
        qa = get_user_model().objects.create_user('separate-synthetic-quality-reviewer')
        for action in ['case.read','issue.read','issue.close_log','evidence.add']:
            Grant.objects.create(user=qa, case=self.c, action=action)
        ref = register_reference(self.a, self.c.pk, 'sample:quality-role', 'schema:psl/role-assignment/v1',
                                 {'role':'QA','user_id':qa.pk}, self.e['policy_decision'].pk)
        current = resolve('D05.role_principal_assignments', self.c).configuration
        activate(self.a, self.c, current.component, current.envelope['value']+[ref.ref], self.e['policy_decision'])
        return qa

    def test_team_fix_requires_both_native_closure_roles_and_keeps_actual_reply_time(self):
        qa = self.qa()
        assignment = self.prepared()
        reply = self.resolve(assignment)
        self.assertEqual(issue_teams.validate_reply(reply,self.issue).pk,reply.pk)
        self.assertLess(reply.responded_at,reply.state.resolved_at)
        self.assertEqual(reply.state.status,'Resolved')
        self.assertEqual(reply.state.fix_id,self.fix.pk)
        with self.assertRaises(PermissionDenied):
            issues.close_issue_log(self.a,self.c.pk,self.issue.pk,reply.state_id,'QA',self.fix.pk,'Cannot impersonate QA',rev(self.c))
        issues.close_issue_log(qa,self.c.pk,self.issue.pk,reply.state_id,'QA',self.fix.pk,'Quality checked exact fix',rev(self.c))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.current.status,'Resolved')
        issues.close_issue_log(self.a,self.c.pk,self.issue.pk,reply.state_id,'PM',self.fix.pk,'Project manager closure',rev(self.c))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.current.status,'Closed')
        self.assertEqual(set(reply.state.closure_entries.values_list('actor_id',flat=True)),{qa.pk,self.a.pk})
        self.assertEqual(IssueTeamReply.objects.filter(operation='resolve').count(),1)
        self.client.force_login(self.a)
        page=self.client.get(reverse('issues',args=[self.c.pk]))
        self.assertContains(page,'No further action')
        self.assertContains(page,'View follow-up history')
        self.assertNotContains(page,'Review issue owner or external team')
        self.assertNotContains(page,'Open issue follow-up')

    def test_legacy_rules_allow_progress_but_do_not_invent_resolution_authority_or_ack_clock(self):
        assignment = self.assign()
        self.reply(assignment)
        self.reply(assignment,operation='start')
        with self.assertRaises(ValidationError):
            self.reply(assignment,operation='resolve',resolution_role='PM')
        self.issue.refresh_from_db()
        self.assertEqual(issue_teams.acknowledgement_clock(self.issue)['status'],'unknown')
        self.assertEqual(self.issue.current.status,'In Progress')

    def test_withdrawn_quality_authority_holds_final_closure_without_erasing_its_log(self):
        qa=self.qa()
        assignment=self.prepared()
        reply=self.resolve(assignment)
        issues.close_issue_log(qa,self.c.pk,self.issue.pk,reply.state_id,'QA',self.fix.pk,'Quality checked fix',rev(self.c))
        Grant.objects.filter(user=qa,case=self.c,action='issue.close_log').update(active=False)
        with self.assertRaises(PermissionDenied):
            issues.close_issue_log(self.a,self.c.pk,self.issue.pk,reply.state_id,'PM',self.fix.pk,'Final closure attempt',rev(self.c))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.current.status,'Resolved')
        self.assertEqual(reply.state.closure_entries.count(),1)

    def test_versioned_policy_is_closed_and_owner_slots_can_remain_empty(self):
        v1 = json.loads(Path('fixtures/issue-team-controls.json').read_text())['value']
        v2 = dict(v1,resolution_recorder_roles=[],acknowledgement_clock=None)
        validate_value(v1,SCHEMA)
        validate_value(v2,SCHEMA_V2)
        for value,schema in [(v2,SCHEMA),(dict(v2,acknowledgement_clock='guessed_send_time'),SCHEMA_V2),
                             (dict(v2,resolution_recorder_roles=['Invented']),SCHEMA_V2),
                             (dict(v2,extra=True),SCHEMA_V2),(v2,'unknown-version')]:
            with self.subTest(schema=schema,value=value),self.assertRaises(ValidationError):
                validate_value(value,schema)
        self.configure_resolution(resolution_recorder_roles=[],acknowledgement_clock=None)
        assignment=self.assign()
        self.reply(assignment)
        self.issue.refresh_from_db()
        self.assertFalse(issue_teams.projection(self.a,self.issue)['can_resolve'])

    def test_resolution_requires_exact_current_public_fix_and_critical_root_cause(self):
        assignment=self.prepared()
        for values in [dict(root_cause_id=None),dict(fix_id=self.e['requirements'].pk),dict(fix_id=True),
                       dict(root_cause_id=self.e['requirements'].pk),dict(resolution_role='QA')]:
            args=dict(operation='resolve',fix_id=self.fix.pk,root_cause_id=self.root.pk,resolution_role='PM')
            args.update(values)
            with self.subTest(values=values),self.assertRaises((PermissionDenied,ValidationError)):
                self.reply(assignment,**args)
        private=add_evidence(self.a,self.c.pk,'hr_finance_snapshot','Private source','synthetic:private')
        with self.assertRaises(ValidationError):
            self.reply(assignment,operation='resolve',fix_id=private.pk,root_cause_id=self.root.pk,resolution_role='PM')
        self.assertFalse(IssueTeamReply.objects.filter(operation='resolve').exists())

    def test_resolution_retry_stale_intent_and_current_authority(self):
        assignment=self.prepared()
        self.issue.refresh_from_db()
        original=dict(state_id=self.issue.current_id,expected=rev(self.c),operation_key=uuid4(),
                      responded_at=timezone.now()-timedelta(minutes=1))
        reply=self.resolve(assignment,**original)
        self.assertEqual(self.resolve(assignment,**original).pk,reply.pk)
        with self.assertRaises(ValidationError):
            self.resolve(assignment,**original,source_ref='synthetic:different-resolution')
        Grant.objects.filter(user=self.a,case=self.c,action='issue.work').update(active=False)
        with self.assertRaises(PermissionDenied):
            issue_teams.validate_reply(reply,self.issue)
        self.assertEqual(IssueTeamReply.objects.filter(operation='resolve').count(),1)

    def test_postgresql_scope_guard_refuses_forged_resolution_and_history_rewrite(self):
        assignment=self.assign()
        reply=self.reply(assignment)
        with self.assertRaises(DatabaseError),transaction.atomic():
            IssueTeamReply.objects.create(assignment=assignment,state=assignment.state,operation_key=uuid4(),
                intent_sha256='a'*64,operation='resolve',party='Sample team',channel='email',
                responded_at=timezone.now(),source_ref='synthetic:forged',evidence=assignment.evidence,
                proof_sha256=assignment.evidence.sha256,authority={'protocol':'issue-team-resolution-authority/v1',
                'role':'PM','policies':{}},actor=self.a)
        with self.assertRaises(DatabaseError),transaction.atomic():
            IssueTeamReply.objects.filter(pk=reply.pk).update(operation='resolve')

    def test_source_clock_and_recording_clock_are_explicit_and_preserve_urgency_routes(self):
        from tests.test_escalations import clocks,profile
        from apps.pmo.escalations import timing
        self.configure_resolution()
        assignment=self.assign()
        source_at=timezone.now()-timedelta(hours=2,minutes=30)
        reply=self.reply(assignment,responded_at=source_at)
        self.issue.refresh_from_db()
        clocks(self.a,self.c,self.e['policy_decision'])
        p=profile(self.a,self.c,self.issue.current,self.e['requirements'],impact=True,
                  trigger=timezone.now()-timedelta(hours=3))
        actual=timing(p)
        self.assertEqual(actual['acknowledgement_status'],'ON_TIME')
        self.assertEqual(actual['acknowledgement_at'],source_at.isoformat())
        self.assertEqual(actual['acknowledgement_clock']['reply_id'],reply.pk)
        self.assertTrue(actual['immediate'])
        self.configure_resolution(acknowledgement_clock='recorded_at')
        assignment=self.assign()
        self.issue.refresh_from_db()
        held=issue_teams.acknowledgement_clock(self.issue)
        self.assertEqual(held['status'],'unknown')
        self.assertIn('current team has no',held['finding'])
        self.assertEqual(timing(p)['acknowledgement_status'],'UNKNOWN')

    def test_resolution_and_settings_forms_reuse_native_services_and_reject_extra_fields(self):
        assignment=self.prepared()
        self.issue.refresh_from_db()
        self.client.force_login(self.a)
        url=reverse('issue_team_resolution',args=[self.c.pk,self.issue.pk])
        page=self.client.get(url)
        self.assertContains(page,'Record resolution for closure checks')
        self.assertContains(page,'Africa/Lagos')
        d={'state':self.issue.current_id,'assignment':assignment.pk,'revision':rev(self.c),'operation_key':str(uuid4()),
           'party':'Synthetic Engineering','channel':'email','responded_at':(timezone.now()-timedelta(minutes=1)).isoformat(),
           'source_ref':'synthetic:form-fix','evidence':self.e['requirements'].pk,'fix':self.fix.pk,'root_cause':self.root.pk,
           'resolution_role':'PM','note':'Source fix checked','next_action':'Quality assurance closure checks'}
        self.assertContains(self.client.post(url,dict(d,pretend_approval='yes')),'displayed resolution fields')
        self.assertFalse(IssueTeamReply.objects.filter(operation='resolve').exists())
        self.assertRedirects(self.client.post(url,d),reverse('issues',args=[self.c.pk]))
        page=self.client.get(reverse('issues',args=[self.c.pk]))
        self.assertContains(page,'Synthetic Engineering')
        self.assertContains(page,'actual reply')
        settings=self.client.get(reverse('issue_team_configuration',args=[self.c.pk]))
        self.assertContains(settings,'Roles allowed to record team resolutions')

    def test_recording_clock_and_agent_findings_use_the_same_current_native_profile(self):
        from tests.test_escalations import clocks,profile
        from apps.pmo.escalations import timing
        from apps.agents.escalations import investigate_escalations
        self.configure_resolution(acknowledgement_clock='recorded_at')
        assignment=self.assign()
        reply=self.reply(assignment,responded_at=timezone.now()-timedelta(hours=2,minutes=30))
        self.issue.refresh_from_db()
        clocks(self.a,self.c,self.e['policy_decision'])
        p=profile(self.a,self.c,self.issue.current,self.e['requirements'],trigger=timezone.now()-timedelta(hours=3))
        result=timing(p)
        self.assertEqual(result['acknowledgement_status'],'LATE')
        self.assertEqual(result['acknowledgement_at'],reply.state.acknowledged_at.isoformat())
        run=investigate_escalations(self.a,self.c.pk,rev(self.c),[p.pk])
        self.assertFalse(run.result['approval_granted'])
        self.assertFalse(run.result['communications_dispatched'])
        self.assertEqual(run.result['findings'][0]['timing']['acknowledgement_clock']['reply_id'],reply.pk)
        self.client.force_login(self.a)
        page=self.client.get(reverse('escalations',args=[self.c.pk]))
        self.assertContains(page,'Assessed reply time')
        self.assertContains(page,'time the acknowledgement was recorded in the factory')

    def test_reopened_issue_does_not_reuse_the_previous_cycle_acknowledgement(self):
        from tests.document_helpers import artifact
        qa=self.qa()
        assignment=self.prepared()
        reply=self.resolve(assignment)
        for actor,role in [(qa,'QA'),(self.a,'PM')]:
            issues.close_issue_log(actor,self.c.pk,self.issue.pk,reply.state_id,role,self.fix.pk,'Exact closure',rev(self.c))
        self.issue.refresh_from_db()
        artifact(self.a,self.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
                 {'rules':[{'role':'PM','actions':['reopen']}]},self.e['policy_decision'])
        issues.reopen_issue(self.a,self.c.pk,self.issue.pk,self.issue.current_id,'PM',self.fix.pk,
            'Synthetic new occurrence','Investigate new occurrence',rev(self.c))
        self.issue.refresh_from_db()
        clock=issue_teams.acknowledgement_clock(self.issue)
        self.assertEqual(clock['status'],'known')
        self.assertIsNone(clock['at'])
        self.assertIsNone(clock['reply_id'])
        new_reply=self.reply(assignment,source_ref='synthetic:new-occurrence')
        self.issue.refresh_from_db()
        clock=issue_teams.acknowledgement_clock(self.issue)
        self.assertEqual(clock['reply_id'],new_reply.pk)
        self.assertEqual(clock['at'],new_reply.responded_at)


class IssueTeamResolutionConcurrencyTests(TransactionTestCase):
    setUp = team_helpers.IssueTeamTests.setUp
    assign = team_helpers.IssueTeamTests.assign
    reply = team_helpers.IssueTeamTests.reply
    configure_resolution = IssueTeamResolutionTests.configure_resolution
    prepared = IssueTeamResolutionTests.prepared
    resolve = IssueTeamResolutionTests.resolve

    def test_competing_resolution_retries_keep_one_exact_native_successor(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        assignment=self.prepared()
        self.issue.refresh_from_db()
        state,expected,key=self.issue.current_id,rev(self.c),uuid4()
        at,barrier=timezone.now()-timedelta(minutes=1),Barrier(2)

        def record():
            try:
                barrier.wait(timeout=10)
                return issue_teams.record_reply(self.a,self.c.pk,self.issue.pk,state,assignment.pk,key,
                    'resolve',self.e['requirements'].pk,'Same synthetic fix','Quality closure',
                    'Sample Engineering','email',at,'synthetic:concurrent-fix',expected,
                    fix_id=self.fix.pk,root_cause_id=self.root.pk,resolution_role='PM').pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            values=list(pool.map(lambda _:record(),range(2)))
        self.assertEqual(values[0],values[1])
        self.assertEqual(IssueTeamReply.objects.filter(operation='resolve').count(),1)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.current.status,'Resolved')
