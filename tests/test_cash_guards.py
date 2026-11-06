"""Actual cash facts and effects share preconditions; previews never create money facts."""
import json
from copy import deepcopy
from decimal import Decimal
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
from django.test import TestCase,TransactionTestCase,Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core.models import Audit
from apps.identity.models import Grant
from apps.finance import cash
from apps.finance.models import CashVerification,CashAllocation
from apps.policy import pilot,pilot_bindings,pilot_binding_validators
from apps.policy.services import active_component,reference_values,transition
from apps.policy.models import PilotBinding
from adapters import pilot_guards
from tests.helpers import rev,setup_case
from tests.billing_helpers import evidence,policy
from tests.settlement_helpers import fixture,draft,issue,receipt,assign
from tests.test_release_evaluation_guards import selected,contract_payload


def ready():
    a,c,cov,p,e=fixture();issued=issue(a,c,draft(a,c,p),e);r,_=receipt(a,c,verify=False)
    proof=evidence(a,c,'cash_verification',r.evidence.body)
    return a,c,cov,e,issued,r,proof


class CashGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.a,cls.c,cls.cov,cls.e,cls.issued,cls.r,cls.proof=ready()

    def verify_g(self):return selected(self.a,self.c,'receipt.verify',cash_receipt_id=self.r.pk,role='Finance',cash_verification_evidence_id=self.proof.pk)

    def lot(self):
        lot=cash.verify(self.a,self.c.pk,self.r.pk,'Finance',self.proof.pk,rev(self.c));assign(self.a,self.c,self.r,self.cov,self.e);return lot

    def allocation_g(self,lot,amount='10',key='preview-allocation'):
        return selected(self.a,self.c,'receipt.allocate',cash_lot_id=lot.pk,issued_invoice_id=self.issued.pk,cash_amount=amount,operation_key=key,role='Finance',cash_allocation_evidence_id=self.e['cash_allocation'].pk)

    def test_verification_preview_is_read_only_and_real_service_preserves_idempotent_receipt(self):
        before=(CashVerification.objects.count(),Audit.objects.count(),rev(self.c))
        result=pilot_guards.check(self.a,self.c,self.verify_g());self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(before,(CashVerification.objects.count(),Audit.objects.count(),rev(self.c)))
        self.assertNotIn('customer',json.dumps(result));self.assertNotIn('50.00',json.dumps(result))
        lot=cash.verify(self.a,self.c.pk,self.r.pk,'Finance',self.proof.pk,rev(self.c));self.assertEqual(lot.amount,Decimal('50'))
        again=pilot_guards.check(self.a,self.c,self.verify_g());self.assertEqual(again['state'],'EXISTING_RESERVATION_SOURCE_RECOVERY')
        self.assertEqual(cash.verify(self.a,self.c.pk,self.r.pk,'Finance',self.proof.pk,rev(self.c)).pk,lot.pk)
        self.assertEqual(CashVerification.objects.count(),1)

    def test_current_policy_and_reporter_separation_hold_only_verification_not_capture(self):
        component='D14.recorder_authority_ref';rule=reference_values(active_component(component,self.c))[0]
        policy(self.a,self.c,component,dict(rule,allow_reporter_verify=False))
        self.assertEqual(pilot_guards.check(self.a,self.c,self.verify_g())['findings'],[{'code':'native_authority_denied'}])
        with self.assertRaises(PermissionDenied):cash.verify(self.a,self.c.pk,self.r.pk,'Finance',self.proof.pk,rev(self.c))
        transition(self.a,active_component('D14.receipt_verification_source_ref',self.c).pk,'revoked')
        r,_=receipt(self.a,self.c,ref='capture-still-available',verify=False);self.assertTrue(r.pk)
        self.assertFalse(CashVerification.objects.exists())

    def test_native_numeric_leading_operation_identity_survives_typed_binding_sql_and_retry(self):
        lot=self.lot();key='123-imported-cash-key'
        row=cash.allocate(self.a,self.c.pk,lot.pk,self.issued.pk,'10',key,'Finance',self.e['cash_allocation'].pk,rev(self.c))
        g=self.allocation_g(lot,'10',key);contract,value=contract_payload(self.a,self.c,g)
        pilot_binding_validators.validate(contract,value)
        binding=pilot_bindings.configure(self.a,self.c.pk,contract.pk,value)
        self.assertEqual(binding.payload['guards'][0]['arguments']['operation_key'],key)
        self.assertEqual(pilot_guards.check(self.a,self.c,g)['existing_reservation'],row.pk)
        self.assertEqual(cash.allocate(self.a,self.c.pk,lot.pk,self.issued.pk,'10',key,'Finance',self.e['cash_allocation'].pk,rev(self.c)).pk,row.pk)
        self.assertEqual(CashAllocation.objects.count(),1)

    def test_allocation_matches_actual_capacity_precision_and_exact_retry_identity(self):
        lot=self.lot();g=self.allocation_g(lot);before=(CashAllocation.objects.count(),Audit.objects.count(),rev(self.c))
        self.assertEqual(pilot_guards.check(self.a,self.c,g)['state'],'READY_AT_OBSERVATION')
        self.assertEqual(before,(CashAllocation.objects.count(),Audit.objects.count(),rev(self.c)))
        for amount in ['1000','0.001','0']:
            self.assertEqual(pilot_guards.check(self.a,self.c,self.allocation_g(lot,amount))['state'],'HELD')
            with self.assertRaises(ValidationError):cash.allocate(self.a,self.c.pk,lot.pk,self.issued.pk,amount,'bad-'+amount,'Finance',self.e['cash_allocation'].pk,rev(self.c))
        row=cash.allocate(self.a,self.c.pk,lot.pk,self.issued.pk,'10','preview-allocation','Finance',self.e['cash_allocation'].pk,rev(self.c))
        self.assertEqual(cash.cash_remaining(lot),Decimal('40'));self.assertEqual(cash.open_amount(self.issued),Decimal('22.25'))
        self.assertEqual(pilot_guards.check(self.a,self.c,self.allocation_g(lot))['existing_reservation'],row.pk)
        self.assertEqual(pilot_guards.check(self.a,self.c,self.allocation_g(lot,'11'))['state'],'HELD')
        cash.reverse(self.a,self.c.pk,'allocation',row.pk,'Finance',self.e['cash_correction'].pk,'Human corrects exact allocation',rev(self.c))
        self.assertEqual(cash.cash_remaining(lot),Decimal('50'));self.assertEqual(cash.open_amount(self.issued),Decimal('32.25'))
        self.assertTrue(pilot_guards.check(self.a,self.c,self.allocation_g(lot,'10','fresh-key'))['head']['cash']['reversals'])

    def test_review_ui_agent_and_new_allocation_stale_old_pack_without_creating_cash(self):
        from apps.agents.pilot import investigate
        lot=self.lot();g=self.allocation_g(lot);contract,value=contract_payload(self.a,self.c,g);d=value['deployment']
        client=Client(enforce_csrf_checks=True);client.force_login(self.a);url=reverse('pilot_bindings',args=[self.c.pk,contract.pk])
        self.assertContains(client.get(url),'Exact verified cash lot');self.assertEqual(client.post(url,{}).status_code,403)
        response=client.post(url,dict(operation='receipt.allocate',participant=self.a.pk,**g['arguments'],
            deployment_ref=d['ref'],revision=d['revision'],web_key_ref=d['web_key_ref'],worker_key_ref=d['worker_key_ref'],families=d['families'],freshness_seconds=d['freshness_seconds'],
            csrfmiddlewaretoken=client.cookies['csrftoken'].value,**d['expected']))
        self.assertEqual(response.status_code,302);binding=PilotBinding.objects.get()
        reviewer=get_user_model().objects.create_user(username='cash-preview-reviewer')
        Grant.objects.bulk_create([Grant(user=reviewer,case=self.c,action=k) for k in Grant.objects.filter(user=self.a,case=self.c).values_list('action',flat=True)])
        pilot_bindings.review(reviewer,self.c.pk,binding.pk,'accept','Cash facts only; no verification or allocation performed')
        pack=pilot.capture(self.a,self.c.pk,contract.pk);self.assertTrue(pilot.inspect(self.a,self.c.pk,pack.pk)['current'])
        self.assertTrue(any('Native cash preconditions only' in x for x in investigate(self.a,self.c.pk,pack.pk)['findings']))
        self.assertFalse(CashAllocation.objects.exists())
        cash.allocate(self.a,self.c.pk,lot.pk,self.issued.pk,'1','other-allocation','Finance',self.e['cash_allocation'].pk,rev(self.c))
        self.assertFalse(pilot.inspect(self.a,self.c.pk,pack.pk)['current'])

    def test_source_access_before_lookup_and_typed_sql_foreign_and_pattern_controls(self):
        other,foreign=setup_case(username='foreign-cash');foreign_r,_=receipt(other,foreign,ref='foreign-cash-report',verify=False)
        g=self.verify_g();contract,value=contract_payload(self.a,self.c,g);binding=pilot_bindings.configure(self.a,self.c.pk,contract.pk,value)
        for field,wrong in [('cash_receipt_id',foreign_r.pk),('cash_verification_evidence_id',self.e['cash_correction'].pk),('cash_receipt_id',True)]:
            bad=deepcopy(value);bad['guards'][0]['arguments'][field]=wrong
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,bad)
            successor=pilot.configure(self.a,self.c.pk,dict(contract.payload),contract.pk)
            fields={f.name:getattr(binding,f.name) for f in binding._meta.fields if f.name not in ['id','created_at','contract','payload']}
            with self.assertRaisesMessage(DatabaseError,'PSL'),transaction.atomic():PilotBinding.objects.create(contract=successor,payload=bad,**fields)
            PilotBinding.objects.create(contract=successor,payload=value,**fields);contract=successor
        lot=self.lot();g=self.allocation_g(lot)
        from tests.test_pilot_preflight import selection
        p=selection(self.a,self.c);p['operations']=[g['operation']]
        contract=pilot.configure(self.a,self.c.pk,p,contract.pk);value=deepcopy(value);value['guards']=[g]
        binding=pilot_bindings.configure(self.a,self.c.pk,contract.pk,value)
        for key,wrong in [('cash_amount','1e2'),('operation_key','invalid key')]:
            bad=deepcopy(value);bad['guards'][0]['arguments'][key]=wrong
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,bad)
            successor=pilot.configure(self.a,self.c.pk,dict(contract.payload),contract.pk)
            fields={f.name:getattr(binding,f.name) for f in binding._meta.fields if f.name not in ['id','created_at','contract','payload']}
            with self.assertRaisesMessage(DatabaseError,'PSL'),transaction.atomic():PilotBinding.objects.create(contract=successor,payload=bad,**fields)
            PilotBinding.objects.create(contract=successor,payload=value,**fields);contract=successor
        Grant.objects.filter(user=self.a,case=self.c,action='finance.read').update(active=False)
        for pk in [self.r.pk,999999999]:
            g=self.verify_g();g['arguments']['cash_receipt_id']=pk
            with self.assertRaises(PermissionDenied):pilot_guards.check(self.a,self.c,g)

class CashAutocommitGuardTests(TransactionTestCase):
    def test_preview_requires_no_mutation_transaction_while_native_effect_keeps_locks(self):
        a,c,cov,e,issued,r,proof=ready();self.assertFalse(connection.in_atomic_block)
        result=pilot_guards.check(a,c,selected(a,c,'receipt.verify',cash_receipt_id=r.pk,role='Finance',cash_verification_evidence_id=proof.pk))
        self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertFalse(CashVerification.objects.exists())
        lot=cash.verify(a,c.pk,r.pk,'Finance',proof.pk,rev(c));assign(a,c,r,cov,e)
        result=pilot_guards.check(a,c,selected(a,c,'receipt.allocate',cash_lot_id=lot.pk,issued_invoice_id=issued.pk,cash_amount='10',operation_key='autocommit-preview',role='Finance',cash_allocation_evidence_id=e['cash_allocation'].pk))
        self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertFalse(CashAllocation.objects.exists())
