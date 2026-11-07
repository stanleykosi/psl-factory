"""Bounded C15/C17/C18 contrasts. Synthetic owner evidence, no external authority."""
import json
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.pmo.delivery import GLPI_GATES, UPSTREAM_GATES, record_release_request, prepare_readiness
from apps.pmo.meetings import record_meeting
from apps.policy.models import Configuration, PolicyState
from apps.pmo.models import DeliveryRecord, IssueReferenceObservation
from apps.documents.controlled import create_version, request_review, review_version, reserve_publication
from apps.documents.models import PublicationReceipt, ControlledReview
from tests.test_delivery import DeliveryFixture
from tests.test_issue_references import IssueReferenceTests
from tests.document_helpers import publication_fixture, fields, approved
from tests.helpers import rev

class RetrospectiveBoundary(DeliveryFixture, TestCase):
    def test_C15_retrospective_proposal_cannot_waive_glpi_ceo(self):
        self.setup_delivery(); self.plan(); self.gates(UPSTREAM_GATES)
        a,c=self.actor,self.case
        record_release_request(a,c.pk,self.d.pk,'GLPI-770',self.e['requirements'].pk,'Actual request reference',rev(c))
        self.gates(['glpi_security','glpi_cto'],'GLPI-770')
        policies=list(Configuration.objects.values());states=list(PolicyState.objects.values())
        proposal='Proposal only: omit GLPI CEO approval in a future policy revision'
        m=record_meeting(a,c.pk,'RETRO-770','retrospective',timezone.now(),'Review release controls',proposal,[a.pk],[],self.e['requirements'].pk,rev(c))
        self.assertEqual(m.summary,proposal)
        self.assertEqual(GLPI_GATES,['glpi_security','glpi_cto','glpi_ceo'])
        self.assertEqual(list(Configuration.objects.values()),policies)
        self.assertEqual(list(PolicyState.objects.values()),states)
        with self.assertRaisesMessage(ValidationError,'glpi_ceo'):
            prepare_readiness(a,c.pk,self.d.pk,rev(c))
        self.assertFalse(DeliveryRecord.objects.filter(dossier=self.d,kind='release_ready').exists())
        self.gates(['glpi_ceo'],'GLPI-770')
        ready=prepare_readiness(a,c.pk,self.d.pk,rev(c))
        self.assertFalse(ready.snapshot['deployment_authorized'])
        self.assertEqual(ready.snapshot['financial_controls'],'independent')

class ExternalReferenceBoundary(IssueReferenceTests):
    def test_C17_real_pmo_local_closure_never_changes_supplied_incident_status(self):
        self.setup_reference(); observed=self.observe(); self.correct(observed)
        before=list(IssueReferenceObservation.objects.values())
        s=self.step(self.s,'acknowledge')
        s=self.step(s,'resolve',fix_id=self.fix.pk,root_cause_id=self.rca.pk)
        from apps.pmo.issues import close_issue_log
        for role in ['QA','PM']:
            close_issue_log(self.a,self.c.pk,s.issue_id,s.pk,role,self.fix.pk,'Close only local issue log',rev(self.c))
        s.issue.refresh_from_db()
        self.assertEqual(s.issue.current.status,'Closed')
        self.assertEqual(list(IssueReferenceObservation.objects.values()),before)
        observed.refresh_from_db();self.assertEqual(observed.fields['status'],'Investigating')
        from apps.pmo import issue_references as refs
        self.assertEqual(refs.report(self.a,s.issue)['references'][0]['fields']['status'],'Investigating')

class RevisionReviewBoundary(TestCase):
    def test_C18_same_source_ids_revised_content_cannot_inherit_old_review(self):
        a,c,owner,source,template,recipient,recipients,storage=publication_fixture()
        old=approved(a,c,template,source)
        old_payload=old.payload; old_reviews=list(old.reviews.values_list('pk',flat=True)) if hasattr(old,'reviews') else list(ControlledReview.objects.filter(version=old).values_list('pk',flat=True))
        revised=fields(source);revised['status']['text']='Revised external milestone statement requiring human review'
        revised['internal_notes']['text']='PRIVATE REVISION 770 must never export'
        new=create_version(a,c.pk,template.pk,old.document.title,'client',revised,rev(c),old.document_id)
        self.assertEqual(new.source_manifest,old.source_manifest)
        self.assertNotEqual(new.payload_sha256,old.payload_sha256)
        self.assertNotIn('PRIVATE REVISION 770',json.dumps(new.payload))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,new.pk,rev(c))
        self.assertFalse(ControlledReview.objects.filter(version=new).exists())
        self.assertFalse(PublicationReceipt.objects.exists())
        old.refresh_from_db();self.assertEqual(old.payload,old_payload)
        self.assertEqual(list(ControlledReview.objects.filter(version=old).values_list('pk',flat=True)),old_reviews)

    def test_C18_human_current_content_return_blocks_obsolete_milestone_with_current_ids(self):
        from tests.document_helpers import artifact
        a,c,owner,source,template,recipient,recipients,storage=publication_fixture()
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},owner)
        current=add_evidence(a,c.pk,'progress','Explicit synthetic milestone date: 2026-11-20','synthetic:dated-progress')
        content=fields(current);content['timeline']['text']='Milestone date: 2026-11-01'
        v=create_version(a,c.pk,template.pk,'Stale milestone report','client',content,rev(c))
        self.assertEqual(v.source_manifest[0]['id'],current.pk)
        self.assertEqual(v.source_manifest[0]['sha256'],current.sha256)
        request_review(a,c.pk,v.pk,rev(c))
        review=review_version(a,c.pk,v.pk,'return','Human accuracy review: milestone date conflicts with exact current source; correct before sharing',rev(c))
        self.assertEqual(review.verdict,'return')
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,v.pk,rev(c))
        self.assertFalse(PublicationReceipt.objects.exists())
        self.assertEqual(v.fields['timeline']['text'],'Milestone date: 2026-11-01')

class RFPClockBoundary(TestCase):
    def test_C16_elapsed_no_response_does_not_create_loss_or_archive(self):
        from datetime import timedelta
        from unittest.mock import patch
        from tests import test_rfp as native
        from apps.pmo.models import RFPOutcome, RFPDisposition, RFPIntake
        from apps.agents.rfp import investigate_rfp
        a,c,e,t,route=native.fixture()
        v=native.response(a,c,e);native.approve(a,c,e,v);submission=native.submit(a,c,e,t,v)
        before=list(RFPIntake.objects.values())
        after_year=timezone.now()+timedelta(days=366)
        with patch('django.utils.timezone.now',return_value=after_year):
            run=investigate_rfp(a,c.pk,rev(c))
        self.assertIn('Outcome remains unknown until relationship-owner evidence is captured',run.result['findings'])
        self.assertFalse(RFPOutcome.objects.exists());self.assertFalse(RFPDisposition.objects.exists())
        self.assertEqual(list(RFPIntake.objects.values()),before)
        submission.refresh_from_db();self.assertEqual(submission.response_id,v.pk)

from tests.test_emergencies import EmergencyFixture

class IncidentProductionBoundary(EmergencyFixture, TestCase):
    def test_C19_exact_incident_change_candidate_glpi_and_role_time_chain(self):
        from apps.pmo.emergencies import authorize_emergency
        from apps.pmo.gates import record_gate, verify_gate
        from apps.pmo.models import EmergencyDecision
        # Synthetic explicitly configured coexistence, not a real resolution of Q03.
        self.policies('coexist');self.decisions('coexist')
        pins=[]
        for kind in ['glpi_security','glpi_cto','glpi_ceo']:
            gate=record_gate(self.actor,self.case.pk,self.candidate.pk,kind,'GLPI-770-C19',self.source.pk,rev(self.case))
            verification=verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case))
            pins.append([gate.pk,verification.pk])
        auth=authorize_emergency(self.actor,self.case.pk,self.profile.pk,rev(self.case))
        self.assertEqual(auth.profile.version_id,self.cv.pk)
        self.assertEqual(auth.profile.version.incident_id,self.incident.pk)
        self.assertEqual(auth.profile.candidate_id,self.candidate.pk)
        self.assertEqual(auth.snapshot['glpi'],pins)
        decisions=list(EmergencyDecision.objects.filter(pk__in=auth.snapshot['decision_ids']).order_by('pk'))
        self.assertEqual([d.role for d in decisions],['Incident Lead','Engineering Lead','CTO'])
        self.assertEqual([d.authority_role for d in decisions],['Engineering Lead','Engineering Lead','CTO'])
        self.assertTrue(all(d.created_at<=auth.created_at for d in decisions))
        outcome=self.outcome(auth)
        self.assertEqual(outcome.authorization_id,auth.pk)
        self.assertEqual(outcome.profile.version.incident_id,self.incident.pk)
        self.assertGreaterEqual(outcome.implemented_at,auth.created_at)
        self.assertEqual(auth.profile.version.change.reference,'EM-001')

class RFPRevisionQuestionBoundary(TestCase):
    def test_C16_proposed_revised_requirements_deadline_owner_question(self):
        from datetime import timedelta
        from tests import test_rfp as native
        from apps.pmo import rfp
        from apps.pmo.models import RFPIntake, RFPCase, RFPDisposition
        from apps.agents.rfp import investigate_rfp
        a,c,e,t,route=native.fixture()
        original=list(RFPIntake.objects.values())
        source=add_evidence(a,c.pk,'rfp_intake','Explicit changed requirements: new named deliverable','synthetic:rfp-revision')
        deadline=add_evidence(a,c.pk,'rfp_deadline','Explicit changed deadline supplied by RFP owner','synthetic:rfp-deadline')
        current=rfp.intake(a,c.pk,'RFP-001',source.pk,timezone.now(),'stated',timezone.now()+timedelta(days=5),deadline.pk,'Revised requirements and deadline need source-owner clarification',rev(c))
        self.assertEqual(list(RFPIntake.objects.filter(pk=original[0]['id']).values()),original)
        self.assertEqual(RFPCase.objects.count(),1);self.assertFalse(RFPDisposition.objects.exists())
        result=investigate_rfp(a,c.pk,rev(c)).result
        # Proposed P45 case/version safeguard, not a binding SOP requirement or canonical defect.
        # Behavioral surface assertion, no invented owner, schema or outbound message.
        self.assertTrue(any('requirements' in f.lower() and 'deadline' in f.lower() for f in result['findings']),
                        'Revised requirements/deadline need an explicit source-owner question in the existing findings surface')

class RFPAssistantRevisionBoundary(TestCase):
    def setUp(self):
        from tests import test_rfp as native
        from apps.pmo import rfp
        self.a,self.c,self.e,self.t,self.route=native.fixture()
        self.original=rfp.root(self.c).current_intake

    def revise(self,source=None,status='not_stated',deadline=None,deadline_source=None):
        from apps.pmo import rfp
        return rfp.intake(self.a,self.c.pk,'RFP-001',(source or self.e['rfp_intake']).pk,timezone.now(),status,
                          deadline,deadline_source.pk if deadline_source else None,'Explicit retained revision',rev(self.c))

    def investigate(self):
        from apps.agents.rfp import investigate_rfp
        return investigate_rfp(self.a,self.c.pk,rev(self.c)).result

    def questions(self,result):
        return [f for f in result['findings'] if 'source owner' in f.lower()]

    def test_first_and_unchanged_typed_revision_do_not_invent_changed_facts(self):
        self.assertEqual(self.questions(self.investigate()),[])
        self.revise()
        self.assertEqual(self.questions(self.investigate()),[])

    def test_deadline_unknown_to_stated_uses_typed_fact_without_inferred_requirements(self):
        from datetime import timedelta
        self.revise(status='unknown')
        deadline=add_evidence(self.a,self.c.pk,'rfp_deadline','Deadline prose intentionally not parsed','synthetic:explicit-deadline')
        supplied=timezone.now()+timedelta(days=7)
        current=self.revise(status='stated',deadline=supplied,deadline_source=deadline)
        result=self.investigate();question=self.questions(result)
        self.assertEqual(len(question),1)
        self.assertIn('no requirements change is inferred',question[0])
        self.assertNotIn(supplied.isoformat(),json.dumps(result))
        current.refresh_from_db();self.assertEqual(current.deadline_at,supplied)

    def test_revised_reference_even_identical_body_is_question_not_semantic_assertion(self):
        source=add_evidence(self.a,self.c.pk,'rfp_intake',self.e['rfp_intake'].body,'synthetic:same-body-new-reference')
        self.revise(source)
        question=self.questions(self.investigate())
        self.assertEqual(len(question),1)
        self.assertIn('source reference was revised',question[0])
        self.assertIn('which requirements changed',question[0])
        self.assertIn('source text has not been interpreted',question[0])

    def test_inaccessible_prior_content_is_not_in_question_or_citations(self):
        private=add_evidence(self.a,self.c.pk,'rfp_intake','PRIVATE PRIOR RFP 770','psl:p56-confirmed-request/v1')
        old=self.revise(private)
        current=self.revise()
        result=self.investigate()
        self.assertEqual(self.questions(result),['Retained intake comparison is unavailable under current source access; ask the source owner for a permitted clarification.'])
        self.assertNotIn('PRIVATE PRIOR RFP 770',json.dumps(result))
        self.assertNotIn(private.pk,[c['id'] for c in result['citations']])
        old.refresh_from_db();self.assertEqual(old.evidence_id,private.pk)
        current.refresh_from_db();self.assertEqual(current.evidence_id,self.e['rfp_intake'].pk)

    def test_revoked_source_author_grant_masks_comparison_without_new_business_hold(self):
        from apps.identity.models import Grant
        self.revise(status='unknown')
        Grant.objects.filter(case=self.c,user=self.a,action='evidence.add').update(active=False)
        result=self.investigate()
        self.assertEqual(self.questions(result),['Retained intake comparison is unavailable under current source access; ask the source owner for a permitted clarification.'])
        self.assertFalse(result['approval_granted']);self.assertFalse(result['submission_dispatched'])

    def test_assistance_changes_only_run_audit_not_retained_business_rows_or_revision(self):
        from apps.pmo.models import RFPIntake,RFPCase,RFPAssignment,RFPContribution,RFPResponse,RFPSubmission,RFPOutcome,RFPDisposition,Baseline
        from apps.documents.models import Version,Publication,PublicationReceipt
        from apps.core.models import Evidence
        source=add_evidence(self.a,self.c.pk,'rfp_intake','Source owner supplied updated source','synthetic:changed-source')
        self.revise(source,status='unknown')
        models=[RFPIntake,RFPCase,RFPAssignment,RFPContribution,RFPResponse,RFPSubmission,RFPOutcome,RFPDisposition,Baseline,Version,Publication,PublicationReceipt,Evidence]
        before={m._meta.label:list(m.objects.order_by('pk').values()) for m in models};revision=rev(self.c)
        result=self.investigate()
        self.assertEqual(len(self.questions(result)),1)
        self.assertEqual({m._meta.label:list(m.objects.order_by('pk').values()) for m in models},before)
        self.assertEqual(rev(self.c),revision)
        self.assertFalse(RFPDisposition.objects.exists());self.assertFalse(PublicationReceipt.objects.exists())
