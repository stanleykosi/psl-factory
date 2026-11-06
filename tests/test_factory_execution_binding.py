"""Native reviewed recovery never rewrites the initiator, grant set or lifetime budget."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction,DatabaseError
from django.test import TestCase
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.factory_recovery_validators import COMPONENT,METHOD
from apps.workflows import factory_execution
from apps.workflows.models import FactoryWork,FactoryExecutionBinding
from apps.finance.models import InvoiceJob,InvoiceReview
from tests.factory_helpers import fixture

class FactoryExecutionBindingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data=fixture(username='execution-recovery-reviewer')
        cls.worker=get_user_model().objects.create_user(username='execution-recovery-worker')
        f=cls.data
        for action in ['case.read','finance.read','factory.read','factory.execute']:Grant.objects.create(case=f['case'],user=cls.worker,action=action)
        now=timezone.now()
        cls.rule=dict(definition='pmo-finance/v1',method=METHOD,principal_id=cls.worker.pk,reviewer_id=f['actor'].pk,
            review_role='Finance',independent_of_worker=True,valid_from=now.isoformat(),valid_until=(now+timedelta(hours=1)).isoformat())
        cls.policy=draft_operator_policy(f['actor'],f['case'].pk,COMPONENT,{'rules':[cls.rule]},f['evidence']['policy_decision'].pk,now)
        transition(f['actor'],cls.policy.pk,'validated');transition(f['actor'],cls.policy.pk,'active')

    def bind(self):
        f=self.data;return factory_execution.bind(f['actor'],f['work'].pk,f['work'].revision,f['evidence']['policy_decision'].pk,
            'Synthetic reviewed replacement authority; no business decision or grant supplied')

    def test_binding_preserves_the_original_starter_and_grants_and_budget(self):
        f=self.data;work=f['work'];before=FactoryWork.objects.values().get(pk=work.pk)
        grants=list(Grant.objects.filter(case=f['case']).order_by('pk').values())
        binding=self.bind();work.refresh_from_db()
        self.assertEqual(work.actor_id,f['actor'].pk);self.assertEqual(work.execution_actor_id,self.worker.pk)
        self.assertEqual(work.execution_binding_id,binding.pk);self.assertEqual(binding.previous_id,None)
        for key in ['budget_used','budget_limit','request','request_hash','business_key','created_at','source_head_id','invoice_id']:
            self.assertEqual(getattr(work,key),before[key])
        self.assertEqual(list(Grant.objects.filter(case=f['case']).order_by('pk').values()),grants)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())

    def test_withdrawn_binding_never_falls_back_to_the_original_starter(self):
        binding=self.bind();work=self.data['work'];work.refresh_from_db()
        transition(self.data['actor'],self.policy.pk,'revoked')
        with self.assertRaises(ValidationError):factory_execution.execution_actor(work)
        self.assertEqual(work.actor_id,self.data['actor'].pk);self.assertEqual(work.execution_binding_id,binding.pk)

    def test_useful_invoice_agent_work_uses_replacement_and_not_the_starter(self):
        from apps.workflows import factory
        from apps.agents.models import AgentRun
        f=self.data;Grant.objects.create(case=f['case'],user=self.worker,action='agent.extract')
        self.bind();Grant.objects.filter(case=f['case'],user=f['actor'],action='factory.execute').update(active=False)
        self.assertTrue(factory.run_once(f['work'].pk))
        f['work'].refresh_from_db();self.assertEqual(f['work'].actor_id,f['actor'].pk)
        self.assertEqual(f['work'].budget_used,100)
        self.assertTrue(AgentRun.objects.exists());self.assertEqual(set(AgentRun.objects.values_list('actor_id',flat=True)),{self.worker.pk})
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())

    def test_database_preserves_binding_and_starter_identity_and_refuses_pointer_reset(self):
        binding=self.bind();work=self.data['work'];work.refresh_from_db()
        for update in [dict(execution_binding_id=None,revision=work.revision+1,fence=work.fence+1),dict(actor_id=self.worker.pk)]:
            with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=work.pk).update(**update)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryExecutionBinding.objects.filter(pk=binding.pk).update(reason='Rewritten history')
        with self.assertRaisesMessage(ValidationError,'STALE_VERSION'):
            factory_execution.bind(self.data['actor'],work.pk,work.revision-1,self.data['evidence']['policy_decision'].pk,'Stale repeated command')
        self.assertEqual(FactoryExecutionBinding.objects.count(),1)

    def test_database_refuses_a_forged_rule_not_present_in_the_registered_policy(self):
        f=self.data;forged=dict(self.rule,principal_id=f['actor'].pk,independent_of_worker=False)
        with self.assertRaises(DatabaseError),transaction.atomic():
            FactoryExecutionBinding.objects.create(work=f['work'],previous=None,sequence=1,work_revision=f['work'].revision+1,
                principal=f['actor'],reviewer=f['actor'],configuration=self.policy,evidence=f['evidence']['policy_decision'],
                rule=forged,reason='Cannot manufacture authority from a different rule')
        self.assertFalse(FactoryExecutionBinding.objects.exists())

    def test_operator_reviews_exact_current_replacement_and_rejects_stale_post(self):
        from django.urls import reverse
        f=self.data;url=reverse('factory_execution_review',args=[f['work'].pk])
        self.client.force_login(f['actor'])
        response=self.client.get(url)
        self.assertContains(response,'Review worker replacement');self.assertContains(response,self.worker.username)
        self.assertEqual(response['Cache-Control'],'no-store')
        data={'revision':f['work'].revision,'evidence':f['evidence']['policy_decision'].pk,'reason':'Reviewed synthetic recovery'}
        self.assertEqual(self.client.post(url,data).status_code,302)
        response=self.client.post(url,data)
        self.assertContains(response,'STALE_VERSION');self.assertEqual(FactoryExecutionBinding.objects.count(),1)
        self.assertEqual(FactoryWork.objects.get(pk=f['work'].pk).actor_id,f['actor'].pk)

    def test_recovery_settings_preserve_other_rules_and_refuse_stale_draft(self):
        from django.urls import reverse
        from apps.policy.models import Configuration
        from apps.policy.services import reference_values
        f=self.data;url=reverse('factory_execution_configuration',args=[f['case'].pk])
        self.client.force_login(f['actor'])
        response=self.client.get(url);self.assertContains(response,'Worker recovery')
        data={'action':'draft','base':self.policy.pk,'definition':'planning/v1','evidence':f['evidence']['policy_decision'].pk}
        self.assertEqual(self.client.post(url,data).status_code,302)
        latest=Configuration.objects.filter(case=f['case'],component=COMPONENT).order_by('-revision').first()
        rules=reference_values(latest)[0]['rules']
        self.assertEqual(next(r for r in rules if r['definition']=='pmo-finance/v1'),self.rule)
        self.assertIsNone(next(r for r in rules if r['definition']=='planning/v1')['independent_of_worker'])
        self.assertContains(self.client.post(url,data),'Settings changed')
        self.assertEqual(Configuration.objects.filter(case=f['case'],component=COMPONENT).count(),2)
        self.assertFalse(FactoryExecutionBinding.objects.exists())

    def test_execute_permission_alone_cannot_review_recovery(self):
        from django.urls import reverse
        self.client.force_login(self.worker)
        response=self.client.post(reverse('factory_execution_review',args=[self.data['work'].pk]),
                                  {'revision':self.data['work'].revision,'evidence':self.data['evidence']['policy_decision'].pk,'reason':'Not an authorised reviewer'})
        self.assertEqual(response.status_code,403);self.assertFalse(FactoryExecutionBinding.objects.exists())

    def test_failed_claim_cannot_overwrite_a_successful_replacement_claim(self):
        from unittest.mock import patch
        from apps.workflows import factory
        f=self.data
        actual_claim=factory.claim
        def competing_claim(work_id):
            self.assertIsNotNone(actual_claim(work_id))
            raise ValidationError('A different attempted claim failed after the winner acquired its lease')
        with patch.object(factory,'claim',side_effect=competing_claim):
            self.assertFalse(factory.run_once(f['work'].pk))
        current=FactoryWork.objects.get(pk=f['work'].pk)
        self.assertGreater(current.lease_until,timezone.now());self.assertEqual(current.revision,f['work'].revision)
        self.assertEqual(current.finding,'');self.assertNotEqual(current.status,'blocked')
