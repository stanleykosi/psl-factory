"""Opaque planning protocol over real authenticated HTTP and native PostgreSQL services."""
import json
from django.test import TestCase
from apps.workflows import factory
from apps.workflows.models import FactoryPlanningReceipt,HumanTask
from apps.finance.models import FinanceRun
from tests.readiness_helpers import endpoint
from tests.factory_coordinator_helpers import gateway

class FactoryPlannerGatewayTests(TestCase):
    def test_incorrect_independent_planning_canary_holds_only_factory_planning(self):
        with endpoint() as state:
            state['planning_canary_output']={'activity':'ACT11','citations':['probe0']}
            f=gateway(state,prefix='bad-canary',expect_ready=False);work=f['work']
            self.assertFalse(f['assessment'].result['capability_ready'])
            self.assertFalse(factory.run_once(work.pk));work.refresh_from_db()
            self.assertEqual(work.budget_used,0);self.assertEqual(work.status,'configuration_needed')
            self.assertEqual(state['planning_evaluations'],1);self.assertEqual(state.get('planning_calls',0),0)
            self.assertFalse(FactoryPlanningReceipt.objects.exists())

    def test_reviewed_gateway_prepares_accounting_with_only_opaque_metadata(self):
        with endpoint() as state:
            f=gateway(state);work=f['work'];factory.run_until_wait(work.pk);work.refresh_from_db()
            self.assertEqual(work.status,'waiting',work.finding)
            self.assertTrue(HumanTask.objects.filter(case=f['case'],kind='factory_accounting_review',context__purpose='output',status='open').exists())
            self.assertTrue(FactoryPlanningReceipt.objects.exists());self.assertFalse(FactoryPlanningReceipt.objects.filter(valid=False).exists())
            from apps.workflows import factory_accounting
            task=HumanTask.objects.get(case=f['case'],kind='factory_accounting_review',context__purpose='output',status='open')
            task=factory_accounting.claim(f['actor'],task.pk,task.revision)
            factory_accounting.decide(f['actor'],task.pk,task.revision,'approve',f['evidence']['finance_review'].pk,'Synthetic exact report reviewed independently of provider planning')
            factory.run_until_wait(work.pk);work.refresh_from_db();self.assertEqual(work.status,'verified',work.finding)
            from apps.documents.models import PublicationReceipt
            self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=work).count(),1)
            for body in state['planning_inputs']:
                self.assertEqual(set(body),{'protocol','model_id','data_scope','eligible','citation_handles','tools','token_limit','max_output_chars'})
                self.assertEqual(body['tools'],[])
                self.assertEqual(body['token_limit'],100);self.assertEqual(body['max_output_chars'],2048)
                self.assertTrue(all(isinstance(key,str) and key.startswith('c') for key in body['citation_handles']))
                self.assertNotIn(str(f['case'].pk),json.dumps(body));self.assertNotIn(f['actor'].username,json.dumps(body))

    def test_lost_response_recovers_original_receipt_and_reservation_without_another_send(self):
        from apps.agents import factory_coordinator as coordinator
        with endpoint() as state:
            f=gateway(state,prefix='lost-plan');work=f['work'];state['lose_planning_response']=True
            self.assertFalse(factory.run_once(work.pk));work.refresh_from_db()
            self.assertEqual(work.status,'waiting_effect',work.finding);spent=work.budget_used
            self.assertEqual(state['planning_calls'],1);self.assertFalse(FactoryPlanningReceipt.objects.exists())
            self.assertTrue(factory.run_once(work.pk));work.refresh_from_db()
            self.assertEqual(work.status,'ready');self.assertEqual(work.budget_used,spent)
            self.assertEqual(FactoryPlanningReceipt.objects.count(),1);self.assertEqual(state['planning_calls'],1)
            self.assertTrue(factory.run_once(work.pk));work.refresh_from_db()
            self.assertEqual(work.budget_used,spent);self.assertEqual(state['planning_calls'],1)
            self.assertIsNone(coordinator.pending(work));self.assertFalse(FinanceRun.objects.exists())

    def test_cancellation_keeps_original_planning_uncertainty_until_receipt_is_observed(self):
        from apps.agents import factory_coordinator
        with endpoint() as state:
            f=gateway(state,prefix='cancel-plan');work=f['work'];state['lose_planning_response']=True
            factory.run_once(work.pk);work.refresh_from_db();spent=work.budget_used
            factory.manage(f['actor'],work.pk,work.revision,'cancel');work.refresh_from_db()
            self.assertTrue(work.cancel_requested);self.assertEqual(work.status,'waiting_effect')
            factory_coordinator.reconcile(f['actor'],work.pk,work.revision);work.refresh_from_db()
            self.assertEqual(work.status,'cancelled');self.assertEqual(work.budget_used,spent)
            self.assertEqual(state['planning_calls'],1);self.assertFalse(FinanceRun.objects.exists())

    def test_malformed_nonfinite_provider_response_remains_unknown_without_resend(self):
        with endpoint() as state:
            f=gateway(state,prefix='malformed-plan');state['planning_output']={'activity':float('nan'),'citations':['c0']}
            factory.run_once(f['work'].pk);f['work'].refresh_from_db();spent=f['work'].budget_used
            self.assertEqual(f['work'].status,'waiting_effect')
            factory.run_once(f['work'].pk);f['work'].refresh_from_db()
            self.assertEqual(state['planning_calls'],1);self.assertEqual(f['work'].budget_used,spent)
            self.assertFalse(FactoryPlanningReceipt.objects.exists());self.assertFalse(FinanceRun.objects.exists())


from django.test import TransactionTestCase

class FactoryPlannerConcurrencyTests(TransactionTestCase):
    def test_two_actual_connections_share_one_live_planning_request_and_reservation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import close_old_connections
        with endpoint() as state:
            f=gateway(state,prefix='concurrent-plan');work=f['work']
            entered=Event();release=Event();state.update(planning_entered=entered,planning_release=release)
            def advance():
                close_old_connections()
                try:return factory.run_once(work.pk)
                finally:close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(advance)
                try:
                    self.assertTrue(entered.wait(timeout=20))
                    second=pool.submit(advance);self.assertFalse(second.result(timeout=20))
                finally:release.set()
                self.assertTrue(first.result(timeout=30))
            work.refresh_from_db();self.assertEqual(work.budget_used,100);self.assertEqual(state['planning_calls'],1)
            self.assertEqual(FactoryPlanningReceipt.objects.count(),1)

class FactoryPlannerGuardTests(TestCase):

    def test_no_receipt_cannot_dispatch_business_work(self):
        with endpoint() as state:
            f=gateway(state,prefix='absent-plan');work=f['work']
            state.update(lose_planning_response=True,planning_no_commit=True)
            factory.run_once(work.pk);work.refresh_from_db();spent=work.budget_used
            self.assertFalse(factory.run_once(work.pk));work.refresh_from_db()
            self.assertEqual(work.status,'waiting_effect');self.assertEqual(work.budget_used,spent)
            self.assertEqual(state['planning_calls'],1);self.assertFalse(FinanceRun.objects.exists())

    def test_forbidden_choice_is_rejected_without_raw_output_or_business_action(self):
        with endpoint() as state:
            f=gateway(state,prefix='forbidden-plan');state['planning_output']={'activity':'ACT11','citations':['c0'],'approve':True}
            self.assertFalse(factory.run_once(f['work'].pk));f['work'].refresh_from_db()
            self.assertEqual(f['work'].status,'blocked');receipt=FactoryPlanningReceipt.objects.get()
            self.assertFalse(receipt.valid);self.assertEqual(receipt.result,{})
            self.assertNotIn('approve',json.dumps(receipt.result));self.assertFalse(FinanceRun.objects.exists())

    def test_operator_ui_recovers_receipt_after_policy_withdrawal_without_new_authority(self):
        from django.urls import reverse
        from django.test import Client
        from apps.policy.services import transition
        with endpoint() as state:
            f=gateway(state,prefix='operator-plan');work=f['work'];state['lose_planning_response']=True
            factory.run_once(work.pk);work.refresh_from_db();spent=work.budget_used
            transition(f['actor'],f['coordination'].pk,'revoked')
            self.client.force_login(f['actor']);url=reverse('factory_detail',args=[work.pk])
            page=self.client.get(url);self.assertEqual(page.status_code,200);self.assertContains(page,'Check original planning response')
            secure=Client(enforce_csrf_checks=True);secure.force_login(f['actor'])
            lookup=reverse('factory_coordinator_reconcile',args=[work.pk])
            self.assertEqual(secure.post(lookup,{'revision':work.revision}).status_code,403)
            response=self.client.post(lookup,{'revision':work.revision});self.assertEqual(response.status_code,302)
            work.refresh_from_db();self.assertEqual(work.budget_used,spent);self.assertEqual(state['planning_calls'],1)
            self.assertEqual(FactoryPlanningReceipt.objects.count(),1)
            self.assertFalse(factory.run_once(work.pk));self.assertFalse(FinanceRun.objects.exists())

    def test_database_refuses_a_forged_choice_and_current_access_controls_lookup(self):
        from django.db import transaction,DatabaseError
        from apps.agents import factory_coordinator
        from apps.identity.models import Grant
        from django.core.exceptions import PermissionDenied
        with endpoint() as state:
            f=gateway(state,prefix='scope-plan');work=f['work'];state.update(lose_planning_response=True,planning_no_commit=True)
            factory.run_once(work.pk);work.refresh_from_db();attempt=factory_coordinator.pending(work)
            with self.assertRaises(DatabaseError),transaction.atomic():
                FactoryPlanningReceipt.objects.create(attempt=attempt,actor=f['actor'],valid=True,
                    result={'activity':'ACT11','citations':[f['source'].evidence_id]},output_sha256='a'*64,binding=attempt.result['binding'])
            Grant.objects.filter(case=f['case'],user=f['actor'],action='factory.execute').update(active=False)
            with self.assertRaises(PermissionDenied):factory_coordinator.reconcile(f['actor'],work.pk,work.revision)
            self.assertEqual(state['planning_calls'],1);self.assertFalse(FactoryPlanningReceipt.objects.exists())
