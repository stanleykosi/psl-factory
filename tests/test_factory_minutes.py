"""P43 factory tests use native PostgreSQL services and explicitly synthetic providers."""
import copy,json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,register_reference
from apps.documents.controlled import review_version
from apps.documents.models import Publication,PublicationJob,PublicationReceipt
from apps.pmo.meetings import change_action,record_meeting
from apps.pmo.models import Meeting,ActionItem,MeetingVersion
from apps.workflows.models import FactoryWork,FactoryAttempt,HumanTask
from apps.workflows import factory,factory_minutes as flow
from .meeting_helpers import meetings_fixture
from .document_helpers import artifact
from .helpers import rev,activate

class FactoryMinutesTests(TestCase):
    def setUp(self):
        self.actor,self.case,self.owner,self.notes,self.template,_,self.previous,self.recipient=meetings_fixture()
        for action in ['factory.start','factory.execute','factory.read','factory.manage']:
            Grant.objects.get_or_create(case=self.case,user=self.actor,action=action)
        self.value={'definition':flow.DEFINITION,'max_steps':60,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[flow.KIND,'meeting_notes'],'information_resolver_id':None,'executor_id':self.actor.pk,'review_role':None,'provider':'synthetic_factory_v1','enabled':True,'extraction_provider':'synthetic_meeting_v1'}
        self.policy=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_minutes_execution',self.value,self.owner.pk,timezone.now()-timedelta(seconds=1));transition(self.actor,self.policy.pk,'validated');transition(self.actor,self.policy.pk,'active')
        self.data={'protocol':flow.PROTOCOL,'meeting_version_id':None,'evidence_id':self.notes.pk,'template_id':self.template.pk,'audience':'internal','publish':False}
    def start(self,outward=False):
        if outward:self.data.update(audience='client',publish=True)
        self.work=flow.start(self.actor,self.case.pk,'MINUTES-1','FORMAL-1',self.data,rev(self.case));return self.work
    def advance(self):
        factory.run_until_wait(self.work.pk);self.work.refresh_from_db();self.case.refresh_from_db();return self.work
    def fields(self,known=True):
        return {'kind':'status','occurred_at':(timezone.now()-timedelta(hours=1)).isoformat(),'purpose':'Review delivery plan and dependencies','summary':'People confirmed the plan and agreed to investigate the dependency.','participant_ids':[self.actor.pk],'decisions':[{'text':'Confirm the current delivery plan.','evidence_id':self.notes.pk,'change_evidence_id':None}],'actions':[{'reference':'ACTION-1','description':'Investigate the dependency before the next review.','owner_id':self.actor.pk if known else None,'due_at':(timezone.now()+timedelta(days=1)).isoformat() if known else None,'evidence_id':self.notes.pk,'change_evidence_id':None,'reason':'Authenticated human records actual commitment'}],'existing_action_ids':[],'note':'Checked actual attribution and agreement, not an inferred model assignment.'}
    def confirm(self,known=True,fields=None):
        r=flow.extraction(self.work);a=flow.confirm(self.actor,self.work.pk,self.work.revision,rev(self.case),fields or self.fields(known),r.pk if r else None);self.work.refresh_from_db();return a
    def rows(self):
        with connection.cursor() as c:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename");names=[r[0] for r in c.fetchall()];result={}
            for n in names:c.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(n)+' t ORDER BY to_jsonb(t)::text');result[n]=c.fetchall()
            return result
    def test_cited_extraction_human_confirmation_internal_minutes_and_action_owner(self):
        self.start();self.advance();r=flow.extraction(self.work);self.assertIsNotNone(r,self.work.finding)
        self.assertIn('Confirm the current delivery plan.',str(r.result));self.assertIsNone(r.result['proposals']['actions'][0]['owner_id']);self.assertFalse(Meeting.objects.filter(reference='FORMAL-1').exists())
        self.confirm();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        b=flow.document(self.work);self.assertIn('Review delivery plan and dependencies',str(b.version.payload));self.assertEqual(ActionItem.objects.get().current.status,'open');self.assertFalse(Publication.objects.exists());self.assertFalse(HumanTask.objects.filter(version=b.version).exists())
        self.assertFalse(flow.verify(self.work,self.actor)['actions_completed']);self.assertFalse(flow.verify(self.work,self.actor)['scope_changed'])
        self.client.force_login(self.actor);before=self.rows();response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertContains(response,'Linked action-owner work');self.assertContains(response,'ACTION-1');self.assertEqual(before,self.rows())
        item=ActionItem.objects.get();change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Done by current owner',rev(self.case),1)
        with self.assertRaises(ValidationError):flow.verify(self.work,self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.assertTrue(flow.projection(self.actor,self.work)['readiness_changed'])
        self.assertContains(self.client.get('/?queue=exceptions'),'FORMAL-1')
        self.assertContains(self.client.get('/?queue=needs_me'),'FORMAL-1')
        self.assertNotContains(self.client.get('/?queue=verified'),'FORMAL-1')
    def test_missing_owner_deadline_remain_explicit_and_do_not_invent_approval_chain(self):
        self.start();self.confirm(False);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        body=str(flow.document(self.work).version.payload);self.assertIn('Owner unassigned',body);self.assertIn('Deadline unknown',body);self.assertIsNone(ActionItem.objects.get().current.owner_id)
    def test_duplicate_intake_and_human_capture_without_execution_policy(self):
        self.start();self.assertEqual(flow.start(self.actor,self.case.pk,'MINUTES-1','FORMAL-1',self.data,1).pk,self.work.pk)
        bad=dict(self.data,audience='client',publish=True)
        with self.assertRaises(ValidationError):flow.start(self.actor,self.case.pk,'MINUTES-1','FORMAL-1',bad,rev(self.case))
        transition(self.actor,self.policy.pk,'revoked');self.confirm();self.advance();self.assertEqual(self.work.status,'configuration_needed');self.assertTrue(Meeting.objects.filter(reference='FORMAL-1').exists())
    def test_scoped_source_denial_and_hostile_attribution_do_not_create_meeting(self):
        self.start();self.advance();fields=self.fields();fields['decisions'][0]['evidence_id']=self.owner.pk
        with self.assertRaises(ValidationError):self.confirm(fields=fields)
        self.assertFalse(Meeting.objects.filter(reference='FORMAL-1').exists())
        other=get_user_model().objects.create_user('ungranted-person');fields=self.fields();fields['actions'][0]['owner_id']=other.pk
        with self.assertRaises(ValidationError):self.confirm(fields=fields)
        Grant.objects.filter(case=self.case,user=self.actor,action='meeting.read').update(active=False)
        with self.assertRaises(PermissionDenied):flow.source(self.work,self.actor)
        with self.assertRaises(PermissionDenied):self.confirm()
    def test_forbidden_source_kind_and_no_implicit_external_choice(self):
        bad=dict(self.data,evidence_id=self.owner.pk)
        with self.assertRaises(ValidationError):flow.start(self.actor,self.case.pk,'bad','bad',bad,rev(self.case))
        bad=dict(self.data,audience='client')
        with self.assertRaises(ValidationError):flow.start(self.actor,self.case.pk,'bad','bad',bad,rev(self.case))
    def test_external_exact_quality_review_all_recipients_and_receipts(self):
        second=get_user_model().objects.create_user('second-recipient');Grant.objects.create(case=self.case,user=second,action='document.receive:client')
        refs=[]
        for u in [self.recipient,second]:refs.append(register_reference(self.actor,self.case.pk,'client:'+str(u.pk),'schema:psl/document-recipient/v1',{'audience':'client','user_id':u.pk},self.owner.pk).ref)
        activate(self.actor,self.case,'D11.recipient_grant_refs',refs,self.owner)
        self.start(True);self.advance();self.confirm();self.advance();b=flow.document(self.work)
        self.assertIsNotNone(b,self.work.finding);self.assertNotEqual(self.work.status,'verified');self.assertFalse(Publication.objects.exists());self.assertTrue(HumanTask.objects.filter(version=b.version,status='open').exists())
        review_version(self.actor,self.case.pk,b.version_id,'approve','Checked exact outward minutes and recipients',rev(self.case));self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=flow.verify(self.work,self.actor);self.assertEqual(len(proof['receipt_ids']),2);self.assertEqual(Publication.objects.get().factory_source_id,self.work.source_head_id);self.assertEqual(ActionItem.objects.get().current.status,'open')
    def test_source_correction_preserves_old_minutes_budget_and_action_history(self):
        self.start();self.confirm();self.advance();before=self.work.budget_used;old=flow.document(self.work);item=ActionItem.objects.get()
        change_action(self.actor,self.case.pk,item.pk,'start',self.notes.pk,'Owner begins work',rev(self.case),1)
        self.data['meeting_version_id']=old.meeting.current_id
        flow.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.data,'Rebuild the changed native action snapshot');self.work.refresh_from_db();fields=self.fields();fields['actions']=[];fields['existing_action_ids']=[item.pk]
        self.confirm(fields=fields);self.advance();new=flow.document(self.work)
        self.assertEqual(self.work.status,'verified',self.work.finding);self.assertNotEqual(new.version_id,old.version_id);self.assertEqual(new.version.document_id,old.version.document_id);self.assertGreater(self.work.budget_used,before);self.assertEqual(ActionItem.objects.count(),1);self.assertEqual(MeetingVersion.objects.filter(meeting__reference='FORMAL-1').count(),2)
    def test_cancel_restart_retains_spent_allowance_and_extraction(self):
        self.start();self.advance();before=self.work.budget_used;r=flow.extraction(self.work)
        factory.manage(self.actor,self.work.pk,self.work.revision,'cancel');factory.run_once(self.work.pk);self.work.refresh_from_db();self.assertEqual(self.work.status,'cancelled')
        flow.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),'Resume the same authorized meeting record');self.work.refresh_from_db();self.assertEqual(self.work.budget_used,before);self.assertEqual(flow.extraction(self.work).pk,r.pk);self.confirm();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_database_rejects_success_without_native_current_confirmation_and_output(self):
        self.start()
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_missing_provider_holds_only_agent_extraction_and_human_capture_remains(self):
        value=dict(self.value,extraction_provider=None,executor_id=None)
        p=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_minutes_execution',value,self.owner.pk,timezone.now()-timedelta(seconds=1));transition(self.actor,p.pk,'validated');transition(self.actor,p.pk,'active')
        self.start();self.advance();self.assertIsNone(flow.extraction(self.work));self.confirm();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)

    def test_unknown_original_receipt_lookup_never_resends_and_correction_waits(self):
        from adapters.publications import InternalPublicationAdapter,PublicationTimeoutAfterAccept
        class LostBeforeAccept(InternalPublicationAdapter):
            sends=0;lookups=0
            def lookup(self,p):self.lookups+=1;return None
            def deliver(self,j,f):self.sends+=1;raise TimeoutError('Synthetic lost outcome')
        self.start(True);self.confirm();self.advance();b=flow.document(self.work)
        review_version(self.actor,self.case.pk,b.version_id,'approve','Exact outward quality review',rev(self.case))
        adapter=LostBeforeAccept();factory.run_until_wait(self.work.pk,adapter=adapter);self.work.refresh_from_db()
        self.assertEqual(self.work.status,'waiting_effect',self.work.finding);self.assertEqual(adapter.sends,1)
        before=self.work.budget_used;count=FactoryAttempt.objects.filter(activity__work=self.work).count()
        with self.assertRaises(ValidationError):flow.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.data,'Must resolve the original outcome')
        flow.reconcile(self.actor,self.work.pk,self.work.revision,adapter);self.work.refresh_from_db();self.assertEqual(adapter.sends,1);self.assertEqual(self.work.budget_used,before);self.assertEqual(FactoryAttempt.objects.filter(activity__work=self.work).count(),count);self.assertEqual(self.work.status,'waiting_effect')
    def test_lost_response_after_accept_recovers_exact_receipt_without_duplicate(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        self.start(True);self.confirm();self.advance();b=flow.document(self.work)
        review_version(self.actor,self.case.pk,b.version_id,'approve','Checked exact output',rev(self.case))
        factory.run_until_wait(self.work.pk,adapter=PublicationTimeoutAfterAccept());self.work.refresh_from_db()
        self.assertEqual(self.work.status,'verified',self.work.finding);self.assertEqual(PublicationReceipt.objects.count(),1);self.assertEqual(Publication.objects.count(),1)
    def test_returned_minutes_get_new_version_new_confirmation_and_review(self):
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},self.owner)
        self.start(True);self.confirm();self.advance();old=flow.document(self.work);item=ActionItem.objects.get()
        review_version(self.actor,self.case.pk,old.version_id,'return','Correct attribution before outward distribution',rev(self.case))
        self.data['meeting_version_id']=old.meeting.current_id
        flow.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.data,'Correct the actual meeting interpretation');self.work.refresh_from_db()
        self.client.force_login(self.actor);response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertContains(response,'Retain or link existing commitments')
        before=MeetingVersion.objects.filter(meeting__reference='FORMAL-1').count()
        with self.assertRaisesRegex(ValidationError,'Retain existing action ID'):self.confirm()
        self.assertEqual(MeetingVersion.objects.filter(meeting__reference='FORMAL-1').count(),before);self.assertEqual(ActionItem.objects.count(),1)
        fields=self.fields();fields['summary']='Corrected attribution after participant review.';fields['actions']=[];fields['existing_action_ids']=[item.pk]
        self.confirm(fields=fields);self.advance();new=flow.document(self.work)
        self.assertNotEqual(new.version_id,old.version_id);self.assertFalse(new.version.reviews.exists());self.assertFalse(Publication.objects.exists());self.assertEqual(ActionItem.objects.count(),1)
    def test_http_intake_confirmation_and_closed_commands(self):
        self.client.force_login(self.actor)
        response=self.client.get('/factory/new/',{'definition':flow.DEFINITION,'case':str(self.case.pk)});self.assertContains(response,'Record formal minutes')
        payload={'definition':flow.DEFINITION,'key':'HTTP-1','reference':'HTTP-MEETING','revision':rev(self.case),'case':str(self.case.pk),'audience':'internal','evidence_id':self.notes.pk,'template_id':self.template.pk}
        response=self.client.post('/factory/new/?definition='+flow.DEFINITION,payload);self.assertEqual(response.status_code,302)
        self.work=FactoryWork.objects.get(request__reference='HTTP-MEETING');url='/work/'+str(self.work.pk)+'/'
        from .test_factory_minutes_console import FactoryMinutesConsoleTests
        page=self.client.get(url);data=FactoryMinutesConsoleTests.browser_payload(self,page);data.update(kind='status',occurred_at='2026-11-06T09:30:00',purpose='Human-confirmed plan',summary='Actual meeting summary',note='Human checked actual attribution',**{'decisions-0-text':'Confirm the plan','commitments-0-reference':'ACTION-1','commitments-0-description':'Investigate dependency','commitments-0-reason':'Actual human commitment'})
        response=self.client.post(url,data);self.assertEqual(response.status_code,302)
        self.work.refresh_from_db();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        before=self.rows();response=self.client.post(url,{'action':'confirm','revision':1,'case_revision':1,'fields':json.dumps(self.fields()),'inject_owner':str(self.actor.pk)});self.assertEqual(response.status_code,200);self.assertEqual(ActionItem.objects.count(),1)
    def test_current_owner_grant_and_stale_human_commands(self):
        self.start();old=self.work.revision;self.advance()
        with self.assertRaises(ValidationError):flow.confirm(self.actor,self.work.pk,old,rev(self.case),self.fields(),None)
        self.confirm();item=ActionItem.objects.get();other=get_user_model().objects.create_user('replacement-action-owner')
        for action in ['action.own','action.work']:Grant.objects.create(case=self.case,user=other,action=action)
        change_action(self.actor,self.case.pk,item.pk,'assign',self.notes.pk,'Explicit reassignment',rev(self.case),1,other.pk,None)
        with self.assertRaises(PermissionDenied):change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Former owner cannot finish',rev(self.case),2)
        state=change_action(other,self.case.pk,item.pk,'start',self.notes.pk,'Current owner begins',rev(self.case),2);self.assertEqual(state.status,'in_progress')

    def test_published_receipts_do_not_hide_revoked_reviewer_or_recipient_grants(self):
        self.start(True);self.confirm();self.advance();b=flow.document(self.work)
        review_version(self.actor,self.case.pk,b.version_id,'approve','Exact current authority',rev(self.case));self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        Grant.objects.filter(case=self.case,user=self.recipient,action='document.receive:client').update(active=False)
        with self.assertRaises(PermissionDenied):flow.verify(self.work,self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_newer_native_document_supersedes_old_factory_snapshot(self):
        from apps.pmo.reporting import draft_minutes
        self.start();self.confirm();self.advance();b=flow.document(self.work)
        draft_minutes(self.actor,self.case.pk,b.meeting_id,self.template.pk,'internal',rev(self.case))
        with self.assertRaises(ValidationError):flow.verify(self.work,self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_existing_meeting_reference_requires_explicit_current_version_intent(self):
        with self.assertRaisesRegex(ValidationError,'explicitly select'):
            flow.start(self.actor,self.case.pk,'EXISTING-1','STATUS-001',self.data,rev(self.case))
        self.assertEqual(MeetingVersion.objects.filter(meeting=self.previous.meeting).count(),1)
        self.data['meeting_version_id']=self.previous.pk
        with self.assertRaisesRegex(ValidationError,'does not match'):
            flow.start(self.actor,self.case.pk,'MISMATCH-1','DIFFERENT',self.data,rev(self.case))
        self.work=flow.start(self.actor,self.case.pk,'EXISTING-1','STATUS-001',self.data,rev(self.case));self.confirm();self.advance()
        self.assertEqual(self.work.status,'verified',self.work.finding);self.assertEqual(MeetingVersion.objects.filter(meeting=self.previous.meeting).count(),2)
    def test_existing_meeting_changes_before_confirmation_require_fresh_intent(self):
        self.data['meeting_version_id']=self.previous.pk
        self.work=flow.start(self.actor,self.case.pk,'EXISTING-1','STATUS-001',self.data,rev(self.case))
        v=record_meeting(self.actor,self.case.pk,'STATUS-001','status',timezone.now(),'Newer native correction','Corrected by a human',[],[],self.notes.pk,rev(self.case),self.previous.meeting_id)
        with self.assertRaisesRegex(ValidationError,'STALE_VERSION'):self.confirm()
        self.data['meeting_version_id']=v.pk
        flow.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.data,'Select the current explicitly corrected meeting');self.work.refresh_from_db();self.confirm();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_native_meeting_created_after_new_intake_cannot_be_silently_overwritten(self):
        self.start()
        v=record_meeting(self.actor,self.case.pk,'FORMAL-1','status',timezone.now(),'Independent native meeting','Do not overwrite without selected revision',[],[],self.notes.pk,rev(self.case))
        with self.assertRaisesRegex(ValidationError,'explicitly select'):self.confirm()
        self.assertEqual(Meeting.objects.get(reference='FORMAL-1').current_id,v.pk);self.assertFalse(ActionItem.objects.exists())
    def test_cross_project_meeting_version_selection_is_denied(self):
        from apps.core.models import Case
        other=Case.objects.create(tenant='other-test-tenant',kind='project',title='Unrelated project',synthetic=True)
        for g in Grant.objects.filter(case=self.case,user=self.actor):Grant.objects.create(case=other,user=self.actor,action=g.action)
        notes=add_evidence(self.actor,other.pk,'meeting_notes','Other project note','synthetic:other')
        v=record_meeting(self.actor,other.pk,'OTHER','status',timezone.now(),'Other','Other',[],[],notes.pk,rev(other))
        self.data['meeting_version_id']=v.pk
        with self.assertRaisesRegex(ValidationError,'from this project'):self.start()

    def test_operational_shaped_human_capture_has_no_synthetic_provider_fallback(self):
        from apps.core.models import Case
        from apps.documents.controlled import register_template
        from apps.agents.meetings import suggest_commitments
        original=self.case
        operational=Case.objects.create(tenant='local-operational-shaped-fixture',title='Local fixture without provider',kind='project',synthetic=False)
        for g in Grant.objects.filter(case=original,user=self.actor):Grant.objects.create(case=operational,user=self.actor,action=g.action)
        proof=add_evidence(self.actor,operational.pk,'policy_decision','Local test template only; no actual operational policy activation','fixture:local')
        template=register_template(self.actor,operational.pk,'Local fixture minutes',self.template.definition,proof.pk,rev(operational))
        notes=add_evidence(self.actor,operational.pk,'meeting_notes','Confirm the current delivery plan.\nInvestigate the dependency before the next review.','fixture:local-notes')
        self.case=operational;self.notes=notes;self.template=template;self.data.update(evidence_id=notes.pk,template_id=template.pk)
        self.start();self.confirm();self.advance();self.assertEqual(self.work.status,'configuration_needed')
        self.assertTrue(Meeting.objects.filter(case=operational,reference='FORMAL-1').exists())
        with self.assertRaisesRegex(ValidationError,'approved real provider'):suggest_commitments(self.actor,operational.pk,notes.pk,rev(operational))
        self.assertIsNone(flow.extraction(self.work))

    def native_ready_publication(self):
        from apps.documents.controlled import reserve_publication
        self.start(True);self.confirm();self.advance();binding=flow.document(self.work)
        review_version(self.actor,self.case.pk,binding.version_id,'approve','Exact outward minutes review',rev(self.case))
        return reserve_publication(self.actor,self.case.pk,binding.version_id,rev(self.case),factory_work_id=self.work.pk)
    def test_native_worker_unknown_and_expired_lease_remain_receipt_only(self):
        from adapters.publications import InternalPublicationAdapter
        from apps.documents.delivery import run_publication_once
        class Counter(InternalPublicationAdapter):
            calls=0
            def deliver(self,*args):self.calls+=1;return super().deliver(*args)
        p=self.native_ready_publication();spent=self.work.budget_used
        for status in ['unknown','leased']:
            PublicationJob.objects.filter(publication=p).update(status=status,lease_until=timezone.now()-timedelta(seconds=1))
            adapter=Counter();self.assertTrue(run_publication_once(adapter,job_id=p.job.pk));self.assertEqual(adapter.calls,0)
            self.assertEqual(PublicationJob.objects.get(publication=p).status,'unknown');self.assertFalse(PublicationReceipt.objects.exists())
        self.work.refresh_from_db();self.assertEqual(self.work.budget_used,spent)
    def test_native_operator_cannot_cancel_or_retry_uncertain_minutes(self):
        from apps.documents.delivery import operate_publication
        p=self.native_ready_publication();PublicationJob.objects.filter(publication=p).update(status='unknown')
        for action in ['cancel','retry']:
            with self.assertRaisesRegex(ValidationError,'receipt-only'):operate_publication(self.actor,self.case.pk,p.job.pk,action,'Keep original unresolved minutes',rev(self.case))
        self.assertEqual(PublicationJob.objects.get(publication=p).status,'unknown')
    def test_native_lookup_failure_cannot_create_safe_to_retry_minutes(self):
        from adapters.publications import InternalPublicationAdapter
        from apps.documents.delivery import run_publication_once,operate_publication
        class FailedLookup(InternalPublicationAdapter):
            def lookup(self,p):raise ValidationError('Synthetic inconclusive receipt lookup')
            def deliver(self,*args):raise AssertionError('Never deliver after an inconclusive receipt lookup')
        p=self.native_ready_publication();PublicationJob.objects.filter(publication=p).update(status='unknown')
        run_publication_once(FailedLookup(),job_id=p.job.pk);job=PublicationJob.objects.get(publication=p);self.assertEqual(job.status,'unknown')
        with self.assertRaisesRegex(ValidationError,'receipt-only'):operate_publication(self.actor,self.case.pk,job.pk,'cancel','Inconclusive lookup is not confirmed absence',rev(self.case))
        self.assertFalse(PublicationReceipt.objects.exists())
    def test_legacy_unbound_minutes_keep_native_idempotent_recovery(self):
        from apps.pmo.reporting import draft_minutes
        from apps.documents.controlled import request_review,reserve_publication
        from apps.documents.delivery import run_publication_once
        from adapters.publications import InternalPublicationAdapter
        class Counter(InternalPublicationAdapter):
            calls=0
            def deliver(self,*args):self.calls+=1;return super().deliver(*args)
        b=draft_minutes(self.actor,self.case.pk,self.previous.meeting_id,self.template.pk,'client',rev(self.case))
        request_review(self.actor,self.case.pk,b.version_id,rev(self.case));review_version(self.actor,self.case.pk,b.version_id,'approve','Legacy native exact outward review',rev(self.case))
        p=reserve_publication(self.actor,self.case.pk,b.version_id,rev(self.case));PublicationJob.objects.filter(publication=p).update(status='unknown')
        adapter=Counter();run_publication_once(adapter,job_id=p.job.pk);self.assertEqual(adapter.calls,1);self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(),1)

from django.test import TransactionTestCase
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
import os,subprocess,sys

class FactoryMinutesDurabilityTests(TransactionTestCase):
    setUp=FactoryMinutesTests.setUp
    start=FactoryMinutesTests.start
    fields=FactoryMinutesTests.fields
    confirm=FactoryMinutesTests.confirm
    def worker(self):
        environment=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        command='from apps.workflows.factory import run_until_wait; run_until_wait('+str(self.work.pk)+')'
        result=subprocess.run([sys.executable,'manage.py','shell','-c',command],env=environment,capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.work.refresh_from_db();self.case.refresh_from_db()
    def test_two_fresh_worker_processes_retain_extraction_and_shared_history(self):
        self.start();self.worker();extraction=flow.extraction(self.work);spent=self.work.budget_used
        attempts=list(FactoryAttempt.objects.filter(activity__work=self.work).values_list('pk',flat=True))
        self.assertIsNotNone(extraction,self.work.finding);self.confirm();self.worker()
        self.assertEqual(self.work.status,'verified',self.work.finding);self.assertEqual(flow.extraction(self.work).pk,extraction.pk)
        self.assertGreater(self.work.budget_used,spent);self.assertEqual(FactoryAttempt.objects.filter(pk__in=attempts).count(),len(attempts));self.assertEqual(ActionItem.objects.count(),1)
    def test_two_connections_reconcile_one_intake_and_one_private_source(self):
        actor_id=self.actor.pk;case_id=self.case.pk;expected=rev(self.case);data=dict(self.data)
        def submit():
            close_old_connections()
            try:return flow.start(get_user_model().objects.get(pk=actor_id),case_id,'CONCURRENT-1','CONCURRENT-MEETING',data,expected).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(lambda _:submit(),range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.count(),1)
        from apps.core.models import Evidence
        self.assertEqual(Evidence.objects.filter(case=self.case,kind=flow.KIND).count(),1)
