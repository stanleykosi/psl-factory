import os,sys,subprocess
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase,override_settings,TestCase
from django.db import close_old_connections,connections,transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows import operator_delivery as w,protection as d
from apps.workflows.operator_models import RecoveryJob,RecoveryArtifact,RecoveryProof
from apps.workflows.operator_recovery import recover,snapshot
from apps.workflows.operator_inventory import jobs
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .operator_helpers import fixture,provision_test_database,effect,proof,policy,evidence
from .helpers import signed,rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators')
class OperatorConcurrencyTests(TransactionTestCase):
 def setUp(self):provision_test_database();self.f=fixture()
 def parallel(self,fn):
  def task(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
 def test_simultaneous_first_export_and_competing_workers(self):
  f=self.f;ids=self.parallel(lambda _:w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export').pk);self.assertEqual(ids[0],ids[1]);self.parallel(lambda _:w.run_once());self.assertEqual(RecoveryArtifact.objects.count(),1)
 def test_simultaneous_first_receipt_has_one_claim(self):
  f=self.f;p=f['plan'];v={'plan_id':p.pk,'plan_sha256':p.sha256,'kind':'restore','scope':p.payload['scope'],'system':'synthetic-race','external_ref':str(f['case'].pk),'receipt_version':'v1','source_ref':p.payload['source_ref'],'source_version':p.payload['source_version'],'target_ref':p.payload['target_ref'],'recorded_at':timezone.now().isoformat(),'outcome':'unknown','evidence_class':'synthetic_report','record_count':None,'manifest_sha256':None,'elapsed_seconds':None,'source_lag_seconds':None};e=evidence(f,'ops_proof',v)
  ids=self.parallel(lambda _:d.capture_proof(f['actor'],f['case'].pk,p.pk,e.pk).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(RecoveryProof.objects.count(),1)
 def test_old_fence_cannot_write_after_reclaim(self):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');pk,old=w.claim();RecoveryJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=w.claim()
  with self.assertRaises(ValidationError):w.dispatch(pk,old,NativeMetadataProtectionAdapter())
  receipt=w.dispatch(pk,new,NativeMetadataProtectionAdapter());w.finish(pk,new,'confirmed',receipt);self.assertEqual(RecoveryArtifact.objects.count(),1)
 def test_revocation_commits_before_native_effect(self):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');pk,fence=w.claim();locked=Event();release=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not release.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['actor'],action='ops.export').update(active=False)
   finally:close_old_connections()
  def dispatch():
   close_old_connections()
   try:
    try:w.dispatch(pk,fence,NativeMetadataProtectionAdapter())
    except PermissionDenied:return 'held'
    return 'used'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(dispatch);release.set();first.result(timeout=30);self.assertEqual(second.result(timeout=30),'held')
  self.assertFalse(RecoveryArtifact.objects.exists())
 def test_separate_process_reconciles_actual_isolated_receipt_after_revocation(self):
  f=self.f;_,e=effect(f,'export');_,b=effect(f,'backup',e.pk);j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk);pk,fence=w.claim();w.dispatch(pk,fence,NativeMetadataProtectionAdapter())
  RecoveryJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action='ops.restore').update(active=False)
  env=os.environ.copy();env.update(PGDATABASE=connections['default'].settings_dict['NAME'],PSL_OPERATOR_DRILL_DB=settings.OPERATOR_DRILL_DATABASE,PYTHONIOENCODING='utf-8')
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_operator_recovery','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
  self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(RecoveryArtifact.objects.filter(job=j).count(),1)
 def test_lookup_unavailable_never_dispatches(self):
  class Unavailable(NativeMetadataProtectionAdapter):
   def lookup(self,j):raise ConnectionError('Synthetic lookup unavailable')
   def deliver(self,j):raise AssertionError('Must not dispatch')
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');w.run_once(Unavailable());j.refresh_from_db();self.assertEqual(j.status,'unknown');self.assertFalse(RecoveryArtifact.objects.exists())

class OperatorSourceRecoveryTests(TestCase):
 def setUp(self):
  self.f=fixture();f=self.f;e=signed(f['actor'],f['case'])
  from apps.pmo.services import complete_milestone
  from apps.workflows.models import Outbox
  complete_milestone(f['actor'],f['case'].pk,'Synthetic operator bridge',e['completion'].pk,rev(f['case']));self.job=Outbox.objects.get(case=f['case'])
 def test_unknown_finance_handoff_cannot_be_cancelled_and_reconciles_once(self):
  from apps.workflows.services import run_once
  from adapters.finance import TimeoutAfterAccept
  from apps.finance.models import Handoff
  f=self.f;run_once(TimeoutAfterAccept());self.job.refresh_from_db();self.assertEqual(self.job.status,'unknown')
  with self.assertRaises(ValidationError):recover(f['actor'],f['case'].pk,'handoff',self.job.pk,'cancel','Investigate uncertain handoff')
  run_once();self.assertEqual(Handoff.objects.count(),1);self.job.refresh_from_db();self.assertEqual(self.job.status,'confirmed')
 def test_scoped_inventory_and_recovery_need_source_permission(self):
  f=self.f;self.assertTrue(any(r['family']=='handoff' for r in jobs(f['actor'],f['case'])[0]));Grant.objects.filter(case=f['case'],user=f['actor'],action='workflow.read').update(active=False)
  self.assertFalse(any(r['family']=='handoff' for r in jobs(f['actor'],f['case'])[0]))
  with self.assertRaises(PermissionDenied):recover(f['actor'],f['case'].pk,'handoff',self.job.pk,'cancel','Current operator scope')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='workflow.read').update(active=True);Grant.objects.filter(case=f['case'],user=f['actor'],action='workflow.operate').update(active=False)
  with self.assertRaises(PermissionDenied):recover(f['actor'],f['case'].pk,'handoff',self.job.pk,'cancel','Current operator scope')
 def test_pending_handoff_cancel_and_held_retry_use_real_source_controls(self):
  f=self.f;recover(f['actor'],f['case'].pk,'handoff',self.job.pk,'cancel','Explicit no-effect cancellation');self.job.refresh_from_db();self.assertEqual(self.job.status,'cancelled')
  from apps.finance.models import Handoff
  self.assertFalse(Handoff.objects.exists())

class OperatorApprovalBridgeTests(TestCase):
 def test_department_route_recovery_delegates_to_source_service(self):
  from .approval_helpers import fixture as approval_fixture
  from apps.pmo import approval_routing
  from apps.policy.operator_validators import OPERATOR
  f=approval_fixture();j=approval_routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
  # Keep the department-owned QA role configuration intact; add only operator rules.
  import json
  from pathlib import Path
  v=json.loads((settings.BASE_DIR/'fixtures/operator-recovery.json').read_text(encoding='utf-8'))['operator'];v.update(operators=[{'user_id':f['actor'].pk,'role':'PM','purposes':['recover','review']}],reviewer_id=f['actor'].pk,reviewer_role='PM',independent_review=False)
  f['sources']={'policy_decision':f['e']['policy_decision']};policy(f,OPERATOR,v)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.operate').update(active=False)
  with self.assertRaises(PermissionDenied):recover(f['actor'],f['case'].pk,'approval',j.pk,'cancel','Department route remains controlled')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.operate').update(active=True);recover(f['actor'],f['case'].pk,'approval',j.pk,'cancel','No route receipt committed');j.refresh_from_db();self.assertEqual(j.status,'cancelled')
