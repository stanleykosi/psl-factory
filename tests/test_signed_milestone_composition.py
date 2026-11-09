"""F34 bounded native contrast. Synthetic owner rules, no new production policy."""
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.finance import billing
from apps.finance.models import Handoff, SignedBaselineIntake, Invoice, InvoicePreparation
from apps.identity.models import Grant
from apps.pmo.commercial import adopt_signed, capture_response, valid_approvals
from apps.pmo.changes import log_change, assess_change, decide_change, authorize_change, CONTRIBUTORS
from apps.pmo.models import Baseline, BaselineAdoption, Milestone
from apps.pmo.services import complete_milestone
from apps.workflows.models import Outbox
from apps.workflows.services import run_once
from adapters.finance import InternalFinanceAdapter, TimeoutAfterAccept
from adapters.signed_baselines import InternalSignedBaselineAdapter
from .helpers import rev
from .signature_helpers import packet_for
from .test_commercial_changes import fixture, proposal, approvals, delivered, change_roles, impact_fixture
from .billing_helpers import coverage, stage_policy, policy, prepare


class SignedMilestoneCompositionTests(TestCase):
    def adopt(self, a, c, e, t, v):
        receipt = delivered(a, c, v, t)
        response = capture_response(a, c.pk, v.pk, receipt.pk, 'signed', e['signature'].pk,
                                    'Synthetic exact signed version checked', rev(c))
        packet_for(a, c, e, v)
        return response

    def test_delayed_v1_completion_survives_lawful_v2_and_current_billing_is_separate(self):
        a, c, e, t = fixture(username='f34-composition')
        change_roles(a, c, e['policy_decision'])
        v1 = proposal(a, c, e); approvals(a, c, v1)
        response = self.adopt(a, c, e, t, v1)
        first = adopt_signed(a, c.pk, v1.pk, response.pk, rev(c))
        intake1 = SignedBaselineIntake.objects.get(adoption=first)
        original_intake = intake1.payload
        m = complete_milestone(a, c.pk, 'M1', e['completion'].pk, rev(c))
        job = Outbox.objects.get(milestone=m)
        original_payload = dict(job.payload)
        completion_audit = Audit.objects.get(case=c, action='milestone.completed', data__milestone=m.pk)
        self.assertEqual(job.status, 'pending')
        self.assertFalse(Handoff.objects.exists())
        cov = coverage(a, c)
        stage_policy(a, c, cov, e['signature'])
        old_billing = prepare(a, c, cov, kind='signed_sow')
        billing.ensure_current(old_billing)

        source = add_evidence(a, c.pk, 'change_request', 'Synthetic explicit cost-changing request', 'synthetic:f34')
        cv = log_change(a, c.pk, 'CR-001', 'Normal', 'Delivery', 'New work', 'Client request', source.pk, rev(c))
        for team in CONTRIBUTORS:
            assess_change(a, c.pk, cv.pk, team, True, True, True, source.pk, 'Explicit impact', rev(c), **impact_fixture(team, True))
        for role in ['Product', 'Engineering', 'Client', 'Engineering Lead', 'Security Manager']:
            decide_change(a, c.pk, cv.pk, role, 'approve', source.pk, 'Exact change decision', rev(c))
        e2 = dict(e)
        for kind in ['plan', 'costing', 'sow', 'signature']:
            e2[kind] = add_evidence(a, c.pk, kind, 'V2 revised '+kind, 'synthetic:f34:v2')
        v2 = proposal(a, c, e2, source)
        self.assertEqual(v2.decisions.count(), 0)
        with self.assertRaises(ValidationError): valid_approvals(v2)
        approvals(a, c, v2)
        self.assertTrue(set(v1.decisions.values_list('pk', flat=True)).isdisjoint(v2.decisions.values_list('pk', flat=True)))
        response2 = self.adopt(a, c, e2, t, v2)
        with self.assertRaises(ValidationError): adopt_signed(a, c.pk, v2.pk, response2.pk, rev(c))
        authorize_change(a, c.pk, cv.pk, v2.pk, rev(c))
        second = adopt_signed(a, c.pk, v2.pk, response2.pk, rev(c))
        self.assertEqual(second.before, first.after)
        self.assertEqual(Baseline.objects.get(case=c).signed_id, e2['signature'].pk)
        with self.assertRaisesMessage(ValidationError, 'stale'): billing.ensure_current(old_billing)

        # Historical association is recoverable from ordered native audit and immutable adoptions.
        prior = Audit.objects.filter(case=c, action='commercial.baseline_adopted', pk__lt=completion_audit.pk).latest('pk')
        subsequent = Audit.objects.get(case=c, action='commercial.baseline_adopted', data__adoption=second.pk)
        self.assertEqual(prior.data['adoption'], first.pk)
        self.assertEqual(prior.data['after'], first.after)
        self.assertGreater(subsequent.pk, completion_audit.pk)
        self.assertTrue(run_once(TimeoutAfterAccept(), case_id=c.pk))
        job.refresh_from_db(); self.assertEqual(job.status, 'unknown')
        h = Handoff.objects.get(milestone=m)
        self.assertEqual(h.payload, original_payload)
        # Existing accepted receipt remains recoverable after sender authority is removed.
        Grant.objects.filter(case=c, user=a, action='milestone.complete').update(active=False)
        with patch.object(InternalFinanceAdapter, 'deliver', side_effect=AssertionError('must lookup, never resend')):
            self.assertTrue(run_once(InternalFinanceAdapter(), case_id=c.pk))
        job.refresh_from_db(); self.assertEqual(job.status, 'confirmed'); self.assertEqual(job.receipt, str(h.pk))
        self.assertFalse(run_once(case_id=c.pk))
        self.assertEqual(InternalSignedBaselineAdapter().deliver(first).pk, intake1.pk)
        intake1.refresh_from_db(); self.assertEqual(intake1.payload, original_intake)
        self.assertEqual(SignedBaselineIntake.objects.count(), 2)
        self.assertEqual(BaselineAdoption.objects.count(), 2)
        self.assertEqual(Milestone.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertEqual(Handoff.objects.count(), 1)
        self.assertFalse(Invoice.objects.exists()); self.assertFalse(InvoicePreparation.objects.exists())

        # Old notification is not itself permission to bill. Missing current predicate holds.
        held = prepare(a, c, cov, kind='completion', h=h)
        self.assertEqual(held.result['status'], 'held'); self.assertIsNone(held.result['total'])
        stage_policy(a, c, cov, e2['signature'])
        policy(a, c, 'D12.stage_terms', [{'coverage_id':cov.pk, 'stage':'completion', 'amount':'50.00', 'due_date':'2026-11-10'}])
        policy(a, c, 'D12.completion_billing_predicate_ref', {'coverage_id':cov.pk, 'stage':'completion', 'milestone_name':'M1'})
        current = prepare(a, c, cov, kind='completion', h=h)
        self.assertEqual(current.result['status'], 'prepared'); self.assertEqual(current.result['total'], '50.00')
        self.assertEqual(current.snapshot['signed_baseline'], e2['signature'].pk)
        self.assertEqual(current.snapshot['handoff_payload_hash'], billing.digest(original_payload))
        billing.ensure_current(current)
        self.assertEqual(prepare(a, c, cov, kind='completion', h=h).pk, current.pk)
        self.assertFalse(any(current.result[k] for k in ['invoice_issued','ledger_posted','cash_received','release_authorized']))
        self.assertFalse(Invoice.objects.exists()); self.assertFalse(InvoicePreparation.objects.exists())
