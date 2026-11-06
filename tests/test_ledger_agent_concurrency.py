from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import ledger_agents as d
from apps.agents import boundary as gateway,boundary_delivery as worker
from .ledger_agent_helpers import fixture,project,extracted,integration
from .ledger_resolution_helpers import second_case,propose,confirm,current
from .ledger_helpers import capture,verify
from .readiness_helpers import endpoint

class LedgerAgentConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture('ledger-agent-concurrency')
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def parallel(self,call):
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(lambda n:self.task(lambda:call(n)),[0,1]))
 def test_two_connections_same_projection_intent_make_one_binding(self):
  f=self.f;ids=self.parallel(lambda _:d.project(f['actor'],f['case'].pk,f['lineage'].pk,'same').pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(d.LedgerProjection.objects.count(),1)
 def test_two_connections_cannot_branch_human_draft_revision(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'revision')
   def call(n):
    try:return d.revise(f['actor'],f['case'].pk,draft.pk,'Human revision '+str(n)).pk
    except ValidationError:return 'held'
   values=self.parallel(call);self.assertEqual(values.count('held'),1);self.assertEqual(d.Draft.objects.count(),2)
 def test_foreign_private_grant_revocation_commits_before_provider_send(self):
  f=self.f;g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant']);b=capture(g);verify(g,b);verify(f,f['lineage']);r=propose(f,f['lineage'],[b]);confirm(f,r);current(f,f['lineage']);locked=Event();commit=Event()
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'scope')
   def first():
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=g['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=g['case'],user=f['actor'],action='ledger.private.read').update(active=False)
   with ThreadPoolExecutor(max_workers=2) as pool:
    one=pool.submit(self.task,first);self.assertTrue(locked.wait(10));two=pool.submit(self.task,lambda:worker.run_once(f['case'].pk));commit.set();one.result(timeout=40);two.result(timeout=40)
   j.refresh_from_db();self.assertEqual(j.status,'held');self.assertNotIn('private_inputs',remote)
