import io,os,sys,subprocess,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.test import TestCase,TransactionTestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.management import call_command,CommandError
from django.db import connection,close_old_connections
from django.utils import timezone
from apps.workflows import factory
from apps.workflows.models import FactoryWork,FactoryActivity,FactoryAttempt,HumanTask,TaskEvent
from apps.finance import invoices,invoice_delivery
from apps.finance.models import Invoice,InvoiceReview,InvoiceJob,InvoiceIssue
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.factory_helpers import fixture,approve

def replacement(f,**changes):
    c=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_execution',{**f['value'],**changes},f['evidence']['policy_decision'].pk,timezone.now())
    transition(f['actor'],c.pk,'validated');transition(f['actor'],c.pk,'active');return c

class FactoryRecoveryTests(TestCase):
    def test_native_worker_rechecks_the_reserved_factory_profile_before_sending(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f);factory.run_once(w.pk);w.refresh_from_db()
        job=InvoiceJob.objects.get();self.assertEqual(job.status,'pending')
        self.assertEqual(job.intent['factory_execution'],{'schema':'factory-invoice-execution/v1','work':w.pk,'profile':f['config'].pk,'executor':f['actor'].pk})
        replacement(f,max_age_seconds=7200)
        with tempfile.TemporaryDirectory() as directory:
            invoice_delivery.run_once(MockFactoryInvoiceAdapter(directory),case_id=f['case'].pk,job_id=job.pk)
            job.refresh_from_db();self.assertEqual(job.status,'held');self.assertIn('policy_changed',job.error)
            self.assertFalse(InvoiceIssue.objects.exists());self.assertEqual(list(Path(directory).glob('*.json')),[])

    def test_recorded_legacy_factory_intent_requires_explicit_native_rebinding(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f);w.refresh_from_db();f['case'].refresh_from_db()
        legacy=invoices.reserve(f['actor'],f['case'].pk,w.invoice_id,'issue','Finance',f['case'].revision)
        self.assertNotIn('factory_execution',legacy.intent)
        # A historical factory request needs durable provenance, not merely the same invoice.
        # This fixture represents the pre-binding coordinator; current unbound human work stays separate.
        historical=FactoryActivity.objects.create(work=w,key=factory.digest(['recorded-legacy-reservation',legacy.pk]),
            kind='ACT11',status='succeeded',plan_revision=w.plan_revision)
        FactoryAttempt.objects.create(activity=historical,number=1,phase='started',fence=w.fence,observation={'invoice':w.invoice_id})
        FactoryAttempt.objects.create(activity=historical,number=1,phase='observed',fence=w.fence,
            observation={'invoice':w.invoice_id},result={'job':legacy.pk,'effect':'issue','fixture':'historical_pre_binding_coordinator'})
        factory.run_once(w.pk);legacy.refresh_from_db();self.assertEqual(legacy.status,'held')
        self.assertIn('Legacy factory intent',legacy.error);self.assertFalse(InvoiceIssue.objects.exists())
        f['case'].refresh_from_db()
        invoice_delivery.operate(f['actor'],f['case'].pk,legacy.pk,'replace_intent','Synthetic current operator reviewed exact factory execution scope',f['case'].revision)
        replacement_job=InvoiceJob.objects.exclude(pk=legacy.pk).get();self.assertEqual(replacement_job.intent['factory_execution']['work'],w.pk)
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        legacy.refresh_from_db();self.assertNotIn('factory_execution',legacy.intent);self.assertEqual(legacy.status,'replaced')
        self.assertEqual(InvoiceIssue.objects.count(),1)
    def test_reviewed_profile_adoption_keeps_lifetime_allowance_and_invalidates_old_review(self):
        from .obligation_helpers import factory_approve_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_approve_identified(f);w.refresh_from_db()
        spent,limit,invoice_id=w.budget_used,w.budget_limit,w.invoice_id;old=InvoiceReview.objects.get()
        config=replacement(f,max_tokens=40000)
        factory.run_once(w.pk);w.refresh_from_db();self.assertEqual(w.status,'blocked')
        with self.assertRaises(ValidationError):factory.adopt_profile(f['actor'],w.pk,w.revision,f['config'].pk,'Wrong stale version')
        factory.adopt_profile(f['actor'],w.pk,w.revision,config.pk,'Synthetic owner reviewed the exact new version')
        w.refresh_from_db();self.assertEqual((w.budget_used,w.budget_limit,w.invoice_id),(spent,limit,invoice_id))
        with self.assertRaisesMessage(ValidationError,'fresh exact-packet'):invoices.reviewed(w.invoice)
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)
        self.assertEqual(InvoiceReview.objects.count(),1);old.refresh_from_db();self.assertNotEqual(old.publication_packet,invoices.review_packet(w.invoice))
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_adoption_requires_current_policy_authority_and_does_not_erase_overspent_new_cap(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db();spent=w.budget_used
        config=replacement(f,max_tokens=100)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=False)
        with self.assertRaises(PermissionDenied):factory.adopt_profile(f['actor'],w.pk,w.revision,config.pk,'No current activation grant')
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=True)
        factory.adopt_profile(f['actor'],w.pk,w.revision,config.pk,'Synthetic smaller limit reviewed')
        factory.run_once(w.pk);w.refresh_from_db();self.assertEqual(w.budget_used,spent)
        self.assertEqual(w.status,'blocked');self.assertIn('BUDGET_EXHAUSTED',w.finding)

    def test_policy_activation_during_planning_rejects_old_tools(self):
        f=fixture();w=f['work']
        class Changed:
            def choose(self,c):
                replacement(f,max_age_seconds=7200)
                return {'activity':c['eligible'][0],'citations':c['evidence_ids']}
        factory.run_once(w.pk,Changed());w.refresh_from_db()
        self.assertEqual(w.status,'blocked');self.assertIn('policy_changed',w.finding)
        self.assertFalse(FactoryActivity.objects.filter(work=w,kind='ACT04').exists());self.assertEqual(w.budget_used,100)

    def test_claim_release_preserves_history_and_does_not_grant_decision_authority(self):
        f=fixture();factory.run_until_wait(f['work'].pk);t=HumanTask.objects.get(kind='factory_review')
        t=factory.claim_task(f['actor'],t.pk,t.revision);original=t.context
        t=factory.release_task_claim(f['actor'],t.pk,t.revision,'Synthetic absence requires a fresh eligible claim')
        self.assertIsNone(t.claimed_by_id);self.assertEqual(t.context,original)
        self.assertEqual(TaskEvent.objects.get(task=t,action='factory.claim_released').data['previous_principal'],f['actor'].pk)
        with self.assertRaises(ValidationError):factory.decide(f['actor'],t.pk,t.revision,'approve',f['proof'].pk,'Unclaimed task cannot decide')
        self.assertFalse(InvoiceReview.objects.exists())

    def test_corrupted_remote_proof_remains_unknown_without_another_effect(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True,delayed_reads=1)
            factory.run_until_wait(w.pk,adapter=adapter);w.refresh_from_db();spent=w.budget_used
            files=list(Path(directory).glob('*.json'));self.assertEqual(len(files),1);files[0].write_text('{truncated',encoding='utf-8')
            with override_settings(FACTORY_ADAPTERS={str(f['case'].pk):adapter}):factory.reconcile(f['actor'],w.pk,w.revision)
            w.refresh_from_db();self.assertEqual(w.status,'waiting_effect');self.assertEqual(w.budget_used,spent)
            self.assertEqual(InvoiceJob.objects.get().status,'unknown');self.assertFalse(InvoiceIssue.objects.exists())
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)

    def test_worker_requires_explicit_work_and_uses_the_same_command_path(self):
        f=fixture();w=f['work']
        with self.assertRaises(CommandError):call_command('work_factory',stdout=io.StringIO())
        call_command('work_factory',work=[w.pk],until_wait=True,stdout=io.StringIO())
        w.refresh_from_db();self.assertEqual(w.status,'waiting');self.assertEqual(Invoice.objects.count(),1)
        self.assertFalse(InvoiceIssue.objects.exists())

class FactoryRecoveryConcurrencyTests(TransactionTestCase):
    def test_cancellation_and_approval_use_the_same_lock_order(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        t=HumanTask.objects.get(kind='factory_review');t=factory.claim_task(f['actor'],t.pk,t.revision)
        def compete(action):
            close_old_connections()
            try:
                if action=='cancel':factory.manage(f['actor'],w.pk,w.revision,'cancel')
                else:factory.decide(f['actor'],t.pk,t.revision,'approve',f['proof'].pk,'Synthetic concurrent exact packet review')
                return action
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,['cancel','approve']))
        self.assertEqual(results.count('stale'),1,results);w.refresh_from_db()
        self.assertEqual(InvoiceReview.objects.count(),0 if w.cancel_requested else 1)
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_separate_process_interruption_retains_attempt_then_recovers_same_activity(self):
        f=fixture();w=f['work'];env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(w.pk),'interrupt'],env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,37,result.stderr.decode())
        w.refresh_from_db();self.assertEqual(w.budget_used,100)
        self.assertEqual(FactoryAttempt.objects.filter(activity__work=w,phase='started').count(),1)
        FactoryWork.objects.filter(pk=w.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(w.pk),'resume'],env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr.decode());w.refresh_from_db();self.assertEqual(w.budget_used,200)
        self.assertEqual(FactoryActivity.objects.filter(work=w,kind='ACT03').count(),1)
        self.assertEqual(FactoryAttempt.objects.filter(activity__work=w,activity__kind='ACT03',phase='started').count(),2)
        self.assertFalse(Invoice.objects.exists())
