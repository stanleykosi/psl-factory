from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import payroll as domain
from apps.finance.models import PayrollInput,PayrollPublication
from .payroll_helpers import fixture,body,pipeline

class PayrollConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,work):
  def connection_work(n):
   close_old_connections()
   try:return work(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(connection_work,[1,2]))
 def test_two_connections_capture_identical_source_once(self):
  f=self.f;raw=body(f,0)
  ids=self.parallel(lambda _:domain.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-A','concurrent-capture',raw,None).pk)
  self.assertEqual(ids[0],ids[1]);self.assertEqual(PayrollInput.objects.filter(operation_key='concurrent-capture').count(),1)
 def test_two_connections_publish_reviewed_aggregate_once(self):
  f=self.f;c,m,a,p=pipeline(f)
  ids=self.parallel(lambda _:domain.publish(f['preparer'],f['case'].pk,a.pk,'concurrent-publication',None).pk)
  self.assertEqual(ids[0],ids[1]);self.assertEqual(PayrollPublication.objects.filter(operation_key='concurrent-publication').count(),1)
  self.assertEqual(PayrollPublication.objects.count(),2)
 def test_revocation_committed_before_reader_blocks_private_values(self):
  f=self.f;c,m,a,p=pipeline(f);locked=Event();commit=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['preparer'],action='payroll.private.read').update(active=False)
   finally:close_old_connections()
  def read():
   close_old_connections()
   try:
    try:domain.private_run(f['preparer'],f['case'].pk,a.pk)
    except PermissionDenied:return 'held'
    return 'read'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(read);commit.set();first.result(timeout=30);self.assertEqual(second.result(timeout=30),'held')
