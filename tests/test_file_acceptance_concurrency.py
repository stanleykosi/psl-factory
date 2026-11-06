import os,sys,json,subprocess,hashlib
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
from apps.documents.protection_models import PrivateProtectionPacket as Packet
from apps.workflows import operator_delivery as ow
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .private_file_helpers import fixture,configure as native_configure,assessed
from .file_acceptance_helpers import package,owners,configure,reviews,rules
from .operator_helpers import evidence
from .readiness_helpers import endpoint

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class FileAcceptanceConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_actual_file_duplicate_packet_review_fresh_process_and_foreign_revocation(self):
  self.enterContext(endpoint());root=Path(self.enterContext(TemporaryDirectory(prefix='file-owner-race-',dir=settings.BASE_DIR/'.runtime')));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=root));f=fixture('file-owner-race',foreign=True)
  lease=ow.claim();self.assertEqual(lease[0],f['file_backup'].pk);receipt=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',receipt);path=root/(f['file_backup'].operation_key+'.json');before=hashlib.sha256(path.read_bytes()).hexdigest()
  native_configure(f);assessed(f);package(f,'file-race-package')
  call=lambda:d.prepare(f['actor'],f['case'].pk,f['file_assessment'].pk,f['protection_package'].pk,'file-race',native_kind='backup').pk
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=300) for x in [pool.submit(self.task,call) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1]);self.assertEqual(Packet.objects.count(),1);f['protection_packet']=Packet.objects.get(pk=ids[0]);f['protection_owner_evidence']=evidence(f,'owner_validation','Synthetic concurrent native file evidence owner decision');owners(f);configure(f,rules(f,receipt_requirement='found'))
  call=lambda:af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'meaning','approve','file-race-meaning',f['protection_owner_evidence'].pk,'Explicit synthetic protection evidence meaning',None).pk
  with ThreadPoolExecutor(max_workers=2) as pool:ids=[x.result(timeout=300) for x in [pool.submit(self.task,call) for _ in range(2)]]
  self.assertEqual(ids[0],ids[1]);self.assertEqual(f['protection_package'].reviews.count(),1);reviews(f,'file-race')
  self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic);env=os.environ.copy();env.update(PGDATABASE='test_psl',PSL_READINESS_DATABASE_REVISION='fixture-v1',PYTHONIOENCODING='utf-8',PSL_TEST_FILE_OWNER_ACTOR=str(f['actor'].pk),PSL_TEST_FILE_OWNER_CASE=str(f['case'].pk),PSL_TEST_FILE_OWNER_PACKET=str(f['protection_packet'].pk),PSL_TEST_FILE_OWNER_ROOT=str(root),PSL_TEST_FILE_OWNER_ENDPOINTS=json.dumps(settings.READINESS_ENDPOINTS),PSL_TEST_FILE_OWNER_SECRETS=json.dumps(settings.READINESS_SECRET_REFS))
  code="""import os,json
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.conf import settings
from apps.core.models import Case
from apps.documents.protection_acceptance import export
assert connection.settings_dict['NAME']=='test_psl'
c=Case.objects.get(pk=os.environ['PSL_TEST_FILE_OWNER_CASE']);assert c.synthetic
root=Path(os.environ['PSL_TEST_FILE_OWNER_ROOT']);assert root.resolve().is_relative_to((settings.BASE_DIR/'.runtime').resolve())
with patch('adapters.operator_protection.storage_root',return_value=root),override_settings(READINESS_ENDPOINTS=json.loads(os.environ['PSL_TEST_FILE_OWNER_ENDPOINTS']),READINESS_SECRET_REFS=json.loads(os.environ['PSL_TEST_FILE_OWNER_SECRETS'])):
 v=export(get_user_model().objects.get(pk=os.environ['PSL_TEST_FILE_OWNER_ACTOR']),c.pk,int(os.environ['PSL_TEST_FILE_OWNER_PACKET']))
 assert v['evidence']['job_kind']=='backup' and v['evidence']['receipt_state']=='found'
 print(json.dumps({'packet':v['packet'],'review':v['acceptance_review'],'operational':v['operational_acceptance']}))
"""
  child=subprocess.run([sys.executable,'-c',code],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=240);self.assertEqual(child.returncode,0,child.stderr);v=json.loads(child.stdout.strip());self.assertEqual(v['packet'],f['protection_packet'].pk);self.assertFalse(v['operational']);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
  client=Client();client.force_login(f['actor']);url=reverse('protection_acceptance_export',args=[f['case'].pk,f['protection_packet'].pk]);self.assertEqual(client.get(url).status_code,200);locked=Event();release=Event()
  def revoke():
   with transaction.atomic():
    Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
    if not release.wait(10):raise AssertionError('Coordination timeout')
    Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));second=pool.submit(self.task,lambda:client.get(url).status_code);release.set();first.result(timeout=90);self.assertEqual(second.result(timeout=300),403)
  self.assertFalse(Grant.objects.get(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').active);self.assertEqual(f['protection_package'].reviews.filter(kind='acceptance').count(),1);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
