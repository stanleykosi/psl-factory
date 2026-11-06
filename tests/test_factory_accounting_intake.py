"""F02 supplied-file entry into native accounting, with explicit local receipts."""
import json
from pathlib import Path
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.finance.models import FinancialImport, FinanceSource, FinanceRun, ImportValidation
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.workflows import factory_accounting_intake as intake, factory_accounting as accounting, factory
from apps.workflows.models import FactoryWork, HumanTask
from tests.finance_analysis_helpers import fixture, policy, METRICS
from tests.helpers import rev


class AccountingSuppliedIntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data=fixture(username='supplied-maker',recipient_username='supplied-reader')

    def supplied(self,body=None):
        a,c,e,values,configs,source,template,recipient=self.data
        evidence=add_evidence(a,c.pk,'financial_input',body if body is not None else values['csv']+'\n','synthetic:supplied-export',rev(c))
        context={'entity':source.entity,'period':'2026-10','currency':source.batch.rows[0]['currency'],
                 'accounting_basis':source.accounting_basis,'extracted_at':source.extracted_at,
                 'completeness':'complete','control_total':source.control_total,'source_evidence_id':source.evidence_id}
        return evidence,context

    def submit(self,key='submission-1',body=None,changes=None):
        a,c,*_=self.data;evidence,context=self.supplied(body)
        context.update(changes or {})
        return intake.submit(a,c.pk,key,evidence.pk,context,'Supplied report',rev(c)),evidence,context

    def test_repeat_submission_receipts_share_import_source_and_work(self):
        a,c,*_=self.data
        result,evidence,context=self.submit()
        counts=(FinancialImport.objects.count(),FinanceSource.objects.count(),FactoryWork.objects.count())
        second=intake.submit(a,c.pk,'submission-2',evidence.pk,context,'Supplied report',rev(c))
        self.assertEqual(result['status'],'started');self.assertEqual(second['work'],result['work'])
        self.assertNotEqual(second['receipt'],result['receipt'])
        self.assertEqual(counts,(FinancialImport.objects.count(),FinanceSource.objects.count(),FactoryWork.objects.count()))
        self.assertEqual(Audit.objects.filter(action=intake.RECEIPT).count(),2)
        again=intake.submit(a,c.pk,'submission-1',evidence.pk,context,'Supplied report',rev(c))
        self.assertEqual(again,result);self.assertEqual(Audit.objects.filter(action=intake.RECEIPT).count(),2)
        with self.assertRaises(ValidationError):intake.submit(a,c.pk,'submission-1',evidence.pk,context,'Changed report',rev(c))

    def test_missing_conventions_preserves_import_then_resumes(self):
        a,c,e,values,configs,*_=self.data
        transition(a,configs['D06.source_schema_ref'].pk,'revoked')
        result,_,_=self.submit()
        self.assertEqual(result['status'],'configuration_needed');self.assertFalse(FactoryWork.objects.exists())
        batch=FinancialImport.objects.get(pk=result['batch']);self.assertEqual(batch.rows[0]['amount'],self.data[5].batch.rows[0]['amount'])
        count=FinancialImport.objects.count()
        policy(a,c,'D06.source_schema_ref',{'columns':['account','amount','currency','period']},e['policy_decision'])
        resumed=intake.resume(a,c.pk,result['receipt'],rev(c))
        self.assertEqual(resumed['status'],'started');self.assertEqual(FinancialImport.objects.count(),count)
        self.assertEqual(Audit.objects.filter(action=intake.RECEIPT).count(),1)

    def test_declared_period_mismatch_quarantines_before_mapping(self):
        result,_,_=self.submit(changes={'period':'2026-09'})
        self.assertEqual(result['status'],'quarantined');self.assertIn('period',str(result['findings']))
        self.assertFalse(FactoryWork.objects.exists());self.assertFalse(FinanceRun.objects.exists())

    def test_policy_currency_mismatch_quarantines_native_validation(self):
        a,c,e,values,*_=self.data
        currency=self.data[5].batch.rows[0]['currency'];other='USD' if currency!='USD' else 'EUR'
        result,_,_=self.submit(body=values['csv'].replace(currency,other),changes={'currency':other})
        self.assertEqual(result['status'],'quarantined');self.assertIn('currency',str(result['findings']))
        self.assertEqual(ImportValidation.objects.get(pk=result['validation']).status,'invalid')
        self.assertFalse(FactoryWork.objects.exists())

    def test_malformed_source_has_durable_receipt_and_unknown_is_not_zero(self):
        a,c,*_=self.data
        result,_,_=self.submit(body='wrong,columns\n1,2')
        self.assertEqual(result['status'],'quarantined');self.assertIsNone(Audit.objects.get(pk=result['receipt']).data['batch'])
        result,_,_=self.submit(key='unknown',body='account,amount,currency,period\nA,,USD,2026-10\n',changes={'currency':'USD'})
        self.assertEqual(result['status'],'quarantined')
        self.assertIsNone(FinancialImport.objects.get(pk=result['batch']).rows[0]['amount'])
        self.assertFalse(FactoryWork.objects.exists())

    def test_withdrawn_authority_stale_revision_and_foreign_receipt_do_not_write(self):
        a,c,*_=self.data;evidence,context=self.supplied()
        revision=rev(c);add_evidence(a,c.pk,'finance_source','A newer source assertion','synthetic:new',revision)
        with self.assertRaises(ValidationError):intake.submit(a,c.pk,'stale',evidence.pk,context,'Report',revision)
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())
        Grant.objects.filter(case=c,user=a,action='finance.import').update(active=False)
        with self.assertRaises(PermissionDenied):intake.submit(a,c.pk,'denied',evidence.pk,context,'Report',rev(c))
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())
        Grant.objects.filter(case=c,user=a,action='finance.import').update(active=True)
        with self.assertRaises(PermissionDenied):intake.resume(a,c.pk,999999,rev(c))

    def test_cross_case_evidence_and_changed_identity_are_rejected(self):
        from tests.helpers import setup_case
        a,c,*_=self.data;other,foreign=setup_case(username='foreign-supplier')
        foreign_evidence=add_evidence(other,foreign.pk,'financial_input','account,amount,currency,period\nA,1,USD,2026-10','synthetic:foreign')
        _,context=self.supplied()
        with self.assertRaises(ValidationError):intake.submit(a,c.pk,'foreign',foreign_evidence.pk,context,'Report',rev(c))
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())

    def test_revised_export_preserves_original_receipt_and_import(self):
        a,c,e,values,*_=self.data
        first,_,_=self.submit();old=FinancialImport.objects.get(pk=first['batch'])
        second,_,_=self.submit(key='revision-2',body=values['csv']+'\n\n')
        self.assertNotEqual(first['batch'],second['batch']);self.assertNotEqual(first['work'],second['work'])
        old.refresh_from_db();self.assertEqual(old.source_sha256,Audit.objects.get(pk=first['receipt']).data['request']['sha256'])

    def test_http_supplied_intake_to_reviewed_accounts_and_recipient_receipt(self):
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.documents.models import PublicationReceipt
        a,c,e,values,configs,old_source,template,recipient=self.data
        value=json.loads(Path('fixtures/factory-accounting.json').read_text());value.pop('classification')
        value.update(information_resolver_id=a.pk,executor_id=a.pk,template_id=template.pk,bu_metrics=METRICS)
        profile=draft_operator_policy(a,c.pk,'OPS.factory_accounting_execution',value,e['policy_decision'].pk,timezone.now())
        transition(a,profile.pk,'validated');transition(a,profile.pk,'active')
        evidence,context=self.supplied();client=Client();client.force_login(a)
        url=reverse('factory_create')+'?definition=finance-accounts/v1&case='+str(c.pk)
        before=(Audit.objects.count(),FinancialImport.objects.count(),FinanceSource.objects.count())
        response=client.get(url);self.assertContains(response,'Start from a supplied trial balance')
        self.assertEqual(before,(Audit.objects.count(),FinancialImport.objects.count(),FinanceSource.objects.count()))
        data={'action':'supplied','supplied-key':'http-intake','supplied-evidence':evidence.pk,
              'supplied-source_evidence':context.pop('source_evidence_id'),'supplied-reference':'Supplied report',
              'supplied-revision':rev(c),'supplied-inventory_confirmed':'on',
              **{'supplied-'+k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in context.items()}}
        response=client.post(url,data);self.assertEqual(response.status_code,302)
        work=FactoryWork.objects.get();self.assertNotEqual(work.request['source'],old_source.pk)
        factory.run_until_wait(work.pk)
        # Native source review is mandatory; the intake does not confer approval.
        source_task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='source',status='open')
        task=accounting.claim(a,source_task.pk,source_task.revision)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic supplied extraction reviewed')
        factory.run_until_wait(work.pk)
        output_task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='output',status='open')
        task=accounting.claim(a,output_task.pk,output_task.revision)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic exact output reviewed')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        receipt=PublicationReceipt.objects.get(publication__factory_work=work)
        self.assertEqual(receipt.recipient_id,recipient.pk)
        self.assertFalse(FinanceRun.objects.get(pk=receipt.publication.version.financedocumentbinding.run_id).result['ledger_posted'])

    def test_http_missing_inventory_and_csrf_do_not_capture(self):
        a,c,*_=self.data;evidence,context=self.supplied();client=Client();client.force_login(a)
        url=reverse('factory_create')+'?definition=finance-accounts/v1&case='+str(c.pk)
        data={'action':'supplied','supplied-key':'missing-inventory','supplied-evidence':evidence.pk,
              'supplied-source_evidence':context.pop('source_evidence_id'),'supplied-reference':'Report','supplied-revision':rev(c),
              **{'supplied-'+k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in context.items()}}
        response=client.post(url,data);self.assertEqual(response.status_code,200)
        self.assertIn('inventory_confirmed',response.context['supplied_form'].errors)
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())
        secure=Client(enforce_csrf_checks=True);secure.force_login(a)
        self.assertEqual(secure.post(url,data).status_code,403)
