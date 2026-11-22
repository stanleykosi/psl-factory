"""Separate synthetic reviewers return exact native bid versions to the preparer."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import commercial, rfp
from apps.pmo.models import CommercialDecision, RFPReview, RFPSubmission
from apps.policy import role_assignments
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_rfp
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class BidReturnHandoffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = helpers.configured('SAMPLE-BID-RETURN')
        cls.maker, cls.case = cls.sample['actor'], cls.sample['case']
        cls.proof = cls.sample['evidence']['policy_decision']
        cls.reviewer = get_user_model().objects.create_user(username='sample-bid-return-reviewer')
        cls.reader = get_user_model().objects.create_user(username='sample-bid-return-response-reader')
        reads = {'case.read', 'factory.read', 'rfp.read'}
        Grant.objects.bulk_create([
            *[Grant(case=cls.case, user=cls.reviewer, action=action) for action in
              reads | {'rfp.review', 'commercial.read', 'commercial.decide'}],
            *[Grant(case=cls.case, user=cls.reader, action=action) for action in reads],
        ])
        roles = reference_values(active_component(role_assignments.COMPONENT, cls.case))
        affected = {'Engineering Lead', 'Head of PMO'}
        assignments = [role for role in roles if role['role'] not in affected]
        assignments.extend({'role': role, 'user_id': cls.reviewer.pk} for role in sorted(affected))
        role_policy = role_assignments.draft(cls.maker, cls.case.pk, assignments, cls.proof.pk, timezone.now())
        transition(cls.maker, role_policy.pk, 'validated')
        transition(cls.maker, role_policy.pk, 'active')

        matrix = reference_values(active_component('D05.decision_action_matrix', cls.case))[0]
        matrix = {**matrix, 'rules': [*matrix['rules'], {'role': 'Head of PMO', 'actions': ['return']}]}
        decision_policy = draft_standard_policy(cls.maker, cls.case.pk, 'D05.decision_action_matrix',
                                                 matrix, cls.proof.pk, timezone.now())
        transition(cls.maker, decision_policy.pk, 'validated')
        transition(cls.maker, decision_policy.pk, 'active')
        rfp.assign(cls.maker, cls.case.pk, cls.maker, 'CEO', cls.proof.pk,
                   'Sample assignment under the separate reviewer role policy.', rev(cls.case))
        cls.work = helpers.start(cls.sample, key='SAMPLE-BID-RETURN')
        factory.run_until_wait(cls.work.pk)
        cls.work.refresh_from_db()
        cls.original = factory_rfp.response_for(cls.work)

    def decision(self, action, target, role, verdict, note):
        self.work.refresh_from_db()
        return self.client.post(reverse('factory_invoice_decision', args=[self.work.pk]), {
            'action': action, 'revision': self.work.revision, 'case_revision': rev(self.case),
            'target': target, 'role': role, 'verdict': verdict, 'note': note, 'evidence': self.proof.pk,
        })

    def correct(self, text):
        self.work.refresh_from_db()
        source = self.sample['payload']
        return self.client.post(reverse('factory_detail', args=[self.work.pk]), {
            'action': 'correct', 'revision': self.work.revision, 'case_revision': rev(self.case),
            'reason': 'Address the precise sample return.', 'response_evidence': source['response_evidence'],
            'public_terms': source['public_terms'], 'lessons': source['lessons'], **source['sources'],
            'requirements-INITIAL_FORMS': 1, 'requirements-TOTAL_FORMS': 1,
            'requirements-0-key': 'R1', 'requirements-0-evidence_id': source['sources']['requirements'],
            'requirements-0-response': text, 'requirements-0-disposition': 'addressed',
        })

    def assert_successor(self, reason, current_heading):
        self.client.force_login(self.maker)
        decision = reverse('factory_invoice_decision', args=[self.work.pk])
        link = reverse('factory_detail', args=[self.work.pk])
        current = self.client.get(decision + '?queue=decisions&q=sample')
        self.assertContains(current, current_heading)
        self.assertContains(current, reason)
        self.assertContains(current, f'Response version {self.original.number}')
        self.assertContains(current, f'{link}?queue=decisions&amp;q=sample#correct-response')
        self.assertEqual(self.correct('Revised sample coverage with the reviewed requirement.').status_code, 302)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        successor = factory_rfp.response_for(self.work)
        self.assertIsNotNone(successor, self.work.finding)
        self.assertNotEqual(successor.pk, self.original.pk)
        self.assertEqual(successor.actor_id, self.maker.pk)
        self.assertFalse(successor.reviews.exists())
        self.assertFalse(successor.commercial.decisions.exists())
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())
        self.assertFalse(RFPSubmission.objects.filter(response__rfp=self.original.rfp).exists())
        history = self.client.get(decision)
        self.assertContains(history, 'Earlier returns')
        self.assertContains(history, reason)
        self.assertContains(history, f'Response version {self.original.number}')
        self.assertNotContains(history, current_heading)
        return successor

    def test_independent_return_reaches_preparer_and_fresh_response_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        reason = 'The sample engineering estimate requires a clearer assumption.'
        self.client.force_login(self.maker)
        self.assertEqual(self.decision('response', self.original.pk, 'Engineering Lead', 'return', reason).status_code, 403)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.decision('response', self.original.pk, 'Engineering Lead', 'return', reason).status_code, 302)
        returned = RFPReview.objects.get(response=self.original, verdict='return')
        self.assertEqual((returned.actor_id, returned.evidence_id), (self.reviewer.pk, self.proof.pk))
        decision = reverse('factory_invoice_decision', args=[self.work.pk])
        self.assertNotContains(self.client.get(decision), '#correct-response')
        self.assertEqual(self.correct('The reviewer cannot correct the preparer source.').status_code, 403)

        successor = self.assert_successor(reason, 'Response returned for changes')
        self.client.force_login(self.reviewer)
        old = self.decision('response', self.original.pk, 'Engineering Lead', 'approve', 'This old version stays returned.')
        self.assertContains(old, 'Review the exact current response')
        self.assertEqual(self.decision('response', successor.pk, 'Engineering Lead', 'approve',
                                       'Reviewed the fresh response version.').status_code, 302)
        self.assertEqual(successor.reviews.get().actor_id, self.reviewer.pk)
        returned.refresh_from_db()
        self.assertEqual(returned.note, reason)

    def test_costing_return_reason_requires_commercial_read_and_retains_exact_version(self):
        self.assertEqual(connection.vendor, 'postgresql')
        rfp.review(self.maker, self.case.pk, self.original.pk, 'PMO Lead', 'approve', self.proof.pk,
                   'Reviewed the synthetic response.', rev(self.case))
        rfp.review(self.reviewer, self.case.pk, self.original.pk, 'Engineering Lead', 'approve', self.proof.pk,
                   'Independently reviewed the synthetic response.', rev(self.case))
        commercial.decide_proposal(self.maker, self.case.pk, self.original.commercial_id, 'PM', 'approve',
                                   'Reviewed the exact synthetic costing.', rev(self.case))
        reason = 'Correct the staffing assumption in the sample proposal.'
        self.client.force_login(self.reviewer)
        self.assertEqual(self.decision('commercial', self.original.commercial_id, 'Head of PMO', 'return', reason).status_code, 302)
        returned = CommercialDecision.objects.get(revision_id=self.original.commercial_id, verdict='return')
        self.assertEqual(returned.actor_id, self.reviewer.pk)
        decision = reverse('factory_invoice_decision', args=[self.work.pk])
        self.assertContains(self.client.get(decision), f'Costing version {self.original.commercial.number}')
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(decision), reason)

        successor = self.assert_successor(reason, 'Costing returned for changes')
        self.assertNotEqual(successor.commercial_id, returned.revision_id)
        self.client.force_login(self.reviewer)
        old = self.decision('commercial', returned.revision_id, 'Head of PMO', 'approve', 'The return cannot be replaced.')
        self.assertContains(old, 'Decide the exact current response costing')
        returned.refresh_from_db()
        self.assertEqual(returned.note, reason)
