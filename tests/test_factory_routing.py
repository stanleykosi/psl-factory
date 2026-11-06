"""Actual native PostgreSQL Finance review and deterministic accountability routing."""
import tempfile
from copy import deepcopy
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.urls import reverse
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError,close_old_connections
from concurrent.futures import ThreadPoolExecutor
from django.utils import timezone
from apps.policy.factory_routing_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_routing as routing
from apps.workflows.models import HumanTask,TaskEvent,FactoryActivity
from apps.finance import invoices,invoice_delivery
from apps.finance.models import InvoiceReview,InvoiceJob,InvoiceIssue,InvoiceDelivery
from apps.identity.models import Grant
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.factory_helpers import fixture,approve
from tests.helpers import rev,setup_case

def configure(f,**changes):
    a=f['actor'];v={'definition':'pmo-finance/v1','process_id':'F30','activity':'ACT10','method':'native_finance_single_review/v1',
        'process_owner_id':a.pk,'activity_owner_id':a.pk,'policy_owner_id':a.pk,'governance_resolver_id':a.pk}
    v.update(changes)
    config=draft_operator_policy(a,f['case'].pk,COMPONENT,v,f['evidence']['policy_decision'].pk,timezone.now())
    transition(a,config.pk,'validated');transition(a,config.pk,'active');return config

class FactoryRoutingTests(TestCase):
    def test_idle_configuration_hold_can_be_stopped_without_worker_or_owner_values(self):
        f=fixture(configure=False,responsibility=False);w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'configuration_needed');self.assertEqual(w.budget_used,0)
        factory.manage(f['actor'],w.pk,w.revision,'cancel');w.refresh_from_db()
        self.assertEqual(w.status,'cancelled');self.assertEqual(w.budget_used,0)

    def test_unknown_owners_allow_useful_draft_but_no_direct_review_or_dispatch(self):
        self.assertEqual(connection.vendor,'postgresql');f=fixture(responsibility=False);w=f['work']
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'owner_needed',w.finding);self.assertIsNotNone(w.invoice_id)
        self.assertTrue(FactoryActivity.objects.filter(work=w,kind='ACT04',status='succeeded').exists())
        self.assertTrue(FactoryActivity.objects.filter(work=w,kind='ACT08',status='succeeded').exists())
        self.assertTrue(FactoryActivity.objects.filter(work=w,kind='ACT09',status='succeeded').exists())
        self.assertTrue(FactoryActivity.objects.filter(work=w,kind='ACT10',status='succeeded').exists())
        task=HumanTask.objects.get(kind='factory_governance');self.assertIsNone(task.context['routing']['governance_resolver_id'])
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())
        with self.assertRaises(ValidationError):invoices.review(f['actor'],f['case'].pk,w.invoice_id,'Finance','approve',f['proof'].pk,'Synthetic review',rev(f['case']))
        with self.assertRaises(PermissionDenied):factory.claim_task(f['actor'],task.pk,task.revision)
        spent=w.budget_used;factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.budget_used,spent)

    def test_governance_recheck_is_not_approval_and_native_review_reaches_receipts(self):
        f=fixture(responsibility=False);configure(f,process_owner_id=None);w=f['work'];a=f['actor']
        factory.run_until_wait(w.pk);w.refresh_from_db();task=HumanTask.objects.get(kind='factory_governance')
        task=factory.claim_task(a,task.pk,task.revision)
        with self.assertRaises(ValidationError):routing.recheck(a,task.pk,task.revision,'Not yet configured')
        configure(f);spent=w.budget_used
        routing.recheck(a,task.pk,task.revision,'Actual reviewed nominations now configured')
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())
        self.assertFalse(TaskEvent.objects.get(action='factory.owners_rechecked').data['approval_granted'])
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertGreater(w.budget_used,spent)
        review=approve(f);self.assertEqual(review.publication_packet['factory_responsibility']['status'],'ACTIVE')
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)

    def test_changed_assignment_invalidates_claim_and_exact_approval_without_erasing_history(self):
        f=fixture();w=f['work'];a=f['actor'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review');task=factory.claim_task(a,task.pk,task.revision)
        first=deepcopy(task.context['packet']);configure(f)
        with self.assertRaises(ValidationError):factory.decide(a,task.pk,task.revision,'approve',f['proof'].pk,'Old packet')
        factory.run_until_wait(w.pk);task.refresh_from_db();self.assertEqual(task.status,'returned')
        self.assertEqual(task.context['packet'],first);approved=approve(f)
        configure(f,policy_owner_id=None)
        with self.assertRaises(ValidationError):invoices.reviewed(approved.invoice)
        with self.assertRaises(ValidationError):invoices.reserve(a,f['case'].pk,approved.invoice_id,'issue','Finance',rev(f['case']),factory_work_id=w.pk)
        self.assertEqual(InvoiceReview.objects.count(),1);self.assertFalse(InvoiceIssue.objects.exists())

    def test_nominations_do_not_grant_native_review_and_revoked_governance_cannot_recheck(self):
        f=fixture(responsibility=False);a=f['actor'];w=f['work'];configure(f,activity_owner_id=None)
        factory.run_until_wait(w.pk);w.refresh_from_db();task=HumanTask.objects.get(kind='factory_governance');task=factory.claim_task(a,task.pk,task.revision)
        configure(f)
        Grant.objects.filter(case=f['case'],user=a,action='policy.configure').update(active=False)
        with self.assertRaises(PermissionDenied):routing.recheck(a,task.pk,task.revision,'Revoked resolver')
        Grant.objects.filter(case=f['case'],user=a,action='finance.invoice.review').update(active=False)
        self.assertEqual(routing.evaluate(w)['eligible_principals'],[])
        self.assertIn('eligible_finance_reviewer',routing.evaluate(w)['missing'])
        self.assertFalse(InvoiceReview.objects.exists())

    def test_policy_ui_and_validator_reject_cross_scope_bool_float_and_unimplemented_methods(self):
        f=fixture();a=f['actor'];c=f['case'];client=Client();client.force_login(a)
        url=reverse('factory_responsibility',args=[c.pk]);self.assertContains(client.get(url),'Invoice responsibilities')
        data={'action':'draft','process_owner_id':'','activity_owner_id':'','policy_owner_id':'','governance_resolver_id':a.pk,'evidence':f['evidence']['policy_decision'].pk}
        self.assertEqual(client.post(url,data).status_code,302)
        config=__import__('apps.policy.models',fromlist=['Configuration']).Configuration.objects.filter(case=c,component=COMPONENT).latest('pk')
        self.assertEqual(client.post(url,{'action':'transition','configuration':config.pk,'state':'validated'}).status_code,302)
        self.assertEqual(client.post(url,{'action':'transition','configuration':config.pk,'state':'active'}).status_code,302)
        self.assertEqual(routing.binding(f['work'])['configuration'],config.pk)
        for changes in [{'process_owner_id':True},{'activity_owner_id':float(a.pk)},{'method':'quorum'},{'process_id':'P02'},{'governance_resolver_id':999999}]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):configure(f,**changes)
        foreign,_=setup_case(username='foreign-owner')
        with self.assertRaises(ValidationError):configure(f,policy_owner_id=foreign.pk)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(a);self.assertEqual(csrf.post(url,data).status_code,403)

    def test_governance_task_identity_is_immutable_and_stop_removes_controls(self):
        f=fixture(responsibility=False);configure(f,policy_owner_id=None);w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_governance')
        with self.assertRaises(DatabaseError),transaction.atomic():
            HumanTask.objects.filter(pk=task.pk).update(context={'work':w.pk,'approval_granted':True})
        task=factory.claim_task(f['actor'],task.pk,task.revision);w.refresh_from_db();factory.manage(f['actor'],w.pk,w.revision,'cancel')
        with self.assertRaises(ValidationError):routing.recheck(f['actor'],task.pk,task.revision,'Stopped')
        client=Client();client.force_login(f['actor']);response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertContains(response,'No action required');self.assertNotContains(response,'name="action" value="responsibility_recheck"')

    def test_positive_lost_response_is_reconciled_after_owner_revocation_without_resend(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db();approve(f)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            job=InvoiceJob.objects.get(kind='issue');self.assertEqual(job.status,'unknown')
            configure(f,process_owner_id=None)
            w.refresh_from_db()
            with override_settings(FACTORY_ADAPTERS={str(f['case'].pk):MockFactoryInvoiceAdapter(directory)}):factory.reconcile(f['actor'],w.pk,w.revision)
            job.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)
            with self.assertRaises(ValidationError):invoices.reserve(f['actor'],f['case'].pk,w.invoice_id,'deliver','Finance',rev(f['case']),factory_work_id=w.pk)
            self.assertFalse(InvoiceDelivery.objects.exists())

    def test_changed_ownership_retires_old_review_before_showing_governance_wait(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk)
        old=HumanTask.objects.get(kind='factory_review');configure(f,process_owner_id=None)
        factory.run_until_wait(w.pk);w.refresh_from_db();old.refresh_from_db()
        self.assertEqual(w.status,'owner_needed');self.assertEqual(old.status,'returned')
        from apps.workflows.factory_views import presentation
        row=presentation(f['actor'],w);self.assertEqual(row['state'],'Owner needed')
        self.assertFalse(any(t.can_decide for t in row['tasks']))
        self.assertFalse(InvoiceReview.objects.exists())

class FactoryRoutingConcurrencyTests(TransactionTestCase):
    def test_two_connections_cannot_complete_one_governance_wait_twice(self):
        f=fixture(responsibility=False);configure(f,policy_owner_id=None);w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_governance');task=factory.claim_task(f['actor'],task.pk,task.revision);configure(f)
        def compete(_):
            close_old_connections()
            try:routing.recheck(f['actor'],task.pk,task.revision,'Synthetic concurrent responsibility recheck');return 'recorded'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,range(2)))
        self.assertEqual(sorted(results),['recorded','stale'])
        self.assertEqual(TaskEvent.objects.filter(task=task,action='factory.owners_rechecked').count(),1)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())
