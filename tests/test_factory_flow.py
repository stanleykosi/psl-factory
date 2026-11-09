from django.test import TransactionTestCase
import tempfile
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.workflows import factory
from apps.workflows.models import FactoryWork,FactoryActivity,FactoryAttempt,HumanTask
from apps.finance.models import Invoice,InvoiceJob,InvoiceIssue,InvoiceDelivery
from apps.policy.services import transition
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.factory_helpers import fixture,approve
from tests.billing_helpers import evidence

class FactoryFlowTests(TransactionTestCase):
    def test_agent_missing_input_resume_exact_approval_mock_receipt_and_verification(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        self.assertEqual(connection.vendor,'postgresql');f=fixture(missing=True);w=f['work']
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'waiting');self.assertEqual(Invoice.objects.count(),0)
        info=HumanTask.objects.get(kind='factory_information');self.assertEqual(info.context['missing'],['factory_information'])
        used=w.budget_used;factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.budget_used,used)
        evidence(f['actor'],f['case'],'factory_information','Synthetic missing acceptance reference now supplied')
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertIsNotNone(w.invoice_id,w.finding)
        info.refresh_from_db();self.assertEqual(info.status,'completed');self.assertEqual(InvoiceIssue.objects.count(),0)
        approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter) # reserve
            factory.run_once(w.pk,adapter=adapter) # remote acceptance; response lost
            self.assertEqual(InvoiceIssue.objects.count(),0)
            self.assertEqual(InvoiceJob.objects.get(kind='issue').status,'unknown')
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
            w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
            from pathlib import Path
            self.assertEqual(len(list(Path(directory).glob('*.json'))),2)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
        self.assertGreater(FactoryAttempt.objects.filter(phase='observed').count(),3)
        self.assertTrue(FactoryActivity.objects.filter(kind='ACT05').exists())
        self.assertTrue(FactoryActivity.objects.filter(kind='ACT12').exists())
        factory.run_until_wait(w.pk);self.assertEqual(Invoice.objects.count(),1)

    def test_same_key_changed_payload_and_cross_case_scope_fail(self):
        f=fixture();w=f['work'];a=f['actor'];c=f['case'];c.refresh_from_db()
        self.assertEqual(factory.start(a,c.pk,w.key,f['coverage'].pk,f['handoff'].pk,'FACTORY-INVOICE',c.revision).pk,w.pk)
        with self.assertRaises(ValidationError):factory.start(a,c.pk,w.key,f['coverage'].pk,f['handoff'].pk,'CHANGED',c.revision)
        Grant.objects.filter(user=a,case=c,action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):factory.access(a,c)

    def test_model_cannot_choose_dispatch_or_fabricate_citations(self):
        f=fixture();w=f['work']
        class Bad:
            def choose(self,context):return {'activity':'ACT11','citations':context['evidence_ids'][:1]}
        factory.run_once(w.pk,Bad());w.refresh_from_db();self.assertEqual(w.status,'blocked')
        self.assertEqual(Invoice.objects.count(),0);self.assertTrue(FactoryAttempt.objects.filter(phase='failed').exists())

    def test_shared_budget_missing_policy_and_revocation_do_not_reset_allowance(self):
        f=fixture(configure=False);w=f['work'];factory.run_once(w.pk);w.refresh_from_db();self.assertEqual(w.status,'configuration_needed')
        self.assertEqual(w.budget_used,0)

    def test_exact_native_packet_changes_require_fresh_human_review(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f);w.refresh_from_db()
        review=w.invoice.invoicereview_set.latest('pk');self.assertTrue(review.publication_packet)
        from tests.billing_helpers import policy
        from apps.policy.services import active_component,reference_values
        v=reference_values(active_component('D08.adapter_contract_ref',f['case']))[0]
        policy(f['actor'],f['case'],'D08.adapter_contract_ref',dict(v,require_due_date=not v['require_due_date']))
        with self.assertRaises(ValidationError):
            from apps.finance.invoices import reviewed
            reviewed(w.invoice)
        self.assertEqual(InvoiceIssue.objects.count(),0)

    def test_database_protects_identity_history_budget_and_false_verification(self):
        f=fixture();w=f['work']
        for sql,params in [
            ('UPDATE workflows_factorywork SET request_hash=%s WHERE id=%s',['f'*64,w.pk]),
            ('UPDATE workflows_factorywork SET budget_used=1 WHERE id=%s',[w.pk]),
            ("UPDATE workflows_factorywork SET status='verified' WHERE id=%s",[w.pk])]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cur:cur.execute(sql,params)
