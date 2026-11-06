from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.finance import ppe
from apps.finance.models import ScheduleWork
from apps.identity.models import Grant
from adapters.ppe import LocalPPEReportAdapter
from .ppe_helpers import fixture,prepare,review,capture
class PPEConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,call):
  def task(n):
   close_old_connections()
   try:return call(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
 def test_two_connections_prepare_one_exact_schedule(self):
  f=self.f;ids=self.parallel(lambda _:ppe.prepare(f['actor'],f['case'].pk,'same',f['register'].pk,None,f['parent'].pk,None).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(ScheduleWork.objects.filter(kind='ppe_schedule').count(),1)
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
 def test_source_correction_commits_before_review_and_holds_old_output(self):
  f=self.f;w=prepare(f)
  self.race(lambda:capture(f),lambda:ppe.review(f['reviewer'],f['case'].pk,w.pk,'schedule','approve',f['e']['finance_review'].pk,'Old output',None))
 def test_reviewer_grant_revocation_commits_before_report_read(self):
  f=self.f;w=prepare(f);review(f,w)
  self.race(lambda:Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ppe.review').update(active=False),lambda:LocalPPEReportAdapter().read(f['reviewer'],w))
