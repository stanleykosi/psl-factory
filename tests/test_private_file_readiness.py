import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase,override_settings
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.workflows import readiness as r,readiness_delivery as w,operator_delivery as ow,private_file_readiness as n
from apps.workflows.readiness_models import PrivateFileReadiness,IntegrationObservation,IntegrationProbe
from apps.workflows.operator_models import RecoveryArtifact,RecoveryJob
from apps.identity.models import Grant
from apps.policy.readiness_validators import PRIVATE_COMPONENT,FILE_SCHEMA
from apps.policy.services import transition
from apps.policy.models import Configuration
from apps.agents.models import AgentRun
from apps.agents import private_file_readiness as agent
from apps.core.evidence_access import public_timeline
from adapters import operator_protection as storage
from adapters.readiness import ReadinessAdapter
from adapters.private_file_readiness import PrivateFileReadinessAdapter
from .private_file_helpers import fixture,capture,configure,probe,assessed,extra_jobs
from .readiness_helpers import endpoint,policy
from .operator_helpers import provision_test_database
from .helpers import rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class PrivateFileReadinessTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());provision_test_database();cls.root=Path(cls.enterClassContext(TemporaryDirectory(prefix='native-private-file-',dir=settings.BASE_DIR/'.runtime')));cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=cls.root));cls.base=fixture()
 def setUp(self):self.f=dict(self.base)
 def ready(self):
  f=self.f;f['file_policy']=configure(f);assessed(f);return f
 def test_exact_backup_not_found_and_database_export_found_closed_scope(self):
  f=self.ready();v=r.report(f['actor'],f['case'].pk,f['file_assessment'].pk);self.assertTrue(v['review_current']);self.assertFalse(v['operational_ready'])
  o=IntegrationObservation.objects.get(contract=f['file_contract'],payload__kind='receipt');self.assertEqual(o.payload['file_receipt_provenance']['state'],'not_found');self.assertFalse(o.payload['storage_write_proven'])
  self.assertEqual(o.payload['storage_probe'],'read_only_directory_inventory');self.assertNotIn('TX-001',json.dumps(o.payload));self.assertNotIn(str(self.root),json.dumps(o.payload));self.assertNotIn('accepted_private_readiness',json.dumps(o.payload))
  f['file_contract']=capture(f,f['file_export'],'sql-export');assessed(f,'sql-export');o=IntegrationObservation.objects.get(contract=f['file_contract'],payload__kind='receipt');self.assertEqual(o.payload['file_receipt_provenance']['state'],'found');self.assertFalse(o.payload['file_receipt_provenance']['file_verified']);self.assertEqual(o.payload['storage_probe'],'not_applicable_sql_export')
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk))
  from adapters.protection_acceptance import ProtectionAcceptanceAdapter
  value=ProtectionAcceptanceAdapter().read(f['actor'],f['file_assessment'])
  self.assertEqual(value['schema_ref'],'schema:psl/private-file-acceptance-evidence/v1');self.assertEqual(value['classification'],'native_private_file_capability_metadata')
  self.assertEqual(value['job_kind'],'export');self.assertEqual(value['file_job'],f['file_export'].pk);self.assertEqual(value['receipt_state'],'found');self.assertNotIn('restore_job',value)
  for key in ['business_acceptance','operational_acceptance','full_database_export','payload_bodies_included','current_authority_restored']:self.assertFalse(value[key])
 def test_missing_policy_holds_only_file_probes_not_capture_or_other_health(self):
  f=self.f;self.assertTrue(n.binding(f['file_contract']))
  with self.assertRaises(ValidationError):probe(f,'health')
  c=r.capture(f['actor'],f['case'].pk,'unrelated',dict(f['file_payload'],family='handoff',target_key='internal:handoff'),f['file_contract_evidence'].pk)
  j=w.reserve(f['actor'],f['case'].pk,c.pk,'independent','health');w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed')
 def test_typed_policy_inventory_roles_private_grants_and_independence(self):
  f=self.f
  for change in [{'private_file_job_ids':[]},{'private_file_job_ids':[999999]},{'private_file_job_ids':[f['file_backup'].pk]*2},{'private_protection_job_ids':[f['file_export'].pk]},{'independent_review':False},{'require_receipt_probe':False},{'probe_user_id':f['reviewer'].pk},{'freshness_seconds':None}]:
   with self.subTest(change=change),self.assertRaises(ValidationError):configure(f,dict(f['file_rules'],**change))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):configure(f)
 def test_private_receipts_cannot_enter_public_contract_or_wrong_job(self):
  f=self.ready();public=r.capture(f['actor'],f['case'].pk,'public-file',f['file_payload'],f['file_contract_evidence'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,public.pk,'launder','receipt',f['file_backup'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['file_contract'].pk,'wrong','receipt',f['file_export'].pk)
  with self.assertRaises(ValidationError):r.capture(f['actor'],f['case'].pk,'private-file',f['file_payload'],f['file_contract_evidence'].pk,predecessor=f['file_contract'].pk)
  j=IntegrationProbe.objects.filter(contract=f['file_contract'],intent__kind='receipt').get();intent=copy.deepcopy(j.intent);intent.pop('native_file')
  with self.assertRaises(DatabaseError),transaction.atomic():IntegrationProbe.objects.create(contract=public,intent_key='sql-public',operation_key='e'*64,intent=intent,actor=f['actor'])
 def test_sql_immutability_lineage_closed_observation_and_no_retroactive_binding(self):
  f=self.ready();b=n.binding(f['file_contract'])
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateFileReadiness.objects.filter(pk=b.pk).update(snapshot={})
  public=r.capture(f['actor'],f['case'].pk,'sql-file',f['file_payload'],f['file_contract_evidence'].pk)
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateFileReadiness.objects.create(contract=public,job=f['file_export'],snapshot=b.snapshot,sha256=b.sha256,actor=f['actor'])
  r.supplied(f['actor'],f['case'].pk,public.pk,'supplied',self.supplied_evidence(public).pk)
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateFileReadiness.objects.create(contract=public,job=b.job,snapshot=b.snapshot,sha256=b.sha256,actor=f['actor'])
  o=IntegrationObservation.objects.filter(contract=f['file_contract'],payload__kind='receipt').get();value=copy.deepcopy(o.payload);value['file_receipt_provenance']['full_database_backup']=True
  with self.assertRaisesMessage(DatabaseError,'Closed file receipt provenance required'),transaction.atomic():IntegrationObservation.objects.create(contract=f['file_contract'],external_key='forged-private',job=o.job,payload=value,sha256=r.digest(value),actor=f['actor'])
 def supplied_evidence(self,c):
  from .operator_helpers import evidence
  return evidence(self.f,'integration_report',json.dumps({'contract_sha256':c.sha256,'kind':'health','outcome':'passed','recorded_at':timezone.now().isoformat(),'source_ref':'supplied'}))
 def test_source_revocation_denies_cached_report_source_forms_and_live_guidance(self):
  f=self.ready();self.client.force_login(f['actor']);o=IntegrationObservation.objects.filter(contract=f['file_contract']).first();url=reverse('integration_source',args=[f['case'].pk,'observation',o.pk]);self.assertEqual(self.client.get(url).status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  self.assertEqual(self.client.get(url).status_code,403)
  with self.assertRaises(PermissionDenied):r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)
  with self.assertRaises(PermissionDenied):capture(f)
  self.assertFalse(n.visible_jobs(f['actor'],f['case']).exists());self.assertFalse(r.visible_contracts(f['actor'],f['case']).filter(pk=f['file_contract'].pk).exists());self.assertEqual(agent.investigate(f['actor'],f['case'])['findings'],[])
 def test_owner_and_transport_withdrawal_keep_history_but_hold_current_use(self):
  f=self.ready()
  from apps.documents import validation as af
  af.review(f['acceptor'],f['case'].pk,f['owner_package'].pk,'acceptance','revoke','withdraw-source',f['owner_evidence'].pk,'Withdraw source owner acceptance',None)
  v=r.report(f['actor'],f['case'].pk,f['file_assessment'].pk);self.assertTrue(v['recorded_ready']);self.assertFalse(v['current_ready'])
  with self.assertRaises(ValidationError):probe(f,'health','held-source')
  r.review(f['reviewer'],f['case'].pk,f['file_assessment'].pk,'withdraw','withdraw',f['file_review_evidence'].pk)
 def test_expiry_policy_revocation_and_budget_preservation(self):
  f=self.f;f['file_policy']=configure(f,dict(f['file_rules'],freshness_seconds=300));assessed(f)
  with patch('apps.workflows.readiness.timezone.now',return_value=timezone.now()+timedelta(seconds=301)):
   self.assertTrue(any('expired' in x for x in r.snapshot(f['file_contract'])[1]['findings']))
  j=w.reserve(f['actor'],f['case'].pk,f['file_contract'].pk,'budget','health');IntegrationProbe.objects.filter(pk=j.pk).update(status='held',attempts=j.intent['max_attempts'])
  with self.assertRaises(ValidationError):w.operate(f['actor'],f['case'].pk,j.pk,'retry','Preserve original budget')
  transition(f['actor'],f['file_policy'].pk,'revoked');self.assertFalse(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['current_ready'])
 def test_committed_probe_reconciles_receipt_before_revoked_authority(self):
  f=self.ready();j=w.reserve(f['actor'],f['case'].pk,f['file_contract'].pk,'lost-finish','health');lease=w.claim(f['case'].pk);w.execute(*lease,ReadinessAdapter());IntegrationProbe.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(IntegrationObservation.objects.filter(job=j).count(),1);self.assertFalse(Grant.objects.get(case=f['case'],user=f['actor'],action='ledger.private.read').active)
 def test_actual_corrupt_missing_and_conflicting_bytes_never_pass_cached_artifact(self):
  f=self.f;extra_jobs(f,'tamper-fixture');configure(f);f['file_contract']=capture(f,reference='tamper-file');lease=ow.claim();receipt=ow.dispatch(*lease,storage.NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',receipt)
  path=self.root/(f['file_backup'].operation_key+'.json');original=path.read_bytes()
  try:
   self.assertEqual(PrivateFileReadinessAdapter().receipts(f['file_backup'])['state'],'found');path.write_bytes(b'corrupt synthetic bytes')
   with self.assertRaises(ValidationError):PrivateFileReadinessAdapter().receipts(f['file_backup'])
   path.unlink();self.assertEqual(PrivateFileReadinessAdapter().receipts(f['file_backup'])['state'],'not_found')
  finally:path.write_bytes(original) # Restore only this test's newly created fixture bytes, never an old artifact.
 def test_v2_file_inventory_preserves_finance_source_and_requires_affected_restore_reassessment(self):
  f=self.f;extra_jobs(f,'policy-version-fixture');lease=ow.claim();value=ow.dispatch(*lease,storage.NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value);backup=RecoveryArtifact.objects.get(job=f['file_backup']);restore=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',backup.pk)
  old_rules=dict(f['file_rules']);old_rules.pop('private_file_job_ids');old_rules['private_protection_job_ids']=[restore.pk];policy(f,PRIVATE_COMPONENT,old_rules)
  from .private_protection_helpers import assessed as old_assessed
  f['restore']=restore;f['private_review_evidence']=f['file_review_evidence'];f['private_contract']=r.capture(f['actor'],f['case'].pk,'old-restore',f['file_payload'],f['file_contract_evidence'].pk,native_protection_job=restore.pk);old_assessed(f);self.assertTrue(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['review_current'])
  configure(f,dict(f['file_rules'],private_protection_job_ids=[restore.pk],private_file_job_ids=[f['file_export'].pk,f['file_backup'].pk]));self.assertFalse(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['review_current'])
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk));old_assessed(f,'after-file-policy');self.assertTrue(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['review_current'])
 def test_live_agent_generic_omissions_and_actual_http_capture_and_policy(self):
  f=self.ready();before=AgentRun.objects.count();self.assertTrue(agent.investigate(f['actor'],f['case'])['findings']);self.assertEqual(AgentRun.objects.count(),before)
  IntegrationProbe.objects.filter(contract=f['file_contract']).update(status='held')
  from apps.agents.integrations import investigate
  run=investigate(f['actor'],f['case'].pk);self.assertEqual(run.result['probe_findings'],[]);self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.private_file_').exists())
  self.client.force_login(f['actor']);url=reverse('integration_readiness',args=[f['case'].pk]);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Private export and file backup readiness');self.assertContains(response,'source pending');self.assertContains(response,'receipt not_found')
  self.assertEqual(self.client.post(url,{'action':'capture','revision':rev(f['case']),'native_file_job':f['file_backup'].pk,'reference':'http-file','payload':json.dumps(f['file_payload']),'evidence':f['file_contract_evidence'].pk}).status_code,302);self.assertTrue(PrivateFileReadiness.objects.filter(contract__reference='http-file').exists())
  count=Configuration.objects.filter(component=PRIVATE_COMPONENT).count();self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':PRIVATE_COMPONENT,'content':json.dumps(f['file_rules']),'evidence':f['e'].pk,'effective_from':timezone.now().isoformat()}).status_code,302);self.assertEqual(Configuration.objects.filter(component=PRIVATE_COMPONENT).count(),count+1);self.assertEqual(Configuration.objects.filter(component=PRIVATE_COMPONENT).latest('pk').envelope['value']['schema_ref'],FILE_SCHEMA)
 def test_pending_export_enrollment_checks_current_proof_then_records_sql_artifact(self):
  f=self.f;ow.operate(f['actor'],f['case'].pk,f['file_backup'].pk,'cancel','Separate pending export fixture')
  from .private_operations_helpers import plan
  plan(f,'pending-export');f['file_export']=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');f['file_contract']=capture(f,f['file_export'],'pending-export')
  configure(f,dict(f['file_rules'],private_file_job_ids=[f['file_export'].pk]));assessed(f,'before-export');r.select(f['actor'],f['case'].pk,f['file_contract'].pk,f['file_selection_evidence'].pk)
  first=IntegrationObservation.objects.filter(contract=f['file_contract'],payload__kind='receipt').get();self.assertEqual(first.payload['file_receipt_provenance']['state'],'not_found')
  lease=ow.claim();self.assertEqual(lease[0],f['file_export'].pk);value=ow.dispatch(*lease,storage.NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value)
  self.assertEqual(RecoveryArtifact.objects.filter(job=f['file_export']).count(),1);self.assertFalse(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['current_ready'])
  assessed(f,'after-export');self.assertTrue(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['review_current']);latest=IntegrationObservation.objects.filter(contract=f['file_contract'],payload__kind='receipt').latest('pk');self.assertEqual(latest.payload['file_receipt_provenance']['state'],'found');self.assertFalse(latest.payload['file_receipt_provenance']['file_verified'])
 def test_actual_windows_file_sharing_denial_holds_current_not_history(self):
  import os,ctypes
  from ctypes import wintypes
  if os.name!='nt':self.skipTest('Actual Windows file-sharing denial evidence')
  f=self.f;extra_jobs(f,'file-sharing-denial');lease=ow.claim();value=ow.dispatch(*lease,storage.NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value);f['file_contract']=capture(f,reference='sharing-denial')
  configure(f,dict(f['file_rules'],private_file_job_ids=[f['file_export'].pk,f['file_backup'].pk]));assessed(f,'sharing-ready');path=self.root/(f['file_backup'].operation_key+'.json')
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];kernel.CreateFileW.restype=wintypes.HANDLE;kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
  handle=kernel.CreateFileW(str(path),0x80000000,0,None,3,128,None);self.assertNotIn(handle,[None,ctypes.c_void_p(-1).value])
  try:
   with self.assertRaisesMessage(ConnectionError,'Sealed file receipt lookup unavailable'):PrivateFileReadinessAdapter().receipts(f['file_backup'])
   report=r.report(f['actor'],f['case'].pk,f['file_assessment'].pk);self.assertTrue(report['recorded_ready']);self.assertFalse(report['current_ready'])
  finally:self.assertTrue(kernel.CloseHandle(handle))
  self.assertTrue(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['current_ready']);self.assertEqual(IntegrationObservation.objects.filter(contract=f['file_contract']).count(),2)
 def test_http_missing_case_and_agent_action_permission(self):
  from uuid import uuid4
  f=self.f;self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('integration_readiness',args=[uuid4()])).status_code,404);self.assertEqual(self.client.get(reverse('integration_source',args=[uuid4(),'contract',f['file_contract'].pk])).status_code,404)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='agent.integrations').update(active=False);count=PrivateFileReadiness.objects.count()
  with self.assertRaises(PermissionDenied):agent.prepare(f['actor'],f['case'].pk,'denied-agent',f['file_payload'],f['file_contract_evidence'].pk,f['file_backup'].pk)
  self.assertEqual(PrivateFileReadiness.objects.count(),count)
 def test_z_enrolled_actual_backup_changes_receipt_and_needs_fresh_review(self):
  f=self.ready();r.select(f['actor'],f['case'].pk,f['file_contract'].pk,f['file_selection_evidence'].pk);lease=ow.claim();self.assertEqual(lease[0],f['file_backup'].pk);value=ow.dispatch(*lease,storage.NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value)
  self.assertFalse(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['current_ready']);assessed(f,'file-found');self.assertTrue(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['review_current']);o=IntegrationObservation.objects.filter(contract=f['file_contract'],payload__kind='receipt').latest('pk');self.assertTrue(o.payload['file_receipt_provenance']['file_verified']);self.assertEqual(o.payload['file_receipt_provenance']['state'],'found')
