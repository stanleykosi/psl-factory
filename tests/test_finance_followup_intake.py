import copy,time,json
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.test import TransactionTestCase,Client,LiveServerTestCase,override_settings
from django.db import transaction,DatabaseError,close_old_connections
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from apps.finance import receipt_followup as source
from apps.finance.transport_models import FinanceAuthenticatedIntake as Receipt
from apps.finance.models import InvoiceIssue,CashVerification
from apps.identity.models import Grant
from apps.policy.followup_transport_validators import INBOUND,SCHEMAS,validate_reference
from adapters import finance_followup_protocol as wire,finance_followup_transport as adapter
from tests.finance_intake_helpers import registry,configure,envelope,command,SECRET
from tests.settlement_helpers import fixture,draft,issue

class FinanceFollowupIntakeTests(TransactionTestCase):
    def fixture(self):
        a,c,_,p,e=fixture();issued=issue(a,c,draft(a,c,p),e)
        return a,c,issued,envelope(c,issued.job)

    def test_policy_authentication_scope_idempotency_history_and_no_decision(self):
        a,c,issued,v=self.fixture();client=Client(enforce_csrf_checks=True)
        with override_settings(**registry(c)):
            self.assertEqual(command(client,c,v).status_code,403);self.assertEqual(Receipt.objects.count(),0)
            cfg,values=configure(a,c)
            for bad in [{'principal_id':999999999},{'evidence_id':999999999},{'allow_synthetic':False},{'signature_window_seconds':0},{'variants':[]}]:
                with self.assertRaises(ValidationError):validate_reference(INBOUND,SimpleNamespace(schema_ref=SCHEMAS[INBOUND][0],content={**values,**bad}),c)
            client.force_login(a)
            self.assertEqual(client.post(wire.path(c.pk,v['operation_key']),wire.encode(v),content_type='application/json').status_code,403) # Session cannot grant API authority.
            self.assertEqual(command(client,c,v,secret='wrong-but-long-synthetic-signing-key').status_code,403)
            self.assertEqual(command(client,c,v,stamp=str(int(time.time())-400)).status_code,403)
            value=command(client,c,v);self.assertEqual(value.status_code,200);ack=value.json();self.assertEqual(ack['outcome'],'acknowledged');self.assertFalse(ack['execution_authorized'])
            self.assertEqual(command(client,c,v).json(),ack);self.assertEqual(command(client,c,v,'GET').json(),ack);self.assertEqual(Receipt.objects.count(),1)
            changed=copy.deepcopy(v);changed['projection']['outcome']='present';self.assertEqual(command(client,c,changed).status_code,403)
            forged=copy.deepcopy(v);forged['operation_key']='1'*64;forged['projection']['source_invoice_id']=999999999
            self.assertEqual(command(client,c,forged).status_code,403)
            self.assertEqual(Receipt.objects.count(),1);r=source.Request.objects.get();report=source.report(a,c.pk,r.pk)
            self.assertEqual(report['source'],'authenticated_metadata_intake_history');self.assertFalse(report['decision_current']);self.assertEqual(source.Decision.objects.count(),0)
            self.assertContains(client.get(reverse('finance_receipt_followup',args=[c.pk])),'Authenticated intake receipt history')
            for operation in ['update','delete']:
                with self.assertRaises(DatabaseError),transaction.atomic():
                    q=Receipt.objects.all();q.update(sha256='0'*64) if operation=='update' else q.delete()
            Grant.objects.filter(user=a,case=c,action='finance.receipt_followup.transport_receive').update(active=False)
            self.assertEqual(command(client,c,v,'GET').json(),ack) # Historical read is distinct from new intake authority.
            newer={**v,'operation_key':'2'*64};self.assertEqual(command(client,c,newer).status_code,403)
            self.assertEqual(command(client,c,newer,'GET').json()['outcome'],'unknown')
            self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(CashVerification.objects.count(),0)

    def test_two_connections_converge_and_foreign_case_cannot_receive(self):
        a,c,issued,v=self.fixture();configure(a,c);barrier=Barrier(2)
        with override_settings(**registry(c)):
            def send(_):
                close_old_connections()
                try:barrier.wait(timeout=30);r=command(Client(enforce_csrf_checks=True),c,v);return r.status_code,r.json()
                finally:close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(send,range(2)))
            self.assertTrue(all(status==200 for status,_ in results));self.assertEqual(results[0],results[1]);self.assertEqual(Receipt.objects.count(),1)
            from tests.helpers import setup_case
            _,foreign=setup_case(username='foreign-intake');bad=copy.deepcopy(v);bad['projection']['source_case_id']=str(foreign.pk)
            self.assertEqual(command(Client(),foreign,bad).status_code,403);self.assertEqual(Receipt.objects.count(),1)

    def test_precomputed_authority_cannot_survive_revocation(self):
        from apps.finance import followup_intake as intake
        a,c,issued,v=self.fixture();configure(a,c)
        with override_settings(**registry(c)):
            actor,cfg,values,role=intake.authority(c,v['sender_ref'],'receive')
            _,_,binding=intake.credentials(c,v['sender_ref'])
            Grant.objects.filter(user=a,case=c,action='finance.receipt_followup.transport_receive').update(active=False)
            with self.assertRaises(PermissionDenied):intake.accept(actor,c,cfg,values,role,binding,v)
            self.assertEqual(Receipt.objects.count(),0);self.assertEqual(source.Request.objects.count(),0)

class FinanceFollowupHttpTests(LiveServerTestCase):
    def test_actual_django_endpoint_and_signed_adapter_receipt(self):
        a,c,_,p,e=fixture();issued=issue(a,c,draft(a,c,p),e);configure(a,c);v=envelope(c,issued.job)
        rules=json.loads(__import__('pathlib').Path('fixtures/finance-followup-transport.json').read_text())['outbound']
        values=registry(c);values['READINESS_ENDPOINTS']={'endpoint:finance-inbox':{'url':self.live_server_url,'classification':'synthetic'}}
        with override_settings(**values):
            public,_=adapter.binding(c,rules)
            job=SimpleNamespace(packet=SimpleNamespace(mapping=SimpleNamespace(plan=SimpleNamespace(case=c))),operation_key=v['operation_key'],intent={'binding':public,'rules':rules,'envelope':v})
            transport=adapter.FinanceFollowupTransport();self.assertIsNone(transport.lookup(job))
            receipt=transport.deliver(job);self.assertEqual(transport.lookup(job),receipt);self.assertEqual(Receipt.objects.count(),1)
            with patch.dict(__import__('os').environ,{'PSL_TEST_FINANCE_INBOX_KEY':SECRET+'rotated'}):
                with self.assertRaises(ValidationError):transport.lookup(job)
            self.assertFalse(receipt['financial_effect_verified']);self.assertEqual(source.Decision.objects.count(),0)
