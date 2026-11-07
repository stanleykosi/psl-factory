"""Exact native continuation authority; external failures only are mocked."""
import copy,json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError,connections,close_old_connections
from django.test import TransactionTestCase
from django.urls import reverse
from apps.finance import preparation_continuation as service, fixed_charge as fixed, contract_coverage as cc, invoices, invoice_delivery, billing
from apps.finance.models import CoveragePreparationContinuation as Continuation, CoveragePreparationReceipt, CoverageNativePreparation, BillingPreparation, InvoiceIssue, InvoiceReview
from apps.identity.models import Grant
from apps.agents import contract_coverage as agent
from apps.core.evidence_access import public_evidence,public_agent_runs
from apps.core.models import Evidence
from apps.agents.models import AgentRun
from adapters.invoices import TimeoutAfterInvoiceAccept
from .test_fixed_contract_bridge import FixedContractBridgeTests
from .settlement_helpers import configured
from .billing_helpers import evidence
from .helpers import rev,setup_case


class PreparationContinuationTests(FixedContractBridgeTests):
    def recipient(self,name='continuation-recipient'):
        user=get_user_model().objects.create_user(username=name,password='isolated-only')
        for action in Grant.objects.filter(user=self.a,case=self.c,active=True).values_list('action',flat=True):
            Grant.objects.create(user=user,case=self.c,action=action)
        for reference in ['register','contract']:self.grant(reference,user)
        return user

    def continuation_proof(self,request,recipient,*,assessment=None,author=None,reason='Explicit current-authorized handoff'):
        author=author or self.a;assessment=assessment or cc.preparation_route(request)['assessment']
        receipt=CoveragePreparationReceipt.objects.get(request=request);prior=service.latest(request)
        payload={'implementation':'fixed-preparation-continuation/v1','receipt':receipt.pk,'request':request.pk,
            'assessment':assessment.pk,'recipient':recipient.pk,'previous':prior.pk if prior else None,'reason':reason}
        proof=cc.supply_evidence(author,self.c.pk,[assessment.terms.register.reference,assessment.terms.contract.reference],['prepare'],
            'coverage_continuation',json.dumps(payload),'synthetic:continuation-test',rev(self.c))
        return proof,payload

    def assign(self,request,recipient,**kwargs):
        proof,p=self.continuation_proof(request,recipient,**kwargs)
        return service.assign(kwargs.get('author') or self.a,self.c.pk,request.pk,p['assessment'],recipient.pk,proof.pk,p['reason'],rev(self.c))

    def test_continuation_after_ack_creates_one_preparation_and_preserves_receipt(self):
        request=self.request();receipt=cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c));original=copy.deepcopy(receipt.payload)
        d=self.recipient();charge=self.charge(request)
        Grant.objects.filter(user=self.b,case=self.c,action='finance.billing.prepare').update(active=False)
        route=self.assign(request,d)
        run=agent.investigate_charge(d,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(run.result['work_route']['recipient'],d.pk);self.assertFalse(run.result['approval_granted'])
        p=fixed.prepare(d,self.c.pk,charge.pk,rev(self.c));same=fixed.prepare(d,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(p.pk,same.pk);self.assertEqual(p.actor_id,d.pk)
        self.assertEqual(fixed.recovered(d,p).payload['continuation_id'],route.pk)
        receipt.refresh_from_db();self.assertEqual(receipt.payload,original);self.assertEqual(receipt.actor_id,self.b.pk)
        self.assertEqual(CoveragePreparationReceipt.objects.count(),1);self.assertEqual(CoverageNativePreparation.objects.count(),1)
        self.assertEqual(InvoiceIssue.objects.count(),0)

    def test_continuation_reuses_preparation_and_existing_exact_review_without_new_approval(self):
        request,charge,p=self.prepared();original=copy.deepcopy(p.snapshot)
        configured(self.a,self.c);i=invoices.draft(self.a,self.c.pk,p.pk,'CONTINUED',date(2026,11,20),rev(self.c))
        from .obligation_helpers import identified
        identified(self.a,self.c,i)
        proof=evidence(self.a,self.c,'invoice_review','Explicit exact original invoice review')
        review=invoices.review(self.a,self.c.pk,i.pk,'Finance','approve',proof.pk,'Original review',rev(self.c));packet=copy.deepcopy(review.publication_packet)
        d=self.recipient();Grant.objects.filter(user=self.b,case=self.c,action='finance.billing.prepare').update(active=False)
        route=self.assign(request,d)
        self.assertEqual(fixed.prepare(d,self.c.pk,charge.pk,rev(self.c)).pk,p.pk)
        with self.assertRaises(PermissionDenied):fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        job=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c));invoice_delivery.run_once(case_id=self.c.pk,job_id=job.pk)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceReview.objects.count(),1)
        review.refresh_from_db();self.assertEqual(review.publication_packet,packet)
        p.refresh_from_db();self.assertEqual(p.actor_id,self.b.pk);self.assertEqual(p.snapshot,original)
        self.assertEqual(BillingPreparation.objects.filter(kind='fixed_contract').count(),1)

    def test_continuation_unknown_effect_requires_original_lookup_then_reuses_issued_preparation(self):
        from adapters.invoices import InternalInvoiceAdapter
        class ExternalBoundaryMock(InternalInvoiceAdapter):
            observed=None
            calls=0
            def deliver(self,pk,fence):
                job,value=invoice_delivery.dispatch_context(pk,fence);self.calls+=1
                binding={'payload':job.invoice.payload,'destination':value['adapter']['recipient_id'],'target':job.invoice_id,'intent':value}
                self.observed={'environment':'synthetic_mock','operation_key':job.operation_key,'payload':job.invoice.payload,
                    'destination':binding['destination'],'fingerprint':billing.digest(binding)}
                raise TimeoutError('Synthetic provider accepted before local receipt commit')
            def lookup(self,job):
                if not self.observed:return None
                invoice_delivery.record_accepted_mock(job.pk,job.fence,self.observed)
                return super().lookup(job)
        request,charge,p=self.prepared();adapter=ExternalBoundaryMock();i,job=self.issued(p,adapter,identity=True);d=self.recipient()
        job.refresh_from_db();self.assertEqual(job.status,'unknown');self.assertEqual(InvoiceIssue.objects.count(),0)
        with self.assertRaises(ValidationError):self.assign(request,d)
        self.assertEqual(Continuation.objects.count(),0)
        Grant.objects.filter(user=self.b,case=self.c,action='finance.billing.prepare').update(active=False)
        Grant.objects.filter(user=self.a,case=self.c,action='finance.invoice.issue').update(active=False)
        self.grant('contract',self.b,[])
        invoice_delivery.run_once(adapter=adapter,case_id=self.c.pk,job_id=job.pk,lookup_only=True)
        job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assign(request,d);self.assertEqual(fixed.prepare(d,self.c.pk,charge.pk,rev(self.c)).pk,p.pk)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(CoverageNativePreparation.objects.count(),1)
        self.assertEqual(fixed.recovered(d,p).receipt.request_id,request.pk);self.assertEqual(adapter.calls,1)

    def test_continuation_source_and_recipient_revocation_hold_new_effect_not_lookup(self):
        request,charge,p=self.prepared();d=self.recipient();route=self.assign(request,d)
        self.grant('contract',d,['read'])
        with self.assertRaises(PermissionDenied):billing.ensure_current(p)
        self.assertEqual(fixed.recovered(self.a,p).preparation_id,p.pk)
        self.assertEqual(service.access(self.a,route).pk,route.pk)
        self.source('contract','contract',dict(self.last_terms.contract.payload,external_version='withdrawn',status='withdrawn'))
        with self.assertRaises((PermissionDenied,ValidationError)):service.access(self.a,route,current=True)
        with self.assertRaises((PermissionDenied,ValidationError)):self.assign(request,self.b)
        self.assertEqual(fixed.recovered(self.a,p).preparation_id,p.pk)

    def test_continuation_repeated_reassignment_and_exact_replay_have_one_current_route(self):
        request,charge,p=self.prepared();d=self.recipient();first=self.assign(request,d)
        replay=service.assign(self.a,self.c.pk,request.pk,first.assessment_id,d.pk,first.evidence_id,first.payload['reason'],rev(self.c))
        self.assertEqual(first.pk,replay.pk)
        second=self.assign(request,self.b)
        self.assertEqual(second.previous_id,first.pk);self.assertEqual(second.version,2)
        with self.assertRaises(ValidationError):service.access(self.a,first,current=True)
        with self.assertRaises(PermissionDenied):fixed.prepare(d,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c)).pk,p.pk)
        self.assertEqual(Continuation.objects.count(),2);self.assertEqual(CoverageNativePreparation.objects.count(),1)

    def test_continuation_authorizer_withdrawal_needs_explicit_current_reattestation(self):
        request,charge,p=self.prepared();d=self.recipient();first=self.assign(request,d)
        Grant.objects.filter(user=self.a,case=self.c,action='coverage.prepare').update(active=False)
        with self.assertRaises(PermissionDenied):billing.ensure_current(p)
        second=self.assign(request,d,author=self.b)
        self.assertEqual(second.previous_id,first.pk);self.assertEqual(second.actor_id,self.b.pk)
        self.assertEqual(fixed.prepare(d,self.c.pk,charge.pk,rev(self.c)).pk,p.pk)

    def test_continuation_foreign_actor_recipient_and_wrong_case_are_denied(self):
        request,charge,p=self.prepared();d=self.recipient();foreign,other=setup_case(username='foreign-continuation')
        proof,body=self.continuation_proof(request,d)
        with self.assertRaises(PermissionDenied):service.assign(foreign,self.c.pk,request.pk,body['assessment'],d.pk,proof.pk,body['reason'],rev(self.c))
        with self.assertRaises(PermissionDenied):service.assign(self.a,self.c.pk,request.pk,body['assessment'],foreign.pk,proof.pk,body['reason'],rev(self.c))
        with self.assertRaises(ValidationError):service.assign(foreign,other.pk,request.pk,body['assessment'],foreign.pk,proof.pk,body['reason'],rev(other))
        self.assertEqual(Continuation.objects.count(),0)

    def test_continuation_sql_duplicate_current_preparation_and_old_recipient_are_denied(self):
        request,charge,p=self.prepared();d=self.recipient();self.assign(request,d)
        attrs={f.name:getattr(p,f.name) for f in p._meta.fields if f.name not in ['id','created_at']}
        for actor in [self.b,d]:
            values=dict(attrs,actor=actor,operation_key=('b' if actor==self.b else 'd')*64)
            with self.assertRaises(DatabaseError),transaction.atomic():BillingPreparation.objects.create(**values)
        self.assertEqual(BillingPreparation.objects.filter(kind='fixed_contract').count(),1)
        self.assertEqual(fixed.prepare(d,self.c.pk,charge.pk,rev(self.c)).pk,p.pk)

    def test_continuation_sql_stale_foreign_and_immutable_route_guards(self):
        request,charge,p=self.prepared();d=self.recipient();first=self.assign(request,d)
        attrs={f.name:getattr(first,f.name) for f in first._meta.fields if f.name not in ['id','created_at']}
        with self.assertRaises(DatabaseError),transaction.atomic():Continuation.objects.create(**dict(attrs,version=2))
        with self.assertRaises(DatabaseError),transaction.atomic():Continuation.objects.filter(pk=first.pk).update(recipient=self.b)
        with self.assertRaises(DatabaseError),transaction.atomic():Continuation.objects.filter(pk=first.pk).delete()
        Grant.objects.filter(user=d,case=self.c,action='finance.billing.prepare').update(active=False)
        configured(self.a,self.c)
        with self.assertRaises((ValidationError,PermissionDenied)):invoices.draft(self.a,self.c.pk,p.pk,'STALE',date(2026,11,20),rev(self.c))
        with connections['default'].cursor() as cur:
            cur.execute('SELECT psl_fixed_preparation_current(%s)',[p.pk]);self.assertFalse(cur.fetchone()[0])
        self.assertEqual(fixed.recovered(self.a,p).preparation_id,p.pk)

    def test_continuation_sql_correctly_shaped_stale_source_route_is_rejected(self):
        request,charge,p=self.prepared();d=self.recipient();first=self.assign(request,d)
        proof,body=self.continuation_proof(request,self.b)
        self.source('contract','contract',dict(self.last_terms.contract.payload,external_version='v-withdrawn',status='withdrawn'))
        with self.assertRaises(DatabaseError),transaction.atomic():
            Continuation.objects.create(receipt=first.receipt,assessment=first.assessment,recipient=self.b,
                previous=first,version=2,payload=body,evidence=proof,actor=self.a)
        self.assertEqual(Continuation.objects.count(),1)
        self.assertEqual(fixed.recovered(self.a,p).preparation_id,p.pk)

    def test_continuation_case_read_withdrawal_denies_reuse_and_private_lookup(self):
        request,charge,p=self.prepared();d=self.recipient();route=self.assign(request,d)
        Grant.objects.filter(user=d,case=self.c,action='case.read').update(active=False)
        with self.assertRaises(PermissionDenied):fixed.prepare(d,self.c.pk,charge.pk,rev(self.c))
        with self.assertRaises(PermissionDenied):fixed.recovered(d,p)
        with self.assertRaises(PermissionDenied):service.access(d,route)
        self.assertEqual(fixed.recovered(self.a,p).preparation_id,p.pk)
        with connections['default'].cursor() as cur:
            cur.execute('SELECT psl_fixed_preparation_current(%s)',[p.pk]);self.assertFalse(cur.fetchone()[0])

    def test_continuation_source_read_withdrawal_does_not_leave_false_current_authority(self):
        request,charge,p=self.prepared();d=self.recipient();route=self.assign(request,d)
        self.grant('contract',d,[permission for permission in cc.PERMISSIONS if permission!='read'])
        with self.assertRaises(PermissionDenied):service.access(self.a,route,current=True)
        with self.assertRaises(PermissionDenied):fixed.prepare(d,self.c.pk,charge.pk,rev(self.c))
        with self.assertRaises(PermissionDenied):fixed.recovered(d,p)
        self.assertEqual(fixed.recovered(self.a,p).preparation_id,p.pk)
        with connections['default'].cursor() as cur:
            cur.execute('SELECT psl_fixed_preparation_current(%s)',[p.pk]);self.assertFalse(cur.fetchone()[0])

    def test_continuation_unknown_effect_is_obligation_scoped_across_source_version_requests(self):
        from .test_contract_coverage import ANNUAL
        request,charge,p=self.prepared();i,job=self.issued(p,TimeoutAfterInvoiceAccept(), identity=True);d=self.recipient()
        new_charge=self.changed_period(dict(ANNUAL,bill_on='2026-10-03'));new_request=new_charge.request
        self.assertNotEqual(request.pk,new_request.pk);self.assertEqual(fixed.obligation(charge),fixed.obligation(new_charge))
        receipt=cc.receive_preparation(self.b,self.c.pk,new_request.pk,None,rev(self.c))
        proof,body=self.continuation_proof(new_request,d)
        with self.assertRaises(ValidationError):service.assign(self.a,self.c.pk,new_request.pk,body['assessment'],d.pk,proof.pk,body['reason'],rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            Continuation.objects.create(receipt=receipt,assessment=new_charge.assessment,recipient=d,previous=None,
                version=1,payload=body,evidence=proof,actor=self.a)
        self.assertEqual(Continuation.objects.count(),0);self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_continuation_native_http_is_private_and_get_is_read_only(self):
        request,charge,p=self.prepared();d=self.recipient();proof,body=self.continuation_proof(request,d)
        self.client.force_login(self.a);url=reverse('finance_contract_coverage',args=[self.c.pk])
        response=self.client.post(url,{'action':'continue_preparation','revision':rev(self.c),'request':request.pk,
            'assessment':body['assessment'],'recipient_id':d.pk,'evidence':proof.pk,'reason':body['reason']})
        self.assertEqual(response.status_code,302);self.assertEqual(Continuation.objects.count(),1)
        before=rev(self.c);response=self.client.get(url);self.assertEqual(response.status_code,200)
        self.assertContains(response,'Continue acknowledged Finance work');self.assertEqual(rev(self.c),before)
        self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=proof.pk).exists())
        run=agent.investigate_charge(d,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(run.result['work_route']['reusable_preparations'],[p.pk])
        self.assertFalse(public_agent_runs(AgentRun.objects.all()).filter(pk=run.pk).exists())


class PreparationContinuationConcurrencyTests(TransactionTestCase):
    reset_sequences=True
    def test_continuation_concurrent_assignment_and_prepare_serialize_then_replay(self):
        helper=PreparationContinuationTests();helper.setUp()
        request=helper.request();cc.receive_preparation(helper.b,helper.c.pk,request.pk,None,rev(helper.c))
        d=helper.recipient();charge=helper.charge(request);proof,body=helper.continuation_proof(request,d)
        def race(fn):
            barrier=Barrier(2)
            def execute():
                close_old_connections();barrier.wait()
                try:return ('ok',fn())
                except ValidationError as exc:return ('stale',str(exc))
                finally:connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(lambda _:execute(),range(2)))
        revision=rev(helper.c)
        results=race(lambda:service.assign(get_user_model().objects.get(pk=helper.a.pk),helper.c.pk,request.pk,body['assessment'],d.pk,proof.pk,body['reason'],revision).pk)
        self.assertEqual(sum(x[0]=='ok' for x in results),1);self.assertEqual(Continuation.objects.count(),1)
        service.assign(helper.a,helper.c.pk,request.pk,body['assessment'],d.pk,proof.pk,body['reason'],rev(helper.c))
        revision=rev(helper.c)
        results=race(lambda:fixed.prepare(get_user_model().objects.get(pk=d.pk),helper.c.pk,charge.pk,revision).pk)
        self.assertEqual(sum(x[0]=='ok' for x in results),1)
        result=fixed.prepare(d,helper.c.pk,charge.pk,rev(helper.c))
        self.assertEqual(BillingPreparation.objects.filter(kind='fixed_contract').count(),1)
        self.assertEqual(CoverageNativePreparation.objects.count(),1);self.assertEqual(CoveragePreparationReceipt.objects.count(),1)
        self.assertEqual(fixed.recovered(d,result).receipt.request_id,request.pk)
