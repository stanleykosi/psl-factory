import os,sys,json,subprocess,time
from datetime import timedelta
import psycopg
from django.utils import timezone
from django.core.exceptions import ValidationError
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
from apps.documents import protection_acceptance as d,validation as af
from apps.documents.protection_models import PrivateProtectionPacket
from .private_protection_helpers import fixture as native_fixture,capture as native_capture,configure as native_configure,assessed
from .protection_acceptance_helpers import package,owners,configure,reviews
from .readiness_helpers import endpoint
from .operator_helpers import provision_test_database,evidence

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class ProtectionAcceptanceConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_duplicate_packet_review_foreign_revocation_and_fresh_process_acceptance_reads(self):
  self.enterContext(endpoint());provision_test_database();tmp=self.enterContext(TemporaryDirectory(prefix='protection-owner-race-',dir=settings.BASE_DIR/'.runtime'));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=Path(tmp)))
  f=native_fixture('protection-owner-race',foreign=True);f['private_contract']=native_capture(f);native_configure(f);assessed(f);package(f)
  call=lambda:d.prepare(f['actor'],f['case'].pk,f['private_assessment'].pk,f['protection_package'].pk,'protection-owner').pk
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=240) for x in [pool.submit(self.task,call) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1]);self.assertEqual(PrivateProtectionPacket.objects.count(),1);f['protection_packet']=PrivateProtectionPacket.objects.get(pk=ids[0]);f['protection_owner_evidence']=evidence(f,'owner_validation','Synthetic concurrent protection owner review')
  owners(f);configure(f)
  call=lambda:af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'meaning','approve','owner-meaning',f['protection_owner_evidence'].pk,'Explicit synthetic protection evidence meaning',None).pk
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=240) for x in [pool.submit(self.task,call) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1]);self.assertEqual(f['protection_package'].reviews.count(),1);reviews(f)
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic)
  env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_OPERATOR_DRILL_DB=settings.OPERATOR_DRILL_DATABASE,PSL_READINESS_DATABASE_REVISION='fixture-v1',PYTHONIOENCODING='utf-8',PSL_TEST_OWNER_ACTOR=str(f['actor'].pk),PSL_TEST_OWNER_CASE=str(f['case'].pk),PSL_TEST_OWNER_PACKET=str(f['protection_packet'].pk),PSL_TEST_OWNER_ENDPOINTS=json.dumps(settings.READINESS_ENDPOINTS),PSL_TEST_OWNER_SECRETS=json.dumps(settings.READINESS_SECRET_REFS))
  code="""import os,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.db import connection
from apps.core.models import Case
from apps.documents.protection_acceptance import export
assert connection.settings_dict['NAME']=='test_psl'
c=Case.objects.get(pk=os.environ['PSL_TEST_OWNER_CASE']);assert c.synthetic
with override_settings(READINESS_ENDPOINTS=json.loads(os.environ['PSL_TEST_OWNER_ENDPOINTS']),READINESS_SECRET_REFS=json.loads(os.environ['PSL_TEST_OWNER_SECRETS'])):
 v=export(get_user_model().objects.get(pk=os.environ['PSL_TEST_OWNER_ACTOR']),c.pk,int(os.environ['PSL_TEST_OWNER_PACKET']))
 print(json.dumps({'packet':v['packet'],'review':v['acceptance_review'],'operational':v['operational_acceptance']}))
"""
  result=subprocess.run([sys.executable,'-c',code],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=180);self.assertEqual(result.returncode,0,result.stderr);v=json.loads(result.stdout.strip());self.assertEqual(v['packet'],f['protection_packet'].pk);self.assertFalse(v['operational'])
  # Hold an actual SQL gate read after dispatch's first fence; let its lease expire.
  from apps.workflows import operator_delivery as ow,readiness as r
  from apps.workflows.operator_models import RecoveryJob
  from adapters.operator_protection import NativeMetadataProtectionAdapter,restore_receipt
  r.select(f['actor'],f['case'].pk,f['private_contract'].pk,f['private_selection_evidence'].pk)
  lease=ow.claim();self.assertEqual(lease[0],f['restore'].pk)
  deadline=timezone.now()+timedelta(seconds=120)
  RecoveryJob.objects.filter(pk=lease[0]).update(lease_until=deadline)
  worker_started=Event();worker_pid=[]
  def dispatch():
   with connection.cursor() as cursor:cursor.execute('SELECT pg_backend_pid()');worker_pid.append(cursor.fetchone()[0])
   worker_started.set();return ow.dispatch(*lease,NativeMetadataProtectionAdapter())
  blocker=psycopg.connect(**connection.get_connection_params())
  try:
   blocker.execute('LOCK TABLE workflows_integrationselection IN ACCESS EXCLUSIVE MODE')
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.task,dispatch)
    try:
     self.assertTrue(worker_started.wait(10));waiting=False;limit=time.monotonic()+110
     while time.monotonic()<limit:
      with connection.cursor() as cursor:
       cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND relation='workflows_integrationselection'::regclass AND NOT granted)",[worker_pid[0]]);waiting=cursor.fetchone()[0]
      if waiting:break
      time.sleep(.05)
     self.assertTrue(waiting,'Real workflow gate must block after its initial fence')
     while timezone.now()<=deadline:time.sleep(.05)
    finally:blocker.rollback()
    with self.assertRaisesMessage(ValidationError,'Expired protection worker fence'):future.result(timeout=240)
  finally:blocker.close()
  self.assertIsNone(restore_receipt(f['restore']))
  client=Client();client.force_login(f['actor']);url=reverse('protection_acceptance_export',args=[f['case'].pk,f['protection_packet'].pk]);self.assertEqual(client.get(url).status_code,200);locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,lambda:client.get(url).status_code);release.set();first.result(timeout=60);self.assertEqual(second.result(timeout=240),403)
  self.assertFalse(Grant.objects.get(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').active);self.assertEqual(f['protection_package'].reviews.filter(kind='acceptance').count(),1)

