"""Connected native accounting preparation, human Finance review and controlled receipts."""
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from apps.policy.services import transition,resolve,reference_values
from apps.policy.models import Configuration
from apps.workflows import factory
from apps.workflows.factory_definitions import definition
from apps.workflows.models import HumanTask
from apps.finance.models import FinanceRun,FinanceReview,FinanceDocumentBinding
from apps.documents.models import PublicationReceipt
from tests.finance_analysis_helpers import fixture,METRICS

class AccountingRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=fixture(username='synthetic-accounting-recovery',recipient_username='synthetic-accounting-recovery-reader')

    def output_wait(self):
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory_accounting as accounting
        a,c,e,values,configs,source,template,recipient=self.data
        work=configured(a,c,e,source,template,METRICS)['work'];factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,kind='factory_accounting_review',status='open')
        return a,c,e,source,work,accounting,task

    def test_missing_formula_policy_holds_only_formula_not_native_mapping_or_allocation(self):
        from tests.factory_accounting_helpers import configured
        a,c,e,values,configs,source,template,recipient=self.data
        transition(a,configs['D06.rule_oracle_refs'].pk,'revoked')
        work=configured(a,c,e,source,template,METRICS)['work'];factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertTrue(FinanceRun.objects.filter(case=c,source=source,kind='mapping').exists())
        self.assertTrue(FinanceRun.objects.filter(case=c,source=source,kind='allocation').exists())
        self.assertFalse(FinanceRun.objects.filter(case=c,source=source,kind='formula').exists())
        self.assertEqual(work.status,'configuration_needed');self.assertIn('D06.rule_oracle_refs',work.finding)

    def test_return_requires_explicit_source_owned_recheck_preserving_history_and_allowance(self):
        from apps.documents.models import Publication
        a,c,e,source,work,accounting,task=self.output_wait()
        task=accounting.claim(a,task.pk,task.revision)
        accounting.decide(a,task.pk,task.revision,'return',e['finance_review'].pk,'Synthetic output requires source-owner follow-up')
        work.refresh_from_db();old_head=work.source_head_id;original=work.request.copy();spent=work.budget_used;limit=work.budget_limit
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'followup_needed');self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        accounting.recheck(a,work.pk,work.revision,source.pk,[],'Explicitly reassessed unchanged source and supplemental inventory')
        work.refresh_from_db();self.assertNotEqual(work.source_head_id,old_head);self.assertEqual(work.request,original)
        self.assertEqual((work.budget_used,work.budget_limit),(spent,limit))
        factory.run_until_wait(work.pk)
        task.refresh_from_db();self.assertEqual(task.status,'returned')
        successor=HumanTask.objects.get(case=c,kind='factory_accounting_review',status='open')
        self.assertNotEqual(successor.pk,task.pk)
        self.assertEqual(FinanceReview.objects.filter(case=c,purpose='output',verdict='return').count(),1)

    def test_committed_delivery_recovers_original_receipts_after_execution_profile_withdrawal(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        from apps.documents.models import PublicationJob,Publication
        a,c,e,source,work,accounting,task=self.output_wait()
        task=accounting.claim(a,task.pk,task.revision)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic exact output approved')
        # One reservation and real recipient-inbox commit, followed by transport loss.
        for _ in range(30):
            factory.run_once(work.pk,adapter=PublicationTimeoutAfterAccept())
            if PublicationJob.objects.filter(publication__factory_work=work,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=work);self.assertEqual(job.status,'unknown')
        receipts=list(PublicationReceipt.objects.filter(publication=job.publication).values_list('pk',flat=True));self.assertTrue(receipts)
        work.refresh_from_db();spent=work.budget_used
        transition(a,work.policy_id,'revoked')
        work.refresh_from_db();client=Client();client.force_login(a);url=reverse('factory_detail',args=[work.pk])
        self.assertContains(client.get(url),'Check original delivery receipts')
        response=client.post(url,{'action':'reconcile','revision':work.revision});self.assertEqual(response.status_code,302)
        job.refresh_from_db();work.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(work.budget_used,spent);self.assertEqual(Publication.objects.filter(factory_work=work).count(),1)
        self.assertEqual(list(PublicationReceipt.objects.filter(publication=job.publication).values_list('pk',flat=True)),receipts)

    def test_missing_receipt_remains_uncertain_without_a_second_delivery(self):
        from adapters.publications import InternalPublicationAdapter
        from apps.documents.models import PublicationJob,Publication
        class LostBeforeCommit(InternalPublicationAdapter):
            deliveries=0
            def deliver(self,job_id,fence):
                self.deliveries+=1;raise TimeoutError('Synthetic connection lost before any inbox commit')
        a,c,e,source,work,accounting,task=self.output_wait()
        task=accounting.claim(a,task.pk,task.revision)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic exact output approved')
        adapter=LostBeforeCommit();factory.run_until_wait(work.pk,adapter=adapter)
        work.refresh_from_db();self.assertEqual(work.status,'waiting_effect',work.finding);self.assertEqual(adapter.deliveries,1)
        job=PublicationJob.objects.get(publication__factory_work=work);self.assertEqual(job.status,'unknown')
        spent=work.budget_used;accounting.reconcile(a,work.pk,work.revision)
        job.refresh_from_db();work.refresh_from_db();self.assertEqual(job.status,'unknown');self.assertEqual(work.status,'waiting_effect')
        self.assertEqual(work.budget_used,spent);self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        self.assertEqual(Publication.objects.filter(factory_work=work).count(),1)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):accounting.recheck(a,work.pk,work.revision,source.pk,[],'Must reconcile the original uncertain effect first')

class FactoryAccountingTests(TestCase):
    def test_controlled_trial_balance_reaches_reviewed_report_and_native_recipient_receipt(self):
        a,c,e,values,configs,source,template,recipient=fixture(username='synthetic-accounting-maker')
        definition('finance-accounts/v1')
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory_accounting as accounting
        f=configured(a,c,e,source,template,METRICS)
        work=f['work'];factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,kind='factory_accounting_review',status='open')
        self.assertEqual(task.context['purpose'],'output')
        client=Client();client.force_login(a)
        url=reverse('factory_detail',args=[work.pk])+'?queue=decisions&q=Accounts'
        response=client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Review the prepared accounting report')
        task=accounting.claim(a,task.pk,task.revision)
        response=client.get(url);self.assertContains(response,'Approve exact Finance subject')
        response=client.post(url,{'action':'decide','task':task.pk,'task_revision':task.revision,'verdict':'approve',
            'evidence':e['finance_review'].pk,'reason':'Synthetic exact accounting output and lineage reviewed'})
        self.assertEqual(response.status_code,302)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        output=FinanceRun.objects.filter(case=c,kind='formula').latest('pk')
        self.assertEqual(output.result['company']['pbt']['value'],'609.99')
        self.assertEqual(output.result['bu_comparison']['pbt']['difference'],'0.00')
        self.assertEqual(FinanceReview.objects.filter(case=c,purpose='output',run=output,verdict='approve').count(),1)
        binding=FinanceDocumentBinding.objects.get(run=output)
        receipt=PublicationReceipt.objects.get(publication__version=binding.version)
        self.assertEqual(receipt.recipient_id,recipient.pk)
        self.assertNotIn('opaque-synthetic',str(receipt.payload));self.assertFalse(output.result['ledger_posted'])
        response=client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'609.99')
        self.assertContains(response,'Confirmed for');self.assertEqual(response.context['row']['state'],'Verified')
        from apps.finance import analysis
        from tests.helpers import rev
        analysis.capture_source(a,c.pk,source.batch_id,source.entity,source.accounting_basis,source.extracted_at,
            source.completeness,source.control_total,e['finance_source'].pk,rev(c))
        response=client.get(reverse('home'),{'queue':'exceptions'})
        changed=next(row for row in response.context['rows'] if row['work'].pk==work.pk)
        self.assertTrue(changed['readiness_changed']);self.assertEqual(changed['state'],'Published report needs review')
        self.assertFalse(any(row['work'].pk==work.pk for row in client.get(reverse('home'),{'queue':'verified'}).context['rows']))
        self.assertEqual(PublicationReceipt.objects.get(pk=receipt.pk).payload_sha256,receipt.payload_sha256)

class AccountingOperatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=fixture(username='synthetic-accounting-operator',recipient_username='synthetic-accounting-reader',review=False)

    def test_intake_requires_explicit_adjustment_inventory_and_uses_current_native_source(self):
        a,c,e,values,configs,source,template,recipient=self.data;client=Client();client.force_login(a)
        url=reverse('factory_create')+'?definition=finance-accounts/v1&case='+str(c.pk)
        response=client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Start accounting preparation')
        revision=response.context['form'].initial['revision']
        response=client.post(url,{'source':source.pk,'reference':'Controlled accounting intake','revision':revision})
        self.assertEqual(response.status_code,200);self.assertEqual(response.context['form'].errors.keys(),{'inventory_confirmed'})
        from apps.workflows.models import FactoryWork
        self.assertFalse(FactoryWork.objects.exists())
        response=client.post(url,{'source':source.pk,'reference':'Controlled accounting intake','revision':revision,'inventory_confirmed':'on'})
        self.assertEqual(response.status_code,302);work=FactoryWork.objects.get()
        self.assertEqual(work.definition,'finance-accounts/v1');self.assertEqual(work.request['adjustment_ids'],[])
        self.assertEqual(work.source_head.kind,'agent_private_accounting_intake');self.assertEqual(work.budget_used,0)
        self.assertEqual(client.get(reverse('factory_detail',args=[work.pk])).status_code,200)
        self.assertEqual(client.get(reverse('factory_create')+'?definition=finance-accounts/v1&case=not-a-workspace').status_code,404)

    def test_accounting_configuration_uses_typed_native_lifecycle_and_can_leave_output_slots_unknown(self):
        import json
        from pathlib import Path
        a,c,e,values,configs,source,template,recipient=self.data;client=Client();client.force_login(a)
        url=reverse('factory_configuration',args=[c.pk])+'?definition=finance-accounts/v1'
        response=client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Preparation scope')
        value=json.loads(Path('fixtures/factory-accounting.json').read_text());value.pop('classification');value.pop('provider');value.pop('review_role')
        value.update(action='draft',information_resolver_id=a.pk,executor_id='',template_id='',audience='',bu_metrics=[],allocation_mode='',
            required_evidence_kinds='finance_source,financial_input',evidence=e['policy_decision'].pk)
        response=client.post(url,value);self.assertEqual(response.status_code,302,getattr(response,'context',None))
        config=Configuration.objects.filter(case=c,component='OPS.factory_accounting_execution').get()
        self.assertEqual(config.states.latest('pk').state,'draft');self.assertEqual(resolve(config.component,c).status,'MISSING')
        for state in ['validated','active']:
            self.assertEqual(client.post(url,{'definition':'finance-accounts/v1','action':'transition','configuration':config.pk,'state':state}).status_code,302)
        actual=reference_values(config)[0]
        for field in ['template_id','audience','executor_id','allocation_mode','bu_metrics']:self.assertIsNone(actual[field])

    def test_source_rule_decisions_have_current_ui_authority_csrf_and_no_context_override(self):
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory_accounting as accounting
        a,c,e,values,configs,source,template,recipient=self.data;f=configured(a,c,e,source,template,METRICS);work=f['work'];factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='source',status='open')
        client=Client();client.force_login(a);url=reverse('factory_detail',args=[work.pk])
        response=client.get(url);self.assertContains(response,'Review the trial-balance source');self.assertContains(response,'Claim Finance review')
        secure=Client(enforce_csrf_checks=True);secure.force_login(a)
        self.assertEqual(secure.post(url,{'action':'claim','task':task.pk,'task_revision':task.revision}).status_code,403)
        self.assertEqual(client.post(url,{'action':'claim','task':task.pk,'task_revision':task.revision}).status_code,302)
        task.refresh_from_db();self.assertEqual(task.claimed_by_id,a.pk)
        before=FinanceReview.objects.count()
        self.assertEqual(client.post(url,{'action':'decide','task':task.pk,'task_revision':task.revision,'verdict':'waive_controls',
            'evidence':e['finance_review'].pk,'reason':'Must not manufacture an allowed decision'}).status_code,302)
        self.assertEqual(FinanceReview.objects.count(),before)
        task.refresh_from_db();self.assertEqual(task.status,'open')
        self.assertEqual(client.post(url,{'action':'claim','task':task.pk+1000000,'task_revision':task.revision}).status_code,404)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic current source review')
        with self.assertRaises(Exception) as caught:
            accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Must not replay the earlier revision')
        from django.core.exceptions import ValidationError
        self.assertIsInstance(caught.exception,ValidationError)

    def test_database_refuses_verified_status_without_native_report_and_recipient_receipts(self):
        from django.db import transaction,IntegrityError,DatabaseError
        from tests.factory_accounting_helpers import configured
        from apps.workflows.models import FactoryWork
        a,c,e,values,configs,source,template,recipient=self.data
        work=configured(a,c,e,source,template,METRICS)['work']
        with self.assertRaises(DatabaseError),transaction.atomic():
            FactoryWork.objects.filter(pk=work.pk).update(status='verified')
        work.refresh_from_db();self.assertNotEqual(work.status,'verified')

    def test_claim_does_not_survive_withdrawn_native_review_grant(self):
        from django.core.exceptions import PermissionDenied
        from apps.identity.models import Grant
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory_accounting as accounting
        a,c,e,values,configs,source,template,recipient=self.data
        work=configured(a,c,e,source,template,METRICS)['work'];factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='source',status='open')
        task=accounting.claim(a,task.pk,task.revision);before=FinanceReview.objects.count()
        Grant.objects.filter(case=c,user=a,action='finance.review').update(active=False)
        with self.assertRaises(PermissionDenied):accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Old claim cannot grant continuing authority')
        self.assertEqual(FinanceReview.objects.count(),before);task.refresh_from_db();self.assertEqual(task.status,'open');self.assertEqual(task.claimed_by_id,a.pk)
        client=Client();client.force_login(a);response=client.get(reverse('factory_detail',args=[work.pk]))
        self.assertEqual(response.status_code,200);self.assertNotContains(response,'Approve exact Finance subject')

    def test_withdrawn_execution_profile_surfaces_in_shared_exceptions_without_running_a_worker(self):
        from tests.factory_accounting_helpers import configured
        a,c,e,values,configs,source,template,recipient=self.data
        work=configured(a,c,e,source,template,METRICS)['work'];factory.run_until_wait(work.pk);work.refresh_from_db()
        transition(a,work.policy_id,'revoked')
        client=Client();client.force_login(a)
        response=client.get(reverse('home'),{'queue':'exceptions'})
        self.assertEqual(response.status_code,200)
        row=next(row for row in response.context['rows'] if row['work'].pk==work.pk)
        self.assertEqual(row['state'],'Execution rules need review');self.assertFalse(row['can_advance'])

    def test_native_source_review_outside_console_reuses_the_same_decision_and_retires_wait(self):
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory_accounting as accounting
        from apps.finance import analysis
        from tests.helpers import rev
        a,c,e,values,configs,source,template,recipient=self.data
        work=configured(a,c,e,source,template,METRICS)['work'];factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='source',status='open');original=task.context.copy()
        review=analysis.review(a,c.pk,'source',source.pk,'Finance','approve',e['finance_review'].pk,'Synthetic source review entered through native Finance',rev(c))
        factory.run_until_wait(work.pk);task.refresh_from_db()
        self.assertEqual(task.status,'completed');self.assertEqual(task.context,original)
        self.assertEqual(FinanceReview.objects.filter(source=source,purpose='source').count(),1)
        self.assertTrue(task.events.filter(action='factory.native_review_observed',data__domain='accounting').exists())


from django.test import TransactionTestCase

class AccountingConcurrencyTests(TransactionTestCase):
    def test_two_postgresql_connections_cannot_claim_the_same_task_revision_twice(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.core.exceptions import ValidationError
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory_accounting as accounting
        from apps.workflows.models import TaskEvent
        a,c,e,values,configs,source,template,recipient=fixture(username='synthetic-accounting-race',recipient_username='synthetic-accounting-race-reader',review=False)
        work=configured(a,c,e,source,template,METRICS)['work'];factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='source',status='open');revision=task.revision;barrier=Barrier(2)
        def claim():
            close_old_connections()
            try:
                barrier.wait(timeout=10);accounting.claim(a,task.pk,revision);return 'claimed'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(claim);second=pool.submit(claim)
            results=[first.result(timeout=30),second.result(timeout=30)]
        self.assertCountEqual(results,['claimed','stale']);task.refresh_from_db()
        self.assertEqual(task.revision,revision+1);self.assertEqual(task.claimed_by_id,a.pk)
        self.assertEqual(TaskEvent.objects.filter(task=task,action='factory.accounting_claimed').count(),1)
        self.assertFalse(FinanceReview.objects.filter(case=c).exists())
