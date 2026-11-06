"""An unavailable planner holds planning, not an independent native Finance decision."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.factory_coordinator_validators import SCOPE
from apps.identity.models import Grant
from apps.workflows import factory,factory_accounting
from apps.workflows.models import HumanTask
from apps.finance.models import FinanceReview
from apps.documents.models import PublicationReceipt
from apps.agents.models import AgentRun
from tests.finance_analysis_helpers import fixture,METRICS
from tests.factory_accounting_helpers import configured


class IndependentFinanceReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case,cls.evidence,_,_,source,template,_=fixture(username='independent-human-review',recipient_username='independent-human-reader')
        cls.coordination=draft_operator_policy(cls.actor,cls.case.pk,'OPS.factory_coordinator',dict(
            mode='internal_permitted_step_v1',contract_id=None,planner_id=cls.actor.pk,data_scope=SCOPE,max_output_chars=2048),
            cls.evidence['policy_decision'].pk,timezone.now())
        transition(cls.actor,cls.coordination.pk,'validated');transition(cls.actor,cls.coordination.pk,'active')
        cls.work=configured(cls.actor,cls.case,cls.evidence,source,template,METRICS,provider='governed_factory_v1')['work']
        factory.run_until_wait(cls.work.pk);cls.work.refresh_from_db()
        cls.task=HumanTask.objects.get(case=cls.case,kind='factory_accounting_review',context__purpose='output',status='open')

    def withdraw(self):
        transition(self.actor,self.coordination.pk,'revoked');self.client.force_login(self.actor)
        return reverse('factory_detail',args=[self.work.pk])

    def test_review_remains_visible_and_records_native_decision_without_planning_or_publication(self):
        url=self.withdraw();spent=self.work.budget_used;runs=AgentRun.objects.count()
        page=self.client.get(url);self.assertContains(page,'609.99');self.assertContains(page,'Claim Finance review')
        self.assertNotContains(page,'OPS.factory_coordinator');self.assertNotContains(page,'Continue eligible accounting work</button>')
        self.assertEqual(self.client.post(url,dict(action='claim',task=self.task.pk,task_revision=self.task.revision)).status_code,302)
        self.task.refresh_from_db()
        self.assertEqual(self.client.post(url,dict(action='decide',task=self.task.pk,task_revision=self.task.revision,
            verdict='approve',evidence=self.evidence['finance_review'].pk,reason='Synthetic exact native output reviewed while planning is unavailable')).status_code,302)
        self.assertEqual(FinanceReview.objects.filter(case=self.case,purpose='output',verdict='approve').count(),1)
        self.task.refresh_from_db();self.assertEqual(self.task.status,'completed')
        self.assertFalse(factory.run_once(self.work.pk))
        self.work.refresh_from_db();self.assertEqual(self.work.budget_used,spent)
        self.assertEqual(AgentRun.objects.count(),runs);self.assertFalse(PublicationReceipt.objects.exists())

    def test_withdrawal_does_not_widen_current_human_review_authority(self):
        url=self.withdraw();Grant.objects.filter(case=self.case,user=self.actor,action='finance.review').update(active=False)
        self.assertNotContains(self.client.get(url),'Claim Finance review')
        self.assertEqual(self.client.post(url,dict(action='claim',task=self.task.pk,task_revision=self.task.revision)).status_code,403)
        self.task.refresh_from_db();self.assertIsNone(self.task.claimed_by_id)
        self.assertFalse(FinanceReview.objects.filter(case=self.case,purpose='output').exists())

    def test_unavailable_execution_owner_does_not_hide_or_block_native_finance_review(self):
        Grant.objects.filter(case=self.case,user=self.actor,action='factory.execute').update(active=False)
        self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk])
        page=self.client.get(url);self.assertContains(page,'609.99');self.assertContains(page,'Claim Finance review')
        self.assertContains(page,'A current execution owner is required')
        self.assertTrue(page.context['row']['execution_owner_needed']);self.assertFalse(page.context['row']['can_advance'])
        task=factory_accounting.claim(self.actor,self.task.pk,self.task.revision)
        review=factory_accounting.decide(self.actor,task.pk,task.revision,'approve',self.evidence['finance_review'].pk,
            'Synthetic native Finance review without worker execution authority')
        self.assertEqual(review.purpose,'output');self.assertFalse(PublicationReceipt.objects.exists())

    def test_policy_read_projection_does_not_grant_calculation_or_private_basis_access(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import PermissionDenied
        from apps.finance import analysis
        reader=get_user_model().objects.create_user(username='policy-metadata-reader')
        for action in ['case.read','finance.read']:Grant.objects.create(case=self.case,user=reader,action=action)
        mapping=self.work.case.financerun_set.get(kind='mapping')
        source=mapping.source;request={'metrics':['revenue','staff_cost','opex','direct_cost','other']}
        with self.assertRaises(PermissionDenied):analysis.stage_snapshot(reader,source,'allocation',mapping,request)
        expected=analysis.stage_snapshot(self.actor,source,'allocation',mapping,request)[0]['policies']
        actual=analysis.stage_policy_components(reader,source,'allocation',mapping,request)
        self.assertEqual(set(actual),set(expected));self.assertTrue(all(isinstance(v,str) for v in actual))
