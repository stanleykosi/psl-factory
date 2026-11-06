from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase,override_settings
from django.db import close_old_connections,transaction
from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import readiness_acceptance as d
from .private_readiness_helpers import fixture,configure,reviews,package
from .readiness_helpers import endpoint

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class PrivateReadinessConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_two_connections_prepare_one_exact_packet(self):
  with endpoint():
   f=fixture('private-owner-race');p=package(f,'two-writers')
   with ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(self.task,lambda:d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,p.pk,'one-intent').pk) for _ in range(2)]
    ids=[x.result(timeout=120) for x in futures]
   self.assertEqual(ids[0],ids[1]);self.assertEqual(d.Packet.objects.filter(case=f['case'],reference='one-intent').count(),1)
 def test_foreign_source_revocation_precedes_cached_accepted_export(self):
  with endpoint():
   f=fixture('private-owner-foreign',foreign=True);configure(f);reviews(f);self.assertEqual(d.export(f['actor'],f['case'].pk,f['packet'].pk)['packet'],f['packet'].pk)
   locked=Event();commit=Event()
   def revoke():
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
   def export():
    try:d.export(f['actor'],f['case'].pk,f['packet'].pk);return 'leaked'
    except PermissionDenied:return 'denied'
   with ThreadPoolExecutor(max_workers=2) as pool:
    one=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));two=pool.submit(self.task,export);commit.set();one.result(timeout=60);self.assertEqual(two.result(timeout=120),'denied')
