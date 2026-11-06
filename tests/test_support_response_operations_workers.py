import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase,override_settings
from django.db import close_old_connections,transaction
from django.conf import settings
from django.core.exceptions import PermissionDenied,ValidationError
from apps.core.models import Case
from apps.identity.models import Grant
from apps.baas import support_release as d,support_release_delivery as worker
from apps.workflows import readiness_delivery as rw
from apps.workflows.readiness_models import IntegrationObservation
from adapters.readiness import ReadinessAdapter
from adapters.support_response import InternalSupportResponseAdapter
from .support_release_helpers import ready,release
from .support_response_operations_helpers import enroll
from .readiness_helpers import endpoint

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class PrivateResponseReadinessConcurrencyTests(TransactionTestCase):
 def setUp(self):
  self.endpoint=endpoint();self.endpoint.__enter__();self.addCleanup(self.endpoint.__exit__,None,None,None);self.f=ready('private-response-readiness-race')
 def test_native_source_revocation_commits_before_readiness_probe(self):
  f=self.f;j=release(f);enroll(f,j,False);probe=rw.reserve(f['actor'],f['case'].pk,f['response_contract'].pk,'ordered','health');pk,fence=rw.claim(f['case'].pk);locked=Event();proceed=Event()
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
    try:rw.execute(pk,fence,ReadinessAdapter());return 'unexpected'
    except (PermissionDenied,ValidationError):return 'held'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(execute);proceed.set();first.result(20);self.assertEqual(second.result(30),'held')
  self.assertFalse(IntegrationObservation.objects.filter(job=probe).exists());self.assertFalse(d.Receipt.objects.exists())
 def test_fresh_worker_recovers_original_receipt_despite_unready_enrollment_and_revocation(self):
  f=self.f;j=release(f)
  class LostReply(InternalSupportResponseAdapter):
   def deliver(self,*args):super().deliver(*args);raise ConnectionError('lost reply')
  worker.run_once(f['case'].pk,LostReply());enroll(f,j,False);Grant.objects.filter(case=f['case'],user=f['actor'],action__in=['support.private.read','integration.select']).update(active=False)
  env=dict(os.environ,DJANGO_SETTINGS_MODULE='config.settings',PYTHONIOENCODING='utf-8')
  script="import django;django.setup();from django.conf import settings;from django.db import connections;settings.DATABASES['default']['NAME']='test_psl';connections.close_all();from django.core.management import call_command;call_command('work_support_responses',case='"+str(f['case'].pk)+"',limit=1)"
  completed=subprocess.run([sys.executable,'-c',script],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60);self.assertEqual(completed.returncode,0,completed.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
