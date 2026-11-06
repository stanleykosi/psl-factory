"""Real lease expiry and a second PostgreSQL connection; no clock or lease rewriting."""
import time
from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.utils import timezone
from apps.agents.factory_coordinator import PlanningUnknown
from apps.workflows import factory
from apps.workflows.models import FactoryWork,FactoryAttempt,FactoryPlanningReceipt
from apps.finance.models import Invoice
from tests.factory_helpers import fixture


class FactoryWorkerExpiryTests(TransactionTestCase):
    def check_late_worker(self, outcome):
        f=fixture(username='expired-'+outcome,lease_seconds=1);pk=f['work'].pk
        replacement={}
        def take_over():
            close_old_connections()
            try:
                replacement['token']=factory.claim(pk)
                replacement['state']=FactoryWork.objects.values().get(pk=pk)
            finally:close_old_connections()
        class SlowProvider:
            def choose(self,context):
                lease=FactoryWork.objects.get(pk=pk).lease_until
                time.sleep(max(0,(lease-timezone.now()).total_seconds())+.05)
                with ThreadPoolExecutor(max_workers=1) as pool:pool.submit(take_over).result(timeout=20)
                if outcome=='unknown':raise PlanningUnknown('Test response unavailable')
                if outcome=='rejected':return {'activity':'ACT11','citations':[]}
                return {'activity':context['eligible'][0],'citations':context['evidence_ids'][:1]}
        self.assertFalse(factory.run_once(pk,provider=SlowProvider()))
        self.assertIsNotNone(replacement['token'])
        self.assertEqual(FactoryWork.objects.values().get(pk=pk),replacement['state'])
        self.assertFalse(FactoryAttempt.objects.filter(phase__in=['failed','observed']).exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertEqual(replacement['state']['budget_used'],100)

    def test_late_answer_cannot_finalize_or_fail_the_new_workers_claim(self):self.check_late_worker('answer')
    def test_late_unknown_response_cannot_park_the_new_workers_claim(self):self.check_late_worker('unknown')

    def test_authenticated_receipt_survives_expiry_without_stale_worker_mutation_or_resend(self):
        from threading import Event
        from tests.readiness_helpers import endpoint
        from tests.factory_coordinator_helpers import gateway
        with endpoint() as state:
            f=gateway(state,prefix='expired-gateway',lease_seconds=10);pk=f['work'].pk
            entered=Event();release=Event();state.update(planning_entered=entered,planning_release=release)
            def advance():
                close_old_connections()
                try:return factory.run_once(pk)
                finally:close_old_connections()
            with ThreadPoolExecutor(max_workers=1) as pool:
                first=pool.submit(advance)
                try:
                    self.assertTrue(entered.wait(timeout=20))
                    with transaction.atomic():
                        work=FactoryWork.objects.select_for_update().get(pk=pk)
                        release.set()
                        time.sleep(max(0,(work.lease_until-timezone.now()).total_seconds())+.05)
                        token=factory.claim(pk);self.assertIsNotNone(token)
                        replacement=FactoryWork.objects.values().get(pk=pk)
                finally:release.set()
                self.assertFalse(first.result(timeout=30))
            self.assertEqual(FactoryWork.objects.values().get(pk=pk),replacement)
            self.assertEqual(FactoryPlanningReceipt.objects.count(),1)
            self.assertFalse(FactoryAttempt.objects.filter(phase__in=['failed','observed']).exists())
            self.assertEqual(state['planning_calls'],1);self.assertEqual(replacement['budget_used'],100)
