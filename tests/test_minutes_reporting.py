from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import os, subprocess, sys, json
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, DatabaseError, connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo.models import Meeting, MeetingVersion, ActionItem, ActionState, MinutesReportBinding, PeriodReport, ReportSchedule, ReportOccurrence
from apps.pmo.meetings import record_meeting, create_action, change_action, action_timing, link_action
from apps.pmo.reporting import draft_minutes, draft_period_report
from apps.pmo.schedules import save_schedule, arm_schedule, pause_schedule, run_report_once
from apps.pmo.clocks import calculate_action_due, report_window, local_time
from apps.policy.services import transition, resolve, PolicyHold
from apps.policy.clock_drafts import draft_clock_policy
from apps.documents.controlled import request_review, review_version, reserve_publication, preflight
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt, PublicationJob, Version
from apps.workflows.models import HumanTask
from apps.agents.meetings import suggest_commitments, investigate_actions
from apps.agents.models import AgentRun
from .helpers import rev, activate
from .document_helpers import artifact
from .meeting_helpers import meetings_fixture, configure_clock

class MinutesReportingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case,cls.owner,cls.notes,cls.minutes,cls.report_template,cls.meeting,cls.recipient=meetings_fixture()

    def action(self,owner=True,due=True):
        return create_action(self.actor,self.case.pk,'ACT-001','Investigate the dependency',self.actor.pk if owner else None,
            timezone.now()+timedelta(days=1) if due else None,self.notes.pk,'Recorded commitment',rev(self.case),self.meeting.meeting_id)

    def approve_publish(self,binding):
        request_review(self.actor,self.case.pk,binding.version_id,rev(self.case))
        review_version(self.actor,self.case.pk,binding.version_id,'approve','Checked exact audience minutes/report',rev(self.case))
        return reserve_publication(self.actor,self.case.pk,binding.version_id,rev(self.case))

    def test_minutes_actions_review_and_actual_recipient_publication(self):
        item=self.action()
        binding=draft_minutes(self.actor,self.case.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        self.approve_publish(binding);run_publication_once()
        receipt=PublicationReceipt.objects.get()
        self.assertIn('ACT-001',str(receipt.payload));self.assertIn('do not amend the signed baseline',str(receipt.payload))
        self.assertEqual(binding.manifest['actions'],[[item.pk,item.current_id]])
        self.assertEqual(PublicationJob.objects.get().status,'confirmed')

    def test_missing_owner_and_deadline_remain_unknown_and_capture_needs_no_calendar(self):
        item=self.action(False,False)
        self.assertIsNone(item.current.owner_id);self.assertIsNone(item.current.due_at)
        self.assertEqual(action_timing(item.current),'UNKNOWN')
        binding=draft_minutes(self.actor,self.case.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        self.assertIn('Owner unassigned',str(binding.version.payload));self.assertIn('Deadline unknown',str(binding.version.payload))
        self.assertEqual(resolve('D04.working_calendar_ref',self.case).status,'MISSING')

    def test_only_current_owner_can_complete_and_current_grants_are_checked(self):
        item=self.action();other=get_user_model().objects.create_user('other-owner')
        for action in ['action.own','action.work']:Grant.objects.create(case=self.case,user=other,action=action)
        with self.assertRaises(PermissionDenied):change_action(other,self.case.pk,item.pk,'complete',self.notes.pk,'Attempt',rev(self.case),1)
        change_action(self.actor,self.case.pk,item.pk,'assign',self.notes.pk,'Reassigned explicitly',rev(self.case),1,other.pk,timezone.now()+timedelta(days=2))
        with self.assertRaises(PermissionDenied):change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Old owner attempt',rev(self.case),2)
        done=change_action(other,self.case.pk,item.pk,'complete',self.notes.pk,'Evidence-backed completion',rev(self.case),2)
        self.assertEqual(done.status,'completed');self.assertEqual(ActionState.objects.count(),3)

    def test_naive_timestamps_and_cross_case_principals_are_rejected(self):
        with self.assertRaises(ValidationError):create_action(self.actor,self.case.pk,'NAIVE','Test',self.actor.pk,'2026-10-21T12:00',self.notes.pk,'No timezone',rev(self.case))
        other=get_user_model().objects.create_user('foreign')
        with self.assertRaises(ValidationError):create_action(self.actor,self.case.pk,'FOREIGN','Test',other.pk,None,self.notes.pk,'No case grant',rev(self.case))
        with self.assertRaises(ValidationError):record_meeting(self.actor,self.case.pk,'BAD','status','2026-10-20T12:00','Bad','Bad',[],[],self.notes.pk,rev(self.case))

    def test_stale_action_and_case_revisions_do_not_overwrite_history(self):
        item=self.action();old_case=rev(self.case)
        change_action(self.actor,self.case.pk,item.pk,'start',self.notes.pk,'Starting',old_case,1)
        with self.assertRaises(ValidationError):change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Stale',rev(self.case),1)
        with self.assertRaises(ValidationError):change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Stale case',old_case,2)
        self.assertEqual(ActionState.objects.count(),2)

    def test_changed_action_holds_old_minutes_and_new_revision_gets_new_review(self):
        item=self.action();binding=draft_minutes(self.actor,self.case.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        self.approve_publish(binding)
        change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Done with source evidence',rev(self.case),1)
        run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())
        revised=draft_minutes(self.actor,self.case.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        self.assertEqual(revised.version.document_id,binding.version.document_id);self.assertEqual(revised.version.number,2)
        self.assertFalse(revised.version.reviews.exists())

    def test_new_meeting_revision_and_previous_action_links_invalidate_snapshot(self):
        item=self.action();binding=draft_minutes(self.actor,self.case.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        changed=record_meeting(self.actor,self.case.pk,'STATUS-001','status',self.meeting.occurred_at,'Corrected purpose','Corrected summary',[],[],self.notes.pk,rev(self.case),self.meeting.meeting_id)
        self.assertEqual(changed.number,2);self.assertTrue(preflight(binding.version))
        next_meeting=record_meeting(self.actor,self.case.pk,'STATUS-002','status',timezone.now(),'Follow-up','Review prior actions',[],[],self.notes.pk,rev(self.case))
        link_action(self.actor,self.case.pk,next_meeting.meeting_id,item.pk,self.notes.pk,rev(self.case))
        followup=draft_minutes(self.actor,self.case.pk,next_meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        self.assertIn('ACT-001',str(followup.version.payload))

    def test_manual_period_reporting_does_not_need_calendar_and_tracks_action_changes(self):
        item=self.action();start=timezone.now()-timedelta(days=7);end=timezone.now()+timedelta(seconds=1)
        binding=draft_period_report(self.actor,self.case.pk,'weekly_client',start,end,self.report_template.pk,'client',rev(self.case))
        self.assertIn('Coverage is local recorded PMO evidence',str(binding.version.payload))
        change_action(self.actor,self.case.pk,item.pk,'complete',self.notes.pk,'Completed',rev(self.case),1)
        self.assertTrue(preflight(binding.version))
        revised=draft_period_report(self.actor,self.case.pk,'weekly_client',start,end,self.report_template.pk,'client',rev(self.case))
        self.assertEqual(PeriodReport.objects.count(),1);self.assertEqual(revised.version.document_id,binding.version.document_id)

    def test_calculated_working_deadline_uses_holidays_and_policy_lineage(self):
        configure_clock(self.actor,self.case,self.owner)
        due,policies,meta=calculate_action_due(self.case,datetime.fromisoformat('2026-10-20T10:00:00+01:00'),timezone.now())
        self.assertEqual(due.isoformat(),'2026-10-23T17:00:00+01:00');self.assertEqual(len(policies),4)
        self.assertIn('anchor',meta)
        artifact(self.actor,self.case,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'action':{'unit':'working_days','amount':1,'anchor_day':'include_if_working'}},self.owner)
        same_day,_,_=calculate_action_due(self.case,datetime.fromisoformat('2026-10-20T10:00:00+01:00'),timezone.now())
        self.assertEqual(same_day.isoformat(),'2026-10-20T17:00:00+01:00')
        with self.assertRaises(ValidationError):artifact(self.actor,self.case,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'action':{'unit':'working_days','amount':2}},self.owner)
        item=create_action(self.actor,self.case.pk,'CALCULATED','Configured follow-up',self.actor.pk,None,self.notes.pk,'Synthetic configured deadline',rev(self.case),self.meeting.meeting_id,True)
        self.assertEqual(item.current.due_basis,'calculated');self.assertEqual(len(item.current.policies),4)

    def test_missing_calendar_holds_only_calculation_and_explicit_due_still_works(self):
        with self.assertRaises(PolicyHold):create_action(self.actor,self.case.pk,'CALC','Calculated',self.actor.pk,None,self.notes.pk,'Missing policy',rev(self.case),self.meeting.meeting_id,True)
        self.assertEqual(ActionItem.objects.count(),0)
        item=self.action();self.assertEqual(item.current.due_basis,'explicit')

    def test_configured_pause_resume_preserves_history_and_elapsed_extension(self):
        configure_clock(self.actor,self.case,self.owner);item=self.action();old_due=item.current.due_at
        fixed=timezone.now()
        with patch('apps.pmo.meetings.timezone.now',return_value=fixed):
            paused=change_action(self.actor,self.case.pk,item.pk,'pause',self.notes.pk,'Configured pause',rev(self.case),1)
        self.assertEqual(action_timing(paused),'PAUSED')
        with patch('apps.pmo.meetings.timezone.now',return_value=fixed+timedelta(hours=2)):
            resumed=change_action(self.actor,self.case.pk,item.pk,'resume',self.notes.pk,'Resume',rev(self.case),2)
        self.assertEqual(resumed.due_at,old_due+timedelta(hours=2));self.assertEqual(ActionState.objects.count(),3)

    def test_revoked_pause_policy_holds_resume_but_explicit_manager_reset_remains(self):
        configure_clock(self.actor,self.case,self.owner);item=self.action()
        paused=change_action(self.actor,self.case.pk,item.pk,'pause',self.notes.pk,'Pause',rev(self.case),1)
        config=resolve('D04.clock_anchor_pause_rules',self.case).configuration;transition(self.actor,config.pk,'revoked')
        with self.assertRaises(PolicyHold):change_action(self.actor,self.case.pk,item.pk,'resume',self.notes.pk,'Resume',rev(self.case),2)
        reset=change_action(self.actor,self.case.pk,item.pk,'assign',self.notes.pk,'Explicit new human deadline',rev(self.case),2,self.actor.pk,timezone.now()+timedelta(days=1))
        self.assertEqual(reset.status,'open');self.assertEqual(reset.due_basis,'explicit')

    def test_report_schedule_dependencies_are_narrow_and_tuesday_is_fixed(self):
        configure_clock(self.actor,self.case,self.owner,calendar=False,anchors=False,action=False)
        due,start,end,policies=report_window(self.case,'weekly_client',datetime.fromisoformat('2026-10-20T12:00:00+01:00'))
        self.assertEqual(due.isoformat(),'2026-10-23T09:00:00+01:00');self.assertEqual(len(policies),2)
        self.assertEqual((end.date()-start.date()).days,7)
        with self.assertRaises(ValidationError):artifact(self.actor,self.case,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',
            {'reporting':{'internal_tuesday':{'weekday':0,'time':'09:00','holiday_treatment':'calendar','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'}}},self.owner)

    def test_short_month_and_dst_are_explicit(self):
        profiles={'monthly_executive':{'day':31,'time':'10:00','month_end_rule':'last_day','holiday_treatment':'calendar','coverage':'previous_calendar_month','coverage_anchor':'scheduled_time'}}
        configure_clock(self.actor,self.case,self.owner,reporting=profiles)
        due,_,_,_=report_window(self.case,'monthly_executive',datetime.fromisoformat('2027-02-01T00:00:00+01:00'))
        self.assertEqual(due.day,28)
        with self.assertRaises(ValidationError):local_time(datetime(2026,10,25).date(),'01:30',ZoneInfo('Europe/London'))
        with self.assertRaises(ValidationError):local_time(datetime(2026,3,29).date(),'01:30',ZoneInfo('Europe/London'))

    def test_schedule_creates_one_draft_and_review_wait_without_publication(self):
        configure_clock(self.actor,self.case,self.owner)
        schedule=save_schedule(self.actor,self.case.pk,'weekly_client',self.report_template.pk,'client',rev(self.case))
        arm_schedule(self.actor,self.case.pk,schedule.pk,'2026-10-20T12:00:00+01:00',rev(self.case))
        due=ReportSchedule.objects.get().next_due_at
        self.assertTrue(run_report_once(due));self.assertFalse(run_report_once(due))
        self.assertEqual(ReportOccurrence.objects.count(),1);self.assertEqual(HumanTask.objects.count(),1)
        self.assertEqual(HumanTask.objects.get().status,'open');self.assertFalse(PublicationJob.objects.exists())
        self.assertEqual(MinutesReportBinding.objects.count(),1)

    def test_schedule_policy_change_is_held_and_manual_reporting_still_works(self):
        configure_clock(self.actor,self.case,self.owner);schedule=save_schedule(self.actor,self.case.pk,'weekly_client',self.report_template.pk,'client',rev(self.case))
        schedule=arm_schedule(self.actor,self.case.pk,schedule.pk,'2026-10-20T12:00:00+01:00',rev(self.case))
        config=resolve('D04.deadline_parameters',self.case).configuration;transition(self.actor,config.pk,'revoked')
        before=rev(self.case)
        run_report_once(schedule.next_due_at);schedule.refresh_from_db();self.assertEqual(schedule.status,'held')
        self.assertGreater(rev(self.case),before)
        self.assertFalse(ReportOccurrence.objects.exists());self.assertFalse(Version.objects.exists())
        draft_period_report(self.actor,self.case.pk,'weekly_client',timezone.now()-timedelta(days=7),timezone.now(),self.report_template.pk,'client',rev(self.case))
        self.assertEqual(Version.objects.count(),1)

    def test_schedule_revoked_dispatch_grant_and_paused_schedule_never_draft(self):
        configure_clock(self.actor,self.case,self.owner);schedule=save_schedule(self.actor,self.case.pk,'weekly_client',self.report_template.pk,'client',rev(self.case))
        schedule=arm_schedule(self.actor,self.case.pk,schedule.pk,'2026-10-20T12:00:00+01:00',rev(self.case))
        Grant.objects.filter(case=self.case,user=self.actor,action='report.draft').update(active=False)
        run_report_once(schedule.next_due_at);schedule.refresh_from_db();self.assertEqual(schedule.status,'held')
        self.assertFalse(ReportOccurrence.objects.exists());self.assertFalse(Version.objects.exists())
        pause_schedule(self.actor,self.case.pk,schedule.pk,'Await owner',rev(self.case));self.assertFalse(run_report_once(schedule.next_due_at))

    def test_holiday_shift_uses_explicit_coverage_anchor(self):
        profile={'weekly_client':{'weekday':2,'time':'09:00','holiday_treatment':'next_working_day','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'}}
        configure_clock(self.actor,self.case,self.owner,reporting=profile)
        due,start,end,policies=report_window(self.case,'weekly_client',datetime.fromisoformat('2026-10-20T12:00:00+01:00'))
        self.assertEqual(due.isoformat(),'2026-10-22T09:00:00+01:00')
        self.assertEqual(end.isoformat(),'2026-10-21T09:00:00+01:00')
        self.assertIn('D04.working_calendar_ref',policies)

    def test_each_new_clock_component_invalid_active_stale_revoked_expired(self):
        from apps.policy.services import save_draft
        from .helpers import envelope
        examples={
            'D04.working_calendar_ref':{'weekdays':[0,1,2,3,4],'holidays':[],'due_time':'17:00'},
            'D04.clock_anchor_pause_rules':{'pause_behavior':'no_extension'},
            'D04.deadline_parameters':{'action':{'unit':'elapsed_hours','amount':24}}}
        for component,value in examples.items():
            with self.subTest(component=component):
                self.assertEqual(resolve(component,self.case).status,'MISSING')
                invalid=draft_clock_policy(self.actor,self.case.pk,component,{},self.owner.pk,timezone.now()-timedelta(days=1))
                with self.assertRaises(ValidationError):transition(self.actor,invalid.pk,'validated')
                first=draft_clock_policy(self.actor,self.case.pk,component,value,self.owner.pk,timezone.now()-timedelta(days=1))
                transition(self.actor,first.pk,'validated');transition(self.actor,first.pk,'active')
                self.assertEqual(resolve(component,self.case).status,'ACTIVE')
                second=draft_clock_policy(self.actor,self.case.pk,component,value,self.owner.pk,timezone.now()-timedelta(days=1))
                transition(self.actor,second.pk,'validated');transition(self.actor,second.pk,'active')
                self.assertEqual(resolve(component,self.case,expected_revision=first.revision).status,'INVALID')
                transition(self.actor,second.pk,'revoked');self.assertEqual(resolve(component,self.case).status,'REVOKED')
                expired_envelope=envelope(self.case,component,second.envelope['value'],self.owner)
                expired_envelope['effective_until']=(timezone.now()-timedelta(hours=1)).isoformat()
                expired=save_draft(self.actor,self.case.pk,expired_envelope)
                transition(self.actor,expired.pk,'validated');transition(self.actor,expired.pk,'active')
                self.assertEqual(resolve(component,self.case).status,'EXPIRED')

    def test_elapsed_deadline_and_policy_revisions_do_not_rewrite_existing_commitment(self):
        configure_clock(self.actor,self.case,self.owner)
        artifact(self.actor,self.case,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'action':{'unit':'elapsed_hours','amount':48}},self.owner)
        due,_,_=calculate_action_due(self.case,datetime.fromisoformat('2026-10-20T10:00:00+01:00'),timezone.now())
        self.assertEqual(due.isoformat(),'2026-10-22T09:00:00+00:00')
        item=create_action(self.actor,self.case.pk,'PINNED','Configured',self.actor.pk,None,self.notes.pk,'Policy-backed',rev(self.case),self.meeting.meeting_id,True)
        original=item.current.due_at
        artifact(self.actor,self.case,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'action':{'unit':'elapsed_hours','amount':72}},self.owner)
        item.refresh_from_db();self.assertEqual(item.current.due_at,original);self.assertEqual(item.states.count(),1)

    def test_clock_configuration_ui_saves_draft_not_authority(self):
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/meetings/'
        response=self.client.post(url,{'action':'clock_draft','revision':rev(self.case),'component':'D04.clock_anchor_pause_rules',
            'value':json.dumps({'pause_behavior':'no_extension'}),'evidence':self.owner.pk,'effective_from':timezone.now().isoformat()})
        self.assertEqual(response.status_code,302);self.assertEqual(resolve('D04.clock_anchor_pause_rules',self.case).status,'MISSING')

    def test_actual_staff_meeting_action_minutes_path(self):
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/meetings/'
        for kind in ['meeting_notes','change_request']:
            captured=self.client.post(f'/cases/{self.case.pk}/',{'action':'evidence','revision':rev(self.case),'kind':kind,'body':'Source capture through staff UI','source':'synthetic:staff-capture'})
            self.assertEqual(captured.status_code,302)
        response=self.client.post(url,{'action':'new_action','revision':rev(self.case),'reference':'UI-001','description':'Follow up',
            'meeting':self.meeting.meeting_id,'owner':self.actor.pk,'due_at':'2026-10-23T17:00:00+01:00','evidence':self.notes.pk,'reason':'Meeting commitment'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(url,{'action':'minutes','revision':rev(self.case),'meeting':self.meeting.meeting_id,'template':self.minutes.pk,'audience':'client'}).status_code,302)
        response=self.client.get(url)
        self.assertContains(response,'UI-001');self.assertContains(response,'id="minutes_template"');self.assertContains(response,'id="report_template"')
        self.assertEqual(MinutesReportBinding.objects.count(),1)

    def test_agents_only_suggest_cited_work_and_cannot_assign_or_change_scope(self):
        run=suggest_commitments(self.actor,self.case.pk,self.notes.pk,rev(self.case));self.assertTrue(run.result['human_confirmation_required'])
        self.assertFalse(ActionItem.objects.exists())
        class Bad:
            name='adversarial-fixture'
            def suggest(inner,e):return {'decisions':[],'actions':[{'quote':'Investigate the dependency before the next review.','evidence_id':e.pk,'owner_id':self.actor.pk,'due_at':None}]}
        with self.assertRaises(ValidationError):suggest_commitments(self.actor,self.case.pk,self.notes.pk,rev(self.case),Bad())
        self.action(False,False);result=investigate_actions(self.actor,self.case.pk)
        self.assertTrue(result.result['findings'][0]['owner_missing']);self.assertFalse(result.result['automatic_escalation_authorized'])

    def test_database_history_and_current_pointers_are_protected(self):
        item=self.action();binding=draft_minutes(self.actor,self.case.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.case))
        for model,values in [(MeetingVersion,{'summary':'rewritten'}),(ActionState,{'reason':'rewritten'}),(MinutesReportBinding,{'manifest':{}})]:
            with self.subTest(model=model),self.assertRaises(DatabaseError),transaction.atomic():model.objects.update(**values)
        with self.assertRaises(DatabaseError),transaction.atomic():ActionItem.objects.filter(pk=item.pk).update(reference='rewritten')
        other=create_action(self.actor,self.case.pk,'OTHER','Other',None,None,self.notes.pk,'Unknown commitment',rev(self.case))
        with self.assertRaises(DatabaseError),transaction.atomic():ActionItem.objects.filter(pk=item.pk).update(current_id=other.current_id)

    def test_other_case_and_ungranted_admin_are_denied(self):
        other=Case.objects.create(title='Other',tenant='other',kind='project')
        with self.assertRaises(PermissionDenied):record_meeting(self.actor,other.pk,'X','status',timezone.now(),'X','X',[],[],self.notes.pk,1)
        admin=get_user_model().objects.create_superuser('new-admin','admin@example.test','test-only')
        self.client.force_login(admin);self.assertEqual(self.client.get(f'/cases/{self.case.pk}/meetings/').status_code,404)


class ReportingProcessTests(TransactionTestCase):
    def fixture(self):
        actor,case,owner,notes,minutes,template,meeting,recipient=meetings_fixture()
        now=timezone.now().astimezone(ZoneInfo('Africa/Lagos'))
        profiles={'weekly_client':{'weekday':now.weekday(),'time':'00:00','holiday_treatment':'calendar','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'}}
        configure_clock(actor,case,owner,calendar=False,anchors=False,reporting=profiles,action=False)
        schedule=save_schedule(actor,case.pk,'weekly_client',template.pk,'client',rev(case))
        schedule=arm_schedule(actor,case.pk,schedule.pk,now-timedelta(days=1),rev(case))
        return actor,case,schedule

    def test_separate_worker_process_generates_draft_once_and_persisted_cursor_resumes(self):
        actor,case,schedule=self.fixture();env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        for _ in range(2):
            result=subprocess.run([sys.executable,'manage.py','work_reports','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(ReportOccurrence.objects.count(),1);self.assertEqual(HumanTask.objects.count(),1)
        self.assertFalse(PublicationJob.objects.exists())

    def test_two_connections_generate_one_occurrence(self):
        actor,case,schedule=self.fixture()
        def work():
            close_old_connections()
            try:return run_report_once()
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:work(),range(2)))
        self.assertEqual(sum(bool(r) for r in results),1);self.assertEqual(ReportOccurrence.objects.count(),1)
