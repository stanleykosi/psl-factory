"""Two real PostgreSQL sessions may not authorise competing receipt reviews."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase,override_settings
from django.db import connection,close_old_connections
from django.core.exceptions import ValidationError
from apps.workflows import factory,factory_receipt_recovery as recovery
from apps.workflows.models import FactoryPlanningRecovery,FactoryPlanningReceipt
from apps.agents import factory_coordinator as coordinator
from tests.factory_coordinator_helpers import gateway
from tests.readiness_helpers import endpoint
from tests.helpers import rev
from tests import test_factory_receipt_recovery as helpers


class ReceiptRecoveryContentionTests(TransactionTestCase):
    def test_same_original_work_revision_has_one_review_and_two_distinct_backend_sessions(self):
        with endpoint() as state:
            f=gateway(state,prefix='receipt-contention');a,c,w=f['actor'],f['case'],f['work']
            state['lose_planning_response']=True;factory.run_once(w.pk);w.refresh_from_db();attempt=coordinator.pending(w)
            state['secret']='contention-rotated-synthetic-token';os.environ['PSL_TEST_READINESS_TOKEN']=state['secret']
            with override_settings(READINESS_SECRET_REFS={'secret:fixture':{'env':'PSL_TEST_READINESS_TOKEN','revision':'fixture-v2'}}):
                contract=helpers.ReceiptRecoveryTests.rotate(self,f);helpers.ReceiptRecoveryTests.configure(self,f)
                expected=w.revision;case_expected=rev(c);barrier=Barrier(2)
                def enter():
                    close_old_connections()
                    try:
                        with connection.cursor() as cur:cur.execute('SELECT pg_backend_pid()');pid=cur.fetchone()[0]
                        barrier.wait(timeout=30)
                        try:
                            recovery.review(a,w.pk,expected,case_expected,attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Actual concurrent receipt review')
                            return pid,'recorded'
                        except ValidationError as exc:
                            if 'STALE_VERSION' not in str(exc):raise
                            return pid,'stale'
                    finally:close_old_connections()
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:enter(),range(2)))
                self.assertEqual(len({pid for pid,_ in results}),2)
                self.assertEqual(sorted(outcome for _,outcome in results),['recorded','stale'])
                self.assertEqual(FactoryPlanningRecovery.objects.filter(attempt=attempt).count(),1)
                self.assertFalse(FactoryPlanningReceipt.objects.filter(attempt=attempt).exists())
                self.assertEqual(state['planning_calls'],1)

    def test_real_receipt_lookup_lease_prevents_another_human_transport_review(self):
        from threading import Event
        from unittest.mock import patch
        from adapters.factory_planner import FactoryPlannerAdapter
        with endpoint() as state:
            f=gateway(state,prefix='receipt-lease');a,c,w=f['actor'],f['case'],f['work']
            state['lose_planning_response']=True;factory.run_once(w.pk);w.refresh_from_db();attempt=coordinator.pending(w);spent=w.budget_used
            state['secret']='lease-rotated-synthetic-token';os.environ['PSL_TEST_READINESS_TOKEN']=state['secret']
            with override_settings(READINESS_SECRET_REFS={'secret:fixture':{'env':'PSL_TEST_READINESS_TOKEN','revision':'fixture-v2'}}):
                contract=helpers.ReceiptRecoveryTests.rotate(self,f);helpers.ReceiptRecoveryTests.configure(self,f)
                recovery.review(a,w.pk,w.revision,rev(c),attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Original finite receipt review')
                w.refresh_from_db();expected=w.revision;entered=Event();release=Event();lookup=FactoryPlannerAdapter.lookup
                def paused(adapter,intent,private):
                    entered.set()
                    if not release.wait(timeout=30):raise TimeoutError('Synthetic lookup barrier expired')
                    return lookup(adapter,intent,private)
                def run():
                    close_old_connections()
                    try:return coordinator.reconcile(a,w.pk,expected).pk
                    finally:close_old_connections()
                with patch.object(FactoryPlannerAdapter,'lookup',paused),ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(run)
                    try:
                        self.assertTrue(entered.wait(timeout=30));w.refresh_from_db()
                        with self.assertRaisesMessage(ValidationError,'CONFLICT'):
                            recovery.review(a,w.pk,w.revision,rev(c),attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Cannot replace an active receipt lookup')
                    finally:release.set()
                    self.assertEqual(future.result(timeout=60),w.pk)
                w.refresh_from_db();self.assertEqual(w.budget_used,spent)
                self.assertEqual(FactoryPlanningRecovery.objects.filter(attempt=attempt).count(),1)
                self.assertEqual(FactoryPlanningReceipt.objects.filter(attempt=attempt).count(),1)
                self.assertEqual(state['planning_calls'],1)
