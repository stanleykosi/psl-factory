from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.test import TransactionTestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,close_old_connections
from django.utils import timezone
from django.urls import reverse
from apps.finance import followup_successors as d,receipt_followup as source,invoice_delivery,invoices
from apps.finance.models import InvoiceIssue,InvoiceJob,CashVerification
from apps.identity.models import Grant
from apps.agents.receipt_followup import investigate
from apps.policy.services import transition
from tests.followup_successor_helpers import request,configure
from tests.correction_helpers import fixture,note,apply
from tests.helpers import rev,setup_case

class FollowupSuccessorTests(TransactionTestCase):
    def fixture(self):
        a,c,cov,iss,e=fixture();original=iss.job
        target=apply(a,c,note(a,c,iss,e),e)
        r,proof=request(a,c,original)
        p=d.propose(a,c.pk,r.pk,original.pk,target.pk,'legal_correction',proof.pk,'Synthetic exact legal correction lineage','proposal')
        return a,c,iss,r,proof,p

    def test_capture_policy_review_ui_agent_revocation_and_sql_history(self):
        a,c,iss,r,e,p=self.fixture()
        self.assertEqual(d.status(p)['status'],'proposed')
        with self.assertRaises(ValidationError):d.review(a,c.pk,p.pk,'approve',e.pk,'Missing criteria','missing')
        b,cfg,policy_evidence=configure(a,c,r)
        from types import SimpleNamespace
        from apps.policy.followup_successor_validators import validate_reference,COMPONENT,SCHEMA
        from apps.policy.services import reference_values
        value=reference_values(cfg)[0]
        for bad in [{'relations':[]},{'evidence_kinds':[]},{'reviewer_id':None},{'allow_synthetic':False},{'valid_seconds':0},{'relations':['replay_archived_job']}]:
            with self.assertRaises(ValidationError):validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content={**value,**bad}),c)
        with self.assertRaises(PermissionDenied):d.review(a,c.pk,p.pk,'approve',e.pk,'Self review forbidden','self')
        reviewer_client=Client();reviewer_client.force_login(b)
        response=reviewer_client.post(reverse('finance_receipt_followup',args=[c.pk]),{'action':'review_successor','proposal_id':p.pk,'verdict':'approve','evidence_id':e.pk,'note':'Independent lineage only, no effect approval','operation_key':'accept'})
        self.assertEqual(response.status_code,302);review=d.Review.objects.get(proposal=p,operation_key='accept')
        self.assertEqual(d.review(b,c.pk,p.pk,'approve',e.pk,'Independent lineage only, no effect approval','accept').pk,review.pk)
        result=d.report(a,c.pk,r.pk)['lineage'][0];self.assertEqual(result['status'],'current');self.assertEqual(result['successor_receipt'],'present')
        self.assertFalse(result['execution_authorized']);self.assertFalse(result['debt_waived'])
        client=Client();client.force_login(a);url=reverse('finance_receipt_followup',args=[c.pk])
        self.assertContains(client.get(url),'Successor proposal history')
        answer=client.post(url,{'action':'investigate','request_id':r.pk}).json();self.assertEqual(answer['successors'][0]['status'],'current');self.assertEqual(answer['effect_tools'],[])
        with patch('apps.finance.followup_successors.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
            self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['status'],'stale')
        for model,pk in [(d.Proposal,p.pk),(d.Review,review.pk)]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).update(note='rewrite')
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).delete()
        Grant.objects.filter(user=b,case=c,action='finance.receipt_followup.review_successor').update(active=False)
        self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['status'],'stale')
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(CashVerification.objects.count(),0)

    def test_duplicate_ownership_scope_policy_successor_and_decline(self):
        a,c,iss,r,e,p=self.fixture();b,cfg,_=configure(a,c,r)
        barrier=Barrier(2)
        def propose(_):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                return d.propose(a,c.pk,r.pk,p.original_id,p.successor_id,p.relation,e.pk,'Duplicate exact source-owned lineage','concurrent').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(propose,range(2)))
        self.assertEqual(ids[0],ids[1])
        d.review(b,c.pk,p.pk,'approve',e.pk,'Independent exact lineage','first')
        with self.assertRaises(ValidationError):d.review(b,c.pk,ids[0],'approve',e.pk,'Competing current owner','competing')
        d.review(b,c.pk,p.pk,'hold',e.pk,'Explicitly retire earlier lineage','retire')
        d.review(b,c.pk,ids[0],'approve',e.pk,'Independent successor proposal','second')
        with self.assertRaises(ValidationError):d.propose(a,c.pk,r.pk,p.original_id,p.original_id,p.relation,e.pk,'Same job is not a successor','same')
        with self.assertRaises(ValidationError):d.propose(a,c.pk,r.pk,p.successor_id,p.original_id,p.relation,e.pk,'Original mismatches request correction','wrong-original')
        foreign,foreign_case=setup_case(username='foreign-lineage')
        with self.assertRaises(d.Proposal.DoesNotExist):d.review(foreign,foreign_case.pk,p.pk,'approve',e.pk,'Cross-case refused','foreign')
        source.decide(a,c.pk,r.pk,'decline','Current owner declines further follow-up','decline')
        self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['status'],'stale')
        transition(a,cfg.pk,'revoked')
        self.assertTrue(all(x['status']!='current' for x in d.report(a,c.pk,r.pk)['lineage']))
        from tests.billing_helpers import coverage,prices,usage,prepare,evidence
        from tests.settlement_helpers import draft,approve
        second=coverage(a,c,contract='different-obligation');prices(a,c,second)
        body='transaction_id,customer,service,contract,period,unit,quantity\ntx-distinct-obligation,client-example,api-usage,different-obligation,2026-10,request,12\n'
        prep=prepare(a,c,second,u=usage(a,c,second,body));invoice=draft(a,c,prep,reference='INV-DIFFERENT')
        approve(a,c,invoice,{'invoice_review':evidence(a,c,'invoice_review','Synthetic distinct obligation invoice review')})
        target=invoices.reserve(a,c.pk,invoice.pk,'issue','Finance',rev(c))
        with self.assertRaises(ValidationError):d.propose(a,c.pk,r.pk,p.original_id,target.pk,'intent_generation',e.pk,'Different obligation is not a successor','other-obligation')

    def test_normal_generation_replacement_unknown_receipt_and_successor(self):
        from tests.settlement_helpers import fixture as settlement,draft,approve
        from adapters.invoices import InternalInvoiceAdapter
        a,c,_,preparation,e=settlement();invoice=draft(a,c,preparation);approve(a,c,invoice,e)
        original=invoices.reserve(a,c.pk,invoice.pk,'issue','Finance',rev(c))
        with patch.object(InternalInvoiceAdapter,'deliver',side_effect=TimeoutError('Synthetic uncertain external effect')):invoice_delivery.run_once()
        original.refresh_from_db();self.assertEqual(original.status,'unknown')
        with self.assertRaises(ValidationError):invoice_delivery.operate(a,c.pk,original.pk,'replace_intent','Unresolved effects cannot be replaced',rev(c))
        # Real worker lookup then explicit pre-effect hold: no internal workflow mock.
        with patch.object(InternalInvoiceAdapter,'deliver',side_effect=ValidationError('Synthetic adapter pre-effect rejection')):invoice_delivery.run_once()
        invoice_delivery.operate(a,c.pk,original.pk,'replace_intent','Normal current operator replacement',rev(c))
        target=InvoiceJob.objects.filter(invoice=invoice).order_by('-generation').first()
        r,proof=request(a,c,original);p=d.propose(a,c.pk,r.pk,original.pk,target.pk,'intent_generation',proof.pk,'Normal replacement lineage','generation')
        b,_,_=configure(a,c,r);d.review(b,c.pk,p.pk,'approve',proof.pk,'Independent generation lineage','approve')
        self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['successor_receipt'],'unknown')
        # Reviewer-role configuration changed the original financial review pin. Lineage cannot bypass it.
        invoice_delivery.run_once();target.refresh_from_db();self.assertEqual(target.status,'held')
        self.assertEqual(InvoiceIssue.objects.count(),0)
        approve(a,c,invoice,e)
        invoice_delivery.operate(a,c.pk,target.pk,'replace_intent','Normal fresh Finance review and intent successor',rev(c))
        final=InvoiceJob.objects.filter(invoice=invoice).order_by('-generation').first()
        self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['status'],'stale')
        successor=d.propose(a,c.pk,r.pk,original.pk,final.pk,'intent_generation',proof.pk,'Explicit current source generation after fresh financial approval','fresh-generation')
        d.review(b,c.pk,successor.pk,'approve',proof.pk,'Independent current lineage, ordinary release controls remain','fresh-approve')
        from adapters.invoices import TimeoutAfterInvoiceAccept
        invoice_delivery.run_once(TimeoutAfterInvoiceAccept())
        self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['status'],'stale')
        self.assertEqual(InvoiceIssue.objects.count(),1)
        invoice_delivery.run_once();self.assertEqual(d.report(a,c.pk,r.pk)['lineage'][0]['successor_receipt'],'present')
        self.assertEqual(InvoiceIssue.objects.count(),1)
