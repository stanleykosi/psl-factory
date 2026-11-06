import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection,close_old_connections
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.services import transition,PolicyHold,register_reference
from apps.policy.change_drafts import draft_standard_policy
from apps.pmo.recoveries import request_recovery,decide_recovery,finalize_recovery,active_recovery
from apps.pmo.emergencies import reconcile_retrospective,retrospective_inputs,capture_profile
from apps.pmo.emergency_followups import create_followup,complete_followup
from apps.pmo.models import AuthorityRecoveryRequest,AuthorityRecoveryDecision,AuthorityRecoveryRecord,EmergencyFollowup,ChangeAuthorization,ChangeExecutionEvent,EmergencyRetrospectiveRecord
from apps.agents.authority_recovery import investigate_recovery
from apps.documents.models import PublicationReceipt,PublicationJob
from apps.documents.delivery import run_publication_once
from adapters.emergencies import LocalEmergencyEvidenceAdapter
from . import test_emergencies as emergency
from . import test_commercial_changes as commercial
from .helpers import rev,activate,setup_case
from .document_helpers import artifact

RULE={'roles':['PMO Lead'],'scope':'authority_only','original_times':'preserve','financial_release_controls':'independent'}


class RecoveryFixture(emergency.EmergencyFixture):
    def recovery_policy(self,roles=None):
        rule=dict(RULE,roles=roles or ['PMO Lead'])
        return artifact(self.actor,self.case,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v2',
            {'unchanged_subject_reuse_roles':[],'changed_cost_requires_full_chain':True,
             'historical_authority':{'emergency_outcome':rule,'signed_adoption':rule}},self.e['policy_decision'])

    def request(self,outcome):
        return request_recovery(self.actor,self.case.pk,'emergency_outcome',outcome.pk,self.decision.pk,'Current human responsibility, original times retained',rev(self.case))

    def approve(self,r,roles=None):
        for role in roles or ['PMO Lead']:
            decide_recovery(self.actor,self.case.pk,r.pk,role,'approve',self.decision.pk,'Reaffirm unchanged historical evidence',rev(self.case))
        return finalize_recovery(self.actor,self.case.pk,r.pk,rev(self.case))

    def followup(self,outcome,reference='FOLLOW-001',category='Normal'):
        source=self.evidence('change_request','Further ordinary scope work with fresh cost investigation')
        return create_followup(self.actor,self.case.pk,outcome.pk,reference,category,'API','Further scope and cost work','Investigate financial and scope consequences',source.pk,rev(self.case))


class AuthorityRecoveryTests(RecoveryFixture,TestCase):
    def test_revoked_historical_grant_recovers_only_current_reconciliation_and_preserves_times(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome);self.recovery_policy()
        original=(outcome.authorization.created_at,outcome.implemented_at,outcome.created_at,outcome.authorization.snapshot)
        Grant.objects.filter(case=self.case,user=self.actor,action='emergency.decide').update(active=False)
        with self.assertRaises(PermissionDenied):retrospective_inputs(self.case,outcome)
        r=self.request(outcome)
        with self.assertRaisesMessage(ValidationError,'approval required'):finalize_recovery(self.actor,self.case.pk,r.pk,rev(self.case))
        recovered=self.approve(r)
        result=reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        self.assertEqual(result.snapshot['authority_recovery_id'],recovered.pk)
        outcome.refresh_from_db();self.assertEqual(original,(outcome.authorization.created_at,outcome.implemented_at,outcome.created_at,outcome.authorization.snapshot))
        self.assertGreater(recovered.created_at,outcome.implemented_at)
        with self.assertRaises(DatabaseError),transaction.atomic():AuthorityRecoveryRequest.objects.filter(pk=r.pk).update(note='Rewrite')
        with self.assertRaises(DatabaseError),transaction.atomic():AuthorityRecoveryRecord.objects.filter(pk=recovered.pk).delete()
        self.assertEqual(connection.vendor,'postgresql')

    def test_missing_policy_holds_recovery_only_and_original_missing_authority_is_not_recovered(self):
        outcome=self.outcome(self.authorized())
        with self.assertRaises(PolicyHold):self.request(outcome)
        followup=self.followup(outcome);self.assertEqual(followup.outcome_id,outcome.pk)
        self.assertFalse(ChangeExecutionEvent.objects.exists())

    def test_absent_or_late_preauthorization_is_never_recoverable(self):
        self.recovery_policy();outcome=self.outcome()
        with self.assertRaisesMessage(ValidationError,'missing preauthorization'):self.request(outcome)
        self.assertEqual(AuthorityRecoveryRequest.objects.count(),0)

    def test_authorization_recorded_after_claimed_actual_instant_cannot_be_recovered(self):
        auth=self.authorized();outcome=self.outcome(auth,timezone.now()-timedelta(days=3));self.recovery_policy()
        with self.assertRaisesMessage(ValidationError,'missing preauthorization'):self.request(outcome)

    def test_policy_source_and_grant_drift_invalidate_current_recovery(self):
        outcome=self.outcome(self.authorized());self.recovery_policy();r=self.request(outcome);record=self.approve(r)
        self.assertEqual(active_recovery(self.case,'emergency_outcome',outcome.pk).pk,record.pk)
        Grant.objects.filter(case=self.case,user=self.actor,action='authority.decide').update(active=False)
        self.assertIsNone(active_recovery(self.case,'emergency_outcome',outcome.pk))
        Grant.objects.filter(case=self.case,user=self.actor,action='authority.decide').update(active=True)
        self.recovery_policy()
        self.assertIsNone(active_recovery(self.case,'emergency_outcome',outcome.pk))
        with self.assertRaisesMessage(ValidationError,'changed'):self.approve(r)
        self.policies()
        with self.assertRaisesMessage(ValidationError,'source or D01'):self.request(outcome)

    def test_new_profile_cannot_be_reaffirmed_as_original(self):
        outcome=self.outcome(self.authorized());self.recovery_policy()
        capture_profile(self.actor,self.case.pk,self.cv.pk,self.candidate.pk,True,False,self.classification.pk,'New incident facts',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'source revision/profile changed'):self.request(outcome)

    def test_current_replacement_human_must_hold_configured_role_and_grants(self):
        outcome=self.outcome(self.authorized());self.recovery_policy()
        replacement=get_user_model().objects.create_user('current-owner')
        for action in ['case.read','authority.read','authority.decide']:Grant.objects.create(case=self.case,user=replacement,action=action)
        refs=[]
        for role in ['PM','Head of PMO','CEO','PMO Lead','Engineering Lead','Security Lead','CTO','Product']:
            user=replacement if role=='PMO Lead' else self.actor
            ref=register_reference(self.actor,self.case.pk,'recovery-replacement:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':user.pk},self.e['policy_decision'].pk);refs.append(ref.ref)
        activate(self.actor,self.case,'D05.role_principal_assignments',refs,self.e['policy_decision'])
        r=self.request(outcome)
        with self.assertRaises(PermissionDenied):decide_recovery(self.actor,self.case.pk,r.pk,'PMO Lead','approve',self.decision.pk,'Former owner',rev(self.case))
        decide_recovery(replacement,self.case.pk,r.pk,'PMO Lead','approve',self.decision.pk,'Current owner reaffirmation',rev(self.case))
        record=finalize_recovery(self.actor,self.case.pk,r.pk,rev(self.case));self.assertEqual(record.decision_ids,list(r.decisions.values_list('pk',flat=True)))
        Grant.objects.filter(case=self.case,user=replacement,action='authority.decide').update(active=False)
        self.assertIsNone(active_recovery(self.case,'emergency_outcome',outcome.pk))

    def test_each_configured_role_required_and_later_request_suspends_old_recovery(self):
        outcome=self.outcome(self.authorized());self.recovery_policy(['PMO Lead','CEO']);r=self.request(outcome)
        decide_recovery(self.actor,self.case.pk,r.pk,'PMO Lead','approve',self.decision.pk,'Current decision',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'CEO'):finalize_recovery(self.actor,self.case.pk,r.pk,rev(self.case))
        self.approve(r,['CEO']);self.assertIsNotNone(active_recovery(self.case,'emergency_outcome',outcome.pk))
        self.request(outcome);self.assertIsNone(active_recovery(self.case,'emergency_outcome',outcome.pk))

    def test_rejection_configured_actions_and_missing_role_do_not_approve(self):
        outcome=self.outcome(self.authorized());self.recovery_policy();r=self.request(outcome)
        with self.assertRaises(ValidationError):decide_recovery(self.actor,self.case.pk,r.pk,'Client','approve',self.decision.pk,'Not configured',rev(self.case))
        with self.assertRaises(PolicyHold):decide_recovery(self.actor,self.case.pk,r.pk,'PMO Lead','reject',self.decision.pk,'Reject',rev(self.case))
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['reject']}]},self.e['policy_decision'])
        r=self.request(outcome)
        decide_recovery(self.actor,self.case.pk,r.pk,'PMO Lead','reject',self.decision.pk,'Human rejection',rev(self.case))
        with self.assertRaises(ValidationError):finalize_recovery(self.actor,self.case.pk,r.pk,rev(self.case))

    def test_v1_compatible_and_v2_rejects_waiver_empty_roles_unknown_targets(self):
        for rule in [dict(RULE,roles=[]),dict(RULE,roles=['Administrator']),dict(RULE,original_times='backdate'),dict(RULE,financial_release_controls='waived')]:
            with self.assertRaises(ValidationError):artifact(self.actor,self.case,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v2',
                {'unchanged_subject_reuse_roles':[],'changed_cost_requires_full_chain':True,'historical_authority':{'emergency_outcome':rule}},self.e['policy_decision'])
        artifact(self.actor,self.case,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v1',
            {'unchanged_subject_reuse_roles':[],'changed_cost_requires_full_chain':True},self.e['policy_decision'])
        outcome=self.outcome(self.authorized())
        with self.assertRaisesMessage(ValidationError,'unconfigured'):self.request(outcome)

    def test_ui_agent_scope_stale_and_admin_cannot_grant_authority(self):
        outcome=self.outcome(self.authorized());self.recovery_policy();self.client.force_login(self.actor)
        url=f'/cases/{self.case.pk}/authority/'
        self.assertContains(self.client.get(url),'Historical authority and Emergency follow-up')
        self.assertEqual(self.client.post(url,{'action':'request','kind':'emergency_outcome','target':outcome.pk,'evidence':self.decision.pk,'note':'UI request','revision':rev(self.case)}).status_code,302)
        r=AuthorityRecoveryRequest.objects.get();run=investigate_recovery(self.actor,self.case.pk,r.pk,rev(self.case))
        self.assertFalse(run.result['approval_granted']);self.assertIn(outcome.evidence_id,run.result['source_evidence_ids'])
        with self.assertRaises(ValidationError):decide_recovery(self.actor,self.case.pk,r.pk,'PMO Lead','approve',self.decision.pk,'Stale',rev(self.case)-1)
        admin=get_user_model().objects.create_superuser('recovery-admin','admin@example.test','test-only')
        with self.assertRaises(PermissionDenied):decide_recovery(admin,self.case.pk,r.pk,'PMO Lead','approve',self.decision.pk,'Admin flag',rev(self.case))
        other,_=setup_case(username='foreign-recovery');self.client.force_login(other);self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(AuthorityRecoveryDecision.objects.count(),0)

    def test_fresh_recovery_and_followup_invalidate_queued_report(self):
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome);self.recovery_policy()
        version=self.report(outcome);self.request(outcome)
        self.assertTrue(run_publication_once());self.assertEqual(PublicationJob.objects.get(publication__version=version).status,'held')
        before=LocalEmergencyEvidenceAdapter().read(self.case,outcome)['manifest'];self.followup(outcome)
        after=LocalEmergencyEvidenceAdapter().read(self.case,outcome)['manifest'];self.assertNotEqual(before,after)
        self.assertIsNone(after['followups'][0]['impact']['cost_impact'])
        self.assertFalse(PublicationReceipt.objects.exists())


class EmergencyFollowupTests(RecoveryFixture,TestCase):
    ready=commercial.ChangeExecutionTests.ready
    change_template=commercial.ChangeExecutionTests.change_template
    publish_change=commercial.ChangeExecutionTests.publish_change

    def test_cost_followup_runs_ordinary_approval_signed_adoption_execution_publication_closure(self):
        from apps.pmo.changes import assess_change,decide_change,authorize_change,CONTRIBUTORS
        from apps.pmo.commercial import propose,adopt_signed,capture_response
        from apps.pmo.change_execution import record_execution,close_change,validate_authorization
        from apps.finance.models import SignedBaselineIntake
        outcome=self.outcome(self.authorized());self.clocks();self.reviewed(outcome)
        original=reconcile_retrospective(self.actor,self.case.pk,outcome.pk,rev(self.case))
        f=self.followup(outcome);self.t=self.old_template
        commercial.change_roles(self.actor,self.case,self.e['policy_decision'])
        for team in CONTRIBUTORS:assess_change(self.actor,self.case.pk,f.version_id,team,True,False,False,f.version.evidence_id,'Further work impact',rev(self.case),**commercial.impact_fixture(team))
        for role in ['Product','Engineering']:decide_change(self.actor,self.case.pk,f.version_id,role,'approve',f.version.evidence_id,'Ordinary source-bound decision',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'Cost impact'):authorize_change(self.actor,self.case.pk,f.version_id,None,rev(self.case))
        sources={k:self.e[k].pk for k in commercial.SOURCE_KINDS}
        for k in ['plan','costing','sow']:sources[k]=self.evidence(k,'Further scope commercial '+k).pk
        v=propose(self.actor,self.case.pk,sources,f.version.evidence_id,'Separate forward scope/cost proposal',rev(self.case));commercial.approvals(self.actor,self.case,v)
        auth=authorize_change(self.actor,self.case.pk,f.version_id,v.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'Adopt the signed'):record_execution(self.actor,self.case.pk,auth.pk,'plan_updated',sources['plan'],'Before signature',rev(self.case))
        receipt=commercial.delivered(self.actor,self.case,v,self.t)
        signature=self.evidence('signature','New signed ordinary SOW')
        response=capture_response(self.actor,self.case.pk,v.pk,receipt.pk,'signed',signature.pk,'Matched signed outward receipt',rev(self.case))
        adoption=adopt_signed(self.actor,self.case.pk,v.pk,response.pk,rev(self.case))
        self.assertEqual(SignedBaselineIntake.objects.count(),1)
        self.assertFalse(ChangeExecutionEvent.objects.exists())
        # Re-roster after signed adoption. Current recovery restores evidence tracking, never signature/adoption.
        self.recovery_policy();Grant.objects.filter(case=self.case,user=self.actor,action='commercial.decide').update(active=False)
        with self.assertRaises(PermissionDenied):validate_authorization(self.case,auth)
        r=request_recovery(self.actor,self.case.pk,'signed_adoption',adoption.pk,signature.pk,'Current responsibility for signed history',rev(self.case));recovered=self.approve(r)
        self.assertIsNotNone(recovered);validate_authorization(self.case,auth)
        t=self.change_template();notice=self.publish_change(auth,t,'notice')
        # A new recovery requires a fresh reviewed document even for unchanged execution/source text.
        r2=request_recovery(self.actor,self.case.pk,'signed_adoption',adoption.pk,signature.pk,'New responsibility review',rev(self.case));self.approve(r2)
        from apps.documents.controlled import preflight
        self.assertTrue(preflight(notice.publication.version))
        self.publish_change(auth,t,'notice');self.ready(auth);go_live=self.publish_change(auth,t,'go_live')
        pm=self.evidence('signature','PM exact go-live');client=self.evidence('signature','Client exact go-live')
        closure=close_change(self.actor,self.case.pk,auth.pk,go_live.pk,pm.pk,client.pk,'Both exact acceptance signatures verified',rev(self.case))
        completion=complete_followup(self.actor,self.case.pk,f.pk,closure.pk,'Ordinary signed controls complete',rev(self.case))
        self.assertEqual(completion.closure_id,closure.pk)
        self.assertEqual(EmergencyRetrospectiveRecord.objects.get().pk,original.pk)
        self.assertEqual(len(auth.execution.all()),4)
        with self.assertRaises(ValidationError):complete_followup(self.actor,self.case.pk,f.pk,closure.pk,'Duplicate',rev(self.case))
        # A later independent baseline does not erase the Emergency's original source/time history.
        historical=self.request(outcome);self.assertEqual(historical.snapshot['source']['authorization_id'],outcome.authorization_id)

    def test_followup_fresh_unique_ordinary_source_and_no_automatic_execution(self):
        outcome=self.outcome();f=self.followup(outcome)
        self.assertEqual(f.version.category,'Normal');self.assertEqual(ChangeAuthorization.objects.count(),0)
        with self.assertRaisesMessage(ValidationError,'unique'):self.followup(outcome)
        with self.assertRaisesMessage(ValidationError,'ordinary'):self.followup(outcome,'EM-INVALID','Emergency')
        with self.assertRaises(ValidationError):complete_followup(self.actor,self.case.pk,f.pk,999,'No closure',rev(self.case))
        self.assertFalse(ChangeExecutionEvent.objects.exists())
        with self.assertRaises(DatabaseError),transaction.atomic():EmergencyFollowup.objects.filter(pk=f.pk).update(note='Rewrite')

    def test_followup_revision_preserves_ancestor_and_needs_new_ordinary_controls(self):
        from apps.pmo.changes import log_change
        from apps.pmo.emergency_followups import link_followup_revision
        outcome=self.outcome();f=self.followup(outcome)
        version=log_change(self.actor,self.case.pk,f.version.change.reference,'Normal','API','Revised further work','Owner correction',f.version.evidence_id,rev(self.case))
        linked=link_followup_revision(self.actor,self.case.pk,f.pk,version.pk,'Current revised follow-up',rev(self.case))
        self.assertEqual(linked.supersedes_id,f.pk);self.assertEqual(linked.outcome_id,outcome.pk)
        self.assertEqual(linked.version.assessments.count(),0);self.assertEqual(linked.version.decisions.count(),0)
        with self.assertRaises(ValidationError):link_followup_revision(self.actor,self.case.pk,f.pk,version.pk,'Duplicate',rev(self.case))
        self.assertEqual(EmergencyFollowup.objects.count(),2)


class RecoveryConcurrencyTests(RecoveryFixture,TransactionTestCase):
    def test_two_actual_postgres_connections_finalize_once(self):
        outcome=self.outcome(self.authorized());self.recovery_policy();r=self.request(outcome)
        decide_recovery(self.actor,self.case.pk,r.pk,'PMO Lead','approve',self.decision.pk,'Current decision',rev(self.case));expected=rev(self.case)
        def finalize():
            close_old_connections()
            try:finalize_recovery(get_user_model().objects.get(pk=self.actor.pk),self.case.pk,r.pk,expected);return 'recorded'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:finalize(),range(2)))
        self.assertCountEqual(results,['recorded','stale']);self.assertEqual(AuthorityRecoveryRecord.objects.count(),1)
