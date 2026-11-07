"""Exact native preparation -> shared factory; synthetic providers only."""
import copy
import tempfile
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase, TransactionTestCase
from django.db import connection, transaction, DatabaseError, close_old_connections
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.finance import billing, invoices, invoice_delivery, usage_intake
from apps.finance.models import Invoice, InvoiceIssue, InvoiceDelivery, InvoiceReview, InvoiceJob, BillingPreparation
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_invoice_intake as intake
from apps.workflows.models import FactoryWork, FactoryActivity, FactoryAttempt, HumanTask, FactoryInvoicePreparationBinding
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.usage_intake_helpers import fixture, receive, prices, correction
from tests.billing_helpers import prepare, evidence, policy
from tests.settlement_helpers import configured
from tests.helpers import rev
from tests.factory_helpers import approve


def configuration(a,c,executor=None):
    proof=evidence(a,c,'policy_decision','Synthetic explicit factory preparation configuration')
    owners={'definition':'pmo-finance/v1','process_id':'F30','activity':'ACT10','method':'native_finance_single_review/v1',
        'process_owner_id':a.pk,'activity_owner_id':a.pk,'policy_owner_id':a.pk,'governance_resolver_id':a.pk}
    value={'definition':'pmo-finance/v1','max_steps':40,'max_tokens':20000,'tokens_per_call':100,'max_children':100,'max_depth':1,
        'lease_seconds':120,'max_age_seconds':86400,'required_evidence_kinds':['billing_coverage'],
        'information_resolver_id':a.pk,'executor_id':(executor or a).pk,'review_role':'Finance','provider':'synthetic_factory_v1','enabled':True}
    for component,values in [('OPS.factory_responsibility',owners),('OPS.factory_execution',value)]:
        if component=='OPS.factory_responsibility':
            from apps.policy.factory_routing_validators import COMPONENT
            component=COMPONENT
        config=draft_operator_policy(a,c.pk,component,values,proof.pk,timezone.now())
        transition(a,config.pk,'validated');transition(a,config.pk,'active')
    return evidence(a,c,'invoice_review','Synthetic exact native packet approval')


def prepared(username='intake'):
    a,c,covs,source,controls=fixture(username)
    receipt=receive(a,c,source,controls);accepted=usage_intake.accept(a,c.pk,receipt.source_id,rev(c))
    prices(a,c,covs);p=prepare(a,c,covs[0],u=accepted.partitions.get(coverage=covs[0]))
    configured(a,c);proof=configuration(a,c)
    return dict(actor=a,case=c,coverage=covs[0],prep=p,receipt=receipt,source=source,controls=controls,proof=proof)


def start(f,**kwargs):
    values=dict(key='EXACT-1',preparation_id=f['prep'].pk,reference='USAGE-INVOICE',due_date=date(2026,11,20),expected=rev(f['case']))
    values.update(kwargs)
    f['work']=intake.start(f['actor'],f['case'].pk,**values)
    return f['work']


class FactoryInvoiceIntakeTests(TestCase):
    def test_collective_intake_agent_exact_human_review_issue_delivery(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=prepared();w=start(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'waiting',w.finding);self.assertIsNotNone(w.invoice_id)
        self.assertEqual(w.invoice.amount,20);self.assertEqual(w.invoice.preparation_id,f['prep'].pk)
        self.assertFalse(FactoryActivity.objects.filter(work=w,kind='ACT06').exists())
        self.assertFalse(InvoiceIssue.objects.exists());self.assertTrue(FactoryAttempt.objects.filter(activity__work=w,phase='observed',result__preparation=f['prep'].pk).exists())
        approve(f)
        with tempfile.TemporaryDirectory() as directory:
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
        self.assertEqual(start(f,key='DIFFERENT-KEY').pk,w.pk)
        self.assertEqual(FactoryWork.objects.count(),1)

    def test_explicit_existing_approved_invoice_reuses_review_identity(self):
        f=prepared();a,c,p=f['actor'],f['case'],f['prep']
        i=invoices.draft(a,c.pk,p.pk,'USAGE-INVOICE',date(2026,11,20),rev(c))
        r=invoices.review(a,c.pk,i.pk,'Finance','approve',f['proof'].pk,'Exact existing approval',rev(c))
        before=copy.deepcopy(r.publication_packet)
        w=start(f,invoice_id=i.pk);factory.run_until_wait(w.pk);w.refresh_from_db()
        r.refresh_from_db();self.assertEqual(r.publication_packet,before);self.assertEqual(invoices.review_packet(i),before)
        self.assertEqual(Invoice.objects.count(),1);self.assertEqual(InvoiceReview.objects.count(),1)
        self.assertEqual(w.invoice_id,i.pk)
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)

    def test_existing_issued_invoice_reused_without_another_issue(self):
        f=prepared();a,c,p=f['actor'],f['case'],f['prep']
        i=invoices.draft(a,c.pk,p.pk,'USAGE-INVOICE',date(2026,11,20),rev(c))
        from tests.obligation_helpers import identified
        identified(a,c,i)
        r=invoices.review(a,c.pk,i.pk,'Finance','approve',f['proof'].pk,'Exact approved native invoice',rev(c))
        j=invoices.reserve(a,c.pk,i.pk,'issue','Finance',rev(c));invoice_delivery.run_once(case_id=c.pk,job_id=j.pk)
        old=list(InvoiceIssue.objects.values());w=start(f,invoice_id=i.pk)
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(list(InvoiceIssue.objects.values()),old);self.assertEqual(InvoiceReview.objects.count(),1)

    def test_no_inferred_invoice_cross_source_and_payload_conflict(self):
        f=prepared();w=start(f)
        with self.assertRaises(ValidationError):start(f,key='OTHER',reference='DIFFERENT')
        other=prepared('other')
        with self.assertRaises(ValidationError):start(f,key='OTHER',preparation_id=other['prep'].pk)
        factory.run_until_wait(w.pk);w.refresh_from_db()
        with self.assertRaises(ValidationError):start(f,key='RETRY',invoice_id=w.invoice_id)
        self.assertEqual(FactoryWork.objects.filter(case=f['case']).count(),1)

    def test_correction_holds_then_explicit_successor_retains_budget_and_history(self):
        f=prepared();a,c=f['actor'],f['case'];w=start(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        budget=w.budget_used;old=w.invoice_id;origin=copy.deepcopy(w.request)
        s,control=correction(f['source'],f['controls']);receipt=receive(a,c,s,control,delivery='corrected',operation='corrected',predecessor=f['receipt'].source_id)
        accepted=usage_intake.accept(a,c.pk,receipt.source_id,rev(c));p=prepare(a,c,f['coverage'],u=accepted.partitions.get(coverage=f['coverage']))
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'blocked')
        b=intake.replace(a,w.pk,p.pk,'USAGE-INVOICE',date(2026,11,20),w.revision,'Exact accepted corrected report')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertIsNotNone(w.invoice_id,w.finding)
        self.assertEqual(w.request,origin);self.assertGreater(w.budget_used,budget);self.assertNotEqual(w.invoice_id,old)
        self.assertEqual(w.invoice.amount,24);self.assertEqual(b.preparation_id,p.pk);self.assertEqual(Invoice.objects.count(),2)
        self.assertEqual(FactoryActivity.objects.filter(work=w,kind='ACT04',status='succeeded').count(),2)
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('UPDATE workflows_factoryinvoicepreparationbinding SET reason=%s WHERE id=%s',['rewrite',b.pk])

    def test_withdrawal_stops_unissued_preparation(self):
        f=prepared();w=start(f);a,c=f['actor'],f['case']
        proof=evidence(a,c,'usage_intake_withdrawal','Synthetic exact withdrawn source')
        usage_intake.withdraw(a,c.pk,f['receipt'].source_id,proof.pk,'Reported source withdrawn',rev(c))
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'blocked');self.assertFalse(Invoice.objects.exists())

    def test_timeout_original_lookup_after_draft_authority_revocation(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=prepared();w=start(f);factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            self.assertEqual(InvoiceJob.objects.get(kind='issue').status,'unknown')
            Grant.objects.filter(user=f['actor'],case=f['case'],action='finance.invoice.draft').update(active=False)
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
            self.assertEqual(InvoiceIssue.objects.count(),1)
            self.assertEqual(Invoice.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),0)
        self.assertTrue(FactoryAttempt.objects.filter(activity__work=w,activity__kind='ACT12',phase='observed').exists())

    def test_http_intake_and_readonly_console_preserve_rows(self):
        f=prepared();self.client.force_login(f['actor']);c=f['case']
        response=self.client.post('/factory/new/',{'mode':intake.MODE,'case':str(c.pk),'key':'HTTP','preparation':f['prep'].pk,
            'reference':'USAGE-INVOICE','due_date':'2026-11-20','revision':rev(c)})
        self.assertEqual(response.status_code,302,response.content[:1000]);w=FactoryWork.objects.get(case=c)
        before=list(FactoryWork.objects.values());response=self.client.get(f'/work/{w.pk}/')
        self.assertContains(response,'Exact Finance preparation');self.assertEqual(list(FactoryWork.objects.values()),before)


class FactoryInvoiceIntakeConcurrencyTests(TransactionTestCase):
    def test_two_connections_different_keys_one_obligation(self):
        f=prepared('race');barrier=Barrier(2);actor_id=f['actor'].pk;case_id=f['case'].pk;pid=f['prep'].pk
        def invoke(key):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=actor_id);barrier.wait(timeout=15)
                return intake.start(actor,case_id,key,pid,'USAGE-INVOICE',date(2026,11,20),None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(invoke,['one','two']))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.count(),1)


    def test_two_writers_cannot_append_parallel_successors(self):
        f=prepared('successor-race');w=start(f);a,c=f['actor'],f['case']
        s,controls=correction(f['source'],f['controls']);r=receive(a,c,s,controls,delivery='correct',operation='correct',predecessor=f['receipt'].source_id)
        accepted=usage_intake.accept(a,c.pk,r.source_id,rev(c));p=prepare(a,c,f['coverage'],u=accepted.partitions.get(coverage=f['coverage']))
        barrier=Barrier(2)
        def invoke(_):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=a.pk);barrier.wait(timeout=15)
                try:return intake.replace(actor,w.pk,p.pk,'USAGE-INVOICE',date(2026,11,20),w.revision,'Explicit concurrent correction').pk
                except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(invoke,[1,2]))
        self.assertEqual(results.count('stale'),1);self.assertEqual(FactoryInvoicePreparationBinding.objects.count(),1)
        w.refresh_from_db();self.assertEqual(w.preparation_id,p.pk)


class FactoryFixedPreparationTests(TestCase):
    def fixed(self):
        from tests.test_preparation_continuation import PreparationContinuationTests
        h=PreparationContinuationTests();h.setUp();request,charge,prep=h.prepared()
        configured(h.a,h.c);proof=configuration(h.a,h.c)
        return h,request,charge,prep,proof

    def test_post_ack_reassignment_keeps_original_preparer_and_native_receipt(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        h,request,charge,prep,proof=self.fixed()
        from apps.finance.models import CoveragePreparationReceipt
        receipt=list(CoveragePreparationReceipt.objects.values());d=h.recipient('new-factory-preparer');route=h.assign(request,d)
        Grant.objects.filter(user=h.b,case=h.c,action='finance.billing.prepare').update(active=False)
        f=dict(actor=d,case=h.c,prep=prep,proof=proof)
        w=start(f,reference='ANNUAL-FACTORY')
        self.assertEqual(w.actor_id,d.pk);self.assertEqual(w.preparation.actor_id,h.b.pk)
        self.assertEqual(w.request['preparation']['continuation'],route.pk)
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertIsNotNone(w.invoice_id,w.finding)
        self.assertEqual(w.invoice.amount,1200);self.assertEqual(w.invoice.actor_id,d.pk)
        approve(dict(actor=h.a,case=h.c,proof=proof,work=w,binding_actor=d))
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(list(CoveragePreparationReceipt.objects.values()),receipt)

    def test_changed_continuation_requires_explicit_binding_without_recreating_invoice(self):
        h,request,charge,prep,proof=self.fixed();f=dict(actor=h.b,case=h.c,prep=prep,proof=proof)
        w=start(f,reference='ANNUAL-PIN');factory.run_until_wait(w.pk);w.refresh_from_db();invoice=w.invoice_id
        d=h.recipient('replacement-continuation');route=h.assign(request,d)
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'blocked')
        budget=w.budget_used
        binding=intake.replace(h.b,w.pk,prep.pk,'ANNUAL-PIN',date(2026,11,20),w.revision,'Explicit new continuation recipient')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.invoice_id,invoice);self.assertEqual(Invoice.objects.count(),1)
        self.assertEqual(binding.payload['preparation']['continuation'],route.pk);self.assertGreaterEqual(w.budget_used,budget)
        self.assertEqual(w.actor_id,h.b.pk)

    def test_private_fixed_preparation_not_visible_to_generic_finance_reader(self):
        h,request,charge,prep,proof=self.fixed();w=start(dict(actor=h.b,case=h.c,prep=prep,proof=proof))
        reader=get_user_model().objects.create_user(username='generic-finance-reader')
        for action in ['case.read','finance.read','factory.read','factory.start']:
            Grant.objects.create(user=reader,case=h.c,action=action)
        self.client.force_login(reader)
        self.assertEqual(self.client.get(f'/work/{w.pk}/').status_code,404)
        response=self.client.get(f'/factory/new/?case={h.c.pk}')
        self.assertNotContains(response,f'fixed_contract preparation #{prep.pk}')
        with self.assertRaises(PermissionDenied):start(dict(actor=reader,case=h.c,prep=prep),key='PRIVATE')

class FactoryInvoicePreparationGuards(TestCase):
    def test_stale_destination_requires_new_review_and_no_unapproved_send(self):
        f=prepared();w=start(f);factory.run_until_wait(w.pk);approve(f)
        from apps.policy.services import active_component,reference_values
        value=reference_values(active_component('D08.adapter_contract_ref',f['case']))[0]
        other=get_user_model().objects.create_user(username='new-destination')
        Grant.objects.create(user=other,case=f['case'],action='finance.invoice.receive')
        policy(f['actor'],f['case'],'D08.adapter_contract_ref',dict(value,recipient_id=other.pk))
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertFalse(InvoiceIssue.objects.exists());self.assertEqual(w.status,'waiting',w.finding)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)

    def test_cancel_before_effect_keeps_preparation_and_history(self):
        f=prepared();w=start(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        original=copy.deepcopy(w.request);factory.manage(f['actor'],w.pk,w.revision,'cancel')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'cancelled');self.assertEqual(w.request,original)
        self.assertEqual(BillingPreparation.objects.count(),1);self.assertEqual(InvoiceIssue.objects.count(),0)

    def test_sql_cross_preparation_and_stale_attachment_denied(self):
        f=prepared();w=start(f);other=prepared('guard-other')
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('UPDATE workflows_factorywork SET preparation_id=%s WHERE id=%s',[other['prep'].pk,w.pk])
        a,c=f['actor'],f['case'];proof=evidence(a,c,'usage_intake_withdrawal','Withdrawn before forged attachment')
        usage_intake.withdraw(a,c.pk,f['receipt'].source_id,proof.pk,'Withdrawn source',rev(c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            FactoryWork.objects.create(case=c,actor=a,key='FORGED',business_key='f'*64,request=w.request,request_hash=w.request_hash,preparation=f['prep'])


class FactoryCompletionCompatibility(TestCase):
    def test_completion_business_key_remains_exact_original_contract(self):
        from tests.factory_helpers import fixture as completion_fixture
        f=completion_fixture();w=f['work'];cov=f['coverage']
        self.assertEqual(w.business_key,billing.digest({'case':str(f['case'].pk),'customer':cov.customer,
            'contract':cov.contract,'kind':'completion','usage':None}))
        self.assertNotIn('mode',w.request)
        from tests.obligation_helpers import factory_approve_identified
        factory.run_until_wait(w.pk);factory_approve_identified(f)
        with tempfile.TemporaryDirectory() as directory:
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
