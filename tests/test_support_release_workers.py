import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import close_old_connections,transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.core.models import Case
from apps.identity.models import Grant
from apps.baas import support_release as d,support_release_delivery as worker
from adapters.support_response import InternalSupportResponseAdapter
from .support_release_helpers import ready,packet,release
from .readiness_helpers import endpoint

class SupportReleaseWorkerTests(TransactionTestCase):
 def setUp(self):
  self.endpoint=endpoint();self.endpoint.__enter__();self.addCleanup(self.endpoint.__exit__,None,None,None);self.f=ready('response-race')
 def parallel(self,fn):
  def call(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(call,[0,1]))
 def test_competing_packet_intents_human_decisions_and_workers(self):
  f=self.f;ids=self.parallel(lambda _:packet(f).pk);self.assertEqual(ids[0],ids[1]);p=d.Packet.objects.get()
  def approve(_):
   try:return d.decide(f['reviewer'],f['case'].pk,p.pk,'release').pk
   except ValidationError:return None
  decisions=self.parallel(approve);self.assertEqual(len([x for x in decisions if x]),1);self.assertEqual(d.Job.objects.count(),1);self.parallel(lambda _:worker.run_once(f['case'].pk));self.assertEqual(d.Receipt.objects.count(),1);self.assertEqual(d.Job.objects.get().status,'confirmed')
 def test_recipient_revocation_commits_before_local_effect(self):
  f=self.f;j=release(f);pk,fence=worker.claim(f['case'].pk);locked=Event();proceed=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not proceed.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['actor'],action='support.response.receive').update(active=False)
   finally:close_old_connections()
  def deliver():
   close_old_connections()
   try:
    from django.core.exceptions import PermissionDenied
    try:worker.deliver_internal(pk,fence);return 'unexpected'
    except (PermissionDenied,ValidationError):return 'held'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(deliver);proceed.set();first.result(20);self.assertEqual(second.result(30),'held')
  self.assertFalse(d.Receipt.objects.exists())
 def test_separate_worker_recovers_committed_receipt_after_source_revocation(self):
  f=self.f;j=release(f)
  class LoseReply(InternalSupportResponseAdapter):
   def deliver(self,*args):super().deliver(*args);raise ConnectionError('lost reply')
  worker.run_once(f['case'].pk,LoseReply());Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
  env=dict(os.environ,DJANGO_SETTINGS_MODULE='config.settings',PYTHONIOENCODING='utf-8')
  script="import django;django.setup();from django.conf import settings;from django.db import connections;settings.DATABASES['default']['NAME']='test_psl';connections.close_all();from django.core.management import call_command;call_command('work_support_responses',case='"+str(f['case'].pk)+"',limit=1)"
  completed=subprocess.run([sys.executable,'-c',script],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
  self.assertEqual(completed.returncode,0,completed.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
