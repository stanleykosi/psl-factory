import os,sys,json,subprocess,hashlib
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
from apps.workflows import operator_delivery as w
from apps.workflows.operator_models import RecoveryArtifact
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .accepted_protection_operations_helpers import fixture,plan
from .operator_helpers import provision_test_database
from .readiness_helpers import endpoint

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class AcceptedProtectionConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_duplicate_reservations_workers_foreign_revocation_and_fresh_process_receipt_recovery(self):
  self.enterContext(endpoint());root=Path(self.enterContext(TemporaryDirectory(prefix='accepted-protection-race-',dir=settings.BASE_DIR/'.runtime')));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=root));provision_test_database();f=fixture('accepted-protection-race',foreign=True);plan(f)
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=360) for x in [pool.submit(self.task,lambda:w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export').pk) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1])
  with ThreadPoolExecutor(max_workers=2) as pool:[x.result(timeout=360) for x in [pool.submit(self.task,w.run_once) for _ in range(2)]]
  e=RecoveryArtifact.objects.get(job_id=ids[0]);self.assertEqual(RecoveryArtifact.objects.filter(job_id=ids[0]).count(),1)
  j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',e.pk);lease=w.claim();self.assertEqual(lease[0],j.pk);w.dispatch(*lease,NativeMetadataProtectionAdapter())
  path=root/(j.operation_key+'.json');before=hashlib.sha256(path.read_bytes()).hexdigest();type(j).objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
  client=Client();client.force_login(f['actor']);url=reverse('operator_artifact',args=[f['case'].pk,e.pk]);self.assertEqual(client.get(url).status_code,200);locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,lambda:client.get(url).status_code);release.set();first.result(timeout=90);self.assertEqual(second.result(timeout=360),403)
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic);env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_OPERATOR_DRILL_DB=settings.OPERATOR_DRILL_DATABASE,PSL_READINESS_DATABASE_REVISION='fixture-v1',PSL_TEST_PROTECTION_ROOT=str(root),PYTHONIOENCODING='utf-8')
  code="""import os
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.db import connection
from django.conf import settings
from apps.workflows.operator_delivery import run_once
assert connection.settings_dict['NAME']=='test_psl'
root=Path(os.environ['PSL_TEST_PROTECTION_ROOT']);assert root.resolve().is_relative_to((settings.BASE_DIR/'.runtime').resolve())
with patch('adapters.operator_protection.storage_root',return_value=root):assert run_once()
"""
  child=subprocess.run([sys.executable,'-c',code],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=120);self.assertEqual(child.returncode,0,child.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(j.attempts,2);self.assertEqual(RecoveryArtifact.objects.filter(job=j).count(),1);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before);self.assertFalse(Grant.objects.get(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').active)
