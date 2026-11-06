from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.finance import ledger,ledger_resolution as d
from apps.identity.models import Grant
from .ledger_resolution_helpers import fixture,aliases,propose,confirm,current,second_case
from .ledger_helpers import capture,verify

class LedgerResolutionConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def race(self,case,mutation,action):
  locked=Event();commit=Event()
  def first():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=case.pk);locked.set()
    if not commit.wait(10):raise AssertionError('Coordination timeout')
    mutation()
  def second():
   try:action()
   except (ValidationError,PermissionDenied):return 'held'
   return 'used'
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(self.task,first);self.assertTrue(locked.wait(10));b=pool.submit(self.task,second);commit.set();a.result(timeout=40);self.assertEqual(b.result(timeout=40),'held')
 def test_overlapping_proposals_serialize_and_only_latest_can_be_confirmed(self):
  f=self.f;a,b=aliases(f)
  with ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(self.task,lambda n=n:propose(f,a,[b],reference='parallel-'+str(n)).pk) for n in range(2)]
   ids=[x.result(timeout=40) for x in futures]
  old,new=[d.Resolution.objects.get(pk=pk) for pk in sorted(ids)]
  with self.assertRaises(ValidationError):confirm(f,old)
  confirm(f,new);self.assertTrue(current(f,a))
 def test_new_claim_commits_before_resolution_review(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);self.race(f['case'],lambda:capture(f),lambda:confirm(f,r));self.assertFalse(d.Review.objects.exists())
 def test_foreign_reviewer_revocation_commits_before_report(self):
  f=self.f;g=second_case(f);a=capture(f);b=capture(g);verify(f,a);verify(g,b);r=propose(f,a,[b]);confirm(f,r);current(f,a)
  self.race(g['case'],lambda:Grant.objects.filter(case=g['case'],user=f['reviewer'],action='ledger.resolve_review').update(active=False),lambda:ledger.report(f['actor'],f['case'].pk,a.pk))

 def test_cross_case_current_use_locks_all_principals_in_one_global_order(self):
  from time import monotonic,sleep
  from django.db import connection
  from django.contrib.auth import get_user_model
  f=self.f;g=second_case(f);a=capture(f);b=capture(g);verify(f,a);verify(g,b);r=propose(f,a,[b]);confirm(f,r);current(f,a)
  first,second=sorted([f['case'],g['case']],key=lambda c:c.pk)
  low=get_user_model().objects.create_user(username='global-lock-low');high=get_user_model().objects.create_user(username='global-lock-high')
  Grant.objects.create(case=second,user=low,action='case.read');Grant.objects.create(case=first,user=high,action='case.read')
  ready=Event();pid=[]
  def read():
   with connection.cursor() as cursor:cursor.execute('SELECT pg_backend_pid()');pid.append(cursor.fetchone()[0])
   ready.set();return ledger.report(f['actor'],f['case'].pk,a.pk)
  with ThreadPoolExecutor(max_workers=1) as pool:
   with transaction.atomic():
    get_user_model().objects.select_for_update().get(pk=low.pk)
    future=pool.submit(self.task,read);self.assertTrue(ready.wait(10))
    deadline=monotonic()+10
    while True:
     with connection.cursor() as cursor:cursor.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',[pid[0]]);row=cursor.fetchone()
     if row and row[0]=='Lock':break
     if monotonic()>deadline:raise AssertionError('Report never reached principal lock')
     sleep(.02)
    # An independent identity writer can lock the higher principal while the report waits for low.
    # The previous per-case user order held high already, causing this wait cycle.
    with connection.cursor() as cursor:cursor.execute("SET LOCAL lock_timeout='2s'")
    get_user_model().objects.select_for_update().get(pk=high.pk)
   self.assertEqual(future.result(timeout=40)['incumbent']['target_reference'],'QB-101')
