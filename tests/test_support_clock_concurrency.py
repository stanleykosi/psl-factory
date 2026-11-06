from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import close_old_connections,transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.baas import support_clock_corrections as d
from .support_clock_helpers import fixture,propose,confirm,successor
from .support_channel_helpers import claim
from .readiness_helpers import endpoint

class ClockConcurrencyTests(TransactionTestCase):
 def setUp(self):
  self.endpoint=endpoint();self.endpoint.__enter__();self.addCleanup(self.endpoint.__exit__,None,None,None);self.f=fixture('clock-concurrency')
 def parallel(self,fn):
  def run(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(run,[0,1]))
 def test_source_successor_and_competing_clock_proposals_have_single_lineage(self):
  f=self.f;claim(f);old=f['claim']
  ids=self.parallel(lambda _:d.successor(f['actor'],f['case'].pk,old.pk,'same','v2',f['e']['agent_private_channel_successor'].pk).pk);self.assertEqual(ids[0],ids[1])
  def propose_competing(n):
   try:return propose(f,'withdraw',key='candidate'+str(n)).pk
   except ValidationError:return None
  ids=self.parallel(propose_competing);self.assertEqual(sum(x is not None for x in ids),1);self.assertEqual(d.Correction.objects.count(),1)
 def test_ordered_source_revocation_prevents_human_correction_review(self):
  f=self.f;r=propose(f,'withdraw');locked=Event();proceed=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not proceed.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.private.read').update(active=False)
   finally:close_old_connections()
  def review():
   close_old_connections()
   try:
    try:confirm(f,r);return 'unexpected'
    except (ValidationError,PermissionDenied):return 'held'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(review);proceed.set();first.result(20);self.assertEqual(second.result(30),'held')
  self.assertFalse(d.Review.objects.exists())
