"""Read-only, historical F02 lineage without additional worker grants."""
from django.core.exceptions import PermissionDenied
from django.test import TestCase, Client
from django.urls import reverse
from apps.core.models import Audit
from apps.core.services import event
from apps.finance.models import FinanceRun, ImportValidation
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.workflows import factory_accounting_intake as intake
from apps.workflows.models import FactoryWork
from tests.finance_analysis_helpers import fixture
from tests.helpers import rev
from tests import test_factory_accounting_intake as intake_tests


class AccountingProvenanceTests(TestCase):
    supplied=intake_tests.AccountingSuppliedIntakeTests.supplied
    submit=intake_tests.AccountingSuppliedIntakeTests.submit

    @classmethod
    def setUpTestData(cls):
        cls.data=fixture(username='provenance-maker',recipient_username='provenance-reader')

    def test_exact_work_projection_and_get_are_read_only(self):
        a,c,*_=self.data;result,evidence,context=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        before=(Audit.objects.count(),rev(c),ImportValidation.objects.count(),FinanceRun.objects.count())
        facts=intake.provenance(a,work)
        self.assertTrue(facts['historical_only']);self.assertEqual((facts['total'],facts['shown'],facts['omitted']),(1,1,0))
        link=facts['items'][0]
        self.assertEqual((link['receipt'],link['source'],link['batch'],link['validation'],link['work']),
                         (result['receipt'],result['source'],result['batch'],result['validation'],result['work']))
        self.assertEqual(link['submitted_evidence'],evidence.pk);self.assertEqual(link['sha256'],evidence.sha256)
        self.assertEqual(link['validation_policies'],ImportValidation.objects.get(pk=result['validation']).policies)
        client=Client();client.force_login(a);response=client.get(reverse('factory_detail',args=[work.pk]))
        self.assertContains(response,'Trial-balance intake lineage');self.assertContains(response,f'validation #{result["validation"]}')
        self.assertContains(response,'not current Finance approval or QuickBooks authenticity')
        self.assertEqual(response.context['intake_provenance'],facts)
        c.refresh_from_db();self.assertEqual(before,(Audit.objects.count(),c.revision,ImportValidation.objects.count(),FinanceRun.objects.count()))

    def test_worker_investigation_does_not_require_factory_read(self):
        from adapters.factory_accounting import NativeAccountingAdapter
        from apps.agents.models import AgentRun
        from apps.finance.models import FinanceSource
        a,c,*_=self.data;result,_,_=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        Grant.objects.filter(case=c,user=a,action='factory.read').update(active=False)
        with self.assertRaises(PermissionDenied):intake.provenance(a,work)
        outcome=NativeAccountingAdapter().investigate(work,FinanceSource.objects.get(pk=result['source']))
        log=AgentRun.objects.get(pk=outcome['agent_run'])
        self.assertEqual(log.result['intake_provenance']['items'][0]['validation'],result['validation'])
        self.assertEqual(outcome['intake_provenance'],log.result['intake_provenance'])
        self.assertFalse(log.result['approval_granted'])
        Grant.objects.filter(case=c,user=a,action='factory.execute').update(active=False)
        count=AgentRun.objects.count()
        with self.assertRaises(PermissionDenied):NativeAccountingAdapter().investigate(work,FinanceSource.objects.get(pk=result['source']))
        self.assertEqual(AgentRun.objects.count(),count)

    def test_each_read_grant_and_foreign_case_are_enforced(self):
        from tests.helpers import setup_case
        a,c,*_=self.data;result,_,_=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        other,foreign=setup_case(username='foreign-provenance-reader')
        with self.assertRaises(PermissionDenied):intake.provenance(other,work)
        for action in ['factory.read','finance.read','case.read']:
            Grant.objects.filter(case=c,user=a,action=action).update(active=False)
            with self.assertRaises(PermissionDenied):intake.provenance(a,work)
            Grant.objects.filter(case=c,user=a,action=action).update(active=True)

    def test_policy_revocation_preserves_historical_pins_without_approval(self):
        a,c,e,values,configs,*_=self.data;result,_,_=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        facts=intake.provenance(a,work)
        transition(a,configs['D06.unit_sign_currency_period'].pk,'revoked')
        self.assertEqual(intake.provenance(a,work),facts)
        self.assertTrue(facts['historical_only']);self.assertNotIn('approved',facts['items'][0])

    def test_existing_source_absence_is_explicit(self):
        from apps.workflows import factory_accounting
        a,c,e,values,configs,source,*_=self.data
        work=factory_accounting.start(a,c.pk,'existing',source.pk,[],'Existing report',rev(c))
        facts=intake.provenance(a,work)
        self.assertEqual(facts['total'],0);self.assertFalse(facts['selected_source_recorded']);self.assertEqual(facts['items'],[])

    def test_unmatched_validation_is_withheld_and_coverage_is_bounded(self):
        a,c,e,values,configs,original,*_=self.data;result,_,_=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        foreign_validation=ImportValidation.objects.filter(batch=original.batch).latest('pk')
        event(a,c,intake.RESULT,**{**result,'validation':foreign_validation.pk})
        facts=intake.provenance(a,work)
        self.assertEqual((facts['total'],facts['shown'],facts['unavailable']),(2,1,1))
        self.assertNotIn(foreign_validation.pk,[link['validation'] for link in facts['items']])
        # Append-only synthetic history tests display coverage, not new business receipts.
        for _ in range(50):event(a,c,intake.RESULT,**result)
        facts=intake.provenance(a,work)
        self.assertEqual((facts['total'],facts['examined'],facts['shown'],facts['omitted']),(52,50,50,2))

    def test_newer_context_does_not_erase_original_intake_history(self):
        from apps.finance import analysis
        a,c,e,*_=self.data;result,_,_=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        facts=intake.provenance(a,work)
        source=analysis.source_for(c,result['source'])
        analysis.capture_source(a,c.pk,source.batch_id,source.entity,source.accounting_basis,source.extracted_at,
                                source.completeness,source.control_total,source.evidence_id,rev(c))
        self.assertEqual(intake.provenance(a,work),facts)

    def test_repeat_receipt_is_outside_native_investigation_identity(self):
        import json
        from pathlib import Path
        from apps.workflows import factory_accounting
        a,c,*_=self.data;result,evidence,context=self.submit();work=FactoryWork.objects.get(pk=result['work'])
        value=json.loads(Path('fixtures/factory-accounting.json').read_text())
        before,*_=factory_accounting.snapshot(work,value,reader=a)
        key=factory_accounting.investigation_key(work,before)
        intake.submit(a,c.pk,'another-receipt',evidence.pk,context,'Supplied report',rev(c))
        work.refresh_from_db();work.case.refresh_from_db()
        after,*_=factory_accounting.snapshot(work,value,reader=a)
        self.assertEqual(factory_accounting.investigation_key(work,after),key)
        self.assertNotIn('intake_provenance',after)
        self.assertEqual(intake.provenance(a,work)['total'],2)
