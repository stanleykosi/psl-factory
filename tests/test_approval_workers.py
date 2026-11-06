import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.db import close_old_connections,transaction,connections
from django.test import TransactionTestCase
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.pmo import approvals as d,approval_routing as routing
from apps.pmo.models import ApprovalSourceReceipt,ApprovalRouteJob,ApprovalRouteReceipt
from .approval_helpers import fixture,evidence,capture,observe

class ApprovalConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture('approval-race')
 def supplied(self,f):
  r=f['request'];return evidence(f,'approval_source',{'request_id':r.pk,'kind':r.kind,'subject':r.subject,'system':'synthetic-qa','source_owner':'QA Lead','source_actor_ref':'synthetic-qa-owner','external_ref':'SAME-SOURCE','source_version':'v1','decision':'accepted','decided_at':(timezone.now()-timedelta(seconds=10)).isoformat(),'signature_ref':'signed-reference-only','critical_defects':0})
 def parallel(self,call):
  def task(n):
   close_old_connections()
   try:return call(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
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
 def test_concurrent_capture_is_one_incumbent_receipt(self):
  f=self.f;e=self.supplied(f);ids=self.parallel(lambda _:d.capture(f['actor'],f['case'].pk,f['request'].pk,e.pk).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(ApprovalSourceReceipt.objects.count(),1)
 def test_cross_case_incumbent_identity_has_one_claim(self):
  cases=[self.f,fixture('approval-other-race')];sources=[self.supplied(f) for f in cases]
  def call(n):
   f=cases[n]
   try:return d.capture(f['actor'],f['case'].pk,f['request'].pk,sources[n].pk).pk
   except ValidationError:return 'held'
  out=self.parallel(call);self.assertEqual(out.count('held'),1);self.assertEqual(ApprovalSourceReceipt.objects.count(),1)
 def test_concurrent_route_reservations_deliver_once(self):
  f=self.f;ids=self.parallel(lambda _:routing.reserve(f['actor'],f['case'].pk,f['request'].pk).pk);self.assertEqual(ids[0],ids[1]);self.parallel(lambda _:routing.run_once());self.assertEqual(ApprovalRouteReceipt.objects.count(),1)
 def test_unavailable_observation_commits_before_export(self):
  f=self.f;s=capture(f);o=observe(f,s);self.race(lambda:observe(f,s,'unavailable',actor=f['actor']),lambda:d.export_gate(f['owner'],f['case'].pk,o.pk))
 def test_owner_revocation_commits_before_route_delivery(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk);pk,fence=routing.claim();self.race(lambda:Grant.objects.filter(user=f['owner'],case=f['case'],action='approval.receive').update(active=False),lambda:routing.deliver_local(pk,fence));self.assertFalse(ApprovalRouteReceipt.objects.exists())
 def test_separate_worker_recovers_committed_receipt_after_sender_revocation(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk);pk,fence=routing.claim();routing.deliver_local(pk,fence)
  ApprovalRouteJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(user=f['actor'],case=f['case'],action='approval.route').update(active=False)
  env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
  process=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_approval_routes','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
  self.assertEqual(process.returncode,0,process.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(ApprovalRouteReceipt.objects.count(),1)
 def test_old_worker_fence_cannot_deliver_after_reclaim(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk);pk,old=routing.claim();ApprovalRouteJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=routing.claim()
  with self.assertRaises(ValidationError):routing.deliver_local(pk,old)
  routing.deliver_local(pk,new);routing.finish(pk,new,'confirmed');self.assertEqual(ApprovalRouteReceipt.objects.count(),1)
