import os,sys,subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.test import TransactionTestCase,override_settings,Client
from django.conf import settings
from django.db import close_old_connections,transaction,connection
from django.utils import timezone
from django.urls import reverse
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows import readiness as r,readiness_delivery as w
from apps.workflows.readiness_models import PrivateProtectionReadiness,IntegrationObservation,IntegrationProbe
from adapters.readiness import ReadinessAdapter
from .private_protection_helpers import fixture,capture,configure
from .readiness_helpers import endpoint
from .operator_helpers import provision_test_database

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class PrivateProtectionConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_duplicate_bindings_workers_foreign_revocation_and_restarted_receipt_reconciliation(self):
  self.enterContext(endpoint());provision_test_database()
  tmp=self.enterContext(TemporaryDirectory(prefix='private-protection-race-',dir=settings.BASE_DIR/'.runtime'))
  self.enterContext(patch('adapters.operator_protection.storage_root',return_value=Path(tmp)))
  f=fixture('private-protection-race',foreign=True)
  with ThreadPoolExecutor(max_workers=2) as pool:
   ids=[x.result(timeout=180) for x in [pool.submit(self.task,lambda:capture(f).pk) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1]);self.assertEqual(PrivateProtectionReadiness.objects.count(),1)
  from apps.workflows.readiness_models import IntegrationContract
  f['private_contract']=IntegrationContract.objects.get(pk=ids[0]);configure(f)
  with ThreadPoolExecutor(max_workers=2) as pool:
   ids=[x.result(timeout=180) for x in [pool.submit(self.task,lambda:w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,'race-health','health').pk) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1])
  with ThreadPoolExecutor(max_workers=2) as pool:
   [x.result(timeout=180) for x in [pool.submit(self.task,lambda:w.run_once(case_id=f['case'].pk)) for _ in range(2)]]
  self.assertEqual(IntegrationObservation.objects.filter(job_id=ids[0]).count(),1)
  j=w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,'lost-finish','receipt',f['restore'].pk)
  lease=w.claim(f['case'].pk);w.execute(*lease,ReadinessAdapter())
  IntegrationProbe.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
  observation=IntegrationObservation.objects.get(job=j);url=reverse('integration_source',args=[f['case'].pk,'observation',observation.pk]);client=Client();client.force_login(f['actor']);self.assertEqual(client.get(url).status_code,200)
  locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,lambda:client.get(url).status_code);release.set();first.result(timeout=60);self.assertEqual(second.result(timeout=180),403)
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic)
  env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_OPERATOR_DRILL_DB=settings.OPERATOR_DRILL_DATABASE,PSL_READINESS_DATABASE_REVISION='fixture-v1',PYTHONIOENCODING='utf-8')
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_integration_readiness','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=90)
  self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(IntegrationObservation.objects.filter(job=j).count(),1)
  self.assertFalse(Grant.objects.get(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').active)
