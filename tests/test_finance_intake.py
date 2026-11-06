import hashlib
import json
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from apps.core.services import add_evidence
from apps.policy.services import register_reference, save_draft, transition, PolicyHold
from apps.finance.services import capture_import, validate_import, begin_invoice_preparation
from apps.finance.models import FinancialImport, InvoicePreparation
from apps.workflows.services import run_once
from apps.pmo.services import complete_milestone
from apps.identity.models import Grant
from .helpers import setup_case, rev, envelope, activate, signed

class FinanceIntakeTests(TestCase):
    def setUp(self):
        self.actor,self.case=setup_case()
        self.decision=add_evidence(self.actor,self.case.pk,'policy_decision','Synthetic source conventions decision','synthetic:owner')

    def conventions(self):
        source=register_reference(self.actor,self.case.pk,'source:csv-v1','schema:psl/controlled-csv/v1',
            {'columns':['account','amount','currency','period']},self.decision.pk)
        activate(self.actor,self.case,'D06.source_schema_ref',source.ref,self.decision)
        content={'currency':'NGN','unit':'major_currency','period':'2026-10','sign_convention':'debit_positive'}
        convention=register_reference(self.actor,self.case.pk,'convention:test','schema:psl/source-conventions/v1',content,self.decision.pk)
        value={'artifact_ref':convention.ref,'artifact_version':convention.version,'sha256':convention.sha256,'schema_ref':convention.schema_ref}
        activate(self.actor,self.case,'D06.unit_sign_currency_period',value,self.decision)

    def capture(self,text):
        e=add_evidence(self.actor,self.case.pk,'financial_input',text,'synthetic:csv')
        return capture_import(self.actor,self.case.pk,e.pk,rev(self.case))

    def test_unknown_amount_is_not_zero_and_source_survives_missing_policy(self):
        batch=self.capture('account,amount,currency,period\n100,,NGN,2026-10\n')
        self.assertIsNone(batch.rows[0]['amount'])
        with self.assertRaises(PolicyHold):validate_import(self.actor,self.case.pk,batch.pk,rev(self.case))
        self.assertEqual(FinancialImport.objects.count(),1)
        self.assertEqual(batch.rows[0]['account'],'100')

    def test_configured_source_validation_preserves_exact_decimal_lineage(self):
        self.conventions()
        batch=self.capture('account,amount,currency,period\n100,123456.78901234,NGN,2026-10\n200,-4.01,NGN,2026-10\n')
        result=validate_import(self.actor,self.case.pk,batch.pk,rev(self.case))
        self.assertEqual(result.status,'validated_source')
        self.assertEqual(batch.rows[0]['amount'],'123456.78901234')
        self.assertEqual(len(result.policies),2)
        self.assertEqual(len(batch.source_sha256),64)

    def test_invalid_source_and_mixed_currency_never_claim_validation(self):
        self.conventions()
        batch=self.capture('account,amount,currency,period\n100,NaN,NGN,2026-10\n200,1.00,USD,2026-09\n')
        result=validate_import(self.actor,self.case.pk,batch.pk,rev(self.case))
        self.assertEqual(result.status,'invalid');self.assertGreaterEqual(len(result.findings),3)

    def test_duplicate_content_and_wrong_columns_are_rejected(self):
        text='account,amount,currency,period\n100,1.00,NGN,2026-10\n'
        self.capture(text)
        with self.assertRaises(ValidationError):self.capture(text)
        with self.assertRaises(ValidationError):self.capture('account,balance\n100,1\n')
        self.assertEqual(FinancialImport.objects.count(),1)

    def test_import_screen_uses_same_services_and_keeps_policy_hold_visible(self):
        e=add_evidence(self.actor,self.case.pk,'financial_input','account,amount,currency,period\n100,1,NGN,2026-10\n','synthetic:csv')
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/'
        self.assertEqual(self.client.post(url,{'action':'import','evidence':e.pk,'revision':rev(self.case)}).status_code,302)
        batch=FinancialImport.objects.get()
        result=self.client.post(url,{'action':'validate_import','batch':batch.pk,'revision':rev(self.case)})
        self.assertContains(result,'D06.source_schema_ref')
        self.assertEqual(batch.importvalidation_set.count(),0)

    def test_preparation_intake_does_not_create_or_issue_invoice(self):
        e=signed(self.actor,self.case)
        complete_milestone(self.actor,self.case.pk,'Delivery',e['completion'].pk,rev(self.case));run_once()
        from apps.finance.models import Handoff
        result=begin_invoice_preparation(self.actor,self.case.pk,Handoff.objects.get().pk,rev(self.case))
        self.assertEqual(result.status,'evidence_received')
        with self.assertRaises(ValidationError):begin_invoice_preparation(self.actor,self.case.pk,Handoff.objects.get().pk,rev(self.case))
        self.assertEqual(InvoicePreparation.objects.count(),1)

    def test_reference_hash_tampering_and_invalid_conventions_are_rejected(self):
        content={'currency':'NGN','unit':'major_currency','period':'2026-99','sign_convention':'debit_positive'}
        record=register_reference(self.actor,self.case.pk,'bad-convention','schema:psl/source-conventions/v1',content,self.decision.pk)
        value={'artifact_ref':record.ref,'artifact_version':1,'sha256':record.sha256,'schema_ref':record.schema_ref}
        draft=save_draft(self.actor,self.case.pk,envelope(self.case,'D06.unit_sign_currency_period',value,self.decision))
        with self.assertRaises(ValidationError):transition(self.actor,draft.pk,'validated')
        value['sha256']='0'*64
        draft=save_draft(self.actor,self.case.pk,envelope(self.case,'D06.unit_sign_currency_period',value,self.decision))
        with self.assertRaises(ValidationError):transition(self.actor,draft.pk,'validated')

    def test_configuration_rejects_nonobject_envelope(self):
        with self.assertRaises(ValidationError):save_draft(self.actor,self.case.pk,[])
