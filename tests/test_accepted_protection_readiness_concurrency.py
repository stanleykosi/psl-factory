import os,sys,subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase,override_settings,Client
from django.conf import settings
from django.db import transaction,close_old_connections,connection
from django.urls import reverse
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows import readiness as r,readiness_delivery as w,operator_delivery as ow
from apps.workflows.readiness_models import IntegrationObservation,IntegrationProbe
from apps.workflows.operator_models import RecoveryArtifact
from apps.policy.readiness_validators import ACCEPTED_COMPONENT
from apps.documents.contracts import digest
from apps.workflows.operator_models import RecoveryJob
from adapters.readiness import ReadinessAdapter
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .accepted_protection_operations_helpers import fixture,plan
from .operator_helpers import evidence,provision_test_database
from .readiness_helpers import endpoint,policy

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class AcceptedProtectionReadinessConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_duplicate_probes_workers_foreign_revocation_and_fresh_process_recovery(self):
  self.enterContext(endpoint());root=Path(self.enterContext(TemporaryDirectory(prefix='af13-native-race-',dir=settings.BASE_DIR/'.runtime')));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=root));provision_test_database();f=fixture('af13-native-race',foreign=True);plan(f)
  j=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');lease=ow.claim();self.assertEqual(lease[0],j.pk);v=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',v);a=RecoveryArtifact.objects.get(job=j);backup=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',a.pk)
  c=r.capture(f['actor'],f['case'].pk,'af13-race',f['file_payload'],evidence(f,'integration_contract').pk,native_accepted_protection_job=backup.pk)
  rules=dict(f['file_rules']);rules.pop('private_protection_job_ids');rules.pop('private_file_job_ids');rules['accepted_protection_job_ids']=[backup.pk];policy(f,ACCEPTED_COMPONENT,rules)
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=360) for x in [pool.submit(self.task,lambda:w.reserve(f['actor'],f['case'].pk,c.pk,'same-health','health').pk) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1])
  with ThreadPoolExecutor(max_workers=2) as pool:[x.result(timeout=360) for x in [pool.submit(self.task,lambda:w.run_once(case_id=f['case'].pk)) for _ in range(2)]]
  self.assertEqual(IntegrationObservation.objects.filter(job_id=ids[0]).count(),1)
  receipt=w.reserve(f['actor'],f['case'].pk,c.pk,'native-receipt','receipt',backup.pk);self.assertTrue(w.run_once(case_id=f['case'].pk));receipt.refresh_from_db();self.assertEqual(receipt.status,'confirmed')
  assessed=r.assess(f['actor'],f['case'].pk,c.pk,'native-reviewed');r.review(f['reviewer'],f['case'].pk,assessed.pk,'confirm','native-reviewed',evidence(f,'integration_review').pk);r.select(f['actor'],f['case'].pk,c.pk,evidence(f,'integration_selection').pk)
  source_lease=ow.claim();self.assertEqual(source_lease[0],backup.pk);ow.dispatch(*source_lease,NativeMetadataProtectionAdapter());ow.finish(*source_lease,'unknown');path=root/(backup.operation_key+'.json');before=digest(path.read_bytes().hex());self.assertFalse(RecoveryArtifact.objects.filter(job=backup).exists())
  j=w.reserve(f['actor'],f['case'].pk,c.pk,'lost-health','health');lease=w.claim(f['case'].pk);self.assertEqual(lease[0],j.pk);w.execute(*lease,ReadinessAdapter());IntegrationProbe.objects.filter(pk=j.pk).update(status='unknown')
  client=Client();client.force_login(f['actor']);url=reverse('integration_source',args=[f['case'].pk,'contract',c.pk]);self.assertEqual(client.get(url).status_code,200);locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,lambda:client.get(url).status_code);release.set();first.result(timeout=90);self.assertEqual(second.result(timeout=360),403)
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_OPERATOR_DRILL_DB=settings.OPERATOR_DRILL_DATABASE,PSL_READINESS_DATABASE_REVISION='fixture-v1',PSL_TEST_PROTECTION_ROOT=str(root),PYTHONIOENCODING='utf-8')
  code="import os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');import django;django.setup();from django.db import connection;from apps.workflows.readiness_delivery import run_once;from apps.workflows.operator_delivery import run_once as recover_operator;from pathlib import Path;from unittest.mock import patch;assert connection.settings_dict['NAME']=='test_psl';assert run_once(case_id="+repr(str(f['case'].pk))+')'+";root=Path(os.environ['PSL_TEST_PROTECTION_ROOT']);assert root.resolve().is_relative_to((Path.cwd()/'.runtime').resolve());config=patch('adapters.operator_protection.storage_root',return_value=root);config.start();assert recover_operator();config.stop()"
  child=subprocess.run([sys.executable,'-c',code],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=120);self.assertEqual(child.returncode,0,child.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(j.attempts,2);self.assertEqual(IntegrationObservation.objects.filter(job=j).count(),1);backup.refresh_from_db();self.assertEqual(backup.status,'confirmed');self.assertEqual(backup.attempts,2);self.assertEqual(RecoveryArtifact.objects.filter(job=backup).count(),1);self.assertEqual(digest(path.read_bytes().hex()),before);self.assertFalse(Grant.objects.get(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').active)
