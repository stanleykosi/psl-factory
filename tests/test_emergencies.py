import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta,datetime,timezone as utc
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError,close_old_connections
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from django.conf import settings
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition,PolicyHold
from apps.policy.change_drafts import draft_standard_policy
from apps.pmo.changes import log_change
from apps.pmo.gates import register_candidate,record_gate,verify_gate
from apps.pmo.models import (EmergencyProfile,EmergencyDecision,EmergencyAuthorization,EmergencyOutcome,
    EmergencyReview,EmergencyRetrospectiveDecision,EmergencyRetrospectiveRecord,EmergencyDeadlineSignal,EmergencyScanCursor)
from apps.pmo.emergencies import (capture_profile,decide_emergency,authorize_emergency,capture_outcome,record_review,
    decide_retrospective,reconcile_retrospective,timing,preauthorization_inputs)
from apps.pmo.emergency_obligations import scan_outcome,scan_due
from apps.pmo.emergency_documents import draft_retrospective
from apps.agents.emergencies import investigate_emergency
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt,PublicationJob
from adapters.pmo_reporting import LocalPMOReportingAdapter
from .helpers import activate,rev,setup_case
from .document_helpers import artifact
from .test_commercial_changes import fixture

GATES={'preauthorization_roles':['Incident Lead','Engineering Lead'],'p1_additional_roles':['CTO'],
    'retrospective_roles':['Product','Engineering Lead'],'financial_controls':'independent','deployment_dispatch':'not_granted'}


class EmergencyFixture:
    def setUp(self):
        self.actor,self.case,self.e,self.old_template=fixture(existing=True)
        a,c=self.actor,self.case
        refs=[]
        for role in ['PM','Head of PMO','CEO','PMO Lead','Engineering Lead','Security Lead','CTO','Product']:
            r=register_reference(a,c.pk,'emergency-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':a.pk},self.e['policy_decision'].pk);refs.append(r.ref)
        self.roles=activate(a,c,'D05.role_principal_assignments',refs,self.e['policy_decision'])
        self.incident=self.evidence('incident','Synthetic external Engineering incident')
        self.classification=self.evidence('incident_classification','Explicit critical production and P1 owner attestation, not severity inference')
        self.source=self.evidence('change_request','Synthetic Emergency request')
        self.decision=self.evidence('emergency_decision','Synthetic exact human decision evidence')
        self.implementation=self.evidence('change_implementation','Synthetic actual owner outcome')
        self.review_evidence=self.evidence('post_implementation_review','Synthetic post-implementation owner review')
        self.cv=log_change(a,c.pk,'EM-001','Emergency','API','Emergency procedure','Incident needs immediate work',self.source.pk,rev(c),self.incident.pk)
        self.candidate=register_candidate(a,c.pk,'emergency-candidate',self.e['requirements'].pk,rev(c))
        self.profile=capture_profile(a,c.pk,self.cv.pk,self.candidate.pk,True,True,self.classification.pk,'Explicit source classification',rev(c))

    def evidence(self,kind,body):return add_evidence(self.actor,self.case.pk,kind,body,'synthetic:emergency-tests')

    def policies(self,mode='coexist',overlap='explicit_same_person',incident_role='Engineering Lead'):
        value={'mode':mode,'incident_lead_role':incident_role,'incident_engineering_overlap':overlap,
            'exception_roles':[] if mode=='coexist' else ['CEO'],'priority_basis':'explicit_incident_p1_attestation'}
        if mode=='defer':value['deferred_checkpoint']='before_retrospective_reconciliation'
        config=draft_standard_policy(self.actor,self.case.pk,'D01.emergency_glpi_relationship',value,self.e['policy_decision'].pk,timezone.now()-timedelta(hours=1))
        transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')
        gates=artifact(self.actor,self.case,'D01.satisfied_gate_map','schema:psl/change-satisfied-gates/v2',{'emergency':GATES},self.e['policy_decision'])
        return config,gates

    def decisions(self,mode='coexist',incident_role='Engineering Lead'):
        for role in ['Incident Lead','Engineering Lead','CTO']+(['GLPI exception:CEO'] if mode!='coexist' else []):
            decide_emergency(self.actor,self.case.pk,self.profile.pk,role,incident_role,'approve',self.decision.pk,'Human checked exact incident/profile',rev(self.case))

    def glpi(self):
        for kind in ['glpi_security','glpi_cto','glpi_ceo']:
            record=record_gate(self.actor,self.case.pk,self.candidate.pk,kind,'synthetic:'+kind,self.source.pk,rev(self.case))
            verify_gate(self.actor,self.case.pk,record.pk,rev(self.case))

    def clocks(self,days=1,weekdays=None,holidays=None,anchor_day='exclude'):
        a,c,e=self.actor,self.case,self.e['policy_decision']
        activate(a,c,'D04.iana_timezone','UTC',e)
        r=register_reference(a,c.pk,'emergency-calendar','schema:psl/working-calendar/v1',
            {'weekdays':weekdays if weekdays is not None else list(range(7)),'holidays':holidays or [],'due_time':'23:59'},e.pk)
        activate(a,c,'D04.working_calendar_ref',r.ref,e)
        artifact(a,c,'D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',
            {'emergency':{'anchor':'implemented_at','pause':'no_pause','anchor_day':anchor_day}},e)
        return artifact(a,c,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'emergency':{'retrospective_working_days':days}},e)

    def authorized(self,mode='coexist'):
        self.policies(mode);self.decisions(mode)
        if mode=='coexist':self.glpi()
        return authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))

    def outcome(self,auth=None,implemented=None):
        return capture_outcome(self.actor,self.case.pk,self.profile.pk,auth.pk if auth else None,
            implemented or timezone.now(),self.implementation.pk,'Captured actual external owner result',rev(self.case))

    def reviewed(self,outcome):
        r=record_review(self.actor,self.case.pk,outcome.pk,self.review_evidence.pk,'Mandatory owner review',rev(self.case))
        for role in ['Product','Engineering Lead']:
            decide_retrospective(self.actor,self.case.pk,outcome.pk,role,'approve',self.decision.pk,'Exact post-implementation review checked',rev(self.case))
        return r

    def report(self,outcome):
        t=register_template(self.actor,self.case.pk,'Emergency report',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','status','next_steps'],'internal':['executive_summary','status','next_steps']}},self.e['policy_decision'].pk,rev(self.case))
        artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
            {'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},self.e['policy_decision'])
        version=draft_retrospective(self.actor,self.case.pk,outcome.pk,t.pk,'client',rev(self.case))
        request_review(self.actor,self.case.pk,version.pk,rev(self.case))
        review_version(self.actor,self.case.pk,version.pk,'approve','PMO Lead checked exact projection',rev(self.case))
        reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case));return version


class EmergencyTests(EmergencyFixture,TestCase):
    def test_coexist_preauthorization_review_retrospective_and_reviewed_publication(self):
        auth=self.authorized();self.assertEqual(connection.vendor,'postgresql')
        self.assertEqual(len(auth.snapshot['glpi']),3);self.assertEqual(len(auth.snapshot['decision_ids']),3)
        outcome=self.outcome(auth);self.clocks();self.reviewed(outcome)
        record=reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertEqual(record.snapshot['status'],'evidenced_on_time')
        version=self.report(outcome);self.assertTrue(run_publication_once())
        receipt=PublicationReceipt.objects.get(publication__version=version)
        self.assertIn('evidenced_on_time',json.dumps(receipt.payload))
        self.assertFalse(investigate_emergency(self.actor,self.case.pk,outcome.pk,rev(self.case)).result['deployment_dispatched'])
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(f'/cases/{self.case.pk}/emergencies/'),'evidenced_on_time')

    def test_prescribed_decisions_and_actual_outcomes_do_not_require_glpi_or_calendar_policy(self):
        self.decisions()
        with self.assertRaises(PolicyHold):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))
        outcome=self.outcome(implemented=timezone.now()-timedelta(days=3));self.reviewed(outcome)
        self.assertIsNone(timing(self.case,outcome)['log_due_at'])
        with self.assertRaisesMessage(ValidationError,'Missing pre-implementation'):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertEqual(len(scan_outcome(self.actor,self.case.pk,outcome.pk)),1)
        self.assertEqual(len(scan_outcome(self.actor,self.case.pk,outcome.pk)),0)

    def test_missing_or_unknown_incident_priority_is_not_inferred_from_critical(self):
        self.policies();self.glpi();self.decisions()
        self.profile=capture_profile(self.actor,self.case.pk,self.cv.pk,self.candidate.pk,True,None,self.classification.pk,'P1 is unknown',rev(self.case))
        self.decisions()
        with self.assertRaisesMessage(ValidationError,'P1 basis'):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))

    def test_p1_needs_cto_and_non_p1_still_needs_both_prescribed_roles(self):
        self.policies();self.glpi()
        for role in ['Incident Lead','Engineering Lead']:
            decide_emergency(self.actor,self.case.pk,self.profile.pk,role,'Engineering Lead','approve',self.decision.pk,'Checked',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'CTO'):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))
        self.profile=capture_profile(self.actor,self.case.pk,self.cv.pk,self.candidate.pk,True,False,self.classification.pk,'Explicit non-P1',rev(self.case))
        for role in ['Incident Lead','Engineering Lead']:
            decide_emergency(self.actor,self.case.pk,self.profile.pk,role,'Engineering Lead','approve',self.decision.pk,'Checked',rev(self.case))
        self.assertEqual(len(authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case)).snapshot['decision_ids']),2)

    def test_distinct_people_rule_does_not_silently_count_one_actor_twice(self):
        self.policies(overlap='distinct_people');self.glpi();self.decisions()
        with self.assertRaisesMessage(ValidationError,'distinct people'):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))

    def test_coexist_needs_verified_current_glpi_not_just_text_or_old_acceptance(self):
        self.policies();self.decisions()
        record_gate(self.actor,self.case.pk,self.candidate.pk,'glpi_security','claims-approved',self.source.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'source-verified GLPI'):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))
        self.glpi()
        record_gate(self.actor,self.case.pk,self.candidate.pk,'glpi_security','new-unverified-source',self.source.pk,rev(self.case))
        with self.assertRaises(ValidationError):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))

    def test_defer_needs_exception_decision_and_later_glpi_before_reconciliation(self):
        self.policies('defer');self.decisions()  # No exception decision yet.
        with self.assertRaisesMessage(ValidationError,'GLPI exception:CEO'):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))
        decide_emergency(self.actor,self.case.pk,self.profile.pk,'GLPI exception:CEO','','approve',self.decision.pk,'Explicit configured deferral',rev(self.case))
        auth=authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case));outcome=self.outcome(auth)
        self.clocks();self.reviewed(outcome)
        with self.assertRaisesMessage(ValidationError,'GLPI'):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.glpi();self.assertEqual(reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case)).snapshot['status'],'evidenced_on_time')

    def test_replace_is_explicit_human_exception_and_never_financial_or_dispatch_permission(self):
        auth=self.authorized('replace');self.assertEqual(auth.snapshot['glpi'],[])
        self.assertEqual(len(auth.snapshot['decision_ids']),4)
        outcome=self.outcome(auth);self.clocks();self.reviewed(outcome)
        result=reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertEqual(result.snapshot['status'],'evidenced_on_time')
        from apps.pmo.changes import authorize_change
        with self.assertRaises(ValidationError):authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))

    def test_missing_calendar_holds_only_deadline_reconciliation_not_human_decisions(self):
        outcome=self.outcome(self.authorized());self.reviewed(outcome)
        artifact(self.actor,self.case,'D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',
            {'emergency':{'anchor':'implemented_at','pause':'no_pause','anchor_day':'exclude'}},self.e['policy_decision'])
        clock=timing(self.case,outcome);self.assertIsNotNone(clock['log_due_at']);self.assertIsNone(clock['retrospective_due_at'])
        with self.assertRaises(ValidationError):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertEqual(EmergencyRetrospectiveDecision.objects.count(),2)

    def test_working_days_holiday_and_elapsed_log_boundary(self):
        now=timezone.now();friday=(now-timedelta(days=14)).date()
        while friday.weekday()!=4:friday-=timedelta(days=1)
        implemented=datetime.combine(friday,datetime.min.time(),tzinfo=utc.utc)+timedelta(hours=10)
        outcome=self.outcome(implemented=implemented)
        monday=friday+timedelta(days=3);self.clocks(days=2,weekdays=[0,1,2,3,4],holidays=[monday.isoformat()])
        clock=timing(self.case,outcome,implemented+timedelta(hours=24))
        self.assertEqual(clock['log_due_at'],(implemented+timedelta(hours=24)).isoformat())
        self.assertTrue(clock['log_late'])
        self.assertEqual(datetime.fromisoformat(clock['retrospective_due_at']).date(),friday+timedelta(days=5))
        self.assertEqual({s.kind for s in scan_outcome(self.actor,self.case.pk,outcome.pk)},
            {'missing_preauthorization','late_emergency_log','retrospective_deadline_exception'})

    def test_late_log_and_later_authority_never_become_preauthorization(self):
        auth=self.authorized();outcome=self.outcome(auth,timezone.now()-timedelta(days=5));self.clocks();self.reviewed(outcome)
        with self.assertRaisesMessage(ValidationError,'Missing pre-implementation'):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        with self.assertRaises(ValidationError):decide_emergency(self.actor,self.case.pk,self.profile.pk,'CTO','','approve',self.decision.pk,'Too late',rev(self.case))
        with self.assertRaises(ValidationError):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))
        self.assertTrue(timing(self.case,outcome)['log_late'])

    def test_review_revision_invalidates_old_retrospective_decisions(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        record_review(self.actor,self.case.pk,outcome.pk,self.review_evidence.pk,'Corrected owner review',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'review-bound'):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))

    def test_new_source_or_revoked_source_grant_holds_queued_report(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        version=self.report(outcome)
        Grant.objects.filter(case=self.case,user=self.actor,action='emergency.retrospective_decide').update(active=False)
        self.assertTrue(run_publication_once())
        self.assertEqual(PublicationJob.objects.get(publication__version=version).status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication__version=version).exists())

    def test_superseded_or_revoked_policy_keeps_history_but_holds_reconciliation(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        configs=self.policies()
        with self.assertRaises(ValidationError):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        transition(self.actor,configs[0].pk,'revoked')
        with self.assertRaises(PolicyHold):preauthorization_inputs(self.case,self.profile)
        self.assertEqual(EmergencyAuthorization.objects.count(),1)

    def test_policy_validation_rejects_inferred_priority_overlap_waiver_and_wrong_deadlines(self):
        a,c=self.actor,self.case
        base={'mode':'coexist','incident_lead_role':'Engineering Lead','incident_engineering_overlap':'explicit_same_person','exception_roles':[],'priority_basis':'explicit_incident_p1_attestation'}
        for change in [{'priority_basis':'Critical_is_P1'},{'mode':'replace'},{'incident_lead_role':'PM'},
                {'incident_lead_role':'Security Lead'},{'incident_engineering_overlap':'unspecified'}]:
            config=draft_standard_policy(a,c.pk,'D01.emergency_glpi_relationship',dict(base,**change),self.e['policy_decision'].pk,timezone.now())
            with self.assertRaises(ValidationError):transition(a,config.pk,'validated')
        for days in [0,3,None]:
            with self.assertRaises(ValidationError):artifact(a,c,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'emergency':{'retrospective_working_days':days}},self.e['policy_decision'])
        with self.assertRaises(ValidationError):artifact(a,c,'D01.satisfied_gate_map','schema:psl/change-satisfied-gates/v2',{'emergency':dict(GATES,financial_controls='waived')},self.e['policy_decision'])

    def test_staff_ui_draft_investigation_stale_scope_admin_and_postgres_history(self):
        a,c=self.actor,self.case;outcome=self.outcome()
        self.client.force_login(a);url=f'/cases/{c.pk}/emergencies/'
        self.assertContains(self.client.get(url),'Emergency authorization and retrospective evidence')
        response=self.client.post(url,{'action':'policy','component':'D04.deadline_parameters','value':json.dumps({'emergency':{'retrospective_working_days':2}}),
            'evidence':self.e['policy_decision'].pk,'effective_from':timezone.now().isoformat(),'revision':rev(c)})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(url,{'action':'investigate','outcome':outcome.pk,'revision':rev(c)}).status_code,302)
        self.assertEqual(EmergencyRetrospectiveDecision.objects.count(),0)
        with self.assertRaises(ValidationError):capture_outcome(a,c.pk,self.profile.pk,None,timezone.now()+timedelta(days=1),self.implementation.pk,'Future event',rev(c))
        with self.assertRaises(ValidationError):record_review(a,c.pk,outcome.pk,self.review_evidence.pk,'Stale',rev(c)-1)
        with self.assertRaises(DatabaseError),transaction.atomic():EmergencyOutcome.objects.filter(pk=outcome.pk).update(note='Backdate')
        admin=get_user_model().objects.create_superuser('admin','admin@example.test','test-only')
        with self.assertRaises(PermissionDenied):record_review(admin,c.pk,outcome.pk,self.review_evidence.pk,'Admin flag',rev(c))
        other,foreign=setup_case(username='foreign')
        with self.assertRaises(ValidationError):capture_profile(a,c.pk,self.cv.pk,999999,True,True,self.classification.pk,'Wrong candidate',rev(c))
        self.client.force_login(other);self.assertEqual(self.client.get(url).status_code,404)

    def test_return_rejection_and_current_authority_are_not_ignored(self):
        self.policies();self.glpi();self.decisions()
        with self.assertRaises(PolicyHold):decide_emergency(self.actor,self.case.pk,self.profile.pk,'CTO','','reject',self.decision.pk,'Rejected',rev(self.case))
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'CTO','actions':['reject']}]},self.e['policy_decision'])
        decide_emergency(self.actor,self.case.pk,self.profile.pk,'CTO','','reject',self.decision.pk,'Rejected exact source',rev(self.case))
        with self.assertRaises(ValidationError):authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))

    def test_reporting_manifest_and_cited_agent_bind_actual_sources_without_effects(self):
        outcome=self.outcome();start=timezone.now()-timedelta(days=1);end=timezone.now()+timedelta(days=1)
        before=LocalPMOReportingAdapter().read(self.case,start,end,timezone.now())['manifest']
        scan_outcome(self.actor,self.case.pk,outcome.pk)
        after=LocalPMOReportingAdapter().read(self.case,start,end,timezone.now())['manifest'];self.assertNotEqual(before,after)
        run=investigate_emergency(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertFalse(run.result['approval_granted']);self.assertIn(self.incident.pk,run.result['source_evidence_ids'])
        self.assertTrue(run.result['findings']);self.assertFalse(PublicationReceipt.objects.exists())

    def test_new_review_holds_queued_source_bound_report(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        version=self.report(outcome)
        record_review(self.actor,self.case.pk,outcome.pk,self.review_evidence.pk,'New exact owner review',rev(self.case))
        self.assertTrue(run_publication_once())
        self.assertEqual(PublicationJob.objects.get(publication__version=version).status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication__version=version).exists())

    def test_expired_future_relationship_and_late_decision_classification(self):
        from apps.policy.services import save_draft
        from .helpers import envelope
        from apps.pmo.emergencies import completion_status
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        decisions=list(EmergencyRetrospectiveDecision.objects.all())
        self.assertEqual(completion_status({'log_late':False},decisions,min(d.created_at for d in decisions)-timedelta(microseconds=1)),
            'completed_with_lateness_exception')
        self.assertEqual(completion_status({'log_late':True},decisions,timezone.now()+timedelta(days=1)),
            'completed_with_lateness_exception')
        from apps.policy.services import active_component
        current=active_component('D01.emergency_glpi_relationship',self.case)
        for start,end in [(timezone.now()-timedelta(days=2),timezone.now()-timedelta(days=1)),(timezone.now()+timedelta(days=1),None)]:
            env=envelope(self.case,current.component,current.envelope['value'],self.e['policy_decision'])
            env.update(effective_from=start.isoformat(),effective_until=end.isoformat() if end else None)
            config=save_draft(self.actor,self.case.pk,env);transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')
            with self.assertRaises(PolicyHold):preauthorization_inputs(self.case,self.profile)

    def test_deadline_policy_change_requires_human_reaffirmation_and_preserves_history(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        previous=list(EmergencyRetrospectiveDecision.objects.values_list('timing',flat=True))
        self.clocks(days=2)
        with self.assertRaisesMessage(ValidationError,'Deadline policy changed'):reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        for role in ['Product','Engineering Lead']:
            decide_retrospective(self.actor,self.case.pk,outcome.pk,role,'approve',self.decision.pk,'Human reaffirmation of changed clock',rev(self.case))
        reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertEqual(list(EmergencyRetrospectiveDecision.objects.order_by('pk').values_list('timing',flat=True)[:2]),previous)
        self.assertEqual(EmergencyRetrospectiveDecision.objects.count(),4)

    def test_distinct_engineering_principal_revocation_holds_publisher_with_unchanged_access(self):
        engineer=get_user_model().objects.create_user('separate-engineer')
        for action in ['case.read','emergency.read','emergency.decide','emergency.retrospective_decide']:
            Grant.objects.create(case=self.case,user=engineer,action=action)
        refs=[]
        for role in ['PM','Head of PMO','CEO','PMO Lead','Engineering Lead','Security Lead','CTO','Product']:
            user=engineer if role=='Engineering Lead' else self.actor
            r=register_reference(self.actor,self.case.pk,'separate:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':user.pk},self.e['policy_decision'].pk);refs.append(r.ref)
        activate(self.actor,self.case,'D05.role_principal_assignments',refs,self.e['policy_decision'])
        self.policies(incident_role='Security Lead',overlap='distinct_people');self.glpi()
        for role in ['Incident Lead','Engineering Lead','CTO']:
            actor=engineer if role=='Engineering Lead' else self.actor
            decide_emergency(actor,self.case.pk,self.profile.pk,role,'Security Lead','approve',self.decision.pk,'Separate actual human principal',rev(self.case))
        auth=authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case));outcome=self.outcome(auth)
        self.clocks();record_review(self.actor,self.case.pk,outcome.pk,self.review_evidence.pk,'Owner review',rev(self.case))
        for role in ['Product','Engineering Lead']:
            actor=engineer if role=='Engineering Lead' else self.actor
            decide_retrospective(actor,self.case.pk,outcome.pk,role,'approve',self.decision.pk,'Separate review owner',rev(self.case))
        version=self.report(outcome)
        Grant.objects.filter(case=self.case,user=engineer,action='emergency.decide').update(active=False)
        self.assertTrue(run_publication_once())
        self.assertEqual(PublicationJob.objects.get(publication__version=version).status,'held')
        self.assertTrue(Grant.objects.get(case=self.case,user=self.actor,action='document.publish').active)


class EmergencyProcessTests(EmergencyFixture,TransactionTestCase):
    def test_actual_repeated_process_resumes_cursor_without_duplicate_signal(self):
        outcome=self.outcome()
        for _ in range(2):
            result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_emergency_obligations','--limit','1'],
                cwd=settings.BASE_DIR,capture_output=True,text=True,env=self.worker_env(),timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(EmergencyDeadlineSignal.objects.filter(outcome=outcome).count(),1)
        self.assertEqual(EmergencyScanCursor.objects.get().last_outcome_id,outcome.pk)
    def worker_env(self):
        import os
        return dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])

    def test_two_real_connections_signal_once(self):
        outcome=self.outcome();actor_id=self.actor.pk;case_id=self.case.pk
        def work():
            close_old_connections()
            try:return len(scan_outcome(get_user_model().objects.get(pk=actor_id),case_id,outcome.pk))
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(lambda _:work(),range(2)))
        self.assertEqual(sum(result),1);self.assertEqual(EmergencyDeadlineSignal.objects.count(),1)
