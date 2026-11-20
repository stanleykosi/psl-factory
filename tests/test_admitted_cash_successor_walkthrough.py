"""Independent cash correction review and exact Project Money readback."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Case
from apps.finance import cash
from apps.finance.models import (CashAllocation, CashReceipt, CashReversal, CashSuccessor, CashSuccessorAcceptance,
                                 CashVerification, FinancialCorrectionReview, InvoiceDelivery, InvoiceIssue, InvoiceJob)
from apps.identity import staff
from apps.identity.models import Grant
from tests import railway_admitted_cash_successor_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'}


@patch.dict('os.environ', ENVIRONMENT)
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedCashSuccessorWalkthroughTests(TestCase):
    def test_exact_trial_review_and_separate_successor_application_reconcile_project_money(self):
        configuration = configured()
        origin = configuration['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(configuration['actor'], origin.pk, 'sample-admitted-cash-successor',
                                         'Sample cash correction executor', 'sample-cash-correction@example.invalid',
                                         ['case.read'], rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!cash.successor.369')
        actor_grants = Grant.objects.filter(user__in=[maker, reviewer])
        original_grants = set(actor_grants.values_list('case_id', 'user_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
        sample = seed.prepare(invitation.pk, maker.pk)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), sample)
        case = Case.objects.get(pk=sample['case'], synthetic=True, tenant=seed.TENANT)
        self.assertEqual(set(actor_grants.exclude(case=case).values_list('case_id', 'user_id', 'action', 'active')),
                         original_grants)
        issue = InvoiceIssue.objects.get(pk=sample['issue'], invoice__case=case)
        original_lot = CashVerification.objects.get(pk=sample['original_lot'], receipt__case=case)
        original_allocation = CashAllocation.objects.get(pk=sample['original_allocation'], lot=original_lot, issue=issue)
        request = CashSuccessor.objects.get(pk=sample['request'], case=case, parent=original_lot)
        self.assertNotIn(request.actor_id, (maker.pk, reviewer.pk))
        self.assertEqual((original_lot.amount, original_allocation.amount), (Decimal('50.00'), Decimal('20.00')))
        self.assertEqual(cash.open_amount(issue), Decimal('32.25'))
        self.assertFalse(FinancialCorrectionReview.objects.filter(successor=request).exists())
        self.assertFalse(CashSuccessorAcceptance.objects.filter(request=request).exists())

        def correct(action, **fields):
            return self.client.post(sample['corrections_path'], {'action': action, 'revision': rev(case),
                                                              'successor': request.pk, 'role': 'Finance', **fields})

        def assert_money(paid, owed, *, applied):
            page = self.client.get(sample['money_path'])
            self.assertContains(page, seed.REFERENCE)
            [line] = page.context['money']['selected']['invoices']
            self.assertEqual((line['invoice'].pk, line['invoice'].version, line['paid'], line['owed']),
                             (issue.invoice_id, issue.invoice.version, Decimal(paid), Decimal(owed)))
            label = f'Applied receipt {sample["transaction"]}'
            if applied:
                self.assertContains(page, label)
            else:
                self.assertNotContains(page, label)

        self.client.force_login(reviewer)
        assert_money('0', '32.25', applied=False)
        page = self.client.get(sample['corrections_path'])
        self.assertContains(page, f'original lot #{original_lot.pk}')
        self.assertContains(page, 'proposed amount 40 NGN')
        self.assertEqual(Decimal(request.payload['amount']), Decimal('40.00'))
        self.assertEqual(correct('apply_successor').status_code, 403)
        decision = correct('review', kind='cash', verdict='approve', evidence=sample['review_proof'],
                           reason=seed.REVIEW_REASON)
        self.assertRedirects(decision, sample['corrections_path'], fetch_redirect_response=False)
        approved = FinancialCorrectionReview.objects.get(successor=request)
        self.assertEqual((approved.actor_id, approved.snapshot['reversal']), (reviewer.pk, sample['original_reversal']))
        self.assertFalse(CashSuccessorAcceptance.objects.filter(request=request).exists())

        self.client.force_login(maker)
        self.assertEqual(correct('review', kind='cash', verdict='return', evidence=sample['review_proof'],
                                 reason='Wrong person for this decision.').status_code, 403)
        applied = correct('apply_successor')
        self.assertRedirects(applied, sample['corrections_path'], fetch_redirect_response=False)
        acceptance = CashSuccessorAcceptance.objects.get(request=request, review=approved, parent=original_lot)
        lot = acceptance.lot
        self.assertEqual((acceptance.actor_id, lot.amount, lot.receipt_id),
                         (maker.pk, Decimal('40.00'), original_lot.receipt_id))
        self.assertEqual(cash.cash_remaining(lot), Decimal('40.00'))
        assert_money('0', '32.25', applied=False)
        tracked = self.client.post(sample['settlement_path'], {'action': 'allocate', 'revision': rev(case),
            'lot': lot.pk, 'issue': issue.pk, 'amount': seed.ALLOCATION_AMOUNT, 'operation_key': seed.ALLOCATION_KEY,
            'role': 'Finance', 'evidence': sample['allocation_proof']})
        self.assertRedirects(tracked, sample['settlement_path'], fetch_redirect_response=False)
        self.assertEqual(cash.cash_remaining(lot), Decimal('15.00'))
        assert_money('25.00', '7.25', applied=True)

        history = self.client.get(sample['settlement_path'])
        self.assertContains(history, f'Full reversal #{sample["original_reversal"]}')
        self.assertContains(history, f'Allocation #{original_allocation.pk}')
        self.assertContains(history, f'Verified lot #{original_lot.pk}')
        self.assertContains(history, f'Verified lot #{lot.pk}')
        self.assertEqual(CashReceipt.objects.filter(case=case).count(), 1)
        self.assertEqual(CashVerification.objects.filter(receipt=original_lot.receipt).count(), 2)
        self.assertEqual(CashReversal.objects.filter(allocation=original_allocation).count(), 1)
        self.assertEqual(InvoiceIssue.objects.filter(invoice__case=case).count(), 1)
        self.assertFalse(InvoiceDelivery.objects.filter(invoice__case=case).exists())
        self.assertEqual(list(InvoiceJob.objects.filter(invoice__case=case).values_list('kind', 'status')),
                         [('issue', 'confirmed')])
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), sample)
