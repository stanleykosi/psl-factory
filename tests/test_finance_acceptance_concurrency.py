from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.finance import acceptance as d,ledger_agents as finance
from apps.documents import validation as af13
from apps.policy.ledger_validators import HANDOFF
from .finance_acceptance_helpers import fixture,draft,handoff,validate,af13_reviews,decide
from .ledger_resolution_helpers import second_case,propose,confirm,current
from .ledger_helpers import capture,verify,policy
from .readiness_helpers import endpoint

class FinanceAcceptanceConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def parallel(self,call):
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(lambda n:self.task(lambda:call(n)),[0,1]))
 def test_same_handoff_and_receipt_intents_commit_once_on_two_connections(self):
  f=fixture('finance-handoff-race')
  with endpoint():
   draft(f);ids=self.parallel(lambda _:d.prepare(f['actor'],f['case'].pk,f['draft'].pk,f['package'].pk,'same').pk);self.assertEqual(ids[0],ids[1]);f['handoff']=d.Handoff.objects.get();receipts=self.parallel(lambda _:decide(f,'receive').pk);self.assertEqual(receipts[0],receipts[1]);self.assertEqual(d.Decision.objects.count(),1)
 def test_two_explicit_successors_cannot_branch_to_different_packages(self):
  f=fixture('finance-handoff-branch')
  with endpoint():
   h=handoff(f);packages=[af13.prepare_package(f['actor'],f['case'].pk,'target-'+str(n),f['package'].payload,f['e'].pk,None) for n in [1,2]];policy(f,HANDOFF,dict(f['routing'],package_ids=[p.pk for p in packages]))
   def call(n):
    try:return d.prepare(f['actor'],f['case'].pk,f['draft'].pk,packages[n].pk,h.reference,h.pk).pk
    except ValidationError:return 'held'
   values=self.parallel(call);self.assertEqual(values.count('held'),1);self.assertEqual(d.Handoff.objects.count(),2)
 def test_foreign_grant_revocation_commits_before_acceptance_export(self):
  f=fixture('finance-handoff-scope');g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant']);Grant.objects.bulk_create([Grant(case=g['case'],user=f['acceptor'],action=k) for k in ACTIONS]);w=capture(g);verify(g,w);verify(f,f['lineage']);confirm(f,propose(f,f['lineage'],[w]));current(f,f['lineage']);locked=Event();commit=Event()
  with endpoint():
   validate(f);af13_reviews(f);decide(f,'accept')
   def revoke():
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=g['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=g['case'],user=f['acceptor'],action='ledger.private.read').update(active=False)
   def export():
    try:af13.acceptance_report(f['acceptor'],f['case'].pk,f['af13_reviews'][-1].pk);return 'leaked'
    except PermissionDenied:return 'denied'
   with ThreadPoolExecutor(max_workers=2) as pool:
    one=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));two=pool.submit(self.task,export);commit.set();one.result(timeout=60);self.assertEqual(two.result(timeout=60),'denied')
