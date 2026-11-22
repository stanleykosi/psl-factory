from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import public_timeline
from apps.core.services import add_evidence
from apps.documents.contracts import digest
from apps.finance import cash, short_payments
from apps.finance.models import InvoiceShortPaymentDecision, PaymentReleaseReservation, PaymentReminderDispatch
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.short_payment_validators import COMPONENT
from tests import settlement_helpers as settlement
from tests.helpers import rev
from tests.obligation_helpers import issue_identified


class InvoiceShortPaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, coverage, prep, cls.proofs = settlement.fixture()
        cls.issue = issue_identified(cls.actor, cls.case, settlement.draft(cls.actor, cls.case, prep), cls.proofs)
        receipt, lot = settlement.receipt(cls.actor, cls.case, amount='2.00', ref='sample-short-payment')
        settlement.assign(cls.actor, cls.case, receipt, coverage, cls.proofs)
        cls.allocation = settlement.allocate(cls.actor, cls.case, lot, cls.issue, '2.00', cls.proofs)
        cls.policy_proof = add_evidence(cls.actor, cls.case.pk, 'policy_decision',
                                        'Synthetic short-payment decision rule', 'synthetic:short-payment')
        cls.path = reverse('invoice_short_payment', args=[cls.case.pk, cls.issue.pk])

    def activate(self, value):
        config = draft_operator_policy(self.actor, self.case.pk, COMPONENT, value, self.policy_proof.pk,
                                      timezone.now() - timedelta(seconds=1))
        transition(self.actor, config.pk, 'validated')
        transition(self.actor, config.pk, 'active')
        return config

    def post_data(self):
        return {'revision': rev(self.case), 'position': digest(short_payments.position(self.issue)),
                'allocation': self.allocation.pk, 'treatment': 'record_exception',
                'reason': 'The synthetic remittance is incomplete. Hold the outstanding balance.'}

    def test_missing_rule_leaves_exact_amounts_and_scoped_history_readable(self):
        self.client.force_login(self.actor)
        page = self.client.get(self.path)
        self.assertContains(page, 'Short-payment rule needed')
        self.assertContains(page, 'sample-short-payment')
        self.assertContains(page, 'Still owed')
        self.assertNotContains(page, 'Record decision')
        self.assertEqual(self.client.post(self.path, self.post_data()).status_code, 403)
        draft_post = {'action': 'draft_rule', 'revision': rev(self.case), 'reviewer': self.actor.pk,
                      'evidence': self.policy_proof.pk, 'treatments': ['request_proof']}
        self.assertContains(self.client.post(self.path, draft_post, follow=True), 'Draft rule saved for review')
        self.assertContains(self.client.get(self.path), 'Short-payment rule needed')
        reader = get_user_model().objects.create_user('sample-unauthorized-short-payment')
        Grant.objects.create(user=reader, case=self.case, action='case.read')
        Grant.objects.create(user=reader, case=self.case, action='finance.read')
        self.client.force_login(reader)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertFalse(InvoiceShortPaymentDecision.objects.exists())
        with self.assertRaises(ValidationError):
            self.activate({'reviewer_id': None, 'treatments': ['record_exception']})

    def test_review_neither_changes_debt_nor_dispatches_and_stale_facts_are_refused(self):
        config = self.activate({'reviewer_id': self.actor.pk, 'treatments': ['record_exception']})
        open_amount = cash.open_amount(self.issue)
        post = self.post_data()
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(self.path), 'Approve an exception')
        no_extra_choice = self.client.post(self.path, {**post, 'treatment': 'reject_exception'})
        self.assertEqual(no_extra_choice.status_code, 200)
        self.assertFalse(InvoiceShortPaymentDecision.objects.exists())
        self.assertContains(self.client.post(self.path, post, follow=True), 'Finance decision recorded')
        result = self.issue.short_payment_decisions.get()
        self.assertEqual(result.authority[COMPONENT], config.pk)
        self.assertEqual(result.position_sha256, post['position'])
        self.assertEqual(cash.open_amount(self.issue), open_amount)
        self.assertFalse(PaymentReleaseReservation.objects.exists())
        self.assertFalse(PaymentReminderDispatch.objects.exists())
        self.assertFalse(public_timeline(self.case).filter(action='finance.short_payment.decided').exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.issue.short_payment_decisions.update(reason='rewrite the original')
        with self.assertRaises(PermissionDenied):
            short_payments.decide(self.actor, self.case.pk, self.issue.pk, rev(self.case), post['position'],
                                  post['allocation'], 'reject_exception', 'Unconfigured treatment')
        cash.reverse(self.actor, self.case.pk, 'allocation', self.allocation.pk, 'Finance',
                     self.proofs['cash_correction'].pk, 'Sample checked full reversal', rev(self.case))
        with self.assertRaisesMessage(ValidationError, 'Review the current invoice balance'):
            short_payments.decide(self.actor, self.case.pk, self.issue.pk, rev(self.case), post['position'],
                                  post['allocation'], post['treatment'], post['reason'])
        self.assertContains(self.client.get(self.path), 'Earlier balance')
        self.assertEqual(self.issue.short_payment_decisions.count(), 1)

    def test_guarded_browser_preparations_keep_both_policies_distinct_and_are_idempotent(self):
        from tests.railway_batch_walkthrough_seed import prepare_short_payment

        self.client.force_login(self.actor)
        for mode, label in [('unconfigured', 'Short-payment rule needed'),
                            ('configured', 'Keep the balance owed and request proof')]:
            key = f'short_payment_{mode}'
            sample = prepare_short_payment(self.actor, key)
            replay = prepare_short_payment(self.actor, key)
            self.assertEqual(sample['issue'], replay['issue'])
            self.assertTrue(replay['existing_work_preserved'])
            self.assertContains(self.client.get(sample['path']), label)
        self.assertFalse(InvoiceShortPaymentDecision.objects.exists())
        self.assertFalse(PaymentReminderDispatch.objects.exists())

    def test_api_rule_draft_and_exact_review_leave_the_receivable_unchanged(self):
        url = f'/api/v1/projects/{self.case.pk}/invoices/{self.issue.pk}/short-payment'
        self.client.force_login(self.actor)
        original = self.client.get(url).json()
        self.assertEqual(original['treatments'], [])
        self.assertEqual(original['allocations'][0]['id'], self.allocation.pk)
        draft = self.client.post(url, {'action': 'draft_rule', 'revision': original['revision'],
            'rule': {'reviewer_id': self.actor.pk, 'treatments': ['record_exception']},
            'evidence_id': self.policy_proof.pk}, content_type='application/json')
        self.assertEqual(draft.status_code, 201, draft.content)
        self.assertEqual(self.client.get(url).json()['treatments'], [])
        transition(self.actor, draft.json()['id'], 'validated')
        transition(self.actor, draft.json()['id'], 'active')
        current = self.client.get(url).json()
        command = {'action': 'decide', 'revision': current['revision'], 'position': current['position'],
                   'allocation_id': self.allocation.pk, 'treatment': 'record_exception', 'reason': 'Review unpaid balance'}
        decision = self.client.post(url, command, content_type='application/json')
        self.assertEqual(decision.status_code, 201, decision.content)
        saved = self.client.get(url).json()
        self.assertEqual(saved['balance'], original['balance'])
        self.assertEqual(saved['history'][0]['id'], decision.json()['id'])
        self.assertTrue(saved['history'][0]['current_position'])
        self.assertFalse(PaymentReleaseReservation.objects.exists())
        self.assertFalse(PaymentReminderDispatch.objects.exists())
        cash.reverse(self.actor, self.case.pk, 'allocation', self.allocation.pk, 'Finance',
                     self.proofs['cash_correction'].pk, 'Synthetic reversal', rev(self.case))
        stale = self.client.post(url, {**command, 'revision': rev(self.case)}, content_type='application/json')
        self.assertEqual(stale.status_code, 422, stale.content)
        self.assertFalse(self.client.get(url).json()['history'][0]['current_position'])
        self.assertEqual(InvoiceShortPaymentDecision.objects.count(), 1)
