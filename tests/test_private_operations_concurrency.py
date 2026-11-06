import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import TransactionTestCase,override_settings,Client
from django.conf import settings
from django.db import close_old_connections,transaction,connection
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Case
from apps.identity.models import Grant
from apps.documents import validation as af
from apps.workflows import operator_delivery as w
from apps.workflows.operator_models import RecoveryArtifact
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .private_operations_helpers import fixture,effect
from .operator_helpers import provision_test_database
from .readiness_helpers import endpoint

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class PrivateOperationsConcurrencyTests(TransactionTestCase):
 def setUp(self):
  self.enterContext(endpoint());provision_test_database();tmp=self.enterContext(TemporaryDirectory(prefix='private-ops-race-',dir=settings.BASE_DIR/'.runtime'));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=Path(tmp)))
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_two_connections_reserve_and_workers_confirm_one_export(self):
  f=fixture('private-ops-race')
  with ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(self.task,lambda:w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export').pk) for _ in range(2)];ids=[x.result(timeout=120) for x in futures]
  self.assertEqual(ids[0],ids[1])
  with ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(self.task,w.run_once) for _ in range(2)];[x.result(timeout=120) for x in futures]
  self.assertEqual(RecoveryArtifact.objects.filter(job_id=ids[0]).count(),1)
 def test_foreign_source_revocation_precedes_cached_http_artifact_download(self):
  f=fixture('private-ops-foreign',foreign=True);export=effect(f,'export');url=reverse('operator_artifact',args=[f['case'].pk,export.pk]);client=Client();client.force_login(f['actor']);self.assertEqual(client.get(url).status_code,200);locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  def download():return client.get(url).status_code
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,download);release.set();first.result(timeout=60);self.assertEqual(second.result(timeout=120),403)
 def test_new_process_reconciles_actual_restore_after_owner_and_source_revocation(self):
  f=fixture('private-ops-restart');export=effect(f,'export');backup=effect(f,'backup',export.pk);job=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',backup.pk);lease=w.claim();w.dispatch(*lease,NativeMetadataProtectionAdapter())
  # Simulate process loss after the actual isolated PostgreSQL commit, before local finish.
  type(job).objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
  af.review(f['acceptor'],f['case'].pk,f['owner_package'].pk,'acceptance','revoke','after-restore-commit',f['owner_evidence'].pk,'Retain original committed effect, withdraw current owner approval',None)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic)
  env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_OPERATOR_DRILL_DB=settings.OPERATOR_DRILL_DATABASE,PSL_READINESS_DATABASE_REVISION='fixture-v1',PYTHONIOENCODING='utf-8')
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_operator_recovery','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=90)
  self.assertEqual(result.returncode,0,result.stderr);job.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(RecoveryArtifact.objects.filter(job=job).count(),1)
  self.assertFalse(Grant.objects.get(case=f['case'],user=f['actor'],action='ledger.private.read').active);self.assertEqual(f['owner_package'].reviews.filter(kind='acceptance').latest('pk').verdict,'revoke')
