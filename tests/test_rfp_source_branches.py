"""Focused native RFP branches, using synthetic authority and mock delivery.

Source locators: reference/12-payment-exception-policy/process-execution-bindings.json
P45 (SOP 6.1), P46 (6.2), P47 (6.3–6.4), P48 (6.5–6.6, 7).
The version/receipt safeguards are engineering controls, not new business policy.
These tests do not appoint actual owners or establish whole-process acceptance.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.agents.rfp import investigate_rfp
from apps.core.services import add_evidence
from apps.documents.controlled import (
    preflight, request_review, reserve_publication, review_version,
)
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from apps.pmo import commercial, rfp, rfp_documents
from apps.pmo.models import RFPCase, RFPDisposition, RFPSubmission
from tests.document_helpers import artifact
from tests.helpers import rev
from tests import test_rfp as native


class RFPSourceBranchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, cls.evidence, cls.template, _ = native.fixture()

    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')

    def revised_intake(self):
        a, c, e = self.actor, self.case, self.evidence
        source = add_evidence(a, c.pk, 'rfp_intake',
                              'Synthetic revised customer requirements', 'synthetic:revised-rfp')
        return rfp.intake(a, c.pk, 'RFP-001', source.pk, timezone.now(),
                          'not_stated', None, None,
                          'Revised source explicitly states no submission deadline', rev(c))

    def contribute(self, excluded=()):
        for team, kind in rfp.TEAMS.items():
            if team not in excluded:
                rfp.contribute(self.actor, self.case.pk, team,
                               self.evidence[kind].pk, rev(self.case))

    def test_configured_non_ceo_assignment_and_revised_intake_preserve_history(self):
        # P45: CEO assignment is "if provided", not a universal bid/no-bid gate.
        a, c, e = self.actor, self.case, self.evidence
        original = native.response(a, c, e)
        old_snapshot = original.snapshot
        artifact(a, c, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v2',
                 {'rfp': {'assignment_roles': ['Head of PMO'], 'outcome_roles': ['Client']}},
                 e['policy_decision'])
        intake = self.revised_intake()
        self.contribute()
        with self.assertRaisesMessage(ValidationError, 'Assign an accountable PM'):
            native.response(a, c, e)
        with self.assertRaises(PermissionDenied):
            rfp.assign(a, c.pk, a, 'CEO', e['policy_decision'].pk,
                       'CEO is not the configured assignment role', rev(c))
        assignment = rfp.assign(a, c.pk, a, 'Head of PMO', e['policy_decision'].pk,
                                'Synthetic configured assignment of revised intake', rev(c))
        current = native.response(a, c, e)
        self.assertEqual(current.intake_id, intake.pk)
        self.assertEqual(current.assignment_id, assignment.pk)
        self.assertEqual(assignment.role, 'Head of PMO')
        self.assertEqual(current.rfp_id, original.rfp_id)
        self.assertEqual(current.commercial.previous_id, original.commercial_id)
        original.refresh_from_db()
        self.assertEqual(original.snapshot, old_snapshot)
        self.assertNotEqual(original.intake_id, current.intake_id)
        with self.assertRaises(ValidationError):
            rfp.current_response(c, original.pk)
        self.assertEqual(RFPCase.objects.filter(case=c).count(), 1)
        self.assertFalse(current.commercial.decisions.exists())
        self.assertFalse(RFPDisposition.objects.exists())

    def test_missing_security_input_stays_visible_until_native_contribution(self):
        # P46: all four teams contribute; absent Security is not zero effort.
        a, c, e = self.actor, self.case, self.evidence
        intake = self.revised_intake()
        rfp.assign(a, c.pk, a, 'CEO', e['policy_decision'].pk,
                   'Assign revised requirements', rev(c))
        self.contribute(excluded={'Security'})
        with self.assertRaisesMessage(ValidationError, 'Capture Security input'):
            native.response(a, c, e)
        result = investigate_rfp(a, c.pk, rev(c)).result
        self.assertTrue(any('Capture Security input' in x for x in result['findings']))
        self.assertFalse(result['approval_granted'])
        self.assertFalse(result['submission_dispatched'])
        self.assertFalse(intake.contributions.filter(team='Security').exists())
        self.assertFalse(rfp.root(c).responses.exists())
        self.assertFalse(PublicationReceipt.objects.exists())
        security = rfp.contribute(a, c.pk, 'Security', e['security_estimate'].pk, rev(c))
        response = native.response(a, c, e)
        self.assertEqual(response.snapshot['inputs']['Security']['id'], security.pk)
        self.assertEqual(response.commercial.sources['security_estimate'], security.evidence_id)
        native.approve(a, c, e, response)
        submission = native.submit(a, c, e, self.template, response)
        self.assertEqual(submission.response_id, response.pk)
        self.assertEqual(PublicationReceipt.objects.count(), 1)

    def changed_after_ceo(self, kind):
        a, c, e = self.actor, self.case, self.evidence
        old = native.response(a, c, e)
        native.approve(a, c, e, old)
        old_decisions = list(old.commercial.decisions.values_list('pk', flat=True))
        old_sources = dict(old.commercial.sources)
        document = rfp_documents.draft(a, c.pk, old.pk, self.template.pk, 'client_bid', rev(c))
        request_review(a, c.pk, document.pk, rev(c))
        review_version(a, c.pk, document.pk, 'approve', 'Review exact original bid', rev(c))
        publication = reserve_publication(a, c.pk, document.pk, rev(c))
        revised = dict(e)
        revised[kind] = add_evidence(a, c.pk, kind,
                                     'Synthetic revised ' + kind + ': 120 instead of 100',
                                     'synthetic:post-ceo-revision')
        current = native.response(a, c, revised)
        self.assertEqual(current.commercial.previous_id, old.commercial_id)
        self.assertFalse(current.commercial.decisions.exists())
        self.assertFalse(current.reviews.exists())
        self.assertTrue(preflight(document))
        self.assertTrue(run_publication_once(job_id=publication.job.pk))
        publication.job.refresh_from_db()
        self.assertEqual(publication.job.status, 'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
        with self.assertRaises(ValidationError):
            rfp_documents.draft(a, c.pk, current.pk, self.template.pk, 'client_bid', rev(c))
        for role in rfp.REVIEW_ROLES:
            rfp.review(a, c.pk, current.pk, role, 'approve', e['policy_decision'].pk,
                       'Review revised response', rev(c))
        with self.assertRaisesMessage(ValidationError, 'Current commercial approvals missing: PM'):
            commercial.decide_proposal(a, c.pk, current.commercial_id, 'CEO', 'approve',
                                       'Cannot reuse prior CEO decision', rev(c))
        for role in ['PM', 'Head of PMO']:
            commercial.decide_proposal(a, c.pk, current.commercial_id, role, 'approve',
                                       'Fresh exact costing decision', rev(c))
        with self.assertRaisesMessage(ValidationError, 'Current commercial approvals missing: CEO'):
            rfp_documents.draft(a, c.pk, current.pk, self.template.pk, 'client_bid', rev(c))
        commercial.decide_proposal(a, c.pk, current.commercial_id, 'CEO', 'approve',
                                   'Fresh final costing decision', rev(c))
        fresh = rfp_documents.draft(a, c.pk, current.pk, self.template.pk, 'client_bid', rev(c))
        with self.assertRaises(ValidationError):
            reserve_publication(a, c.pk, fresh.pk, rev(c))
        request_review(a, c.pk, fresh.pk, rev(c))
        review_version(a, c.pk, fresh.pk, 'approve', 'Review exact revised outward bid', rev(c))
        queued = reserve_publication(a, c.pk, fresh.pk, rev(c))
        self.assertTrue(run_publication_once(job_id=queued.job.pk))
        submission = rfp_documents.capture_submission(a, c.pk, fresh.pk, rev(c))
        self.assertEqual(submission.response_id, current.pk)
        self.assertEqual(PublicationReceipt.objects.count(), 1)
        self.assertEqual(RFPSubmission.objects.count(), 1)
        old.commercial.refresh_from_db()
        self.assertEqual(old.commercial.sources, old_sources)
        self.assertEqual(list(old.commercial.decisions.values_list('pk', flat=True)), old_decisions)
        self.assertFalse(current.commercial.decisions.filter(inherited__isnull=False).exists())
        self.assertEqual(rfp.public_terms_for(current).pk, revised['rfp_commercial_terms'].pk)
        self.assertEqual(current.commercial.sources['costing'], revised['costing'].pk)

    def test_changed_costing_after_ceo_requires_fresh_chain_and_outward_review(self):
        # P48 / SOP 7: cost changes repeat the costing chain.
        self.changed_after_ceo('costing')

    def test_changed_public_terms_after_ceo_cannot_reuse_exact_bid_approvals(self):
        # P47/P48: bind decisions and quality review to the revised client response.
        # This conservative exact-response control asserts no general non-cost reuse policy.
        self.changed_after_ceo('rfp_commercial_terms')

    def test_mixed_version_reviews_do_not_jointly_approve_current_response(self):
        # P47 / SOP 6.3–6.4: both named reviewers review the exact response.
        # P47-M02 describes the mixed-version safeguard as an engineering control.
        a, c, e = self.actor, self.case, self.evidence
        old = native.response(a, c, e)
        old_review = rfp.review(a, c.pk, old.pk, 'PMO Lead', 'approve',
                                e['policy_decision'].pk, 'Review original response', rev(c))
        old_snapshot = old.snapshot
        current = native.response(a, c, e)
        engineering = rfp.review(a, c.pk, current.pk, 'Engineering Lead', 'approve',
                                  e['policy_decision'].pk, 'Review revised response', rev(c))
        with self.assertRaisesMessage(ValidationError, 'Current RFP review missing: PMO Lead'):
            rfp.reviewed(current)
        with self.assertRaisesMessage(ValidationError, 'Current RFP review missing: PMO Lead'):
            commercial.decide_proposal(a, c.pk, current.commercial_id, 'PM', 'approve',
                                       'Mixed response versions are not joint review', rev(c))
        with self.assertRaisesMessage(ValidationError, 'Current RFP review missing: PMO Lead'):
            rfp_documents.draft(a, c.pk, current.pk, self.template.pk, 'client_bid', rev(c))
        self.assertFalse(current.commercial.decisions.exists())
        self.assertFalse(PublicationReceipt.objects.exists())
        old.refresh_from_db()
        old_review.refresh_from_db()
        self.assertEqual(old.snapshot, old_snapshot)
        self.assertEqual(old_review.response_id, old.pk)
        self.assertEqual(old_review.verdict, 'approve')
        self.assertEqual(list(old.reviews.values_list('pk', flat=True)), [old_review.pk])
        self.assertEqual(list(current.reviews.values_list('pk', flat=True)), [engineering.pk])
        pmo = rfp.review(a, c.pk, current.pk, 'PMO Lead', 'approve',
                         e['policy_decision'].pk, 'Review exact revised response', rev(c))
        self.assertCountEqual(rfp.reviewed(current), [engineering.pk, pmo.pk])
        for role in ['PM', 'Head of PMO', 'CEO']:
            commercial.decide_proposal(a, c.pk, current.commercial_id, role, 'approve',
                                       'Fresh ordered costing decision', rev(c))
        submission = native.submit(a, c, e, self.template, current)
        self.assertEqual(submission.response_id, current.pk)
        self.assertEqual(PublicationReceipt.objects.count(), 1)
        self.assertEqual(list(old.reviews.values_list('pk', flat=True)), [old_review.pk])
