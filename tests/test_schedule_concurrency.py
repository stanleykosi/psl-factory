from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import schedules as d
from apps.finance.models import ScheduleWork,ScheduleAdjustment,FinanceAdjustment
from adapters.schedules import LocalScheduleReportAdapter
from .schedule_helpers import fixture,detail,row,review

class ScheduleConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,call):
  def task(n):
   close_old_connections()
   try:return call(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
 def test_two_connections_prepare_same_intent_once(self):
  f=self.f;payload=f['values']['detail']
  for r in payload['rows']:r['evidence_id']=f['e']['income_detail'].pk
  ids=self.parallel(lambda _:d.prepare(f['actor'],f['case'].pk,'income','same',f['parent'].pk,payload,f['e']['income_detail'].pk,None).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(ScheduleWork.objects.count(),1)
 def test_two_connections_export_one_reviewed_adjustment(self):
  f=self.f;w=detail(f,[row(f,'add','20','additive',lines=[{'account':'sales','amount':'20'}])]);review(f,w)
  ids=self.parallel(lambda _:d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,None).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(ScheduleAdjustment.objects.count(),1);self.assertEqual(FinanceAdjustment.objects.count(),1)
 def test_committed_reviewer_revocation_blocks_second_connection_report(self):
  f=self.f;w=detail(f);review(f,w);locked=Event();commit=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.review').update(active=False)
   finally:close_old_connections()
  def read():
   close_old_connections()
   try:
    try:LocalScheduleReportAdapter().read(f['reviewer'],w)
    except PermissionDenied:return 'held'
    return 'read'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(revoke);self.assertTrue(locked.wait(10));b=pool.submit(read);commit.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')
 def test_committed_successor_blocks_old_review_on_second_connection(self):
  f=self.f;w=detail(f);locked=Event();commit=Event()
  def revise():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     d.prepare(f['actor'],f['case'].pk,'income','income',f['parent'].pk,dict(w.payload,rows=[row(f,'corrected','-1000')]),f['e']['income_detail'].pk,None)
   finally:close_old_connections()
  def approve():
   close_old_connections()
   try:
    try:d.review(f['reviewer'],f['case'].pk,w.pk,'approve',f['e']['finance_review'].pk,'Old revision',None)
    except ValidationError:return 'held'
    return 'approved'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(revise);self.assertTrue(locked.wait(10));b=pool.submit(approve);commit.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')
