import tempfile
from django.test import TestCase,TransactionTestCase
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
from django.utils import timezone
from datetime import timedelta
from apps.workflows import factory
from apps.workflows.models import FactoryWork,FactoryActivity,FactoryAttempt,HumanTask
from apps.finance.models import Invoice,InvoiceJob,InvoiceIssue,InvoiceDelivery
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.factory_helpers import fixture,approve
from tests.billing_helpers import evidence

class FactoryControlTests(TestCase):
    def test_returned_packet_reworks_changed_terms_without_rewriting_history(self):
        from apps.finance.models import InvoiceReview
        from tests.billing_helpers import policy
        from django.utils import timezone
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db();original=w.invoice
        t=HumanTask.objects.get(kind='factory_review');t=factory.claim_task(f['actor'],t.pk,t.revision)
        factory.decide(f['actor'],t.pk,t.revision,'return',f['proof'].pk,'Synthetic amount requires source correction')
        policy(f['actor'],f['case'],'D12.stage_terms',[{'coverage_id':f['coverage'].pk,'stage':'completion','amount':'43.00','due_date':(timezone.localdate()+timedelta(days=7)).isoformat()}])
        w.refresh_from_db();used=w.budget_used;factory.manage(f['actor'],w.pk,w.revision,'resume');factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertNotEqual(w.invoice_id,original.pk);self.assertEqual(w.invoice.version,2)
        self.assertEqual(w.invoice.payload['amount'],'43.00');original.refresh_from_db();self.assertEqual(original.payload['amount'],'42.00')
        self.assertEqual(InvoiceReview.objects.get().verdict,'return');self.assertGreater(w.budget_used,used)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_new_form_key_cannot_create_another_business_budget(self):
        f=fixture();w=f['work'];factory.run_once(w.pk);w.refresh_from_db()
        used=w.budget_used;f['case'].refresh_from_db()
        duplicate=factory.start(f['actor'],f['case'].pk,'ANOTHER-FORM',f['coverage'].pk,f['handoff'].pk,'FACTORY-INVOICE',f['case'].revision)
        self.assertEqual(duplicate.pk,w.pk);self.assertEqual(duplicate.budget_used,used)
        with self.assertRaises(ValidationError):
            factory.start(f['actor'],f['case'].pk,'THIRD-FORM',f['coverage'].pk,f['handoff'].pk,'CHANGED-REFERENCE',f['case'].revision)
        self.assertEqual(FactoryWork.objects.count(),1)

    def test_existing_finance_screen_review_is_observed_as_the_same_decision(self):
        from apps.finance import invoices
        from apps.finance.models import InvoiceReview
        from apps.workflows.models import TaskEvent
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db();f['case'].refresh_from_db()
        review=invoices.review(f['actor'],f['case'].pk,w.invoice_id,'Finance','approve',f['proof'].pk,'Synthetic native Finance review',f['case'].revision)
        factory.run_once(w.pk)
        task=HumanTask.objects.get(kind='factory_review');self.assertEqual(task.status,'completed')
        self.assertEqual(InvoiceReview.objects.count(),1)
        self.assertEqual(TaskEvent.objects.get(task=task,action='factory.native_review_observed').data['native_review'],review.pk)

    def test_reconciliation_activity_does_not_write_a_financial_draft(self):
        f=fixture();w=f['work'];factory.run_once(w.pk) # source investigation
        class Reconcile:
            def choose(self,c):return {'activity':'ACT06','citations':c['evidence_ids']}
        factory.run_once(w.pk,Reconcile());w.refresh_from_db()
        self.assertIsNone(w.preparation_id);self.assertFalse(Invoice.objects.exists())
        self.assertTrue(FactoryActivity.objects.filter(work=w,kind='ACT06',status='succeeded').exists())
        factory.run_once(w.pk);w.refresh_from_db();self.assertIsNotNone(w.invoice_id)

    def test_aggregate_budget_stops_another_call_including_retry(self):
        f=fixture(max_tokens=100);w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.budget_used,100);self.assertEqual(w.status,'blocked');self.assertIn('BUDGET_EXHAUSTED',w.finding)
        factory.manage(f['actor'],w.pk,w.revision,'resume');factory.run_once(w.pk);w.refresh_from_db()
        self.assertEqual(w.budget_used,100);self.assertEqual(Invoice.objects.count(),0)

    def test_unsupported_citation_cannot_become_a_native_result(self):
        f=fixture()
        class Bad:
            def choose(self,c):return {'activity':c['eligible'][0],'citations':[999999999]}
        factory.run_once(f['work'].pk,Bad());w=FactoryWork.objects.get(pk=f['work'].pk)
        self.assertEqual(w.status,'blocked');self.assertIn('Unsupported citation',w.finding)
        self.assertEqual(Invoice.objects.count(),0)

    def test_missing_resolver_does_not_create_fictional_owner(self):
        f=fixture(missing=True,information_resolver_id=None);factory.run_until_wait(f['work'].pk)
        w=FactoryWork.objects.get(pk=f['work'].pk);self.assertEqual(w.status,'owner_needed');self.assertFalse(HumanTask.objects.exists())
        self.assertTrue(FactoryActivity.objects.filter(work=w,kind='ACT04',status='succeeded').exists())

    def test_source_successor_invalidates_exact_review_without_editing_old_task(self):
        f=fixture(missing=True);w=f['work'];evidence(f['actor'],f['case'],'factory_information','Synthetic initial supporting information')
        factory.run_until_wait(w.pk);approve(f);w.refresh_from_db()
        old=HumanTask.objects.get(kind='factory_review');packet=old.context['packet']
        evidence(f['actor'],f['case'],'factory_information','Synthetic source correction requiring new review')
        factory.run_until_wait(w.pk);old.refresh_from_db();self.assertEqual(old.context['packet'],packet)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review').count(),2);self.assertFalse(InvoiceIssue.objects.exists())

    def test_changed_completion_cannot_silently_replace_pmo_acceptance(self):
        f=fixture();evidence(f['actor'],f['case'],'completion','Conflicting new completion source awaiting PMO correction')
        factory.run_until_wait(f['work'].pk);w=FactoryWork.objects.get(pk=f['work'].pk)
        self.assertEqual(w.status,'blocked');self.assertIn('COMPLETION_SOURCE_CONFLICT',w.finding)
        self.assertFalse(Invoice.objects.exists())

    def test_plan_and_child_are_reserved_together(self):
        f=fixture(max_children=1);factory.run_once(f['work'].pk);w=FactoryWork.objects.get(pk=f['work'].pk)
        self.assertEqual(w.status,'blocked');self.assertEqual(w.budget_used,0);self.assertFalse(w.activities.exists())

    def test_cancellation_while_model_is_running_closes_without_a_financial_effect(self):
        f=fixture();w=f['work']
        class Cancel:
            def choose(self,c):
                current=FactoryWork.objects.get(pk=w.pk);factory.manage(f['actor'],w.pk,current.revision,'cancel')
                return {'activity':c['eligible'][0],'citations':c['evidence_ids']}
        factory.run_once(w.pk,Cancel());w.refresh_from_db()
        self.assertEqual(w.status,'cancelled');self.assertFalse(Invoice.objects.exists())
        from apps.workflows.factory_views import presentation
        row=presentation(f['actor'],w);self.assertEqual(row['state'],'Cancelled')
        self.assertEqual(row['owner'],'No action required');self.assertEqual(row['blocker'],'')
        self.assertEqual(row['next_action'],'Inspect the stopped work and its retained history')
        self.assertFalse(row['can_advance']);self.assertFalse(row['can_reconcile']);self.assertFalse(row['needs_me'])

    def test_stop_after_exact_invoice_delivery_keeps_finance_followup_distinct_from_verification(self):
        from apps.workflows.factory_views import presentation
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory)
            for _ in range(30):
                factory.run_once(w.pk,adapter=adapter)
                if InvoiceDelivery.objects.filter(invoice_id=w.invoice_id).exists():break
                w.refresh_from_db()
            w.refresh_from_db();self.assertEqual(InvoiceDelivery.objects.filter(invoice_id=w.invoice_id).count(),1)
            self.assertNotEqual(w.status,'verified');factory.manage(f['actor'],w.pk,w.revision,'cancel')
            factory.run_until_wait(w.pk,adapter=adapter);w.refresh_from_db();self.assertEqual(w.status,'followup_needed')
            row=presentation(f['actor'],w);self.assertEqual(row['state'],'Stopped; invoice follow-up needed')
            self.assertIn('Finance correction workflow',row['next_action']);self.assertFalse(row['can_advance'])
            self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)

    def test_positive_remote_proof_is_recorded_after_cancellation_without_new_delivery(self):
        from django.test import override_settings
        from apps.identity.models import Grant
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True,delayed_reads=1)
            factory.run_until_wait(w.pk,adapter=adapter);w.refresh_from_db();self.assertEqual(w.status,'waiting_effect')
            Grant.objects.filter(user=f['actor'],case=f['case'],action='finance.invoice.issue').update(active=False)
            factory.manage(f['actor'],w.pk,w.revision,'cancel');w.refresh_from_db()
            with override_settings(FACTORY_ADAPTERS={str(f['case'].pk):adapter}):factory.reconcile(f['actor'],w.pk,w.revision)
            w.refresh_from_db();self.assertEqual(w.status,'followup_needed',w.finding)
            self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceJob.objects.count(),1)
            from pathlib import Path
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            factory.run_until_wait(w.pk,adapter=adapter);self.assertFalse(InvoiceDelivery.objects.exists())

    def test_eventual_absence_parks_without_model_poll_or_duplicate_publication(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True,delayed_reads=2)
            factory.run_until_wait(w.pk,adapter=adapter);w.refresh_from_db();self.assertEqual(w.status,'waiting_effect',w.finding)
            self.assertEqual(InvoiceJob.objects.get(kind='issue').status,'unknown');used=w.budget_used
            factory.run_until_wait(w.pk,adapter=adapter);w.refresh_from_db();self.assertEqual(w.budget_used,used)
            self.assertFalse(InvoiceIssue.objects.exists())

    def test_cancel_before_dispatch_never_means_undo_of_an_accepted_effect(self):
        f=fixture();w=f['work'];factory.manage(f['actor'],w.pk,w.revision,'cancel');factory.run_once(w.pk)
        w.refresh_from_db();self.assertEqual(w.status,'cancelled');self.assertEqual(Invoice.objects.count(),0)

    def test_stale_lease_cannot_finalize_another_attempt(self):
        f=fixture();w=f['work'];token=factory.claim(w.pk)
        FactoryWork.objects.filter(pk=w.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        new=factory.claim(w.pk);self.assertGreater(new,token)
        with self.assertRaises(ValidationError):factory.record_failure(w.pk,token,ValidationError('stale'))

class FactoryConcurrencyTests(TransactionTestCase):
    def test_two_workers_share_one_current_claim(self):
        f=fixture();pk=f['work'].pk
        def compete(_):
            close_old_connections()
            try:return factory.claim(pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
