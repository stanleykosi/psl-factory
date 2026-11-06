"""Native human work needs its own current authority, not a functioning planner."""
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.workflows import factory,factory_routing
from apps.workflows.models import HumanTask,TaskEvent
from apps.finance.models import InvoiceReview,InvoiceJob,Invoice
from apps.agents.models import AgentRun
from tests.factory_helpers import fixture
from tests.helpers import rev
from tests.test_factory_coordinator_recovery import configure
from tests.test_factory_routing import configure as route_configuration


class IndependentInvoiceReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data=fixture(username='independent-invoice-human',provider='governed_factory_v1')
        f=cls.data;cls.coordination=configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        cls.task=HumanTask.objects.get(case=f['case'],kind='factory_review',status='open')

    def withdraw(self):
        f=self.data;transition(f['actor'],self.coordination.pk,'revoked');self.client.force_login(f['actor'])
        return f,reverse('factory_detail',args=[f['work'].pk])

    def test_exact_native_review_continues_but_no_agent_or_invoice_effect_is_authorised(self):
        f,url=self.withdraw();work=f['work'];spent=work.budget_used;runs=AgentRun.objects.count()
        page=self.client.get(url);self.assertEqual(page.status_code,200)
        self.assertTrue(next(t for t in page.context['row']['tasks'] if t.pk==self.task.pk).can_claim)
        self.assertEqual(page.context['row']['state'],'Awaiting Finance decision')
        task=factory.claim_task(f['actor'],self.task.pk,self.task.revision)
        review=factory.decide(f['actor'],task.pk,task.revision,'approve',f['proof'].pk,'Synthetic exact invoice review while planning is unavailable')
        self.assertEqual(review.publication_packet,self.task.context['packet']);self.assertEqual(InvoiceReview.objects.count(),1)
        self.assertFalse(factory.run_once(work.pk));work.refresh_from_db()
        self.assertEqual(work.budget_used,spent);self.assertEqual(AgentRun.objects.count(),runs);self.assertFalse(InvoiceJob.objects.exists())

    def test_current_finance_permission_is_still_required(self):
        f,url=self.withdraw();Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.invoice.review').update(active=False)
        with self.assertRaisesMessage(ValidationError,'STALE_AUTHORITY'):
            factory.claim_task(f['actor'],self.task.pk,self.task.revision)
        page=self.client.get(url)
        self.assertFalse(next(t for t in page.context['row']['tasks'] if t.pk==self.task.pk).can_claim)
        self.assertFalse(InvoiceReview.objects.exists())

    def test_changed_native_routing_still_invalidates_the_old_subject(self):
        f,_=self.withdraw();route_configuration(f)
        with self.assertRaises(ValidationError):factory.claim_task(f['actor'],self.task.pk,self.task.revision)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())


class IndependentInformationTests(TestCase):
    def test_requested_information_can_be_supplied_with_planning_withdrawn(self):
        f=fixture(username='independent-information-human',provider='governed_factory_v1',missing=True)
        policy=configure(f['actor'],f['case'],f['evidence']['policy_decision']);factory.run_until_wait(f['work'].pk)
        work=f['work'];work.refresh_from_db();spent=work.budget_used
        transition(f['actor'],policy.pk,'revoked');task=HumanTask.objects.get(case=f['case'],kind='factory_information',status='open')
        self.client.force_login(f['actor']);page=self.client.get(reverse('factory_detail',args=[work.pk]))
        self.assertTrue(next(t for t in page.context['row']['tasks'] if t.pk==task.pk).can_claim)
        task=factory.claim_task(f['actor'],task.pk,task.revision)
        proof=factory.provide_information(f['actor'],task.pk,task.revision,rev(f['case']),'factory_information',
            'Synthetic requested acceptance reference supplied by the configured owner','synthetic:human-information')
        self.assertEqual(TaskEvent.objects.get(task=task,action='factory.information_received').data['evidence'],proof.pk)
        self.assertFalse(factory.run_once(work.pk));work.refresh_from_db();self.assertEqual(work.budget_used,spent)
        self.assertFalse(Invoice.objects.exists())


class IndependentResponsibilityTests(TestCase):
    def test_human_owner_recheck_is_not_planning_or_finance_approval(self):
        f=fixture(username='independent-responsibility-human',provider='governed_factory_v1',responsibility=False)
        route_configuration(f,process_owner_id=None);policy=configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db();spent=f['work'].budget_used
        transition(f['actor'],policy.pk,'revoked');task=HumanTask.objects.get(case=f['case'],kind='factory_governance',status='open')
        task=factory.claim_task(f['actor'],task.pk,task.revision);route_configuration(f)
        self.client.force_login(f['actor']);page=self.client.get(reverse('home'),{'queue':'needs_me'})
        row=next(row for row in page.context['rows'] if row['work'].pk==f['work'].pk)
        self.assertEqual(row['next_action'],'Review responsibility assignments and recheck the current Finance route')
        factory_routing.recheck(f['actor'],task.pk,task.revision,'Synthetic current owners validated independently of planning')
        self.assertFalse(TaskEvent.objects.get(task=task,action='factory.owners_rechecked').data['approval_granted'])
        self.assertFalse(factory.run_once(f['work'].pk));f['work'].refresh_from_db()
        self.assertEqual(f['work'].budget_used,spent);self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())


from django.test import TransactionTestCase

class IndependentResponsibilityConcurrencyTests(TransactionTestCase):
    def test_two_connections_close_one_wait_while_planning_is_withdrawn(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        f=fixture(username='independent-concurrent-human',provider='governed_factory_v1',responsibility=False)
        route_configuration(f,policy_owner_id=None);policy=configure(f['actor'],f['case'],f['evidence']['policy_decision'])
        factory.run_until_wait(f['work'].pk)
        task=HumanTask.objects.get(case=f['case'],kind='factory_governance',status='open')
        task=factory.claim_task(f['actor'],task.pk,task.revision);route_configuration(f);transition(f['actor'],policy.pk,'revoked')
        def recheck():
            close_old_connections()
            try:factory_routing.recheck(f['actor'],task.pk,task.revision,'Synthetic concurrent owner recheck');return 'recorded'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:recheck(),range(2)))
        self.assertEqual(sorted(results),['recorded','stale'])
        self.assertEqual(TaskEvent.objects.filter(task=task,action='factory.owners_rechecked').count(),1)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())
