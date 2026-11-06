import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import close_old_connections,connections,transaction
from django.conf import settings
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.agents import boundary as gateway,boundary_delivery as worker
from apps.baas import support_agent as d
from .support_agent_helpers import fixture,project,integration,extracted
from .readiness_helpers import endpoint

class SupportAgentConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture('native-race')
 def parallel(self,fn):
  def call(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(call,[0,1]))
 def test_competing_native_projection_and_reviewed_reuse_create_one_each(self):
  f=self.f;ids=self.parallel(lambda _:d.project(f['actor'],f['case'].pk,f['intake'].pk,'same').pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(d.SupportProjection.objects.count(),1);f['binding']=d.SupportProjection.objects.get();f['projection']=f['binding'].projection
  with endpoint():
   r=extracted(f);ids=self.parallel(lambda _:d.reuse(f['actor'],f['case'].pk,r.pk,'same-draft').pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(d.Draft.objects.count(),1)
 def test_native_permission_revocation_commits_before_worker_send(self):
  f=self.f;locked=Event();release=Event()
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'ordered');pk,fence=worker.claim(f['case'].pk)
   def first():
    close_old_connections()
    try:
     with transaction.atomic():
      Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
      if not release.wait(10):raise AssertionError('Coordination timeout')
      Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
    finally:close_old_connections()
   def second():
    close_old_connections()
    try:
     try:worker.execute(pk,fence)
     except (ValidationError,PermissionDenied):return 'held'
     return 'sent'
    finally:close_old_connections()
   with ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(first);self.assertTrue(locked.wait(10));b=pool.submit(second);release.set();a.result(timeout=45);self.assertEqual(b.result(timeout=45),'held')
   self.assertNotIn('private_inputs',remote);self.assertFalse(gateway.Receipt.objects.exists())
 def test_lost_response_reconciles_after_native_revocation_without_allowing_reuse(self):
  f=self.f
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'unknown');remote['lose_response']=True;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'unknown');Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);remote['lose_response']=False;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
   with self.assertRaises(PermissionDenied):d.reuse(f['actor'],f['case'].pk,gateway.Receipt.objects.get(job=j).pk,'no-authority')
 def test_separate_process_recovers_committed_local_receipt_with_native_grants_revoked(self):
  f=self.f
  with endpoint():r=extracted(f)
  j=r.job;gateway.Job.objects.filter(pk=j.pk).update(status='leased',lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
  env=os.environ.copy();env.update(PGDATABASE=connections['default'].settings_dict['NAME'],PYTHONIOENCODING='utf-8')
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_private_evidence','--case',str(f['case'].pk),'--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60);self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(gateway.Receipt.objects.count(),1)
