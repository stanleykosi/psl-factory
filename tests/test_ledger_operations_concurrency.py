from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows import operator_inventory as inv,operator_recovery as ops
from apps.agents import boundary as gateway
from .ledger_agent_helpers import fixture,project,integration
from .ledger_operations_helpers import operators
from .ledger_resolution_helpers import second_case,propose,confirm,current
from .ledger_helpers import capture,verify
from .readiness_helpers import endpoint

class LedgerOperationsConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def reserve(self,f):
  project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');return gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'operator')
 def test_two_operators_cannot_retry_same_held_job_twice(self):
  f=fixture('ledger-ops-race');operators(f)
  with endpoint():
   j=self.reserve(f);gateway.Job.objects.filter(pk=j.pk).update(status='held',attempts=1)
   def call():
    try:ops.recover(f['actor'],f['case'].pk,'ledgerdata',j.pk,'retry','Concurrent original retry');return 'retried'
    except ValidationError:return 'held'
   with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:self.task(call),[0,1]))
   self.assertCountEqual(values,['retried','held']);j.refresh_from_db();self.assertEqual(j.attempts,1);self.assertEqual(gateway.Job.objects.count(),1)
 def test_foreign_revocation_commits_before_shared_inventory_snapshot(self):
  f=fixture('ledger-ops-scope');g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant']);w=capture(g);verify(g,w);verify(f,f['lineage']);confirm(f,propose(f,f['lineage'],[w]));current(f,f['lineage'])
  with endpoint():self.reserve(f)
  locked=Event();commit=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=g['case'].pk);locked.set()
    if not commit.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=g['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   one=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));two=pool.submit(self.task,lambda:ops.snapshot(f['actor'],f['case'].pk,'after-revocation'));commit.set();one.result(timeout=40);result=two.result(timeout=40)
  self.assertFalse(any(r['family']=='ledgerdata' for r in result.manifest['jobs']));self.assertIn('ledgerdata',result.manifest['omitted_families'])
