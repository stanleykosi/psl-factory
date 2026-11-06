from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import hrfinance as domain
from apps.finance.models import HRReadSnapshot
from .hrfinance_helpers import fixture,body,capture
class HRFinanceConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def test_two_connections_capture_same_export_once(self):
  f=self.f;raw=body(f)
  def work(_):
   close_old_connections()
   try:return domain.capture(f['hr'],f['case'].pk,f['contract'].pk,'same',raw,None).pk
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(work,[1,2]))
  self.assertEqual(rows[0],rows[1]);self.assertEqual(HRReadSnapshot.objects.count(),1)
 def test_recipient_revocation_before_read_serializes_and_blocks_rows(self):
  f=self.f;s=capture(f);locked=Event();commit=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['finance'],action='hrfinance.snapshot.read').update(active=False)
   finally:close_old_connections()
  def read():
   close_old_connections()
   try:
    try:domain.read_snapshot(f['finance'],s)
    except PermissionDenied:return 'held'
    return 'read'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(read);commit.set();first.result(timeout=30);self.assertEqual(second.result(timeout=30),'held')
