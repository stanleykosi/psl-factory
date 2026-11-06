import os,sys,subprocess,json,hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.test import TransactionTestCase,override_settings,Client
from django.conf import settings
from django.db import transaction,close_old_connections,connection
from django.utils import timezone
from django.urls import reverse
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows import readiness as r,readiness_delivery as w,operator_delivery as ow
from apps.workflows.readiness_models import IntegrationContract,IntegrationObservation,IntegrationProbe,PrivateFileReadiness
from apps.workflows.operator_models import RecoveryArtifact,RecoveryJob
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .private_file_helpers import fixture,capture,configure,probe
from .readiness_helpers import endpoint

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class PrivateFileConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_duplicate_bindings_competing_probes_foreign_revocation_and_restarted_file_receipt_recovery(self):
  self.enterContext(endpoint());tmp=Path(self.enterContext(TemporaryDirectory(prefix='native-file-race-',dir=settings.BASE_DIR/'.runtime')));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=tmp));f=fixture('file-race',foreign=True)
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=240) for x in [pool.submit(self.task,lambda:capture(f,reference='file-race').pk) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1]);self.assertEqual(PrivateFileReadiness.objects.filter(contract__reference='file-race').count(),1);f['file_contract']=IntegrationContract.objects.get(pk=ids[0]);configure(f)
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=240) for x in [pool.submit(self.task,lambda:w.reserve(f['actor'],f['case'].pk,f['file_contract'].pk,'race-health','health').pk) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1])
  with ThreadPoolExecutor(max_workers=2) as pool:[x.result(timeout=240) for x in [pool.submit(self.task,lambda:w.run_once(case_id=f['case'].pk)) for _ in range(2)]]
  self.assertEqual(IntegrationObservation.objects.filter(job_id=ids[0]).count(),1);self.assertEqual(IntegrationProbe.objects.get(pk=ids[0]).status,'confirmed')
  probe(f,'receipt','race-receipt');a=r.assess(f['actor'],f['case'].pk,f['file_contract'].pk,'race-ready');r.review(f['reviewer'],f['case'].pk,a.pk,'confirm','race-ready',f['file_review_evidence'].pk);r.select(f['actor'],f['case'].pk,f['file_contract'].pk,f['file_selection_evidence'].pk)
  lease=ow.claim();self.assertEqual(lease[0],f['file_backup'].pk);ow.dispatch(*lease,NativeMetadataProtectionAdapter());path=tmp/(f['file_backup'].operation_key+'.json');before=hashlib.sha256(path.read_bytes()).hexdigest();self.assertFalse(RecoveryArtifact.objects.filter(job=f['file_backup']).exists());RecoveryJob.objects.filter(pk=lease[0]).update(lease_until=timezone.now()-timedelta(seconds=1))
  from apps.agents.private_file_readiness import investigate
  advice=next(x for x in investigate(f['actor'],f['case'])['findings'] if x['contract']==f['file_contract'].pk);self.assertTrue(advice['source_receipt_recovery_needed']);self.assertEqual(advice['receipt_state'],'found')
  observation=IntegrationObservation.objects.filter(contract=f['file_contract'],payload__kind='receipt').get();client=Client();client.force_login(f['actor']);url=reverse('integration_source',args=[f['case'].pk,'observation',observation.pk]);self.assertEqual(client.get(url).status_code,200);locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,lambda:client.get(url).status_code);release.set();first.result(timeout=60);self.assertEqual(second.result(timeout=240),403)
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic);env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_TEST_NATIVE_FILE_ROOT=str(tmp),PSL_TEST_NATIVE_FILE_JOB=str(f['file_backup'].pk),PYTHONIOENCODING='utf-8')
  code="""import os
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from django.db import connection
from apps.workflows.operator_models import RecoveryJob
from apps.workflows import operator_delivery as worker
assert connection.settings_dict['NAME']=='test_psl'
root=Path(os.environ['PSL_TEST_NATIVE_FILE_ROOT']);assert root.resolve().is_relative_to((settings.BASE_DIR/'.runtime').resolve())
j=RecoveryJob.objects.select_related('plan__case').get(pk=int(os.environ['PSL_TEST_NATIVE_FILE_JOB']));assert j.plan.case.synthetic and j.kind=='backup'
with patch('adapters.operator_protection.storage_root',return_value=root):assert worker.run_once()
"""
  child=subprocess.run([sys.executable,'-c',code],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=120);self.assertEqual(child.returncode,0,child.stderr);f['file_backup'].refresh_from_db();self.assertEqual(f['file_backup'].status,'confirmed');self.assertEqual(RecoveryArtifact.objects.filter(job=f['file_backup']).count(),1);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before);self.assertFalse(Grant.objects.get(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').active)
