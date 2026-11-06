import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.baas import support_channel as d,support_channel_delivery as worker
from adapters.support_channel import SupportChannelAdapter
from .support_channel_helpers import fixture,claim,reviewed,output,gateway
from .readiness_helpers import endpoint

class SupportChannelConcurrencyTests(TransactionTestCase):
 def setUp(self):
  self.endpoint=endpoint();self.endpoint.__enter__();self.addCleanup(self.endpoint.__exit__,None,None,None);self.f=fixture('channel-race')
 def parallel(self,fn):
  def call(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(call,[0,1]))
 def test_competing_claims_and_human_attestations_preserve_one_message_clock(self):
  f=self.f;ids=self.parallel(lambda _:d.capture(f['actor'],f['case'].pk,f['release_job'].packet_id,'same','same-external','v1').pk);self.assertEqual(ids[0],ids[1]);f['claim']=d.Claim.objects.get()
  with gateway() as remote:
   r=reviewed(f,remote)
   def attest(_):
    try:return d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk).pk
    except ValidationError:return None
   ids=self.parallel(attest);self.assertEqual(len([x for x in ids if x]),1);self.assertEqual(d.Attestation.objects.count(),1)
 def test_source_revocation_commits_before_gateway_read(self):
  f=self.f;claim(f);locked=Event();proceed=Event()
  with gateway() as remote:
   remote['receipts'][f['claim'].payload['receipt_key']]=output(f);j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'ordered');pk,fence=worker.claim(f['case'].pk)
   def revoke():
    close_old_connections()
    try:
     with transaction.atomic():
      Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
      if not proceed.wait(10):raise AssertionError('Coordination timeout')
      Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
    finally:close_old_connections()
   def execute():
    close_old_connections()
    try:
     try:worker.execute(pk,fence,SupportChannelAdapter());return 'unexpected'
     except (PermissionDenied,ValidationError):return 'held'
    finally:close_old_connections()
   with ThreadPoolExecutor(max_workers=2) as pool:
    first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(execute);proceed.set();first.result(20);self.assertEqual(second.result(30),'held')
   self.assertEqual(remote['calls'],0);self.assertFalse(d.Receipt.objects.exists())
 def test_fresh_worker_recovers_committed_observation_after_source_and_runtime_binding_revocation(self):
  f=self.f;claim(f)
  with gateway() as remote:
   remote['receipts'][f['claim'].payload['receipt_key']]=output(f);j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'crash');pk,fence=worker.claim(f['case'].pk);worker.execute(pk,fence,SupportChannelAdapter());self.assertEqual(remote['calls'],1)
  d.Job.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
  env=dict(os.environ,DJANGO_SETTINGS_MODULE='config.settings',PYTHONIOENCODING='utf-8')
  script="import django;django.setup();from django.conf import settings;from django.db import connections;settings.DATABASES['default']['NAME']='test_psl';connections.close_all();from django.core.management import call_command;call_command('work_support_channels',case='"+str(f['case'].pk)+"',limit=1)"
  completed=subprocess.run([sys.executable,'-c',script],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60);self.assertEqual(completed.returncode,0,completed.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1);self.assertFalse(d.Attestation.objects.exists())
