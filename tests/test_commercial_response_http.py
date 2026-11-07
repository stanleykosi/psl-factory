"""P19: exercise the actual operator response boundary, not a service substitute."""
from django.test import TestCase
from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo.models import ClientResponse, Baseline, BaselineAdoption
from .helpers import rev, setup_case
from .test_commercial_changes import fixture, proposal, approvals, delivered


class CommercialResponseHTTPTests(TestCase):
    def setUp(self):
        self.actor, self.case, self.e, self.template = fixture()
        self.proposal = proposal(self.actor, self.case, self.e)
        approvals(self.actor, self.case, self.proposal)
        self.receipt = delivered(self.actor, self.case, self.proposal, self.template)
        self.feedback = add_evidence(self.actor, self.case.pk, 'client_feedback', 'Client requests revision', 'synthetic:client')
        self.client.force_login(self.actor)
        self.url = f'/cases/{self.case.pk}/commercial/'

    def data(self, kind='feedback', **overrides):
        result = dict(action='response', revision=rev(self.case), proposal=self.proposal.pk,
                      receipt=self.receipt.pk, kind=kind, note='Human captured exact client reply',
                      evidence=self.e['signature'].pk if kind == 'signed' else self.feedback.pk)
        result.update(overrides)
        return result

    def snapshot(self):
        return (rev(self.case), ClientResponse.objects.count(), Audit.objects.count(),
                Baseline.objects.count(), BaselineAdoption.objects.count())

    def test_feedback_signed_and_declined_reach_native_capture(self):
        for kind in ['feedback', 'signed', 'declined']:
            with self.subTest(kind=kind):
                before = rev(self.case)
                response = self.client.post(self.url, self.data(kind))
                self.assertEqual(response.status_code, 302)
                captured = ClientResponse.objects.get(kind=kind)
                self.assertEqual(captured.receipt_id, self.receipt.pk)
                self.assertEqual(captured.actor_id, self.actor.pk)
                self.assertEqual(captured.revision_id, self.proposal.pk)
                self.assertEqual(rev(self.case), before + 1)
                self.assertTrue(Audit.objects.filter(case=self.case, action='commercial.client_response', data__response=captured.pk).exists())
        self.assertFalse(Baseline.objects.exists())
        self.assertFalse(BaselineAdoption.objects.exists())

    def test_invalid_kind_evidence_receipt_and_blank_note_preserve_rows(self):
        for override in [dict(kind='approve'), dict(evidence=self.e['plan'].pk),
                         dict(receipt=0), dict(proposal=0), dict(note=''), dict(evidence='bad')]:
            with self.subTest(override=override):
                before = self.snapshot()
                self.assertEqual(self.client.post(self.url, self.data(**override)).status_code, 200)
                self.assertEqual(self.snapshot(), before)

    def test_stale_revision_and_duplicate_capture_preserve_rows(self):
        request = self.data()
        self.assertEqual(self.client.post(self.url, request).status_code, 302)
        before = self.snapshot()
        self.assertContains(self.client.post(self.url, request), 'Stale revision')
        self.assertEqual(self.snapshot(), before)
        self.assertContains(self.client.post(self.url, self.data()), 'already captured')
        self.assertEqual(self.snapshot(), before)

    def test_revoked_response_permission_preserves_rows(self):
        Grant.objects.filter(user=self.actor, case=self.case, action='commercial.response').update(active=False)
        before = self.snapshot()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_foreign_case_response_identities_preserve_rows(self):
        other_actor, other, evidence, template = fixture(username='other-commercial')
        foreign = proposal(other_actor, other, evidence)
        approvals(other_actor, other, foreign)
        receipt = delivered(other_actor, other, foreign, template)
        for override in [dict(proposal=foreign.pk), dict(receipt=receipt.pk), dict(kind='signed', evidence=evidence['signature'].pk)]:
            with self.subTest(override=override):
                before = self.snapshot()
                self.assertEqual(self.client.post(self.url, self.data(**override)).status_code, 200)
                self.assertEqual(self.snapshot(), before)
