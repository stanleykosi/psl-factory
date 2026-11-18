"""Real owner-message preparation, decisions, effects and original receipt recovery."""
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from adapters.issue_messages import SyntheticIssueMailbox, expected_receipt
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import issue_messages as messages, issues
from apps.pmo.issue_message_models import (IssueMessageDraft, IssueMessageReview, IssueMessageDispatch,
    IssueMessageAttempt, IssueMessageReceipt, IssueMessageCancellation, SyntheticIssueMessage)
from apps.policy.issue_message_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests import test_issue_teams as team_helpers
from tests.helpers import rev


def configure(entry,**changes):
    from tests.document_helpers import artifact
    from apps.policy.services import resolve
    if resolve('D05.decision_action_matrix',entry.c).status!='ACTIVE':
        artifact(entry.a,entry.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
                 {'rules':[{'role':'PM','actions':['return','reject']}]},entry.e['policy_decision'])
    value=json.loads(Path('fixtures/issue-message-controls.json').read_text())['value']
    value.update(changes)
    config=draft_operator_policy(entry.a,entry.c.pk,COMPONENT,value,
        entry.e['policy_decision'].pk,timezone.now())
    transition(entry.a,config.pk,'validated');transition(entry.a,config.pk,'active')
    return config,value


class IssueMessageTests(TestCase):
    def setUp(self):
        team_helpers.IssueTeamTests.setUp(self)
        self.assignment=team_helpers.IssueTeamTests.assign(self)
        self.message_config,self.message_value=configure(self)

    def draft(self,**changes):
        self.issue.refresh_from_db()
        args=dict(actor=self.a,case_id=self.c.pk,issue_id=self.issue.pk,state_id=self.issue.current_id,
                  kind='request',operation_key=uuid4(),expected=rev(self.c))
        args.update(changes)
        return messages.prepare(**args)

    def review(self,draft,**changes):
        args=dict(actor=self.a,case_id=self.c.pk,draft_id=draft.pk,role='PM',verdict='approve',
            evidence_id=self.e['requirements'].pk,rationale='Reviewed exact synthetic owner message',expected=rev(self.c))
        args.update(changes)
        return messages.review(**args)

    def release(self,entry,**changes):
        args=dict(actor=self.a,case_id=self.c.pk,review_id=entry.pk,role='PM',channel='email',expected=rev(self.c))
        args.update(changes)
        return messages.release(**args)

    def released(self):
        return self.release(self.review(self.draft()))

    def manual(self):
        value=deepcopy(self.message_value)
        value['routes'][0]['mode']='manual_evidence'
        configure(self,**value)
        dispatch=self.released()
        messages.begin_manual(self.a,self.c.pk,dispatch.pk,rev(self.c))
        return dispatch

    def test_draft_review_release_receipt_is_not_owner_acknowledgement(self):
        self.assertTrue(Grant.objects.filter(user=self.a,case=self.c,action='issue.message.prepare').exists())
        draft=self.draft()
        self.assertIn(self.issue.reference,draft.body)
        self.assertIn('SAMPLE Engineering',draft.source['team_label'])
        self.assertFalse(draft.run.result['communications_dispatched'])
        dispatch=self.release(self.review(draft))
        self.assertEqual(messages.status(dispatch)[0],'Queued')
        self.assertTrue(messages.run_once(dispatch.pk))
        receipt=IssueMessageReceipt.objects.get(dispatch=dispatch)
        self.assertTrue(receipt.delivered)
        self.assertEqual(SyntheticIssueMessage.objects.count(),1)
        self.assertEqual(messages.status(dispatch)[0],'Delivered')
        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.current.acknowledged_at)
        self.assertFalse(messages.run_once(dispatch.pk))
        facts=messages.chronology(self.a,self.c,self.issue.pk)
        self.assertEqual(facts['reminder_due_at'],receipt.delivered_at+timedelta(hours=1))
        self.assertEqual(facts['escalation_due_at'],receipt.delivered_at+timedelta(hours=2))

    def test_exact_retries_return_original_records_and_conflicting_intents_are_refused(self):
        self.issue.refresh_from_db()
        op,revision=uuid4(),rev(self.c)
        draft=self.draft(operation_key=op,expected=revision)
        self.assertEqual(self.draft(operation_key=op,expected=revision).pk,draft.pk)
        with self.assertRaises(ValidationError):self.draft(operation_key=op,kind='reminder')
        revision=rev(self.c)
        entry=self.review(draft,expected=revision)
        self.assertEqual(self.review(draft,expected=revision).pk,entry.pk)
        with self.assertRaises(ValidationError):self.review(draft,verdict='return')
        revision=rev(self.c)
        dispatch=self.release(entry,expected=revision)
        self.assertEqual(self.release(entry,expected=revision).pk,dispatch.pk)
        with self.assertRaises(ValidationError):self.release(entry,not_before=timezone.now()+timedelta(days=1))
        self.assertEqual(IssueMessageDraft.objects.count(),1)
        self.assertEqual(IssueMessageDispatch.objects.count(),1)

    def test_returned_wording_needs_a_new_source_bound_revision(self):
        draft=self.draft()
        returned=self.review(draft,verdict='return')
        with self.assertRaises(ValidationError):self.release(returned)
        edited=self.draft(previous_id=draft.pk,body='Please confirm this sample issue and provide its supporting evidence.',
            evidence_id=self.e['requirements'].pk,reason='Human corrected the proposed wording')
        self.assertEqual(edited.previous_id,draft.pk)
        with self.assertRaises(ValidationError):self.review(draft)
        dispatch=self.release(self.review(edited))
        messages.run_once(dispatch.pk)
        self.assertEqual(IssueMessageReceipt.objects.get().dispatch.payload['body'],edited.body)

    def test_missing_owner_values_hold_only_review_release_or_timing(self):
        transition(self.a,self.message_config.pk,'revoked')
        draft=self.draft()
        with self.assertRaises(ValidationError):self.review(draft)
        configure(self,independent_release=None)
        reviewed=self.review(draft)
        with self.assertRaisesMessage(ValidationError,'different people'):self.release(reviewed)
        self.assertFalse(IssueMessageDispatch.objects.exists())
        self.assertFalse(IssueMessageAttempt.objects.exists())

    def test_current_reviewer_preparer_and_sender_authority_are_required_before_effect(self):
        for action in ['issue.message.prepare','issue.message.review','issue.message.release']:
            draft=self.draft()
            entry=self.review(draft)
            dispatch=self.release(entry)
            Grant.objects.filter(user=self.a,case=self.c,action=action).update(active=False)
            self.assertFalse(messages.run_once(dispatch.pk))
            self.assertEqual(messages.status(dispatch)[0],'Needs review')
            self.assertFalse(IssueMessageAttempt.objects.filter(dispatch=dispatch).exists())
            Grant.objects.filter(user=self.a,case=self.c,action=action).update(active=True)
            messages.cancel(self.a,self.c.pk,dispatch.pk,'PM','Retire unsent authority test',rev(self.c))
        self.assertFalse(SyntheticIssueMessage.objects.exists())

    def test_lost_provider_response_recovers_one_original_message_without_resend(self):
        class Interrupted(SyntheticIssueMailbox):
            calls=0
            def deliver(self,dispatch):
                self.calls+=1
                super().deliver(dispatch)
                raise TimeoutError('Synthetic response lost after actual sample acceptance')
        adapter=Interrupted()
        dispatch=self.released()
        self.assertTrue(messages.run_once(dispatch.pk,adapter))
        self.assertEqual(messages.status(dispatch)[0],'Receipt needed')
        self.assertEqual(SyntheticIssueMessage.objects.count(),1)
        with self.assertRaises(ValidationError):
            messages.cancel(self.a,self.c.pk,dispatch.pk,'PM','Cannot cancel an uncertain send',rev(self.c))
        self.assertTrue(messages.run_once(dispatch.pk,adapter,lookup_only=True))
        self.assertTrue(IssueMessageReceipt.objects.get(dispatch=dispatch).delivered)
        self.assertEqual(adapter.calls,1)

    def test_future_schedule_and_source_change_do_not_send_and_unsent_release_can_be_cancelled(self):
        dispatch=self.release(self.review(self.draft()),not_before=timezone.now()+timedelta(days=1))
        self.assertEqual(messages.status(dispatch)[0],'Scheduled')
        self.assertFalse(messages.run_once(dispatch.pk))
        self.issue.refresh_from_db()
        issues.update_issue(self.a,self.c.pk,self.issue.pk,self.issue.current_id,'manage',
            self.e['requirements'].pk,'Changed source facts',rev(self.c),next_action='New source next action')
        self.assertEqual(messages.status(dispatch)[0],'Needs review')
        messages.cancel(self.a,self.c.pk,dispatch.pk,'PM','Cancel exact unsent stale source',rev(self.c))
        self.assertEqual(messages.status(dispatch)[0],'Cancelled')
        self.assertFalse(IssueMessageAttempt.objects.exists())
        self.client.force_login(self.a)
        response=self.client.get(reverse('issue_message_detail',args=[self.c.pk,self.issue.pk,dispatch.review.draft_id]))
        self.assertContains(response,'Cancel exact unsent stale source')
        self.assertContains(response,'Cancelled by')

    def test_reminder_waits_for_configured_interval_and_does_not_move_the_first_escalation_deadline(self):
        dispatch=self.released()
        messages.run_once(dispatch.pk)
        first=IssueMessageReceipt.objects.get(dispatch=dispatch)
        reminder=self.release(self.review(self.draft(kind='reminder')))
        self.assertEqual(reminder.not_before,first.delivered_at+timedelta(hours=1))
        self.assertFalse(messages.run_once(reminder.pk))
        facts=messages.chronology(self.a,self.c,self.issue.pk)
        self.assertEqual(facts['escalation_due_at'],first.delivered_at+timedelta(hours=2))
        with self.assertRaises(ValidationError):self.draft()

    def test_manual_original_receipt_is_exact_and_keeps_unknown_time_unknown(self):
        dispatch=self.manual()
        reference='synthetic:manual-owner-receipt'
        payload=expected_receipt(dispatch,reference,True,None)
        evidence=add_evidence(self.a,self.c.pk,'issue_message_receipt',json.dumps(payload),'synthetic:manual-receipt')
        result=messages.confirm(self.a,self.c.pk,dispatch.pk,'PM',evidence.pk,reference,True,None,rev(self.c))
        self.assertTrue(result.delivered)
        self.assertIsNone(result.delivered_at)
        self.assertEqual(result.clock_source,'human_attested')
        facts=messages.chronology(self.a,self.c,self.issue.pk)
        self.assertIsNone(facts['reminder_due_at'])
        self.assertIn('actual delivery time',facts['finding'])
        self.assertEqual(facts['reminder_hold'],'Delivery time needed')
        self.assertEqual(facts['escalation_target'],'CTO')
        self.assertEqual(facts['last_delivery'].pk,result.pk)

    def test_manual_receipt_refuses_changed_payload_future_time_and_pre_send_clock(self):
        dispatch=self.manual()
        reference='synthetic:manual-clock'
        for at in [timezone.now()+timedelta(days=1),timezone.now()-timedelta(days=1)]:
            value={'operation':str(dispatch.operation),'sha256':dispatch.sha256,
                'recipient':dispatch.payload['recipient'],'channel':'email','reference':reference,
                'delivered':True,'delivered_at':at.isoformat()}
            evidence=add_evidence(self.a,self.c.pk,'issue_message_receipt',json.dumps(value),'synthetic:bad-clock')
            with self.assertRaises(ValidationError):
                messages.confirm(self.a,self.c.pk,dispatch.pk,'PM',evidence.pk,reference,True,at,rev(self.c))
        self.assertFalse(IssueMessageReceipt.objects.exists())

    def test_unknown_reminder_clock_keeps_the_first_request_deadline_and_configured_destination(self):
        value=deepcopy(self.message_value)
        value['routes'][0]['mode']='manual_evidence'
        value['reminder_after_hours']=1/3600000  # One millisecond, synthetic only.
        configure(self,**value)
        first=self.released()
        messages.begin_manual(self.a,self.c.pk,first.pk,rev(self.c))
        source=add_evidence(self.a,self.c.pk,'document','Synthetic first request delivered.','synthetic:first-delivery')
        original=messages.attest(self.a,self.c.pk,first.pk,'PM',source.pk,'synthetic:first',True,
            timezone.now(),True,rev(self.c))
        reminder=self.release(self.review(self.draft(kind='reminder')))
        messages.begin_manual(self.a,self.c.pk,reminder.pk,rev(self.c))
        source=add_evidence(self.a,self.c.pk,'document','Synthetic reminder delivered, actual time unknown.','synthetic:reminder')
        last=messages.attest(self.a,self.c.pk,reminder.pk,'PM',source.pk,'synthetic:reminder',True,None,True,rev(self.c))
        facts=messages.chronology(self.a,self.c,self.issue.pk)
        self.assertEqual(facts['last_delivery'].pk,last.pk)
        self.assertIsNone(facts['reminder_due_at'])
        self.assertEqual(facts['escalation_due_at'],original.delivered_at+timedelta(hours=2))
        self.assertEqual(facts['escalation_target'],'CTO')
        self.client.force_login(self.a)
        response=self.client.get(reverse('issue_messages',args=[self.c.pk,self.issue.pk]))
        self.assertContains(response,'Delivery time needed')
        self.assertContains(response,'Chief technology officer')
        self.assertNotContains(response,'Awaiting timing decision')
        response=self.client.get(reverse('issue_message_detail',args=[self.c.pk,self.issue.pk,reminder.review.draft_id]))
        self.assertContains(response,'Delivered')
        self.assertNotContains(response,'The source, owner or drafting authority changed.')

    def test_postgresql_append_and_scope_guards_cover_native_message_chain(self):
        draft=self.draft()
        with self.assertRaises(DatabaseError),transaction.atomic():
            IssueMessageDraft.objects.filter(pk=draft.pk).update(body='Rewritten proposal')
        dispatch=self.release(self.review(draft))
        with self.assertRaises(DatabaseError),transaction.atomic():
            IssueMessageReceipt.objects.create(dispatch=dispatch,reference='fake-no-send',delivered=True,
                clock_source='synthetic_mailbox',actor=self.a)
        messages.cancel(self.a,self.c.pk,dispatch.pk,'PM','Unsent test cancellation',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            IssueMessageAttempt.objects.create(dispatch=dispatch)
        self.assertEqual(IssueMessageCancellation.objects.count(),1)

    def test_policy_refuses_fake_roles_channels_and_non_sample_mailbox_destinations(self):
        for changes in [dict(sender_roles=['Invented']),dict(clock_basis='guessed_send_time'),
                        dict(reminder_after_hours=0),dict(reminder_after_hours=2,escalation_after_hours=1),
                        dict(routes=[dict(self.message_value['routes'][0],destination='real@example.com')]),
                        dict(routes=[self.message_value['routes'][0],self.message_value['routes'][0]])]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                configure(self,**changes)

    def test_absence_recovery_fences_a_late_effect_before_a_fresh_reviewed_request(self):
        class NeverAccepted(SyntheticIssueMailbox):
            def deliver(self,dispatch):raise TimeoutError('Connection lost before provider acceptance')
        dispatch=self.released()
        messages.run_once(dispatch.pk,NeverAccepted())
        self.assertFalse(SyntheticIssueMessage.objects.exists())
        receipt=messages.recover(self.a,self.c.pk,dispatch.pk,'PM',rev(self.c))
        self.assertFalse(receipt.delivered)
        self.assertFalse(SyntheticIssueMailbox().deliver(dispatch)['delivered'])
        self.assertEqual(SyntheticIssueMessage.objects.count(),1)
        successor=self.released()
        self.assertNotEqual(successor.operation,dispatch.operation)
        messages.run_once(successor.pk)
        self.assertTrue(IssueMessageReceipt.objects.get(dispatch=successor).delivered)

    def test_human_receipt_attestation_keeps_original_proof_and_is_private_to_message_readers(self):
        from apps.core.evidence_access import public_evidence,public_timeline
        dispatch=self.manual()
        origin=add_evidence(self.a,self.c.pk,'document','SYNTHETIC channel receipt for the exact owner message.',
                            'synthetic:owner-channel-proof')
        receipt=messages.attest(self.a,self.c.pk,dispatch.pk,'PM',origin.pk,'synthetic:checked-receipt',
                               True,None,True,rev(self.c))
        self.assertEqual(receipt.source_evidence_id,origin.pk)
        self.assertEqual(receipt.source_sha256,origin.sha256)
        self.assertEqual(messages.receipt_current(self.a,receipt).pk,receipt.pk)
        self.assertFalse(public_evidence(self.c.evidence.filter(pk=receipt.evidence_id)).exists())
        self.assertFalse(public_timeline(self.c).filter(action__startswith='issue.message.').exists())
        with self.assertRaises(DatabaseError),transaction.atomic():
            IssueMessageReceipt.objects.filter(pk=receipt.pk).update(source_sha256='0'*64)

    def test_unchecked_private_or_oversized_receipt_source_is_refused_without_a_wrapper(self):
        from unittest.mock import patch,PropertyMock
        from apps.core.models import Evidence
        dispatch=self.manual()
        private=add_evidence(self.a,self.c.pk,'ledger_source','Private Finance content','synthetic:private')
        with self.assertRaises(ValidationError):
            messages.attest(self.a,self.c.pk,dispatch.pk,'PM',private.pk,'private',True,None,True,rev(self.c))
        source=add_evidence(self.a,self.c.pk,'document','Public channel proof','synthetic:channel')
        with self.assertRaises(ValidationError):
            messages.attest(self.a,self.c.pk,dispatch.pk,'PM',source.pk,'unchecked',True,None,False,rev(self.c))
        oversized=add_evidence(self.a,self.c.pk,'issue_message_receipt','x'*32001,'synthetic:oversize')
        with patch.object(Evidence,'body',new_callable=PropertyMock,side_effect=AssertionError('Oversized payload loaded')):
            with self.assertRaises(ValidationError):messages.receipt_proof(self.a,self.c,oversized.pk)
        self.assertFalse(IssueMessageReceipt.objects.exists())
        self.assertEqual(self.c.evidence.filter(source='psl:human-owner-message-attestation').count(),0)

    def test_source_metadata_stays_deferred_and_withdrawn_original_reader_blocks_body_loading(self):
        from django.contrib.auth import get_user_model
        from unittest.mock import patch,PropertyMock
        issue,assignment=messages.source(self.a,self.c,self.issue.pk)
        self.assertIn('body',issue.current.evidence.get_deferred_fields())
        draft=self.draft()
        reader=get_user_model().objects.create_user('message-evidence-reader')
        for action in ['case.read','issue.read','issue.message.read']:
            Grant.objects.create(user=reader,case=self.c,action=action)
        Grant.objects.filter(user=self.a,case=self.c,action='issue.message.read').update(active=False)
        self.client.force_login(reader)
        with patch.object(IssueMessageDraft,'body',new_callable=PropertyMock,side_effect=AssertionError('Unauthorised body loaded')):
            response=self.client.get(reverse('issue_message_detail',args=[self.c.pk,self.issue.pk,draft.pk]))
        self.assertEqual(response.status_code,403)

    def test_distinct_current_sender_is_required_when_independent_release_is_chosen(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import register_reference,resolve
        from tests.helpers import activate
        sender=get_user_model().objects.create_user('separate-message-sender')
        for action in ['case.read','issue.read','issue.message.read','issue.message.release','issue.message.recover']:
            Grant.objects.create(user=sender,case=self.c,action=action)
        role=register_reference(self.a,self.c.pk,'synthetic:message-sender','schema:psl/role-assignment/v1',
            {'role':'PM','user_id':sender.pk},self.e['policy_decision'].pk)
        assignment=resolve('D05.role_principal_assignments',self.c).configuration
        activate(self.a,self.c,assignment.component,assignment.envelope['value']+[role.ref],self.e['policy_decision'])
        self.assignment=team_helpers.IssueTeamTests.assign(self)
        configure(self,independent_release=True)
        entry=self.review(self.draft())
        with self.assertRaises(PermissionDenied):self.release(entry)
        dispatch=self.release(entry,actor=sender)
        self.assertTrue(messages.run_once(dispatch.pk))
        self.assertEqual(IssueMessageReceipt.objects.get(dispatch=dispatch).actor_id,sender.pk)

    def test_actual_message_forms_edit_review_release_and_display_verified_receipt(self):
        self.client.force_login(self.a)
        url=reverse('issue_messages',args=[self.c.pk,self.issue.pk])
        self.issue.refresh_from_db()
        response=self.client.post(url,{'kind':'request','state':self.issue.current_id,
            'operation_key':str(uuid4()),'revision':rev(self.c)})
        self.assertEqual(response.status_code,302)
        draft=IssueMessageDraft.objects.latest('pk')
        detail=reverse('issue_message_detail',args=[self.c.pk,self.issue.pk,draft.pk])
        self.assertContains(self.client.get(detail),'Record wording decision')
        self.assertEqual(self.client.post(detail,{'action':'edit','body':'Please confirm the source issue and its next action.',
            'state':draft.state_id,'previous':draft.pk,'operation_key':str(uuid4()),'revision':rev(self.c),
            'evidence':self.e['requirements'].pk,'reason':'Human wording correction'}).status_code,302)
        edited=IssueMessageDraft.objects.latest('pk')
        detail=reverse('issue_message_detail',args=[self.c.pk,self.issue.pk,edited.pk])
        self.assertEqual(self.client.post(detail,{'action':'review','role':'PM','verdict':'approve',
            'evidence':self.e['requirements'].pk,'note':'Checked exact source-bound wording','revision':rev(self.c)}).status_code,302)
        self.assertEqual(self.client.post(detail,{'action':'release','role':'PM','channel':'email','revision':rev(self.c)}).status_code,302)
        dispatch=IssueMessageDispatch.objects.get(review__draft=edited)
        messages.run_once(dispatch.pk)
        page=self.client.get(detail)
        self.assertContains(page,'Delivered')
        self.assertContains(page,'Observed automatically in the internal test mailbox.')
        self.assertContains(page,'Please confirm the source issue and its next action.')
        self.assertNotContains(page,'Record wording decision')

    def test_configuration_form_saves_deferred_owner_choices_as_a_draft_only(self):
        self.client.force_login(self.a)
        url=reverse('issue_message_configuration',args=[self.c.pk])
        self.assertContains(self.client.get(url),'Add another destination')
        response=self.client.post(url,{'reviewer_roles':[],'sender_roles':[],
            'independent_release':'','reminder_after_hours':'','escalation_after_hours':'',
            'escalation_target':'','clock_basis':'','draft_on_owner_wait':'','evidence':self.e['policy_decision'].pk,
            'revision':rev(self.c),'routes-TOTAL_FORMS':'0','routes-INITIAL_FORMS':'0'})
        self.assertEqual(response.status_code,302)
        from apps.policy.services import resolve,reference_values
        from apps.policy.models import Configuration
        latest=Configuration.objects.filter(case=self.c,component=COMPONENT).latest('revision')
        self.assertEqual(latest.states.order_by('-pk').first().state,'draft')
        self.assertEqual(reference_values(latest)[0]['routes'],[])
        self.assertEqual(resolve(COMPONENT,self.c).configuration.pk,self.message_config.pk)
        # Submit the actual rendered rows: one current route, the extra row and
        # an untouched added row. Empty rows must not invent email/test choices.
        response=self.client.post(url,{'independent_release':'','reminder_after_hours':'','escalation_after_hours':'',
            'escalation_target':'','clock_basis':'','draft_on_owner_wait':'','evidence':self.e['policy_decision'].pk,
            'revision':rev(self.c),'routes-TOTAL_FORMS':'3','routes-INITIAL_FORMS':'1',
            'routes-0-team_key':self.message_value['routes'][0]['team_key'],'routes-0-channel':'email',
            'routes-0-destination':self.message_value['routes'][0]['destination'],'routes-0-mode':'synthetic_mailbox',
            'routes-1-team_key':'','routes-1-channel':'','routes-1-destination':'','routes-1-mode':'',
            'routes-2-team_key':'','routes-2-channel':'','routes-2-destination':'','routes-2-mode':''})
        self.assertEqual(response.status_code,302)
        latest=Configuration.objects.filter(case=self.c,component=COMPONENT).latest('revision')
        value=reference_values(latest)[0]
        self.assertEqual(value['routes'],self.message_value['routes'])
        self.assertIsNone(value['independent_release'])
        self.assertEqual(value['reviewer_roles'],[])
        self.assertEqual(resolve(COMPONENT,self.c).configuration.pk,self.message_config.pk)

    def test_native_factory_prepares_a_message_then_keeps_the_actual_owner_reply_separate(self):
        from apps.workflows import factory,factory_issues
        from apps.workflows.models import HumanTask
        factory_issues.sync_owner(self.work.pk)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status,'waiting',self.work.finding)
        draft=IssueMessageDraft.objects.get()
        dispatch=self.release(self.review(draft))
        messages.run_once(dispatch.pk)
        task=HumanTask.objects.get(kind='issue_followup',status='open')
        proof=add_evidence(self.a,self.c.pk,'document','SYNTHETIC actual Engineering acknowledgement after the delivered request.',
                           'synthetic:actual-owner-reply')
        self.work.refresh_from_db()
        factory_issues.respond(self.a,self.work.pk,self.work.revision,rev(self.c),task.pk,task.revision,
            'acknowledge',proof.pk,'Engineering acknowledges the sample issue','Investigate documented cause',
            team_reply={'assignment_id':self.assignment.pk,'operation_key':uuid4(),'party':'Sample Engineering',
                'channel':'email','responded_at':timezone.now(),'source_ref':'synthetic:actual-owner-reply'})
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db();self.issue.refresh_from_db()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        self.assertEqual(self.issue.current.status,'Open')
        self.assertTrue(IssueMessageReceipt.objects.get(dispatch=dispatch).delivered)


class IssueMessageConcurrencyTests(TransactionTestCase):
    setUp=IssueMessageTests.setUp
    draft=IssueMessageTests.draft
    review=IssueMessageTests.review
    release=IssueMessageTests.release
    released=IssueMessageTests.released

    def test_recovery_and_late_delivery_share_one_terminal_provider_operation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        class NotAccepted(SyntheticIssueMailbox):
            def deliver(self,dispatch):raise TimeoutError('Provider acceptance unknown')
        dispatch=self.released()
        messages.run_once(dispatch.pk,NotAccepted())
        barrier=Barrier(2)
        expected=rev(self.c)
        def attempt(which):
            try:
                barrier.wait(timeout=10)
                if which:
                    return SyntheticIssueMailbox().deliver(dispatch)['delivered']
                return messages.recover(self.a,self.c.pk,dispatch.pk,'PM',expected).delivered
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,[0,1]))
        self.assertEqual(results[0],results[1])
        self.assertEqual(SyntheticIssueMessage.objects.count(),1)
        self.assertEqual(IssueMessageReceipt.objects.count(),1)
        self.assertEqual(IssueMessageReceipt.objects.get().delivered,results[0])
