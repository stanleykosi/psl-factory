import os
import subprocess
import sys
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction,close_old_connections,connection
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition,resolve,PolicyHold
from apps.pmo.issues import log_issue,update_issue
from apps.pmo.escalations import (capture_profile,request_escalation,decide_escalation,draft_escalation,timing,scan_profile,scan_due)
from apps.pmo.models import EscalationProfile,EscalationDecision,EscalationSignal,EscalationRequest,EscalationScanCursor
from apps.documents.controlled import request_review,review_version,reserve_publication,preflight
from apps.documents.delivery import run_publication_once
from apps.documents.models import Publication,PublicationReceipt,PublicationJob
from apps.agents.escalations import investigate_escalations
from .helpers import rev,activate,setup_case
from .document_helpers import publication_fixture,artifact


def fixture():
    a,c,owner,source,t,recipient,recips,storage=publication_fixture()
    state=log_issue(a,c.pk,'ESC-001','Blocking dependency','Delivery',a.pk,'Investigate dependency',source.pk,'Source-bound issue',rev(c),'High')
    return a,c,owner,source,t,recipient,state


def clocks(a,c,owner,anchor='trigger_at',routes=True):
    clock=artifact(a,c,'D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',{'issues':{'anchor':anchor,'basis':'elapsed_hours','pause':'no_pause'}},owner)
    values={'acknowledgement_hours':2}
    if routes:values['internal_24h_routes']={'Critical':'CTO','High':'PMO','Medium':'PMO','Low':'PMO'}
    params=artifact(a,c,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'issues':values},owner)
    return clock,params


def profile(a,c,state,source,classification='internal',impact=False,trigger=None):
    return capture_profile(a,c.pk,state.issue_id,state.pk,classification,impact,trigger,source.pk,'Captured impact evidence',rev(c))


def publish(a,c,request,t):
    v=draft_escalation(a,c.pk,request.pk,t.pk,rev(c))
    request_review(a,c.pk,v.pk,rev(c));review_version(a,c.pk,v.pk,'approve','Reviewed exact audience version',rev(c))
    p=reserve_publication(a,c.pk,v.pk,rev(c))
    assert run_publication_once()
    return p


class EscalationTests(TestCase):
    def setUp(self):self.a,self.c,self.owner,self.source,self.t,self.recipient,self.state=fixture()

    def test_manual_client_path_requires_human_decision_then_reviewed_delivery_without_clocks(self):
        a,c=self.a,self.c;p=profile(a,c,self.state,self.source,'client_dependent',True)
        r=request_escalation(a,c.pk,p.pk,'escalate','Client',self.source.pk,'Please investigate dependency',rev(c))
        with self.assertRaises(ValidationError):draft_escalation(a,c.pk,r.pk,self.t.pk,rev(c))
        decide_escalation(a,c.pk,r.pk,'Head of PMO','approve','Client communication approved',rev(c))
        pub=publish(a,c,r,self.t)
        receipt=PublicationReceipt.objects.get(publication=pub)
        self.assertEqual(receipt.recipient_id,self.recipient.pk)
        self.assertEqual(receipt.payload['sections'][0]['text'],'Blocking dependency: escalate requested.')
        self.assertEqual(Publication.objects.count(),1)
        self.assertEqual(timing(p)['clock_status'],'UNCONFIGURED')

    def test_client_deescalation_also_needs_decision_and_no_auto_approval(self):
        p=profile(self.a,self.c,self.state,self.source,'client_dependent')
        r=request_escalation(self.a,self.c.pk,p.pk,'de_escalate','Client',self.source.pk,'Proposed de-escalation',rev(self.c))
        with self.assertRaises(ValidationError):draft_escalation(self.a,self.c.pk,r.pk,self.t.pk,rev(self.c))
        self.assertEqual(r.decisions.count(),0);self.assertEqual(Publication.objects.count(),0)
        decide_escalation(self.a,self.c.pk,r.pk,'PMO Lead','approve','Explicit human de-escalation decision',rev(self.c))
        publish(self.a,self.c,r,self.t)
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_immediate_impact_remains_known_when_policy_missing_and_unknowns_are_not_zero(self):
        p=profile(self.a,self.c,self.state,self.source,'unclassified',True)
        result=timing(p)
        self.assertTrue(result['immediate']);self.assertIsNone(result['elapsed_hours']);self.assertIsNone(result['internal_24h'])
        first=scan_profile(self.a,self.c.pk,p.pk)
        self.assertEqual(len(first),1);self.assertEqual(scan_profile(self.a,self.c.pk,p.pk),[])
        self.assertIsNone(EscalationSignal.objects.get().target)
        self.assertFalse(EscalationRequest.objects.exists());self.assertFalse(Publication.objects.exists())

    def test_source_threshold_boundaries_acknowledgement_and_narrow_elapsed_dependencies(self):
        now=timezone.now();anchor=now-timedelta(days=3)
        p=profile(self.a,self.c,self.state,self.source,trigger=anchor)
        clocks(self.a,self.c,self.owner)
        before=timing(p,anchor+timedelta(hours=24,microseconds=-1));at=timing(p,anchor+timedelta(hours=24));late=timing(p,anchor+timedelta(hours=48))
        self.assertFalse(before['internal_24h']);self.assertTrue(at['internal_24h']);self.assertFalse(at['internal_48h'])
        self.assertTrue(late['internal_48h']);self.assertEqual(at['internal_24h_target'],'PMO')
        self.assertEqual(at['acknowledgement_status'],'OVERDUE')
        self.assertEqual(resolve('D04.working_calendar_ref',self.c).status,'MISSING')
        self.assertEqual(resolve('D04.iana_timezone',self.c).status,'MISSING')
        self.assertEqual(len(scan_profile(self.a,self.c.pk,p.pk,anchor+timedelta(hours=48))),3)
        self.assertFalse(Publication.objects.exists())

    def test_clock_trigger_unknown_future_and_severity_routing_unknown_are_explicit(self):
        p=profile(self.a,self.c,self.state,self.source)
        clocks(self.a,self.c,self.owner,routes=False)
        self.assertIsNone(timing(p)['elapsed_hours'])
        p2=profile(self.a,self.c,self.state,self.source,trigger=timezone.now()-timedelta(days=2))
        result=timing(p2)
        self.assertIsNone(result['internal_24h_target']);self.assertTrue(result['internal_48h'])
        self.assertEqual(timing(p2,p2.trigger_at-timedelta(seconds=1))['clock_status'],'FUTURE_ANCHOR')
        with self.assertRaises(ValidationError):profile(self.a,self.c,self.state,self.source,trigger=timezone.now()+timedelta(hours=1))

    def test_logged_anchor_and_acknowledged_late_actual_service_timestamps(self):
        clocks(self.a,self.c,self.owner,'logged_at')
        p=profile(self.a,self.c,self.state,self.source)
        self.assertEqual(timing(p)['anchor'],self.state.created_at.isoformat())
        s=update_issue(self.a,self.c.pk,self.state.issue_id,self.state.pk,'acknowledge',self.source.pk,'Actual owner acknowledgement',rev(self.c))
        clock,params=clocks(self.a,self.c,self.owner,'trigger_at')
        p2=profile(self.a,self.c,s,self.source,trigger=timezone.now()-timedelta(hours=5))
        self.assertEqual(timing(p2)['acknowledgement_status'],'LATE')

    def test_policy_revocation_and_supersession_keep_immediate_but_never_rewrite_signals(self):
        p=profile(self.a,self.c,self.state,self.source,impact=True,trigger=timezone.now()-timedelta(days=3))
        clock,params=clocks(self.a,self.c,self.owner)
        scan_profile(self.a,self.c.pk,p.pk)
        count=EscalationSignal.objects.count()
        clocks(self.a,self.c,self.owner)
        scan_profile(self.a,self.c.pk,p.pk)
        self.assertEqual(EscalationSignal.objects.filter(kind='immediate').count(),1)
        self.assertGreater(EscalationSignal.objects.count(),count)
        current=resolve('D04.clock_anchor_pause_rules',self.c).configuration
        transition(self.a,current.pk,'revoked')
        self.assertEqual(timing(p)['clock_status'],'UNCONFIGURED');self.assertTrue(timing(p)['immediate'])

    def test_invalid_clock_configuration_does_not_install_guessed_rules(self):
        for value in [{'issues':{'anchor':'created','basis':'elapsed_hours','pause':'no_pause'}},
                      {'issues':{'anchor':'trigger_at','basis':'working_days','pause':'no_pause'}}]:
            with self.assertRaises(ValidationError):artifact(self.a,self.c,'D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',value,self.owner)
        for value in [{'issues':{'acknowledgement_hours':0}}, {'issues':{'internal_24h_routes':{'High':'CEO'}}}, {'issues':{'internal_48h_threshold':72}}]:
            with self.assertRaises(ValidationError):artifact(self.a,self.c,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',value,self.owner)

    def test_changed_issue_or_profile_holds_queued_client_message(self):
        p=profile(self.a,self.c,self.state,self.source,'client_dependent')
        r=request_escalation(self.a,self.c.pk,p.pk,'escalate','Client',self.source.pk,'Investigate',rev(self.c))
        decide_escalation(self.a,self.c.pk,r.pk,'PMO Lead','approve','Decision',rev(self.c))
        v=draft_escalation(self.a,self.c.pk,r.pk,self.t.pk,rev(self.c))
        request_review(self.a,self.c.pk,v.pk,rev(self.c));review_version(self.a,self.c.pk,v.pk,'approve','Reviewed',rev(self.c))
        pub=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c))
        update_issue(self.a,self.c.pk,self.state.issue_id,self.state.pk,'acknowledge',self.source.pk,'Owner acknowledges',rev(self.c))
        self.assertTrue(run_publication_once());self.assertEqual(PublicationJob.objects.get(publication=pub).status,'held')
        self.assertFalse(PublicationReceipt.objects.exists())
        with self.assertRaises(ValidationError):request_escalation(self.a,self.c.pk,p.pk,'escalate','CTO',self.source.pk,'Stale',rev(self.c))

    def test_decision_revoked_grant_or_new_profile_requires_fresh_approval(self):
        p=profile(self.a,self.c,self.state,self.source,'client_dependent')
        r=request_escalation(self.a,self.c.pk,p.pk,'escalate','Client',self.source.pk,'Investigate',rev(self.c))
        decide_escalation(self.a,self.c.pk,r.pk,'PMO Lead','approve','Decision',rev(self.c))
        v=draft_escalation(self.a,self.c.pk,r.pk,self.t.pk,rev(self.c))
        Grant.objects.filter(case=self.c,user=self.a,action='issue.escalation_decide').update(active=False)
        self.assertTrue(preflight(v))
        Grant.objects.filter(case=self.c,user=self.a,action='issue.escalation_decide').update(active=True)
        profile(self.a,self.c,self.state,self.source,'client_dependent',True)
        self.assertTrue(preflight(v))

    def test_internal_delivery_requires_actual_configured_role_recipient(self):
        a,c=self.a,self.c
        cto=get_user_model().objects.create_user('cto-recipient')
        Grant.objects.create(case=c,user=cto,action='document.receive:internal')
        assignment=resolve('D05.role_principal_assignments',c).configuration
        ref=register_reference(a,c.pk,'escalation:cto','schema:psl/role-assignment/v1',{'role':'CTO','user_id':cto.pk},self.owner.pk)
        activate(a,c,'D05.role_principal_assignments',assignment.envelope['value']+[ref.ref],self.owner)
        recipient=register_reference(a,c.pk,'internal:wrong','schema:psl/document-recipient/v1',{'audience':'internal','user_id':a.pk},self.owner.pk)
        activate(a,c,'D11.recipient_grant_refs',[recipient.ref],self.owner)
        p=profile(a,c,self.state,self.source)
        r=request_escalation(a,c.pk,p.pk,'escalate','CTO',self.source.pk,'Internal CTO request',rev(c))
        v=draft_escalation(a,c.pk,r.pk,self.t.pk,rev(c));request_review(a,c.pk,v.pk,rev(c));review_version(a,c.pk,v.pk,'approve','Internal quality review',rev(c))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,v.pk,rev(c))
        right=register_reference(a,c.pk,'internal:right','schema:psl/document-recipient/v1',{'audience':'internal','user_id':cto.pk},self.owner.pk)
        activate(a,c,'D11.recipient_grant_refs',[right.ref],self.owner)
        pub=reserve_publication(a,c.pk,v.pk,rev(c));self.assertTrue(run_publication_once())
        self.assertEqual(PublicationReceipt.objects.get().recipient_id,cto.pk)
        self.assertIn('D05.role_principal_assignments',pub.policies)
        self.assertEqual(r.decisions.count(),0)

    def test_history_scope_staleness_and_meaningful_agent(self):
        p=profile(self.a,self.c,self.state,self.source,impact=True)
        with self.assertRaises(ValidationError):capture_profile(self.a,self.c.pk,self.state.issue_id,self.state.pk,'internal',False,None,self.source.pk,'Stale',rev(self.c)-1)
        with self.assertRaises(DatabaseError),transaction.atomic():EscalationProfile.objects.filter(pk=p.pk).update(note='rewrite')
        run=investigate_escalations(self.a,self.c.pk,rev(self.c))
        self.assertFalse(run.result['approval_granted']);self.assertFalse(run.result['communications_dispatched'])
        self.assertEqual(run.result['findings'][0]['evidence_id'],self.source.pk)
        other,case=setup_case(username='other')
        with self.assertRaises(PermissionDenied):request_escalation(other,self.c.pk,p.pk,'escalate','Client',self.source.pk,'No grant',rev(self.c))
        with self.assertRaises(ValidationError):request_escalation(other,case.pk,p.pk,'escalate','Client',self.source.pk,'Foreign profile',rev(case))

    def test_return_requires_its_independent_policy_and_cannot_turn_into_approval(self):
        p=profile(self.a,self.c,self.state,self.source,'client_dependent')
        r=request_escalation(self.a,self.c.pk,p.pk,'escalate','Client',self.source.pk,'Investigate',rev(self.c))
        with self.assertRaises(PolicyHold):decide_escalation(self.a,self.c.pk,r.pk,'PMO Lead','return','Needs revision',rev(self.c))
        artifact(self.a,self.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},self.owner)
        decide_escalation(self.a,self.c.pk,r.pk,'PMO Lead','return','Needs revision',rev(self.c))
        with self.assertRaises(ValidationError):decide_escalation(self.a,self.c.pk,r.pk,'PMO Lead','approve','No new source',rev(self.c))
        self.assertEqual(r.decisions.count(),1)

    def test_worker_cursor_advances_past_non_due_issues(self):
        p=profile(self.a,self.c,self.state,self.source,impact=False)
        state2=log_issue(self.a,self.c.pk,'ESC-002','Second issue','Delivery',self.a.pk,'Investigate',self.source.pk,'Source',rev(self.c),'Low')
        p2=profile(self.a,self.c,state2,self.source,impact=True)
        self.assertEqual(scan_due(1),0)
        self.assertEqual(scan_due(1),1)
        self.assertEqual(EscalationSignal.objects.get().profile_id,p2.pk)
        self.assertEqual(scan_due(1),0)

    def test_escalation_evidence_invalidates_older_reporting_snapshot(self):
        from apps.documents.controlled import register_template
        from apps.pmo.reporting import draft_period_report
        t=register_template(self.a,self.c.pk,'Internal report',{'document_type':'status_report','required_fields':['executive_summary','status'],
            'audience_fields':{'internal':['executive_summary','status']}},self.owner.pk,rev(self.c))
        Grant.objects.get_or_create(case=self.c,user=self.a,action='report.read')
        b=draft_period_report(self.a,self.c.pk,'internal_tuesday',timezone.now()-timedelta(days=7),timezone.now(),t.pk,'internal',rev(self.c))
        self.assertFalse(preflight(b.version))
        profile(self.a,self.c,self.state,self.source)
        self.assertTrue(preflight(b.version))

    def test_separate_head_decision_principal_is_rechecked_on_delivery(self):
        a,c=self.a,self.c
        head=get_user_model().objects.create_user('head-principal')
        Grant.objects.create(case=c,user=head,action='issue.escalation_decide')
        assignment=resolve('D05.role_principal_assignments',c).configuration
        # Replace only Head's role reference; the PMO Lead reviewer is a distinct person.
        from apps.policy.services import reference_values
        values=reference_values(assignment)
        refs=[]
        for i,value in enumerate(values):
            if value['role']=='Head of PMO':value=dict(value,user_id=head.pk)
            ref=register_reference(a,c.pk,'separate:role:'+str(i),'schema:psl/role-assignment/v1',value,self.owner.pk)
            refs.append(ref.ref)
        activate(a,c,'D05.role_principal_assignments',refs,self.owner)
        p=profile(a,c,self.state,self.source,'client_dependent')
        r=request_escalation(a,c.pk,p.pk,'escalate','Client',self.source.pk,'Investigate',rev(c))
        decide_escalation(head,c.pk,r.pk,'Head of PMO','approve','Separate head decision',rev(c))
        v=draft_escalation(a,c.pk,r.pk,self.t.pk,rev(c))
        request_review(a,c.pk,v.pk,rev(c));review_version(a,c.pk,v.pk,'approve','Separate PMO Lead review',rev(c))
        pub=reserve_publication(a,c.pk,v.pk,rev(c))
        Grant.objects.filter(case=c,user=head,action='issue.escalation_decide').update(active=False)
        self.assertTrue(run_publication_once())
        self.assertEqual(PublicationJob.objects.get(publication=pub).status,'held')
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_operational_signal_scan_rejects_injected_test_clock(self):
        a,c=setup_case(synthetic=False,username='operational')
        source=add_evidence(a,c.pk,'issue_impact','Authorized intake evidence','source:operational')
        state=log_issue(a,c.pk,'OP-001','Operational intake','Delivery',a.pk,'Investigate',source.pk,'Intake without guessed severity',rev(c))
        p=profile(a,c,state,source,impact=True)
        with self.assertRaises(ValidationError):scan_profile(a,c.pk,p.pk,timezone.now()+timedelta(days=5))
        self.assertFalse(EscalationSignal.objects.filter(profile=p).exists())

    def test_real_staff_profile_request_decision_and_draft_forms(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/escalations/'
        self.assertEqual(self.client.post(url,{'action':'profile','revision':rev(self.c),'state':self.state.pk,'classification':'client_dependent',
            'timeline_impact':'2','evidence':self.source.pk,'note':'Staff impact evidence'}).status_code,302)
        p=EscalationProfile.objects.get()
        self.assertEqual(self.client.post(url,{'action':'request','revision':rev(self.c),'profile':p.pk,'direction':'escalate','target':'Client','evidence':self.source.pk,'note':'Please investigate'}).status_code,302)
        r=EscalationRequest.objects.get()
        self.assertEqual(self.client.post(url,{'action':'decision','revision':rev(self.c),'request':r.pk,'role':'PMO Lead','verdict':'approve','note':'Human source decision'}).status_code,302)
        self.assertEqual(self.client.post(url,{'action':'draft','revision':rev(self.c),'request':r.pk,'template':self.t.pk}).status_code,302)
        self.assertContains(self.client.get(url),'Request #')
        self.assertContains(self.client.get(f'/cases/{self.c.pk}/issues/'),'Escalation decisions')
        admin=get_user_model().objects.create_superuser('admin','admin@example.test','test-only')
        self.client.force_login(admin);self.assertEqual(self.client.get(url).status_code,404)


class EscalationProcessTests(TransactionTestCase):
    def prepared(self):
        a,c,owner,source,t,recipient,state=fixture()
        p=profile(a,c,state,source,'internal',True,timezone.now()-timedelta(days=3))
        clocks(a,c,owner)
        return a,c,p

    def test_two_connections_signal_once(self):
        a,c,p=self.prepared()
        def scan():
            close_old_connections()
            try:return scan_profile(a,c.pk,p.pk)
            finally:connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:scan(),range(2)))
        self.assertEqual(sum(map(len,results)),4)
        self.assertEqual(EscalationSignal.objects.count(),4)
        self.assertFalse(Publication.objects.exists())

    def test_persisted_cursor_and_repeated_actual_worker_process(self):
        a,c,p=self.prepared()
        env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        cmd=[sys.executable,'manage.py','work_escalations','--limit','1']
        first=subprocess.run(cmd,cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertIn('Created 4',first.stdout)
        second=subprocess.run(cmd,cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(second.returncode,0,second.stderr);self.assertIn('Created 0',second.stdout)
        self.assertEqual(EscalationSignal.objects.count(),4)
        self.assertEqual(EscalationScanCursor.objects.get().after_issue_id,p.state.issue_id)
