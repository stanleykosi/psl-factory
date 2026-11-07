"""Uncertain original invoice effects precede any source-driven replacement draft."""
import tempfile
import os,sys,subprocess,time,json
from pathlib import Path
from django.test import TestCase,TransactionTestCase
from django.db import connection
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy.services import active_component,reference_values,register_reference,transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.workflows import factory
from apps.finance import billing,invoices,invoice_delivery
from apps.finance.models import Invoice,InvoiceJob,InvoiceIssue,InvoiceDelivery
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.factory_helpers import fixture,approve
from tests.billing_helpers import policy
from tests.helpers import rev,activate
from adapters.invoices import InternalInvoiceAdapter

class InvoiceRecoveryPriorityTests(TestCase):
    def test_accepted_lost_response_is_reconciled_before_changed_terms_can_replace_invoice(self):
        from .obligation_helpers import factory_approve_identified
        self.assertEqual(connection.vendor,'postgresql');f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f)
        w.refresh_from_db();original=w.invoice
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            job=InvoiceJob.objects.get(invoice=original,kind='issue');self.assertEqual(job.status,'unknown')
            self.assertFalse(InvoiceIssue.objects.exists());self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            policy(f['actor'],f['case'],'D12.stage_terms',[{'coverage_id':f['coverage'].pk,'stage':'completion',
                'amount':'43.00','due_date':original.due_date.isoformat()}])
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));w.refresh_from_db();job.refresh_from_db()
            self.assertEqual(w.invoice_id,original.pk,'Original uncertain effect must be reconciled before replacing the invoice head')
            self.assertEqual(Invoice.objects.filter(case=f['case']).count(),1)
            self.assertEqual(InvoiceIssue.objects.filter(invoice=original).count(),1)
            self.assertEqual(job.status,'confirmed');self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            self.assertFalse(InvoiceDelivery.objects.exists())
            self.assertIn(w.status,['blocked','followup_needed']);self.assertIn('correction',w.finding.lower())

    def test_receipt_only_mode_refuses_pending_work_and_never_sends_on_negative_lookup(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f);factory.run_once(w.pk)
        job=InvoiceJob.objects.get(kind='issue')
        class NoReceipt(InternalInvoiceAdapter):
            def deliver(self,*args):raise AssertionError('Receipt-only lookup cannot send')
        self.assertFalse(invoice_delivery.run_once(NoReceipt(),case_id=f['case'].pk,job_id=job.pk,lookup_only=True))
        job.refresh_from_db();self.assertEqual(job.status,'pending');self.assertEqual(job.attempts,0)
        with self.assertRaises(ValidationError):invoice_delivery.run_once(NoReceipt(),job_id=job.pk,lookup_only=1)
        with tempfile.TemporaryDirectory() as directory:
            invoice_delivery.run_once(MockFactoryInvoiceAdapter(directory,uncertain_lookup=True),case_id=f['case'].pk,job_id=job.pk)
            job.refresh_from_db();self.assertEqual(job.status,'unknown')
            self.assertTrue(invoice_delivery.run_once(NoReceipt(),case_id=f['case'].pk,job_id=job.pk,lookup_only=True))
            job.refresh_from_db();self.assertEqual(job.status,'unknown')
            self.assertFalse(InvoiceIssue.objects.exists());self.assertEqual(list(Path(directory).glob('*.json')),[])

    def test_missing_current_reviewer_does_not_hide_an_already_accepted_original_receipt(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            job=InvoiceJob.objects.get(kind='issue')
            Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.invoice.review').update(active=False)
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));w.refresh_from_db();job.refresh_from_db()
            self.assertEqual(job.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)
            self.assertFalse(InvoiceDelivery.objects.exists());self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            self.assertEqual(w.status,'owner_needed');self.assertEqual(Invoice.objects.count(),1)

    def test_deactivated_original_executor_does_not_control_observation_of_its_prior_effect(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();a=f['actor'];c=f['case'];w=f['work']
        executor=get_user_model().objects.create_user(username='prior-executor')
        for action in ['case.read','finance.read','factory.read','factory.execute','finance.invoice.issue','finance.invoice.deliver']:
            Grant.objects.create(case=c,user=executor,action=action)
        roles=active_component('D05.role_principal_assignments',c)
        ref=register_reference(a,c.pk,'recovery-executor','schema:psl/role-assignment/v1',{'role':'Finance','user_id':executor.pk},f['evidence']['policy_decision'].pk)
        activate(a,c,'D05.role_principal_assignments',roles.envelope['value']+[ref.ref],f['evidence']['policy_decision'])
        config=draft_operator_policy(a,c.pk,'OPS.factory_execution',{**f['value'],'executor_id':executor.pk},f['evidence']['policy_decision'].pk,timezone.now())
        transition(a,config.pk,'validated');transition(a,config.pk,'active')
        factory.run_until_wait(w.pk);factory_approve_identified(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            job=InvoiceJob.objects.get(kind='issue');self.assertEqual(job.actor_id,executor.pk)
            executor.is_active=False;executor.save(update_fields=['is_active'])
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));job.refresh_from_db()
            self.assertEqual(job.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)
            self.assertFalse(InvoiceDelivery.objects.exists());self.assertEqual(len(list(Path(directory).glob('*.json'))),1)

    def test_human_reservation_on_same_invoice_is_not_owned_or_drained_by_factory(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f);w.refresh_from_db()
        job=invoices.reserve(f['actor'],f['case'].pk,w.invoice_id,'issue','Finance',rev(f['case']))
        self.assertNotIn('factory_execution',job.intent);self.assertEqual(factory.invoice_jobs(w),[])
        with tempfile.TemporaryDirectory() as directory:
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));job.refresh_from_db();w.refresh_from_db()
            self.assertEqual(job.status,'pending');self.assertEqual(job.attempts,0)
            self.assertEqual(list(Path(directory).glob('*.json')),[]);self.assertFalse(InvoiceIssue.objects.exists())
            self.assertEqual(w.status,'blocked')

    def test_native_new_issuance_is_held_by_other_uncertain_invoice_for_same_obligation(self):
        from .obligation_helpers import factory_approve_identified, identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f);w.refresh_from_db();original=w.invoice
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            policy(f['actor'],f['case'],'D12.stage_terms',[{'coverage_id':f['coverage'].pk,'stage':'completion','amount':'43.00','due_date':original.due_date.isoformat()}])
            prep=billing.prepare(f['actor'],f['case'].pk,f['coverage'].pk,'completion',None,f['handoff'].pk,rev(f['case']))
            replacement=invoices.draft(f['actor'],f['case'].pk,prep.pk,original.reference,original.due_date,rev(f['case']))
            identified(f['actor'],f['case'],replacement)
            invoices.review(f['actor'],f['case'].pk,replacement.pk,'Finance','approve',f['proof'].pk,'Synthetic native new-draft review',rev(f['case']))
            with self.assertRaisesMessage(ValidationError,'unresolved native work'):
                invoices.reserve(f['actor'],f['case'].pk,replacement.pk,'issue','Finance',rev(f['case']))
            self.assertEqual(InvoiceJob.objects.count(),1);self.assertFalse(InvoiceIssue.objects.exists())

    def test_recorded_original_job_remains_recoverable_from_a_legacy_replaced_head(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f);w.refresh_from_db();original=w.invoice
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            job=InvoiceJob.objects.get(kind='issue')
            policy(f['actor'],f['case'],'D12.stage_terms',[{'coverage_id':f['coverage'].pk,'stage':'completion','amount':'43.00','due_date':original.due_date.isoformat()}])
            prep=billing.prepare(f['actor'],f['case'].pk,f['coverage'].pk,'completion',None,f['handoff'].pk,rev(f['case']))
            replacement=invoices.draft(f['actor'],f['case'].pk,prep.pk,original.reference,original.due_date,rev(f['case']))
            # Actual persisted shape produced by the pre-fix514 reproduction; no row/receipt deletion or rollback.
            w.refresh_from_db();w.preparation=prep;w.invoice=replacement;w.save(update_fields=['preparation','invoice'])
            self.assertEqual([item.pk for item in factory.invoice_jobs(w)],[job.pk])
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));w.refresh_from_db();job.refresh_from_db()
            self.assertEqual(job.status,'confirmed');self.assertEqual(InvoiceIssue.objects.get().invoice_id,original.pk)
            self.assertEqual(w.invoice_id,replacement.pk);self.assertEqual(Invoice.objects.count(),2)
            self.assertIn('correction',w.finding.lower());self.assertFalse(InvoiceDelivery.objects.exists())
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)

class InvoiceRecoveryRealClockTests(TransactionTestCase):
    def test_process_exit_after_acceptance_and_actual_native_lease_expiry_recover_original_job(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f);factory.run_once(w.pk)
        job=InvoiceJob.objects.get(kind='issue')
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'-m','tests.factory_invoice_receipt_crash',str(job.pk),directory],
                env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME']),capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,53,result.stderr);job.refresh_from_db()
            self.assertEqual(job.status,'leased');self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            self.assertFalse(InvoiceIssue.objects.exists());w.refresh_from_db();spent=w.budget_used
            factory.run_once(w.pk);w.refresh_from_db();self.assertEqual(w.budget_used,spent)
            started=time.monotonic();deadline=started+45
            while timezone.now()<job.lease_until and time.monotonic()<deadline:
                time.sleep(min(5,max(0.01,(job.lease_until-timezone.now()).total_seconds()+0.01)))
            self.assertLessEqual(job.lease_until,timezone.now(),'Observe real lease expiry; never backdate authority or the lease')
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));w.refresh_from_db();job.refresh_from_db()
            self.assertEqual(w.status,'verified',w.finding);self.assertEqual(job.status,'confirmed')
            self.assertEqual(InvoiceIssue.objects.get().job_id,job.pk);self.assertEqual(InvoiceDelivery.objects.count(),1)
            self.assertEqual(InvoiceJob.objects.filter(kind='issue').count(),1);self.assertEqual(len(list(Path(directory).glob('*.json'))),2)
            self.assertEqual(w.budget_limit,20000);self.assertGreater(w.budget_used,spent)
            print(json.dumps({'actual_child_exit':53,'real_lease_expiry_observed':True,'wait_seconds':round(time.monotonic()-started,3),'original_issue_job':job.pk,'environment':'synthetic_mock'}))

    def test_actual_source_age_is_enforced_at_native_factory_send_boundary(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=fixture(max_age_seconds=60);w=f['work'];factory.run_until_wait(w.pk);approve(f);factory.run_once(w.pk)
        job=InvoiceJob.objects.get(kind='issue');source=f['evidence']['completion'];deadline=time.monotonic()+65
        while (timezone.now()-source.created_at).total_seconds()<=60 and time.monotonic()<deadline:time.sleep(5)
        self.assertGreater((timezone.now()-source.created_at).total_seconds(),60)
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(invoice_delivery.run_once(MockFactoryInvoiceAdapter(directory),case_id=f['case'].pk,job_id=job.pk))
            job.refresh_from_db();self.assertEqual(job.status,'held');self.assertIn('Stale factory source',job.error)
            self.assertFalse(InvoiceIssue.objects.exists());self.assertEqual(list(Path(directory).glob('*.json')),[])
