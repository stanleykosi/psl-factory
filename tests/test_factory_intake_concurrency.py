"""Real source-instruction fencing and original provider receipt dependencies."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase,TransactionTestCase
from django.db import connection,close_old_connections
from django.core.exceptions import ValidationError
from apps.core.models import Evidence,Audit
from apps.identity.models import Grant
from apps.workflows import factory,factory_delivery as delivery
from apps.agents import factory_coordinator as coordinator
from tests import test_factory_intake_authority as helpers
from tests.factory_delivery_provider_helpers import planning_provider
from tests.readiness_helpers import endpoint
from tests.helpers import rev


class IntakeReceiptDependencyTests(TestCase):
    def test_unknown_original_planning_receipt_must_be_reconciled_before_fresh_instruction(self):
        with endpoint() as state:
            f=helpers.IntakeAuthorityTests.setup_work(self,delivery);w=f.work
            planning_provider(f,state,'PMO Lead');state['lose_planning_response']=True
            factory.run_once(w.pk);w.refresh_from_db();self.assertEqual(w.status,'waiting_effect',w.finding)
            spent=w.budget_used;head=w.source_head_id;self.assertEqual(state['planning_calls'],1)
            Grant.objects.filter(case=f.case,user=f.starter,action='factory.start').update(active=False)
            with self.assertRaisesMessage(ValidationError,'original planning response'):delivery.reaffirmation(f.actor,w)
            self.assertFalse(Audit.objects.filter(case=f.case,action='factory.delivery_intake_reaffirmed').exists())
            coordinator.reconcile(f.actor,w.pk,w.revision);w.refresh_from_db()
            self.assertIsNotNone(delivery.reaffirmation(f.actor,w)[1])
            self.assertEqual(w.source_head_id,head);self.assertEqual(w.budget_used,spent)
            self.assertEqual(state['planning_calls'],1)


class IntakeContentionTests(TransactionTestCase):
    def test_one_fresh_instruction_per_work_revision_on_two_real_backend_connections(self):
        f=helpers.IntakeAuthorityTests.setup_work(self,delivery);w=f.work
        Grant.objects.filter(case=f.case,user=f.starter,action='factory.start').update(active=False)
        _,packet=delivery.reaffirmation(f.actor,w);expected=w.revision;case_expected=rev(f.case)
        head=w.source_head_id;spent=w.budget_used;barrier=Barrier(2)
        def enter():
            close_old_connections()
            try:
                with connection.cursor() as cur:cur.execute('SELECT pg_backend_pid()');pid=cur.fetchone()[0]
                barrier.wait(timeout=30)
                try:
                    delivery.reaffirm(f.actor,w.pk,expected,case_expected,f.e['requirements'].pk,'Actual simultaneous fresh instruction review',packet)
                    return pid,'recorded'
                except ValidationError as exc:
                    if 'stale' not in str(exc).lower():raise
                    return pid,'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:enter(),range(2)))
        self.assertEqual(len({pid for pid,_ in results}),2)
        self.assertEqual(sorted(result for _,result in results),['recorded','stale'])
        w.refresh_from_db();self.assertNotEqual(w.source_head_id,head);self.assertEqual(w.budget_used,spent)
        self.assertEqual(Evidence.objects.filter(case=f.case,kind=delivery.KIND).count(),2)
        self.assertEqual(Audit.objects.filter(case=f.case,action='factory.delivery_intake_reaffirmed').count(),1)
