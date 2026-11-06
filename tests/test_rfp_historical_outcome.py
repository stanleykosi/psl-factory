"""P49 consumes verified historical submissions, not today's unsent draft permissions."""
from copy import copy,deepcopy
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.documents.models import PublicationReceipt
from apps.documents.controlled import create_version
from apps.documents.controlled import request_review,review_version,reserve_publication
from apps.documents.delivery import run_publication_once
from apps.identity.models import Grant
from apps.pmo import rfp,rfp_documents
from apps.pmo.models import RFPCase,RFPSubmission,RFPDisposition,Baseline
from apps.pmo.rfp_outcomes import historical_submission,outcome_selection_state
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.rfp_outcome_validators import COMPONENT,METHOD
from apps.policy.services import active_component,reference_values,register_reference,transition
from tests import test_rfp as native
from tests.helpers import rev,activate,setup_case


class HistoricalRFPOutcomeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case,cls.evidence,cls.template,_=native.fixture()
        cls.response=native.response(cls.actor,cls.case,cls.evidence)
        native.approve(cls.actor,cls.case,cls.evidence,cls.response)
        cls.submission=native.submit(cls.actor,cls.case,cls.evidence,cls.template,cls.response)

    def actual(self,result='won',submission=None,selection_context=None):
        return rfp.outcome(self.actor,self.case.pk,(submission or self.submission).pk,result,timezone.now(),'Client',
            self.evidence['rfp_outcome'].pk,'Actual synthetic customer outcome for this submitted version',rev(self.case),
            selection_context=selection_context)

    def another_submission(self):
        response=native.response(self.actor,self.case,self.evidence)
        native.approve(self.actor,self.case,self.evidence,response)
        return native.submit(self.actor,self.case,self.evidence,self.template,response)

    def selection_method(self,method=METHOD):
        policy=draft_operator_policy(self.actor,self.case.pk,COMPONENT,{'method':method},
            self.evidence['policy_decision'].pk,timezone.now())
        transition(self.actor,policy.pk,'validated');transition(self.actor,policy.pk,'active')
        return policy

    def test_current_owner_can_convert_exact_submission_after_historical_staff_turnover(self):
        owner=get_user_model().objects.create_user(username='current-outcome-owner')
        Grant.objects.bulk_create([Grant(case=self.case,user=owner,action=action) for action in ['case.read','rfp.read','rfp.outcome','rfp.dispose']])
        old=active_component('D05.role_principal_assignments',self.case);refs=[]
        for index,assignment in enumerate(reference_values(old)):
            value=dict(assignment)
            if value['role']=='Client':value['user_id']=owner.pk
            reference=register_reference(self.actor,self.case.pk,'historical-owner-role:'+str(index),
                'schema:psl/role-assignment/v1',value,self.evidence['policy_decision'].pk)
            refs.append(reference.ref)
        activate(self.actor,self.case,'D05.role_principal_assignments',refs,self.evidence['policy_decision'])
        withdrawn=['rfp.assign','rfp.prepare','rfp.review','commercial.decide','document.review_controlled','rfp.submit',
            *['rfp.contribute:'+team for team in rfp.TEAMS]]
        Grant.objects.filter(case=self.case,user=self.actor,action__in=withdrawn).update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):rfp.current_response(self.case,self.response.pk)
        self.assertEqual(historical_submission(self.case,self.submission).pk,self.response.pk)
        outcome=rfp.outcome(owner,self.case.pk,self.submission.pk,'won',timezone.now(),'Client',self.evidence['rfp_outcome'].pk,
            'Current relationship owner confirmed the historical submitted offer',rev(self.case))
        disposition=rfp.dispose(owner,self.case.pk,outcome.pk,None,rev(self.case))
        self.assertEqual(disposition.kind,'route_a');self.assertEqual(disposition.snapshot['response'],self.response.pk)
        self.assertEqual(disposition.snapshot['sources'],self.response.snapshot)
        self.assertFalse(disposition.snapshot['baseline_imported']);self.assertFalse(Baseline.objects.exists())
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_newer_unsent_draft_does_not_replace_the_actual_submitted_offer(self):
        wording=add_evidence(self.actor,self.case.pk,'rfp_response','Newer unsent response wording','synthetic:unsent-draft')
        newer=rfp.prepare_response(self.actor,self.case.pk,wording.pk,self.response.matrix,
            {kind:self.evidence[kind].pk for kind in ['requirements','plan','costing']},rev(self.case),
            public_terms_id=self.evidence['rfp_commercial_terms'].pk)
        self.assertEqual(RFPSubmission.objects.count(),1)
        self.assertFalse(outcome_selection_state(self.case)['required'])
        outcome=self.actual();disposition=rfp.dispose(self.actor,self.case.pk,outcome.pk,None,rev(self.case))
        self.assertEqual(disposition.snapshot['response'],self.response.pk)
        self.assertEqual(disposition.snapshot['commercial_sources'],self.response.commercial.sources)
        self.assertEqual(RFPCase.objects.get(case=self.case).current_response_id,newer.pk)
        self.assertFalse(newer.submissions.exists());self.assertFalse(Baseline.objects.exists())

    def test_missing_or_changed_submission_claims_cannot_pass_historical_verification(self):
        missing=RFPSubmission(response=self.response,version=self.submission.version,snapshot=self.submission.snapshot,
            receipt_ids=[],submitted_at=timezone.now(),late=False,actor=self.actor)
        with self.assertRaises(ValidationError):historical_submission(self.case,missing)
        bad=copy(self.submission);bad.snapshot=deepcopy(self.submission.snapshot);bad.snapshot['reviews']=[]
        with self.assertRaises(ValidationError):historical_submission(self.case,bad)
        bad=copy(self.submission);bad.receipt_ids=[]
        with self.assertRaises(ValidationError):historical_submission(self.case,bad)
        _,other=setup_case(username='different-rfp-workspace')
        with self.assertRaises(ValidationError):historical_submission(other,self.submission)
        self.assertEqual(historical_submission(self.case,self.submission).pk,self.response.pk)
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_latest_uncertainty_and_current_outcome_authority_still_hold_conversion(self):
        won=self.actual();unknown=self.actual('unknown')
        with self.assertRaises(ValidationError):rfp.dispose(self.actor,self.case.pk,won.pk,None,rev(self.case))
        with self.assertRaises(ValidationError):rfp.dispose(self.actor,self.case.pk,unknown.pk,None,rev(self.case))
        current=self.actual()
        Grant.objects.filter(case=self.case,user=self.actor,action='rfp.outcome').update(active=False)
        with self.assertRaises(PermissionDenied):rfp.dispose(self.actor,self.case.pk,current.pk,None,rev(self.case))
        self.assertFalse(RFPDisposition.objects.exists())

    def test_actual_outcome_recording_survives_incomplete_retained_submission_proof(self):
        # A retained legacy source row is deliberately incomplete; no publication is fabricated.
        version=create_version(self.actor,self.case.pk,self.template.pk,'Retained incomplete response','client',
            deepcopy(self.submission.version.fields),rev(self.case))
        retained=RFPSubmission.objects.create(response=self.response,version=version,snapshot={},receipt_ids=[],
            submitted_at=timezone.now(),late=False,actor=self.actor)
        outcome=self.actual(submission=retained)
        self.assertEqual(outcome.result,'won');self.assertEqual(outcome.submission_id,retained.pk)
        with self.assertRaisesMessage(ValidationError,'binding'):
            rfp.dispose(self.actor,self.case.pk,outcome.pk,None,rev(self.case))
        self.assertFalse(RFPDisposition.objects.exists());self.assertFalse(Baseline.objects.exists())
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_multiple_submissions_hold_conversion_until_current_owner_explicitly_selects(self):
        self.another_submission()
        state=outcome_selection_state(self.case)
        self.assertTrue(state['required']);self.assertIsNone(state['configuration'])
        outcome=self.actual()
        self.assertNotIn('_selection_context',outcome.authority)
        with self.assertRaisesMessage(ValidationError,'Multiple submitted responses'):
            rfp.dispose(self.actor,self.case.pk,outcome.pk,None,rev(self.case))
        null=self.selection_method(None)
        self.assertIsNone(outcome_selection_state(self.case)['configuration'])
        policy=self.selection_method();state=outcome_selection_state(self.case)
        self.assertEqual(state['configuration'],policy.pk);self.assertNotEqual(state['configuration'],null.pk)
        with self.assertRaisesMessage(ValidationError,'STALE_VERSION'):
            self.actual(selection_context={'packet':'0'*64,'acknowledged':True})
        with self.assertRaises(ValidationError):self.actual(selection_context={'packet':state['packet'],'acknowledged':1})
        add_evidence(self.actor,self.case.pk,'document','Unrelated later case note','synthetic:case-note')
        self.assertEqual(outcome_selection_state(self.case)['packet'],state['packet'])
        selected=self.actual(selection_context={'packet':state['packet'],'acknowledged':True})
        self.assertEqual(selected.authority['_selection_context']['submission'],self.submission.pk)
        self.assertEqual(selected.authority['_selection_context']['configuration'],policy.pk)
        self.assertTrue(rfp.outcome_authority_matches(selected.authority,rfp.authority(self.actor,self.case,'outcome','Client')))
        self.another_submission()
        with self.assertRaisesMessage(ValidationError,'fresh actual outcome'):
            rfp.dispose(self.actor,self.case.pk,selected.pk,None,rev(self.case))
        state=outcome_selection_state(self.case)
        renewed=self.actual(selection_context={'packet':state['packet'],'acknowledged':True})
        disposition=rfp.dispose(self.actor,self.case.pk,renewed.pk,None,rev(self.case))
        self.assertEqual(disposition.snapshot['submission'],self.submission.pk)
        self.assertEqual(disposition.snapshot['response'],self.response.pk)
        self.assertEqual(RFPSubmission.objects.count(),3);self.assertEqual(PublicationReceipt.objects.count(),3)
        self.assertFalse(Baseline.objects.exists())

    def test_positive_delivered_receipts_must_be_recorded_before_conversion_but_reservation_is_not_submission(self):
        response=native.response(self.actor,self.case,self.evidence)
        native.approve(self.actor,self.case,self.evidence,response)
        version=rfp_documents.draft(self.actor,self.case.pk,response.pk,self.template.pk,'client_bid',rev(self.case))
        request_review(self.actor,self.case.pk,version.pk,rev(self.case))
        review_version(self.actor,self.case.pk,version.pk,'approve','Exact later response reviewed',rev(self.case))
        publication=reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case))
        reserved=outcome_selection_state(self.case)
        self.assertFalse(reserved['required']);self.assertEqual(reserved['finding'],'')
        self.assertEqual(reserved['inventory']['unrecorded_deliveries'],[])
        self.assertTrue(run_publication_once(job_id=publication.job.pk))
        delivered=outcome_selection_state(self.case)
        self.assertIn('original delivered response receipts',delivered['finding'])
        self.assertEqual(len(delivered['inventory']['submissions']),1)
        self.assertEqual(delivered['inventory']['unrecorded_deliveries'][0]['version'],version.pk)
        self.assertEqual(RFPSubmission.objects.count(),1)
        actual=self.actual()
        self.assertEqual(actual.result,'won')
        with self.assertRaisesMessage(ValidationError,'original delivered response receipts'):
            rfp.dispose(self.actor,self.case.pk,actual.pk,None,rev(self.case))
        rfp_documents.capture_submission(self.actor,self.case.pk,version.pk,rev(self.case))
        recorded=outcome_selection_state(self.case)
        self.assertEqual(recorded['inventory']['unrecorded_deliveries'],[]);self.assertTrue(recorded['required'])
        self.assertIn('Multiple submitted responses',recorded['finding'])
        self.assertFalse(RFPDisposition.objects.exists())

    def test_bounded_display_prefix_keeps_complete_inventory_digest_and_selected_version(self):
        from unittest.mock import patch
        from apps.pmo import rfp_outcomes
        second=self.another_submission();self.selection_method()
        self.actual('unknown');self.actual('pending',submission=second)
        full=outcome_selection_state(self.case)
        with patch.object(rfp_outcomes,'HISTORY_LIMIT',1):
            bounded=outcome_selection_state(self.case)
            self.assertEqual(bounded['packet'],full['packet']);self.assertEqual(bounded['finding'],'')
            for category in ['submissions','earlier_outcomes']:
                self.assertEqual(len(bounded['inventory'][category]),1)
                self.assertEqual(bounded['inventory']['coverage'][category]['count'],2)
                self.assertEqual(bounded['inventory']['coverage'][category]['visible'],1)
            self.actual('unknown')
            changed=outcome_selection_state(self.case)
            self.assertNotEqual(changed['packet'],bounded['packet'])
            self.assertEqual(changed['inventory']['earlier_outcomes'],bounded['inventory']['earlier_outcomes'])
            self.assertEqual(changed['inventory']['coverage']['earlier_outcomes']['count'],3)
            self.assertNotEqual(changed['inventory']['coverage']['earlier_outcomes']['sha256'],bounded['inventory']['coverage']['earlier_outcomes']['sha256'])
            outcome=self.actual(submission=second,selection_context={'packet':changed['packet'],'acknowledged':True})
            context=outcome.authority['_selection_context']
            self.assertEqual(context['selected']['id'],second.pk)
            self.assertEqual(context['inventory']['submissions']['count'],2)
            self.assertNotIn('visible',context['inventory']['submissions'])
            self.assertEqual(rfp.dispose(self.actor,self.case.pk,outcome.pk,None,rev(self.case)).kind,'route_a')
