"""Legacy manual/scheduled reports must check current native source grants."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo.issues import log_issue
from apps.pmo.changes import log_change
from apps.pmo.gates import register_candidate, record_gate
from apps.pmo.rfp import intake
from apps.pmo.reporting import draft_period_report
from apps.pmo.schedules import save_schedule, arm_schedule, run_report_once
from apps.pmo.models import ReportOccurrence
from tests.meeting_helpers import meetings_fixture, configure_clock
from tests.helpers import rev


class LegacyReportAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case,cls.owner,cls.notes,cls.minutes,cls.template,cls.meeting,cls.recipient=meetings_fixture()
        Grant.objects.get_or_create(case=cls.case,user=cls.actor,action='report.read')
        log_issue(cls.actor,cls.case.pk,'SECRET-ISSUE','Private issue','Production',cls.actor.pk,'PRIVATE ISSUE NEXT ACTION',cls.notes.pk,'Recorded by PM',rev(cls.case))
        change=add_evidence(cls.actor,cls.case.pk,'change_request','PRIVATE CHANGE DESCRIPTION','synthetic:change')
        log_change(cls.actor,cls.case.pk,'SECRET-CHANGE','Normal','Module','PRIVATE CHANGE DESCRIPTION','Reason',change.pk,rev(cls.case))
        req=add_evidence(cls.actor,cls.case.pk,'requirements','Synthetic requirements','synthetic:requirements')
        candidate=register_candidate(cls.actor,cls.case.pk,'CANDIDATE',req.pk,rev(cls.case))
        record_gate(cls.actor,cls.case.pk,candidate.pk,'qa_exit','synthetic:qa',req.pk,rev(cls.case))
        rfp=add_evidence(cls.actor,cls.case.pk,'rfp_intake','Synthetic intake','synthetic:rfp')
        intake(cls.actor,cls.case.pk,'RFP',rfp.pk,timezone.now(),'unknown',None,None,'Native intake',rev(cls.case))
        cls.start=timezone.now()-timedelta(days=7);cls.end=timezone.now()+timedelta(seconds=1)

    def rows(self):
        # Full rowsets, not counts: denied calls cannot rewrite existing records.
        with connection.cursor() as cursor:
            cursor.execute("select tablename from pg_tables where schemaname='public' order by tablename")
            result={}
            for (table,) in cursor.fetchall():
                cursor.execute('select row_to_json(t)::text from '+connection.ops.quote_name(table)+' t order by row_to_json(t)::text')
                result[table]=cursor.fetchall()
            return result

    def draft(self,**kwargs):
        return draft_period_report(self.actor,self.case.pk,'weekly_client',self.start,self.end,self.template.pk,'client',rev(self.case),**kwargs)

    def test_each_missing_source_grant_denies_service_without_any_row_writes(self):
        for action in ['report.read','meeting.read','issue.read','change.read','delivery.read','rfp.read']:
            with self.subTest(action=action):
                grant=Grant.objects.get(case=self.case,user=self.actor,action=action)
                grant.delete();before=self.rows()
                with self.assertRaises(PermissionDenied):self.draft()
                self.assertEqual(before,self.rows())
                Grant.objects.create(case=self.case,user=self.actor,action=action)

    def test_manual_http_denies_missing_issue_access_without_partial_writes(self):
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.read').delete()
        self.client.force_login(self.actor);before=self.rows()
        response=self.client.post(f'/cases/{self.case.pk}/meetings/',{'action':'report','revision':rev(self.case),'kind':'weekly_client','start_at':self.start.isoformat(),'end_at':self.end.isoformat(),'template':self.template.pk,'audience':'client'})
        self.assertEqual(response.status_code,403);self.assertEqual(before,self.rows())

    def test_revoked_grant_blocks_new_revision_and_scheduled_reuse(self):
        binding=self.draft();before_version=binding.version_id
        Grant.objects.filter(case=self.case,user=self.actor,action='change.read').update(active=False)
        for reuse in [False,True]:
            before=self.rows()
            with self.assertRaises(PermissionDenied):self.draft(reuse_existing=reuse)
            self.assertEqual(before,self.rows())
        self.assertEqual(binding.version_id,before_version)

    def test_schedule_holds_without_snapshot_document_occurrence_or_review_writes(self):
        configure_clock(self.actor,self.case,self.owner)
        schedule=save_schedule(self.actor,self.case.pk,'weekly_client',self.template.pk,'client',rev(self.case))
        schedule=arm_schedule(self.actor,self.case.pk,schedule.pk,'2026-10-20T12:00:00+01:00',rev(self.case))
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.read').update(active=False)
        before=self.rows();self.assertTrue(run_report_once(schedule.next_due_at));after=self.rows()
        schedule.refresh_from_db();self.assertEqual(schedule.status,'held')
        self.assertFalse(ReportOccurrence.objects.exists())
        allowed={'pmo_reportschedule','core_case','core_audit'}
        self.assertEqual({k:v for k,v in before.items() if k not in allowed},{k:v for k,v in after.items() if k not in allowed})
        self.assertFalse(run_report_once(schedule.next_due_at))

    def test_current_authorized_report_keeps_client_projection_and_idempotent_reuse(self):
        binding=self.draft();before=self.rows()
        self.assertEqual(self.draft(reuse_existing=True).pk,binding.pk)
        self.assertEqual(before,self.rows())
        self.assertIn('PRIVATE ISSUE NEXT ACTION',self.case.evidence.get(kind='report_snapshot').body)
        self.assertNotIn('PRIVATE ISSUE NEXT ACTION',str(binding.version.payload))
        self.assertNotIn('PRIVATE CHANGE DESCRIPTION',str(binding.version.payload))
        self.assertNotIn('SECRET-CHANGE',str(binding.version.payload))
        self.assertTrue(binding.version.fields['scope']['text'].startswith('Unknown:'))
        self.assertTrue(binding.version.fields['dependencies']['text'].startswith('Unknown:'))
        self.assertNotIn('issue_impact',binding.version.payload)

    def test_grant_from_another_case_never_authorizes_source(self):
        from apps.core.models import Case
        other=Case.objects.create(tenant='test-tenant',title='Other',kind='project',synthetic=True)
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.read').delete()
        Grant.objects.create(case=other,user=self.actor,action='issue.read')
        before=self.rows()
        with self.assertRaises(PermissionDenied):self.draft()
        self.assertEqual(before,self.rows())


class EmptySourceReportAccessTests(TestCase):
    def test_absent_optional_domains_do_not_require_extra_grants(self):
        actor,case,owner,notes,minutes,template,meeting,recipient=meetings_fixture()
        required=['case.read','report.read','report.draft','meeting.read','evidence.add','document.draft']
        Grant.objects.filter(case=case,user=actor).exclude(action__in=required).delete()
        now=timezone.now()
        binding=draft_period_report(actor,case.pk,'weekly_client',now-timedelta(days=7),now,template.pk,'client',rev(case))
        self.assertEqual(binding.version.audience,'client')
        self.assertEqual(set(Grant.objects.filter(case=case,user=actor).values_list('action',flat=True)),set(required))
