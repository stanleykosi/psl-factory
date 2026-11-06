"""Synthetic owner configuration; actual Finance/PostgreSQL services, no internal mocks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError,close_old_connections
from django.test import TestCase,TransactionTestCase,Client
from django.urls import reverse
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.models import ImpactAssessment,ImpactReview
from apps.policy.services import resolve,reference_values
from apps.finance import corrections,invoice_delivery
from apps.finance.models import InvoiceJob,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery
from apps.agents.policy_impact import investigate
from adapters.invoices import InternalInvoiceAdapter
from adapters import policy_impact as adapter
from tests.correction_helpers import fixture,note,review
from tests.billing_helpers import policy,evidence
from tests.helpers import rev

KEY='finance.correction_effects'


def pending():
    a,c,cov,issue,e=fixture();r=note(a,c,issue,e);review(a,c,r,e)
    e['policy_decision']=evidence(a,c,'policy_decision','Synthetic correction impact reassessment evidence')
    job=corrections.reserve(a,c.pk,r.pk,'adjust','Finance',rev(c))
    old=resolve('D14.adjustment_correction_rule_refs',c).configuration
    return a,c,issue,e,r,job,old


def successor(a,c,old):
    return policy(a,c,old.component,reference_values(old))


class CorrectionImpactTests(TestCase):
    def rows(self,a,c,old):return impact.page(a,c.pk,old.pk,KEY)['records']

    def test_actual_correction_and_delivery_inherit_lineage_without_financial_payloads(self):
        a,c,issue,e,r,job,old=pending()
        self.assertEqual(self.rows(a,c,old)[0]['state'],'pending_effect')
        invoice_delivery.run_once()
        application=InvoiceCorrectionAcceptance.objects.get(correction=r)
        self.assertEqual(self.rows(a,c,old)[0]['receipt'],application.pk)
        delivery=corrections.reserve(a,c.pk,r.pk,'adjust_deliver','Finance',rev(c))
        rows=self.rows(a,c,old)
        self.assertEqual([x['id'] for x in rows],[job.pk,delivery.pk])
        self.assertEqual(rows[1]['state'],'pending_effect')
        invoice_delivery.run_once()
        rows=self.rows(a,c,old);self.assertEqual(rows[1]['state'],'committed_effect')
        self.assertEqual(rows[1]['receipt_kind'],'adjust_deliver')
        self.assertEqual(rows[1]['acceptance'],application.pk)
        self.assertEqual(InvoiceCorrectionDelivery.objects.get().job_id,delivery.pk)
        self.assertTrue(all(x['domain_route']=='finance_corrections' for x in rows))
        for hidden in ['amount','payload','reason','document_ref','signed_delta','adjusted_face']:
            self.assertFalse(any(hidden in x for x in rows))
        # The source method and actual issuer authority pins also discover the application.
        for component in ['D08.duplicate_correction_rules','D05.role_principal_assignments']:
            cfg=resolve(component,c).configuration
            self.assertTrue(self.rows(a,c,cfg))
        self.assertEqual(impact.page(a,c.pk,old.pk,'finance.invoice_effects')['records'],[])

    def test_lost_reply_keeps_debt_and_reconciles_after_policy_change_without_resending(self):
        a,c,issue,e,r,job,old=pending()
        class LostReply(InternalInvoiceAdapter):
            def deliver(self,*args):super().deliver(*args);raise TimeoutError('Synthetic reply loss')
        invoice_delivery.run_once(LostReply())
        self.assertEqual(self.rows(a,c,old)[0]['state'],'committed_receipt_requires_reconciliation')
        face=corrections.adjusted_face(issue);new=successor(a,c,old)
        row=impact.capture(a,c.pk,old.pk,new.pk,[KEY],e['policy_decision'].pk,'Observe exact committed correction, preserve canonical debt')
        b=get_user_model().objects.create_user(username='correction-impact-reviewer')
        Grant.objects.bulk_create([Grant(user=b,case=c,action=x) for x in ['case.read','policy.read','policy.activate','finance.read']])
        impact.review(b,c.pk,row.pk,'accept',e['policy_decision'].pk,'Engineering review only')
        report=investigate(b,c.pk,row.pk)
        self.assertEqual(len(report['committed_effects']),1);self.assertEqual(report['effect_tools'],[])
        self.assertFalse(report['business_approval'])
        class NoResend(InternalInvoiceAdapter):
            def deliver(self,*args):raise AssertionError('Committed correction must be reconciled by lookup')
        invoice_delivery.run_once(NoResend())
        self.assertEqual(self.rows(a,c,old)[0]['state'],'committed_effect')
        self.assertFalse(impact.inspect(a,c.pk,row.pk)['current'])
        self.assertEqual(corrections.adjusted_face(issue),face)
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
        self.assertEqual(InvoiceJob.objects.get(pk=job.pk).attempts,2)
        self.assertEqual(ImpactReview.objects.count(),1)

    def test_unknown_without_receipt_is_separate_and_cannot_be_accepted_as_delivery(self):
        a,c,issue,e,r,job,old=pending()
        class BeforeAcceptance(InternalInvoiceAdapter):
            def deliver(self,*args):raise TimeoutError('Synthetic transport failure before acceptance')
        invoice_delivery.run_once(BeforeAcceptance())
        record=self.rows(a,c,old)[0];self.assertEqual(record['state'],'uncertain_effect')
        self.assertIsNone(record['receipt']);self.assertIsNone(record['acceptance'])
        self.assertEqual(corrections.adjusted_face(issue),issue.invoice.amount)
        with self.assertRaises(ValidationError):corrections.reserve(a,c.pk,r.pk,'adjust_deliver','Finance',rev(c))
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),0)

    def test_note_delivery_reply_loss_is_separate_from_the_committed_application(self):
        a,c,issue,e,r,job,old=pending();invoice_delivery.run_once()
        delivery=corrections.reserve(a,c.pk,r.pk,'adjust_deliver','Finance',rev(c))
        face=corrections.adjusted_face(issue)
        class LostNoteReply(InternalInvoiceAdapter):
            def deliver(self,*args):super().deliver(*args);raise TimeoutError('Synthetic note reply loss')
        invoice_delivery.run_once(LostNoteReply())
        rows=self.rows(a,c,old)
        self.assertEqual([x['state'] for x in rows],['committed_effect','committed_receipt_requires_reconciliation'])
        self.assertEqual(rows[1]['receipt_sha256'],InvoiceCorrectionDelivery.objects.get().sha256)
        class NoResend(InternalInvoiceAdapter):
            def deliver(self,*args):raise AssertionError('Committed note must not be resent')
        invoice_delivery.run_once(NoResend())
        self.assertEqual(self.rows(a,c,old)[1]['state'],'committed_effect')
        self.assertEqual(InvoiceCorrectionDelivery.objects.count(),1)
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
        self.assertEqual(corrections.adjusted_face(issue),face)
        self.assertEqual(InvoiceJob.objects.get(pk=delivery.pk).attempts,2)

    def test_retired_reservation_and_real_operator_successor_keep_exact_job_lineage(self):
        a,c,issue,e,r,job,old=pending()
        # Changed adapter revision holds ordinary dispatch through the actual worker.
        cfg=resolve('D08.adapter_contract_ref',c).configuration
        policy(a,c,cfg.component,reference_values(cfg)[0]);invoice_delivery.run_once()
        self.assertEqual(self.rows(a,c,old)[0]['status'],'held')
        invoice_delivery.operate(a,c.pk,job.pk,'replace_intent','Synthetic explicit source-owned replacement',rev(c))
        rows=self.rows(a,c,old)
        self.assertEqual(rows[0]['state'],'retired_reservation')
        self.assertEqual(rows[0]['reservation_head'],rows[1]['id'])
        invoice_delivery.run_once();rows=self.rows(a,c,old)
        self.assertIsNone(rows[0]['receipt']);self.assertEqual(rows[1]['state'],'committed_effect')
        self.assertEqual(rows[0]['acceptance'],rows[1]['acceptance'])

    def test_new_native_review_invalidates_assessment_and_finance_access_is_rechecked(self):
        a,c,issue,e,r,job,old=pending();new=successor(a,c,old)
        row=impact.capture(a,c.pk,old.pk,new.pk,[KEY],e['policy_decision'].pk,'Review reserved correction against successor')
        review(a,c,r,e)
        self.assertFalse(impact.inspect(a,c.pk,row.pk)['current'])
        Grant.objects.filter(user=a,case=c,action='finance.read').update(active=False)
        for call in [lambda:self.rows(a,c,old),lambda:impact.inspect(a,c.pk,row.pk),lambda:investigate(a,c.pk,row.pk)]:
            with self.assertRaises(PermissionDenied):call()
        client=Client();client.force_login(a)
        self.assertNotContains(client.get(reverse('policy_impact',args=[c.pk])),KEY)
        self.assertEqual(client.get(reverse('policy_impact_assessment',args=[c.pk,row.pk])).status_code,403)
        self.assertEqual(InvoiceJob.objects.get(pk=job.pk).attempts,0)

    def test_correction_ui_csrf_capture_review_agent_and_closed_current_adapter_sql_contract(self):
        a,c,issue,e,r,job,old=pending();new=successor(a,c,old)
        client=Client(enforce_csrf_checks=True);client.force_login(a);url=reverse('policy_impact',args=[c.pk])
        self.assertContains(client.get(url),KEY);self.assertEqual(client.post(url,{}).status_code,403)
        result=client.post(url,{'previous':old.pk,'successor':new.pk,'adapters':[KEY],'evidence':e['policy_decision'].pk,'reason':'Review exact correction metadata','csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(result.status_code,302);row=ImpactAssessment.objects.get()
        self.assertContains(client.get(result.url),'Correction application and note delivery have separate receipts')
        self.assertContains(client.get(reverse('policy_impact_agent',args=[c.pk,row.pk])),'canonical debt')
        # All sixteen adapters are a valid closed selection, including empty selected domains.
        all_row=impact.capture(a,c.pk,old.pk,new.pk,list(adapter.REGISTRY),e['policy_decision'].pk,'All declared adapters with authorized access')
        self.assertEqual(len(all_row.adapters),16)
        values={f.name:getattr(all_row,f.name) for f in all_row._meta.fields if f.name not in ['id','created_at']}
        for bad in [[KEY,KEY],['unknown.adapter']]:
            with self.assertRaises(ValidationError):impact.selected(bad)
            with self.assertRaises(DatabaseError),transaction.atomic():
                ImpactAssessment.objects.create(**dict(values,adapters=bad,operation_key=impact.digest(bad)))
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),0)
        outsider=get_user_model().objects.create_user(username='correction-impact-outsider')
        for pk in [old.pk,999999999]:
            with self.assertRaises(PermissionDenied):impact.page(outsider,c.pk,pk,KEY)


class CorrectionImpactConcurrencyTests(TransactionTestCase):
    def test_native_correction_job_lock_holds_capture_without_deadlock_or_effect(self):
        a,c,issue,e,r,job,old=pending();new=successor(a,c,old)
        locked,release=Event(),Event()
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    InvoiceJob.objects.select_for_update().get(pk=job.pk);locked.set()
                    self.assertTrue(release.wait(20))
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(holder);self.assertTrue(locked.wait(10))
            try:
                with self.assertRaises(ValidationError):impact.capture(a,c.pk,old.pk,new.pk,[KEY],e['policy_decision'].pk,'Do not block a correction worker')
            finally:release.set()
            future.result(timeout=25)
        self.assertFalse(ImpactAssessment.objects.exists());self.assertFalse(InvoiceCorrectionAcceptance.objects.exists())
        self.assertEqual(InvoiceJob.objects.get(pk=job.pk).attempts,0)
