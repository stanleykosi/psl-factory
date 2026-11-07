import json,hashlib,copy
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase,Client
from django.db import connection,transaction,DatabaseError,close_old_connections
from django.urls import reverse
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.finance import receipt_followup as d,corrections
from apps.finance.models import InvoiceIssue,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery,CashVerification
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.invoice_receipt_validators import SCHEMAS,VARIANTS,FOLLOWUP,validate_reference
from apps.policy.services import transition
from apps.identity.models import Grant
from apps.agents.receipt_followup import investigate
from adapters import native_invoice_receipts as adapter,native_application_archive as n
from tests.invoice_variant_helpers import documents
from tests.billing_helpers import evidence
from tests.helpers import setup_case

class InvoiceVariantTests(TransactionTestCase):
    def original(self,j,c):
        with n.connect(connection.settings_dict['NAME']) as db:
            row_sha=db.execute("SELECT encode(sha256(convert_to(to_jsonb(j)::text,'UTF8')),'hex') FROM finance_invoicejob j WHERE id=%s",[j.pk]).fetchone()[0]
            effect=dict(job_id=j.pk,case_id=str(c.pk),effect_key='a'*64,intent_sha256=row_sha,operation_sha256=hashlib.sha256(j.operation_key.encode()).hexdigest())
            metadata,op,payload=adapter.original(db,effect,1048576)
            return metadata,payload,adapter.receipt(db,metadata,payload)

    def test_exact_four_variants_credit_debit_void_and_negative_receipts(self):
        a,c,iss,e,jobs=documents(identity=True);seen=[]
        for j in jobs:
            m,p,r=self.original(j,c);self.assertEqual(r[0],'present',j.kind);seen.append(m['variant'])
            self.assertNotEqual(m['source_row_sha256'],m['payload_sha256']);self.assertNotEqual(m['source_intent_sha256'],m['payload_sha256'])
            with n.connect(connection.settings_dict['NAME']) as db:
                with self.assertRaises(ValidationError):adapter.receipt(db,m,p,1)
                self.assertEqual(adapter.receipt(db,{**m,'invoice_sha256':'0'*64},p)[0],'conflict')
                self.assertEqual(adapter.receipt(db,{**m,'source_invoice_id':999999999},p)[0],'unknown')
                if j.kind in ['deliver','adjust_deliver']:self.assertEqual(adapter.receipt(db,{**m,'recipient_id':999999999},p)[0],'conflict')
                if j.kind=='adjust':self.assertEqual(adapter.receipt(db,m,{**p,'signed_delta':'999.00'})[0],'conflict')
            self.assertNotIn('lines',m);self.assertNotIn(j.operation_key,json.dumps(m))
        self.assertEqual(set(seen),set(adapter.VARIANTS));self.assertEqual(len(jobs),8)
        self.assertEqual(corrections.adjusted_face(iss),0);self.assertEqual(CashVerification.objects.count(),0)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),3)

    def test_source_owned_ui_missing_policy_idempotency_permissions_sql_and_agent(self):
        a,c,iss,e,jobs=documents()
        m,p,r=self.original(jobs[0],c)
        projection=dict(format='psl.finance-receipt-followup/v1',source_case_id=str(c.pk),source_invoice_id=iss.invoice_id,source_correction_id=None,
            variant='issue',mapping_sha256='a'*64,observation_sha256='b'*64,packet_sha256='c'*64,publication_operation='d'*64,outcome='unknown',
            business_jobs_reenacted=False,debt_waived=False,activation_enabled=False)
        proof=evidence(a,c,'integration_contract','Synthetic reviewed companion supplied by current owner; no execution authority')
        request=d.receive(a,c.pk,projection,proof.pk);self.assertEqual(d.receive(a,c.pk,projection,proof.pk).pk,request.pk)
        with self.assertRaises(ValidationError):d.decide(a,c.pk,request.pk,'investigate','Human investigation','missing-policy')
        values=json.loads(Path('fixtures/invoice-receipt-variants.json').read_text(encoding='utf-8'))
        policy_evidence=evidence(a,c,'policy_decision','Synthetic current Finance owner criteria')
        cfg=draft_operator_policy(a,c.pk,FOLLOWUP,{**values['followup_template'],'owner_id':a.pk},policy_evidence.pk,timezone.now())
        transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        validate_reference(VARIANTS,SimpleNamespace(schema_ref=SCHEMAS[VARIANTS][0],content=values['variants']),c)
        for bad in [{'variants':[],'identifier_contract':'exact_incumbent_ids_v1'},{'variants':['cash'],'identifier_contract':'exact_incumbent_ids_v1'}]:
            with self.assertRaises(ValidationError):validate_reference(VARIANTS,SimpleNamespace(schema_ref=SCHEMAS[VARIANTS][0],content=bad),c)
        with self.assertRaises(ValidationError):validate_reference(FOLLOWUP,SimpleNamespace(schema_ref=SCHEMAS[FOLLOWUP][0],content={**values['followup_template'],'owner_id':999999999}),c)
        decision=d.decide(a,c.pk,request.pk,'investigate','Investigate UNKNOWN with current owner','first')
        self.assertEqual(d.decide(a,c.pk,request.pk,'investigate','Investigate UNKNOWN with current owner','first').pk,decision.pk)
        with self.assertRaises(ValidationError):d.decide(a,c.pk,request.pk,'decline','Different decision same key','first')
        linked=d.decide(a,c.pk,request.pk,'link_current_intent','Explicit current invoice investigation link','link',jobs[0].pk)
        self.assertTrue(d.report(a,c.pk,request.pk)['decision_current']);self.assertFalse(linked.pin['execution_authorized'])
        with patch('apps.finance.receipt_followup.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
            self.assertFalse(d.report(a,c.pk,request.pk)['decision_current'])
            with self.assertRaises(ValidationError):d.decide(a,c.pk,request.pk,'decline','Expired request','expired')
        client=Client();client.force_login(a);url=reverse('finance_receipt_followup',args=[c.pk])
        response=client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store')
        response=client.post(url,{'action':'investigate','request_id':request.pk});self.assertEqual(response.status_code,200);self.assertEqual(response.json()['effect_tools'],[])
        self.assertNotIn('lines',response.content.decode());self.assertNotIn('Synthetic exact legal',response.content.decode())
        other,foreign=setup_case(username='foreign')
        with self.assertRaises(ValidationError):d.receive(other,foreign.pk,projection,proof.pk)
        with self.assertRaises(d.Request.DoesNotExist):d.decide(other,foreign.pk,request.pk,'decline','Foreign scope','foreign')
        with self.assertRaises(DatabaseError),transaction.atomic():
            d.Request.objects.filter(pk=request.pk).update(projection={**projection,'debt_waived':True})
        with self.assertRaises(DatabaseError),transaction.atomic():d.Decision.objects.filter(pk=linked.pk).delete()
        Grant.objects.filter(user=a,case=c,action='finance.receipt_followup.decide').update(active=False)
        self.assertFalse(d.report(a,c.pk,request.pk)['decision_current'])
        with self.assertRaises(PermissionDenied):d.decide(a,c.pk,request.pk,'decline','Revoked owner','revoked')
        self.assertFalse(investigate(a,c.pk,request.pk)['execution_authorized'])
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceCorrectionDelivery.objects.count(),3);self.assertEqual(CashVerification.objects.count(),0)

    def test_canonical_receipt_successor_generation_and_two_connection_intake(self):
        from tests.settlement_helpers import fixture,draft,approve
        from tests.helpers import rev
        from apps.finance import invoices,invoice_delivery
        from apps.finance.models import InvoiceJob
        from adapters.invoices import InternalInvoiceAdapter
        a,c,_,p,e=fixture();i=draft(a,c,p);approve(a,c,i,e)
        j=invoices.reserve(a,c.pk,i.pk,'issue','Finance',rev(c))
        with patch.object(InternalInvoiceAdapter,'deliver',side_effect=ValidationError('Synthetic pre-effect hold')):invoice_delivery.run_once()
        j.refresh_from_db();self.assertEqual(j.status,'held')
        invoice_delivery.operate(a,c.pk,j.pk,'replace_intent','Synthetic explicit current source-owned replacement',rev(c))
        invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'replaced')
        issue=InvoiceIssue.objects.get(invoice=i);self.assertNotEqual(issue.job_id,j.pk)
        m,p,result=self.original(j,c);self.assertEqual(result[0],'present');self.assertFalse(d.current_job(j));self.assertTrue(d.current_job(issue.job))
        projection=dict(format='psl.finance-receipt-followup/v1',source_case_id=str(c.pk),source_invoice_id=i.pk,source_correction_id=None,
            variant='issue',mapping_sha256='a'*64,observation_sha256='b'*64,packet_sha256='c'*64,publication_operation='d'*64,outcome='unknown',
            business_jobs_reenacted=False,debt_waived=False,activation_enabled=False)
        proof=evidence(a,c,'integration_contract','Synthetic duplicate source intake')
        barrier=Barrier(2)
        def receive(_):
            close_old_connections()
            try:
                barrier.wait(timeout=30);return d.receive(a,c.pk,projection,proof.pk).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(receive,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(d.Request.objects.count(),1);self.assertEqual(InvoiceIssue.objects.count(),1)
