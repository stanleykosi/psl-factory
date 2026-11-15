"""One synthetic obligation across PMO, Finance, and recovery."""
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TransactionTestCase
from django.utils import timezone

from adapters.factory_invoices import MockFactoryInvoiceAdapter
from adapters.finance import InternalFinanceAdapter, TimeoutAfterAccept
from apps.finance import receivables
from apps.finance.models import Handoff, InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.models import Grant
from apps.pmo.services import complete_milestone
from apps.workflows import factory
from apps.workflows.models import HumanTask, Outbox
from apps.workflows.services import run_once
from tests.billing_helpers import coverage, evidence, policy, stage_policy
from tests.helpers import rev, setup_case, signed
from tests.obligation_helpers import factory_approve_identified
from tests.settlement_helpers import allocate, assign, configured, receipt
from tests.test_factory_invoice_intake import configuration


class LookupFirstInvoiceAdapter(MockFactoryInvoiceAdapter):
    def deliver(self, pk, fence):
        if InvoiceJob.objects.filter(pk=pk, kind='issue').exists():
            raise AssertionError('An accepted issuance must be recovered by lookup')
        return super().deliver(pk, fence)


class PMOFinanceAcceptanceTests(TransactionTestCase):
    def test_pmo_completion_to_recovered_invoice_and_partial_cash(self):
        finance, case = setup_case(username='synthetic-finance-operator')
        proof = signed(finance, case)
        pmo = get_user_model().objects.create_user(username='synthetic-pmo-operator')
        for action in ('case.read', 'milestone.complete', 'factory.read'):
            Grant.objects.create(case=case, user=pmo, action=action)
        Grant.objects.filter(case=case, user=finance, action='milestone.complete').update(active=False)
        name = 'Synthetic contracted completion'
        with self.assertRaises(PermissionDenied):
            complete_milestone(finance, case.pk, name, proof['completion'].pk, rev(case))
        milestone = complete_milestone(pmo, case.pk, name, proof['completion'].pk, rev(case))
        self.assertEqual(milestone.completed_by_id, pmo.pk)
        self.assertTrue(run_once(TimeoutAfterAccept(), case_id=case.pk))
        outbox = Outbox.objects.get(milestone=milestone, status='unknown')
        handoff = Handoff.objects.get(milestone=milestone)
        self.assertTrue(run_once(InternalFinanceAdapter(), case_id=case.pk))
        outbox.refresh_from_db()
        self.assertEqual((outbox.status, outbox.receipt), ('confirmed', str(handoff.pk)))
        self.assertEqual(Handoff.objects.filter(milestone=milestone).count(), 1)
        self.assertFalse(InvoiceJob.objects.exists())

        contract = coverage(finance, case, amount_basis='gross_including_tax')
        stage_policy(finance, case, contract, proof['signature'])
        policy(finance, case, 'D12.stage_terms', [{'coverage_id': contract.pk, 'stage': 'completion',
            'amount': '42.00', 'due_date': (timezone.localdate() + timedelta(days=7)).isoformat()}])
        policy(finance, case, 'D12.completion_billing_predicate_ref', {
            'coverage_id': contract.pk, 'stage': 'completion', 'milestone_name': name})
        configured(finance, case)
        approval = configuration(finance, case)
        work = factory.start(finance, case.pk, 'ACCEPTANCE', contract.pk, handoff.pk, 'ACCEPTANCE-INV', rev(case))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting', work.finding)
        self.assertEqual(work.invoice.amount, Decimal('42.00'))
        task = HumanTask.objects.get(case=case, kind='factory_review', status='open')
        with self.assertRaises(PermissionDenied):
            factory.claim_task(pmo, task.pk, task.revision)
        self.assertFalse(InvoiceJob.objects.exists())
        review = factory_approve_identified({'actor': finance, 'case': case, 'work': work, 'proof': approval})
        self.assertEqual(review.actor_id, finance.pk)

        with tempfile.TemporaryDirectory() as directory:
            adapter = MockFactoryInvoiceAdapter(directory, lose_response=True)
            self.assertTrue(factory.run_once(work.pk, adapter=adapter))
            self.assertTrue(factory.run_once(work.pk, adapter=adapter))
            original = InvoiceJob.objects.get(kind='issue')
            self.assertEqual(original.status, 'unknown')
            self.assertFalse(InvoiceIssue.objects.exists())
            factory.run_until_wait(work.pk, adapter=LookupFirstInvoiceAdapter(directory))
            self.assertEqual(len(list(Path(directory).glob('*.json'))), 2)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        issued = InvoiceIssue.objects.get(invoice=work.invoice)
        self.assertEqual(issued.job_id, original.pk)
        self.assertEqual(InvoiceDelivery.objects.filter(invoice=work.invoice).count(), 1)

        cash_report, lot = receipt(finance, case, '20.00', 'synthetic-acceptance-cash')
        cash_proofs = {kind: evidence(finance, case, kind, 'Synthetic acceptance evidence')
                       for kind in ('cash_correction', 'cash_allocation')}
        assign(finance, case, cash_report, contract, cash_proofs)
        allocate(finance, case, lot, issued, '20.00', cash_proofs)
        snapshot = receivables.snapshot(finance, case.pk, timezone.localdate(), rev(case))
        self.assertEqual(Decimal(snapshot.result['groups'][0]['receivable']), Decimal('22.00'))
        self.assertFalse(snapshot.result['ledger_posted'])
        self.assertFalse(snapshot.result['deployment_authorized'])
