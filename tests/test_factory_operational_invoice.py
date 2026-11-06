"""Operational-shaped fixture: native investigation/preparation, no external activation."""
from django.test import TestCase
from apps.agents.models import AgentRun
from apps.finance.models import InvoiceJob, InvoiceReview
from apps.workflows import factory
from apps.workflows.models import HumanTask
from apps.identity.models import Grant
from tests.factory_helpers import fixture
from tests.test_factory_coordinator_recovery import configure


class OperationalInvoiceTests(TestCase):
    def test_governed_synthetic_case_exercises_the_same_native_investigator(self):
        f=fixture(username='governed-native-invoice-worker',provider='governed_factory_v1')
        configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        self.assertTrue(factory.run_once(f['work'].pk))
        self.assertTrue(AgentRun.objects.filter(case=f['case'],provider='deterministic-billing-investigation-v1').exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=f['case']).exists())

    def test_native_investigation_permission_cannot_fall_back_to_generic_extraction(self):
        f=fixture(username='denied-native-invoice-worker',provider='governed_factory_v1')
        configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        Grant.objects.filter(case=f['case'],user=f['actor'],action='agent.billing').update(active=False)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'blocked')
        self.assertIsNone(f['work'].invoice_id)
        self.assertFalse(AgentRun.objects.filter(case=f['case']).exclude(provider='internal_permitted_step_v1').exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=f['case']).exists())

    def test_internal_coordination_uses_native_billing_investigation_then_waits_for_finance(self):
        f=fixture(username='operational-shaped-invoice-worker',synthetic=False,provider='governed_factory_v1')
        configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        factory.run_until_wait(f['work'].pk)
        work=f['work'];work.refresh_from_db()
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertIsNotNone(work.invoice_id)
        self.assertEqual(work.invoice.payload['amount'],'42.00')
        self.assertTrue(HumanTask.objects.filter(case=f['case'],kind='factory_review',status='open').exists())
        investigation=AgentRun.objects.get(case=f['case'],provider='deterministic-billing-investigation-v1')
        self.assertEqual(investigation.actor_id,f['actor'].pk)
        self.assertEqual(investigation.result['coverage'],f['coverage'].pk)
        self.assertTrue(investigation.result['citations'])
        self.assertFalse(investigation.result['approval_granted']);self.assertFalse(investigation.result['invoice_issued'])
        self.assertFalse(InvoiceReview.objects.filter(invoice__case=f['case']).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=f['case']).exists())
        self.assertEqual(set(AgentRun.objects.filter(case=f['case']).values_list('provider',flat=True)),
                         {'internal_permitted_step_v1','deterministic-billing-investigation-v1'})
