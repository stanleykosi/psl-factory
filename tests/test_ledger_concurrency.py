from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.finance import ledger
from apps.identity.models import Grant
from .ledger_helpers import fixture,capture,verify,review,evidence
class LedgerConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,call):
  def task(n):
   close_old_connections()
   try:return call(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
 def race(self,mutation,action):
  locked=Event();commit=Event();f=self.f
  def first():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     mutation()
   finally:close_old_connections()
  def second():
   close_old_connections()
   try:
    try:action()
    except (ValidationError,PermissionDenied):return 'held'
    return 'used'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(first);self.assertTrue(locked.wait(10));b=pool.submit(second);commit.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')
 def test_two_connections_duplicate_capture_cannot_create_verified_route(self):
  f=self.f;e=evidence(f,'ledger_source',f['v']['source']);ids=self.parallel(lambda _:ledger.capture(f['actor'],f['case'].pk,e.pk).pk);self.assertNotEqual(ids[0],ids[1])
  for pk in ids:self.assertEqual(verify(f,ledger.exact(f['case'],pk)).status,'held')
 def test_cross_case_duplicate_claims_are_serialised_and_held(self):
  f=self.f;g=fixture('cross-case-preparer','cross-case-reviewer');es=[evidence(z,'ledger_source',z['v']['source']) for z in [f,g]]
  def call(n):
   z=[f,g][n];return ledger.capture(z['actor'],z['case'].pk,es[n].pk).pk
  ids=self.parallel(call)
  for z,pk in zip([f,g],ids):self.assertEqual(verify(z,ledger.exact(z['case'],pk)).status,'held')
 def test_duplicate_commits_before_finance_review(self):
  f=self.f;w=capture(f);x=verify(f,w);self.race(lambda:capture(f),lambda:ledger.review(f['reviewer'],f['case'].pk,x.pk,f['e'].pk))
 def test_reviewer_revocation_commits_before_report(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);self.race(lambda:Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.review').update(active=False),lambda:ledger.report(f['actor'],f['case'].pk,w.pk))
