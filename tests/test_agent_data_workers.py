import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import close_old_connections,connections,transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.agents import boundary as d,boundary_delivery as w
from .agent_data_helpers import fixture_data,ready_data,data_policy
from .readiness_helpers import endpoint

class AgentDataWorkerTests(TransactionTestCase):
 def setUp(self):self.f=fixture_data('private-workers')
 def parallel(self,fn):
  def call(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as p:return list(p.map(call,[0,1]))
 def test_competing_projection_and_intent_reservations_and_workers(self):
  f=self.f;ids=self.parallel(lambda _:d.project(f['actor'],f['case'].pk,f['input'].pk,'P34','parallel',['Milestone evidence reviewed.']).pk);self.assertEqual(ids[0],ids[1])
  with endpoint() as remote:
   ready_data(f);ids=self.parallel(lambda _:d.reserve(f['actor'],f['case'].pk,f['projection'].pk,'parallel').pk);self.assertEqual(ids[0],ids[1]);self.parallel(lambda _:w.run_once(f['case'].pk));self.assertEqual(d.Receipt.objects.count(),2);self.assertEqual(len(remote['private_inputs']),2);self.assertEqual(d.Job.objects.count(),2)
 def test_reclaimed_fence_cannot_send_and_receipt_is_unique(self):
  f=self.f
  with endpoint() as remote:
   j=ready_data(f);pk,old=w.claim(f['case'].pk);d.Job.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=w.claim(f['case'].pk)
   with self.assertRaises(ValidationError):w.execute(pk,old)
   w.execute(pk,new);self.assertEqual(d.Receipt.objects.count(),1);self.assertEqual(len(remote['private_inputs']),1)
 def ordered(self,mutation):
  f=self.f;locked=Event();release=Event()
  with endpoint() as remote:
   j=ready_data(f);pk,fence=w.claim(f['case'].pk)
   def first():
    close_old_connections()
    try:
     with transaction.atomic():
      Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
      if not release.wait(10):raise AssertionError('Coordination timeout')
      mutation()
    finally:close_old_connections()
   def second():
    close_old_connections()
    try:
     try:w.execute(pk,fence)
     except (ValidationError,PermissionDenied):return 'held'
     return 'sent'
    finally:close_old_connections()
   with ThreadPoolExecutor(max_workers=2) as p:
    a=p.submit(first);self.assertTrue(locked.wait(10));b=p.submit(second);release.set();a.result(timeout=45);self.assertEqual(b.result(timeout=45),'held')
   self.assertNotIn('private_inputs',remote);self.assertFalse(d.Receipt.objects.exists())
 def test_grant_revocation_commits_before_private_send(self):
  f=self.f;self.ordered(lambda:Grant.objects.filter(case=f['case'],user=f['actor'],action='agent.data.source').update(active=False))
 def test_policy_replacement_commits_before_private_send(self):
  f=self.f;self.ordered(lambda:data_policy(f,dict(f['data_rules'],max_requests=4)))
 def test_case_scoped_worker_process_reconciles_committed_receipt_without_credentials(self):
  f=self.f
  with endpoint():
   j=ready_data(f);w.run_once(f['case'].pk);self.assertTrue(d.Receipt.objects.filter(job=j).exists())
  d.Job.objects.filter(pk=j.pk).update(status='leased',lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action__startswith='agent.data.').update(active=False)
  env=os.environ.copy();env.update(PGDATABASE=connections['default'].settings_dict['NAME'],PYTHONIOENCODING='utf-8')
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_private_evidence','--case',str(f['case'].pk),'--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60);self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
