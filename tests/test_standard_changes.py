import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition, register_reference, PolicyHold
from apps.policy.change_drafts import draft_standard_policy
from apps.pmo.models import StandardPreapproval, StandardBinding, ChangeAuthorization
from apps.pmo.changes import log_change, assess_change, decide_change, authorize_change, CONTRIBUTORS
from apps.pmo.standard_changes import preapprove, bind_standard, catalogue
from apps.pmo.change_execution import validate_authorization, record_execution, draft_change_document, close_change
from apps.agents.standard_changes import investigate_standard
from apps.documents.controlled import request_review, review_version, reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt, PublicationJob
from adapters.pmo_reporting import LocalPMOReportingAdapter
from .helpers import rev, activate, setup_case
from .document_helpers import artifact
from .test_commercial_changes import fixture, change_roles
from . import test_commercial_changes as commercial_tests


class StandardChangeTests(TestCase):
    ready = commercial_tests.ChangeExecutionTests.ready
    change_template = commercial_tests.ChangeExecutionTests.change_template
    publish_change = commercial_tests.ChangeExecutionTests.publish_change

    def setUp(self):
        self.actor,self.case,self.e,self.t=fixture(existing=True)
        change_roles(self.actor,self.case,self.e['policy_decision'])
        a,c=self.actor,self.case
        self.procedure=add_evidence(a,c.pk,'change_procedure','Synthetic exact low risk procedure; owner verification required','synthetic:procedure')
        self.match=add_evidence(a,c.pk,'change_procedure_match','PM inspected applicability of exact procedure','synthetic:PM')
        self.approval=add_evidence(a,c.pk,'change_preapproval','Human owner decision on exact procedure and conditions','synthetic:owner')
        self.source=add_evidence(a,c.pk,'change_request','Apply the recorded procedure','synthetic:request')
        self.cv=log_change(a,c.pk,'STD-01','Standard','API','Apply procedure','Owner request',self.source.pk,rev(c))
        self.entry={'key':'api-maintenance','module':'API','procedure_evidence_id':self.procedure.pk,
            'procedure_sha256':self.procedure.sha256,'expected_impact':{'cost_impact':False,'timeline_impact':False,'client_facing':False},
            'production_gate':'independent_release_controls'}

    def policies(self,roles=None,entry=None):
        a,c=self.actor,self.case
        config=draft_standard_policy(a,c.pk,'D01.change_type_catalogue',[entry or self.entry],self.e['policy_decision'].pk,timezone.now()-timedelta(hours=1))
        transition(a,config.pk,'validated');transition(a,config.pk,'active')
        gates=artifact(a,c,'D01.satisfied_gate_map','schema:psl/standard-satisfied-gates/v1',
            {'standard':[{'catalogue_key':'api-maintenance','roles':roles or ['Product','Engineering']}]},self.e['policy_decision'])
        return config,gates

    def assessments(self,cost=False,timeline=False,client=False):
        for team in CONTRIBUTORS:
            assess_change(self.actor,self.case.pk,self.cv.pk,team,cost,timeline,client,self.source.pk,'Owner reviewed impact',rev(self.case))

    def bound(self,roles=None):
        self.policies(roles)
        for role in roles or ['Product','Engineering']:
            preapprove(self.actor,self.case.pk,'api-maintenance',role,'approve',self.approval.pk,'Owner reviewed exact procedure',rev(self.case))
        return bind_standard(self.actor,self.case.pk,self.cv.pk,'api-maintenance',self.match.pk,'PM verified exact procedure',rev(self.case))

    def authorized(self):
        self.assessments();self.bound()
        return authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))

    def test_connected_preapproval_execution_review_publication_and_signed_closure(self):
        from apps.pmo.signatures import assert_current_signed_baseline
        from .signature_helpers import reaffirm_for
        with self.assertRaises(ValidationError):assert_current_signed_baseline(self.case)
        reaffirm_for(self.actor,self.case)
        auth=self.authorized();a,c=self.actor,self.case
        self.assertEqual(connection.vendor,'postgresql')
        self.assertEqual(auth.decision_ids,[])
        self.assertEqual(len(auth.preapproval_snapshot['preapproval_ids']),2)
        t=self.change_template();self.publish_change(auth,t,'notice');self.ready(auth)
        receipt=self.publish_change(auth,t,'go_live')
        pm=add_evidence(a,c.pk,'signature','PM exact change acceptance','synthetic:PM')
        client=add_evidence(a,c.pk,'signature','Client exact change acceptance','synthetic:Client')
        from .change_signature_helpers import declaration_for
        close_change(a,c.pk,auth.pk,receipt.pk,pm.pk,client.pk,'PM checked both exact-version signatures',rev(c),attestation=declaration_for(a,auth,receipt,pm,client))
        with self.assertRaises(ValidationError):bind_standard(a,c.pk,self.cv.pk,'api-maintenance',self.match.pk,'Closed history',rev(c))

    def test_no_catalogue_does_not_prevent_intake_assessment_or_investigation(self):
        self.assessments()
        with self.assertRaises(PolicyHold):catalogue(self.case)
        with self.assertRaises(ValidationError):authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        run=investigate_standard(self.actor,self.case.pk,self.cv.pk,rev(self.case))
        self.assertFalse(run.result['approval_granted']);self.assertTrue(run.result['findings'])
        self.assertEqual(self.cv.assessments.count(),4)

    def test_label_configuration_and_source_text_never_supply_human_preapproval(self):
        self.policies();self.assessments();a,c=self.actor,self.case
        bind_standard(a,c.pk,self.cv.pk,'api-maintenance',self.match.pk,'PM matched',rev(c))
        with self.assertRaisesMessage(ValidationError,'human catalogue preapproval'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        with self.assertRaises(ValidationError):preapprove(a,c.pk,'api-maintenance','Product','approve',self.source.pk,'Wrong evidence kind',rev(c))

    def test_only_mapped_gates_are_reused_and_no_cost_or_client_waiver(self):
        self.assessments();self.bound(['Engineering']);a,c=self.actor,self.case
        with self.assertRaisesMessage(ValidationError,'Product'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        decide_change(a,c.pk,self.cv.pk,'Product','approve',self.source.pk,'Specific scope decision',rev(c))
        self.assertEqual(len(authorize_change(a,c.pk,self.cv.pk,None,rev(c)).decision_ids),1)

    def test_positive_impact_conditions_keep_conditional_and_costing_controls(self):
        self.entry['expected_impact']={k:True for k in self.entry['expected_impact']}
        self.assessments(True,True,True);self.bound();a,c=self.actor,self.case
        with self.assertRaisesMessage(ValidationError,'Client'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        for role in ['Client','Engineering Lead','Security Manager']:
            decide_change(a,c.pk,self.cv.pk,role,'approve',self.source.pk,'Conditional decision',rev(c))
        with self.assertRaisesMessage(ValidationError,'approved commercial'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))

    def test_unknown_or_mismatched_impact_cannot_match_conditions(self):
        self.bound();a,c=self.actor,self.case
        self.assessments(cost=None)
        with self.assertRaisesMessage(ValidationError,'unknown'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        self.assessments(cost=True)
        with self.assertRaisesMessage(ValidationError,'conditions'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))

    def test_revoked_and_superseded_policy_invalidates_execution_without_rewriting_history(self):
        auth=self.authorized();a,c=self.actor,self.case
        configs=self.policies()
        with self.assertRaises(ValidationError):validate_authorization(c,auth)
        self.assertEqual(StandardPreapproval.objects.count(),2)
        transition(a,configs[0].pk,'revoked')
        with self.assertRaises(PolicyHold):catalogue(c)
        self.assertEqual(ChangeAuthorization.objects.count(),1)

    def test_new_preapproval_or_pm_match_invalidates_authorization_snapshot(self):
        auth=self.authorized();a,c=self.actor,self.case
        preapprove(a,c.pk,'api-maintenance','Product','approve',self.approval.pk,'Renewed explicit decision',rev(c))
        with self.assertRaisesMessage(ValidationError,'snapshot changed'):validate_authorization(c,auth)

    def test_revoked_preapprover_grant_holds_queued_publication(self):
        auth=self.authorized();a,c=self.actor,self.case;t=self.change_template()
        v=draft_change_document(a,c.pk,auth.pk,t.pk,'notice',rev(c))
        request_review(a,c.pk,v.pk,rev(c));review_version(a,c.pk,v.pk,'approve','Exact review',rev(c))
        reserve_publication(a,c.pk,v.pk,rev(c))
        Grant.objects.filter(case=c,user=a,action='change.preapprove').update(active=False)
        self.assertTrue(run_publication_once())
        self.assertEqual(PublicationJob.objects.get(publication__version=v).status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication__version=v).exists())

    def test_schema_rejects_unknowns_hashes_duplicates_waivers_and_unimplemented_gates(self):
        a,c=self.actor,self.case
        bads=[dict(self.entry,procedure_sha256='0'*64),dict(self.entry,expected_impact={'cost_impact':None}),
            dict(self.entry,production_gate='waived'),dict(self.entry,module=' ')]
        for entry in bads:
            with self.subTest(entry=entry):
                draft=draft_standard_policy(a,c.pk,'D01.change_type_catalogue',[entry],self.e['policy_decision'].pk,timezone.now())
                with self.assertRaises(ValidationError):transition(a,draft.pk,'validated')
        draft=draft_standard_policy(a,c.pk,'D01.change_type_catalogue',[self.entry,self.entry],self.e['policy_decision'].pk,timezone.now())
        with self.assertRaisesMessage(ValidationError,'unique'):transition(a,draft.pk,'validated')
        with self.assertRaises(ValidationError):self.policies(['CEO'])
        with self.assertRaises(ValidationError):self.policies(['Client'])

    def test_typed_ui_draft_match_investigation_and_case_scope(self):
        self.assessments();self.bound();a,c=self.actor,self.case
        self.client.force_login(a);url=f'/cases/{c.pk}/changes/'
        self.assertContains(self.client.get(url),'Standard catalogue and human preapproval')
        response=self.client.post(url,{'action':'standard_investigate','revision':rev(c),'version':self.cv.pk})
        self.assertEqual(response.status_code,302)
        response=self.client.post(url,{'action':'standard_policy','revision':rev(c),'component':'D01.satisfied_gate_map',
            'value':json.dumps({'standard':[{'catalogue_key':'api-maintenance','roles':['Engineering']}]}),
            'evidence':self.e['policy_decision'].pk,'effective_from':timezone.now().isoformat()})
        self.assertEqual(response.status_code,302)
        self.assertEqual(catalogue(c)[1][0]['roles'],['Product','Engineering'])  # Saving never activates.
        other,foreign=setup_case(username='foreign')
        with self.assertRaises(PermissionDenied):bind_standard(other,c.pk,self.cv.pk,'api-maintenance',self.match.pk,'Foreign actor',rev(c))
        with self.assertRaises(ValidationError):bind_standard(a,c.pk,self.cv.pk,'api-maintenance',self.match.pk,'Stale UI',rev(c)-1)

    def test_postgres_history_guards_and_reporting_freshness_and_agent_citations(self):
        self.assessments();before=LocalPMOReportingAdapter().read(self.case,timezone.now()-timedelta(days=1),timezone.now()+timedelta(days=1),timezone.now())['manifest']
        binding=self.bound()
        after=LocalPMOReportingAdapter().read(self.case,timezone.now()-timedelta(days=1),timezone.now()+timedelta(days=1),timezone.now())['manifest']
        self.assertNotEqual(before,after)
        with self.assertRaises(DatabaseError),transaction.atomic():StandardBinding.objects.filter(pk=binding.pk).update(note='Rewrite')
        with self.assertRaises(DatabaseError),transaction.atomic():StandardPreapproval.objects.all().delete()
        run=investigate_standard(self.actor,self.case.pk,self.cv.pk,rev(self.case))
        self.assertEqual(run.result['remaining_roles'],[])
        self.assertFalse(run.result['deployment_authorized'])
        self.assertIn(self.procedure.pk,run.result['source_evidence_ids'])
        self.assertIn(self.approval.pk,run.result['source_evidence_ids'])
        self.assertEqual(ChangeAuthorization.objects.count(),0)

    def test_configured_return_blocks_reuse_and_admin_has_no_authority(self):
        auth=self.authorized();a,c=self.actor,self.case
        with self.assertRaises(PolicyHold):preapprove(a,c.pk,'api-maintenance','Product','return',self.approval.pk,'Needs revision',rev(c))
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
            {'rules':[{'role':'Product','actions':['return']}]},self.e['policy_decision'])
        preapprove(a,c.pk,'api-maintenance','Product','return',self.approval.pk,'Owner returned',rev(c))
        with self.assertRaises(ValidationError):validate_authorization(c,auth)
        admin=get_user_model().objects.create_superuser('admin','admin@example.test','test-only')
        with self.assertRaises(PermissionDenied):preapprove(admin,c.pk,'api-maintenance','Product','approve',self.approval.pk,'Admin flag',rev(c))

    def test_request_specific_return_overrides_catalogue_preapproval(self):
        self.assessments();self.bound();a,c=self.actor,self.case
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
            {'rules':[{'role':'Product','actions':['return']}]},self.e['policy_decision'])
        decide_change(a,c.pk,self.cv.pk,'Product','return',self.source.pk,'Procedure unsuitable for this request',rev(c))
        with self.assertRaisesMessage(ValidationError,'Product'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))

    def test_expired_future_and_foreign_procedure_configuration_stays_unusable(self):
        from apps.policy.services import save_draft
        from .helpers import envelope
        a,c=self.actor,self.case
        configs=self.policies()
        for start,end in [(timezone.now()-timedelta(days=2),timezone.now()-timedelta(days=1)),
                (timezone.now()+timedelta(days=1),None)]:
            value=configs[0].envelope['value']
            env=envelope(c,'D01.change_type_catalogue',value,self.e['policy_decision'])
            env.update(effective_from=start.isoformat(),effective_until=end.isoformat() if end else None)
            config=save_draft(a,c.pk,env);transition(a,config.pk,'validated');transition(a,config.pk,'active')
            with self.assertRaises(PolicyHold):catalogue(c)
        foreign_actor,foreign=setup_case(username='foreign-procedure')
        procedure=add_evidence(foreign_actor,foreign.pk,'change_procedure','Foreign procedure','synthetic:foreign')
        entry=dict(self.entry,procedure_evidence_id=procedure.pk,procedure_sha256=procedure.sha256)
        config=draft_standard_policy(a,c.pk,'D01.change_type_catalogue',[entry],self.e['policy_decision'].pk,timezone.now())
        with self.assertRaises(ValidationError):transition(a,config.pk,'validated')
