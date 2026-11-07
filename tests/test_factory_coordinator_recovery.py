from django.test import TransactionTestCase
"""Existing business receipt recovery must not depend on a planning provider/mode."""
from django.test import TestCase,override_settings
from django.utils import timezone
from django.urls import reverse
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory

def configure(a,c,e):
    p=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',{'mode':'internal_permitted_step_v1','contract_id':None,
        'planner_id':a.pk,'data_scope':'eligible_actions_and_opaque_citations_v1','max_output_chars':512},e.pk,timezone.now())
    transition(a,p.pk,'validated');transition(a,p.pk,'active');return p

class BusinessReceiptRecoveryTests(TransactionTestCase):
    def test_original_invoice_receipt_recovers_after_coordinator_policy_withdrawal(self):
        import tempfile
        from pathlib import Path
        from tests.factory_helpers import fixture,approve
        from tests.obligation_helpers import factory_approve_identified as approve
        from adapters.factory_invoices import MockFactoryInvoiceAdapter
        from apps.finance.models import InvoiceJob,InvoiceIssue,InvoiceDelivery
        f=fixture(provider='governed_factory_v1');w=f['work'];p=configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:
            lost=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=lost);factory.run_once(w.pk,adapter=lost)
            job=InvoiceJob.objects.get(kind='issue');self.assertEqual(job.status,'unknown');w.refresh_from_db();spent=w.budget_used
            transition(f['actor'],p.pk,'revoked')
            self.client.force_login(f['actor']);page=self.client.get(reverse('factory_detail',args=[w.pk]));self.assertEqual(page.status_code,200)
            self.assertTrue(page.context['row']['can_reconcile'])
            with override_settings(FACTORY_ADAPTERS={str(f['case'].pk):MockFactoryInvoiceAdapter(directory)}):factory.reconcile(f['actor'],w.pk,w.revision)
            job.refresh_from_db();w.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(w.budget_used,spent)
            self.assertEqual(InvoiceIssue.objects.count(),1);self.assertFalse(InvoiceDelivery.objects.exists());self.assertEqual(len(list(Path(directory).glob('*.json'))),1)

    def test_original_department_request_receipt_recovers_without_model_invocation(self):
        from tests.test_factory_planning import setup
        from apps.policy.services import reference_values
        from adapters.approvals import InternalApprovalRoutingAdapter
        from apps.pmo.models import ApprovalRouteJob,ApprovalRouteReceipt
        from apps.workflows import factory_planning
        f=setup();a,c,w=f['a'],f['c'],f['work'];p=configure(a,c,f['e']['policy_decision'])
        value=dict(reference_values(f['profile'])[0],provider='governed_factory_v1')
        profile=draft_operator_policy(a,c.pk,'OPS.factory_planning_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(a,profile.pk,'validated');transition(a,profile.pk,'active')
        class Lost(InternalApprovalRoutingAdapter):
            def deliver(self,pk,fence):super().deliver(pk,fence);raise TimeoutError('Synthetic lost response')
        factory.run_once(w.pk);factory.run_once(w.pk);factory.run_once(w.pk,adapter=Lost())
        job=ApprovalRouteJob.objects.get(status='unknown');self.assertEqual(ApprovalRouteReceipt.objects.filter(job=job).count(),1)
        w.refresh_from_db();spent=w.budget_used;transition(a,p.pk,'revoked')
        factory_planning.reconcile(a,w.pk,w.revision);job.refresh_from_db();w.refresh_from_db()
        self.assertEqual(job.status,'confirmed');self.assertEqual(w.budget_used,spent)
        self.assertEqual(ApprovalRouteReceipt.objects.filter(job=job).count(),1)
