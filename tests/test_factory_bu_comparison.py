"""Reuse existing native Finance allocation references; no performance consumer."""
import json
from pathlib import Path
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_bu as bu
from apps.finance import analysis
from apps.finance.bu_models import BUReceipt
from tests import test_bu_comparison as native_fixture
from tests.bu_helpers import source,review
from tests.helpers import rev,setup_case

class FactoryBUComparisonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        native_fixture.BUFinanceComparisonTests.setUpTestData.__func__(cls);f=cls.f
        v=json.loads(Path('fixtures/factory-bu.json').read_text());v.pop('classification')
        p=draft_operator_policy(f['preparer'],f['case'].pk,'OPS.factory_bu_execution',v,f['e']['policy_decision'].pk,timezone.now());transition(f['preparer'],p.pk,'validated');transition(f['preparer'],p.pk,'active');Grant.objects.get_or_create(case=f['case'],user=f['manager'],action='factory.read')
    def start(self,comparison=True):
        f=self.f;self.source=source(f);review(f,self.source);inputs={'mode':'event','payroll_id':None,'source_id':self.source.pk,'rule_ids':[],'comparison':f['comparison'] if comparison else None}
        self.work=bu.start(f['preparer'],f['case'].pk,'COMPARE',inputs,'Selected event and native company reference',rev(f['case']));return inputs
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db()
    def test_required_existing_native_allocation_comparison_remains_connected(self):
        f=self.f;self.start();self.advance();r=bu.result(self.work);self.assertIsNotNone(r,self.work.finding);self.assertTrue(r.payload['finance_company_comparison']['matches']);review(f,r)
        p=bu.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'publish',{});bu.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk});self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_required_missing_reference_holds_exact_native_output(self):
        self.start(False);self.advance();r=bu.result(self.work);self.assertIn('finance_company_comparison_missing',r.metadata['codes'])
        with self.assertRaises(ValidationError):review(self.f,r)
    def test_stale_finance_source_invalidates_factory_selected_comparison(self):
        self.start();f=self.f;s=f['finance'].source
        analysis.capture_source(f['preparer'],f['case'].pk,s.batch_id,s.entity,s.accounting_basis,s.extracted_at,s.completeness,s.control_total,s.evidence_id,rev(f['case']))
        with self.assertRaises(ValidationError):bu.source(self.work)
        self.advance();self.assertIsNone(bu.result(self.work))
    def test_revoked_comparison_reader_does_not_get_financial_values(self):
        self.start();f=self.f;Grant.objects.filter(case=f['case'],user=f['preparer'],action='finance.calculate').update(active=False)
        with self.assertRaises(PermissionDenied):bu.source(self.work)
        self.advance();self.assertIsNone(bu.result(self.work))
    def test_cross_case_existing_comparison_rejected(self):
        f=self.f;a,c=setup_case(username='foreign-comparison')
        with self.assertRaises(ValidationError):bu.native.finance_comparison(a,c,self.source.metadata['scope'] if hasattr(self,'source') else {'entity':'synthetic-company','period':'2026-10','currency':'NGN'},f['comparison'])
    def test_typed_comparison_selector_has_exact_run_and_metric(self):
        self.start();f=self.f
        from apps.workflows.factory_bu_views import InputsForm
        data={'mode':'event','source_id':self.source.pk,'comparison_id':f['comparison']['run_id'],'metric':'revenue'};form=InputsForm(f['case'],f['preparer'],data)
        self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.inputs()['comparison'],f['comparison'])
        data.pop('metric');self.assertFalse(InputsForm(f['case'],f['preparer'],data).is_valid())
