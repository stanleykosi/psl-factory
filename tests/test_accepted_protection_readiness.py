import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase,override_settings
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.urls import reverse
from apps.workflows import readiness as r,readiness_delivery as w,operator_delivery as ow,accepted_protection_readiness as n
from apps.workflows.readiness_models import AcceptedProtectionReadiness,IntegrationObservation,IntegrationProbe
from apps.workflows.operator_models import RecoveryArtifact,RecoveryJob
from apps.documents.contracts import digest
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.readiness_validators import ACCEPTED_COMPONENT
from apps.agents import accepted_protection_readiness as agent
from apps.agents.models import AgentRun
from adapters.accepted_protection_readiness import AcceptedProtectionReadinessAdapter as Adapter
from adapters.readiness import ReadinessAdapter
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .accepted_protection_operations_helpers import fixture,plan
from .operator_helpers import evidence,provision_test_database
from .readiness_helpers import endpoint,policy

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class AcceptedProtectionReadinessTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());provision_test_database();cls.root=Path(cls.enterClassContext(TemporaryDirectory(prefix='af13-native-',dir=settings.BASE_DIR/'.runtime')));cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=cls.root))
  f=fixture('af13-native');plan(f);j=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');lease=ow.claim();assert lease[0]==j.pk;value=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value);f['export']=j;f['artifact']=RecoveryArtifact.objects.get(job=j);f['backup']=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',f['artifact'].pk)
  f['contract_evidence']=evidence(f,'integration_contract');f['review_evidence']=evidence(f,'integration_review');f['selection_evidence']=evidence(f,'integration_selection')
  f['contract']=r.capture(f['actor'],f['case'].pk,'af13-native',f['file_payload'],f['contract_evidence'].pk,native_accepted_protection_job=f['backup'].pk)
  f['native_rules']=dict(f['file_rules']);f['native_rules'].pop('private_file_job_ids');f['native_rules'].pop('private_protection_job_ids');f['native_rules']['accepted_protection_job_ids']=[f['export'].pk,f['backup'].pk]
  cls.base=f;cls.now=timezone.now()
 def setUp(self):
  self.f=dict(self.base);self.enterContext(patch('django.utils.timezone.now',return_value=self.now))
  path=self.root/(self.f['backup'].operation_key+'.json');assert path.parent.resolve()==self.root.resolve();self.addCleanup(lambda:path.unlink(missing_ok=True))
 def configure(self,value=None):return policy(self.f,ACCEPTED_COMPONENT,value or self.f['native_rules'])
 def capture(self,j,ref):
  f=self.f;return r.capture(f['actor'],f['case'].pk,ref,f['file_payload'],f['contract_evidence'].pk,native_accepted_protection_job=j.pk)
 def probe(self,c,kind,key):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,c.pk,key,kind,n.binding(c).job_id if kind=='receipt' else None);self.assertTrue(w.run_once(case_id=f['case'].pk));j.refresh_from_db();self.assertEqual(j.status,'confirmed');return IntegrationObservation.objects.get(job=j)
 def ready(self,c=None,key='native'):
  f=self.f;c=c or f['contract'];self.probe(c,'health',key+'-health');self.probe(c,'receipt',key+'-receipt');a=r.assess(f['actor'],f['case'].pk,c.pk,key);r.review(f['reviewer'],f['case'].pk,a.pk,'confirm',key,f['review_evidence'].pk);self.assertTrue(r.report(f['actor'],f['case'].pk,a.pk)['review_current']);return a
 def effect(self,j):
  lease=ow.claim();self.assertEqual(lease[0],j.pk);v=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',v);return RecoveryArtifact.objects.get(job=j)
 def test_connected_sql_file_isolated_restore_review_and_exact_job_gate(self):
  f=self.f;self.configure();a=self.ready();b=n.binding(f['contract']);self.assertEqual(b.snapshot['finance_inventory'],[]);self.assertEqual(b.snapshot['protection_inventory'][0]['packet'],f['protection_packet'].pk)
  self.assertEqual(Adapter().receipts(f['backup'])['receipt']['state'],'not_found');self.assertIsNone(r.gate(f['case'],'protection',f['export'].pk))
  r.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk);self.assertEqual(r.gate(f['case'],'protection',f['backup'].pk)['assessment'],a.pk);self.assertIsNone(r.gate(f['case'],'protection'))
  backup=self.effect(f['backup']);self.assertEqual(Adapter().receipts(f['backup'])['receipt']['state'],'found');self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready']);self.ready(key='found-backup')
  export_contract=self.capture(f['export'],'af13-sql');self.ready(export_contract,'sql');self.assertTrue(Adapter().receipts(f['export'])['receipt']['artifact'])
  restore=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',backup.pk);c=self.capture(restore,'af13-isolated');self.configure(dict(f['native_rules'],accepted_protection_job_ids=[f['export'].pk,f['backup'].pk,restore.pk]));self.ready(c,'isolated');r.select(f['actor'],f['case'].pk,c.pk,f['selection_evidence'].pk);self.effect(restore);self.assertEqual(Adapter().receipts(restore)['receipt']['state'],'found');self.ready(c,'isolated-found')
  from apps.documents.protection_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['protection_packet'].pk))
  from adapters.protection_acceptance import ProtectionAcceptanceAdapter
  with self.assertRaises(ValidationError):ProtectionAcceptanceAdapter().access(f['actor'],r.IntegrationAssessment.objects.filter(contract=c).last())
 def test_capture_before_policy_and_invalid_inventory_principals_and_source_grants(self):
  f=self.f;self.assertTrue(n.binding(f['contract']))
  with self.assertRaises(ValidationError):self.probe(f['contract'],'health','missing')
  other=r.capture(f['actor'],f['case'].pk,'unrelated-health',dict(f['file_payload'],family='handoff',target_key='internal:handoff'),f['contract_evidence'].pk);self.probe(other,'health','unrelated-health')
  for change in [{'accepted_protection_job_ids':[]},{'accepted_protection_job_ids':[f['file_export'].pk]},{'accepted_protection_job_ids':[f['backup'].pk]*2},{'probe_user_id':f['reviewer'].pk},{'probe_user_id':f['reviewer'].pk,'reviewer_id':f['actor'].pk},{'independent_review':False},{'require_receipt_probe':False},{'freshness_seconds':None}]:
   with self.subTest(change=change),self.assertRaises(ValidationError),transaction.atomic():self.configure(dict(f['native_rules'],**change))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):self.configure()
 def test_native_type_public_wrong_job_and_history_downgrade_denied(self):
  f=self.f;self.configure();public=r.capture(f['actor'],f['case'].pk,'public-af13',f['file_payload'],f['contract_evidence'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,public.pk,'public','receipt',f['backup'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'wrong','receipt',f['export'].pk)
  with self.assertRaises(ValidationError):r.capture(f['actor'],f['case'].pk,'af13-native',f['file_payload'],f['contract_evidence'].pk,predecessor=f['contract'].pk)
  for arg in ['native_file_job','native_protection_job']:
   with self.assertRaises(ValidationError):r.capture(f['actor'],f['case'].pk,'old-kind',f['file_payload'],f['contract_evidence'].pk,**{arg:f['backup'].pk})
 def test_sql_binding_probe_observation_immutability_and_closed_provenance(self):
  f=self.f;self.configure();b=n.binding(f['contract'])
  with self.assertRaises(DatabaseError),transaction.atomic():AcceptedProtectionReadiness.objects.filter(pk=b.pk).update(snapshot={})
  c=r.capture(f['actor'],f['case'].pk,'wrong-binding',f['file_payload'],f['contract_evidence'].pk)
  for change in [{'schema_ref':'schema:psl/private-file/v1'},{'finance_inventory':b.snapshot['protection_inventory']},{'current_authority_restored':True}]:
   v=dict(b.snapshot,**change)
   with self.subTest(change=change),self.assertRaisesMessage(DatabaseError,'Exact closed AF13'),transaction.atomic():AcceptedProtectionReadiness.objects.create(contract=c,job=f['backup'],actor=f['actor'],snapshot=v,sha256=digest(v))
  j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'sql-health','health');intent=copy.deepcopy(j.intent);intent.pop('native_accepted_protection')
  with self.assertRaisesMessage(DatabaseError,'Exact AF13 native probe'),transaction.atomic():IntegrationProbe.objects.create(contract=f['contract'],intent_key='forged',operation_key='a'*64,intent=intent,actor=f['actor'])
  self.assertTrue(w.run_once(case_id=f['case'].pk));o=self.probe(f['contract'],'receipt','sql-receipt');v=copy.deepcopy(o.payload);v['accepted_protection_receipt']['receipt']['full_database_backup']=True
  with self.assertRaisesMessage(DatabaseError,'Closed AF13 receipt'),transaction.atomic():IntegrationObservation.objects.create(contract=f['contract'],job=o.job,external_key='forged-observation',payload=v,sha256=digest(v),actor=f['actor'])
  self.probe(c,'health','before-bind')
  with self.assertRaisesMessage(DatabaseError,'precede readiness history'),transaction.atomic():AcceptedProtectionReadiness.objects.create(contract=c,job=f['backup'],actor=f['actor'],snapshot=b.snapshot,sha256=b.sha256)
 def test_source_withdrawal_policy_revision_expiry_and_transport_withdrawal(self):
  f=self.f;p=self.configure();a=self.ready();self.configure(dict(f['native_rules'],freshness_seconds=300));self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready']);a=self.ready(key='revised')
  with patch('django.utils.timezone.now',return_value=self.now+timedelta(seconds=301)):self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready'])
  with patch('django.utils.timezone.now',return_value=self.now+timedelta(seconds=3601)):
   with self.assertRaises(ValidationError):self.probe(f['contract'],'health','expired-source')
  self.assertFalse(IntegrationProbe.objects.filter(contract=f['contract'],intent_key='expired-source').exists())
  from apps.documents import validation as af
  af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','withdraw-native-source',f['protection_owner_evidence'].pk,'Withdraw AF13 source',None)
  self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready']);r.review(f['reviewer'],f['case'].pk,a.pk,'withdraw','transport-withdraw',f['review_evidence'].pk)
  with self.assertRaises(ValidationError):self.probe(f['contract'],'health','held-owner')
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('integration_source',args=[f['case'].pk,'contract',f['contract'].pk])).status_code,200)
 def test_private_http_agents_ui_recheck_source_and_no_generic_persistence(self):
  f=self.f;self.configure();a=self.ready();self.client.force_login(f['actor']);u=reverse('integration_readiness',args=[f['case'].pk]);response=self.client.get(u);self.assertEqual(response.status_code,200);self.assertContains(response,'AF13 protection operator readiness');self.assertEqual(response['Cache-Control'],'no-store')
  count=AgentRun.objects.count();v=agent.investigate(f['actor'],f['case']);self.assertEqual(v['effect_tools'],[]);self.assertEqual(AgentRun.objects.count(),count);self.assertEqual(v['findings'][0]['operator_job'],f['backup'].pk)
  from apps.agents.integrations import investigate
  run=investigate(f['actor'],f['case'].pk);self.assertNotIn(str(f['contract'].pk),json.dumps(run.result['probe_findings']))
  self.assertNotIn('accepted_private_protection',json.dumps(v));self.assertNotIn(str(self.root),json.dumps(v));self.assertNotIn('TX-001',json.dumps(v))
  from apps.workflows.readiness_views import commands
  form=next(x['form'] for x in commands(f['actor'],f['case']) if x['form'].initial['action']=='capture');self.assertTrue(form.fields['native_accepted_protection_job'].queryset.filter(pk=f['backup'].pk).exists())
  prepared=agent.prepare(f['actor'],f['case'].pk,'typed-agent',f['file_payload'],f['contract_evidence'].pk,f['backup'].pk);self.assertTrue(n.binding(prepared));self.assertEqual(AgentRun.objects.count(),count+1)
  f['case'].refresh_from_db();response=self.client.post(u,{'action':'capture','revision':f['case'].revision,'reference':'http-af13-native','payload':json.dumps(f['file_payload']),'evidence':f['contract_evidence'].pk,'native_accepted_protection_job':f['backup'].pk});self.assertEqual(response.status_code,302);http_contract=r.IntegrationContract.objects.get(case=f['case'],reference='http-af13-native');self.assertEqual(n.binding(http_contract).job_id,f['backup'].pk)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  self.assertEqual(self.client.get(reverse('integration_source',args=[f['case'].pk,'contract',f['contract'].pk])).status_code,403);self.assertFalse(n.visible_jobs(f['actor'],f['case']).exists());self.assertEqual(agent.investigate(f['actor'],f['case'])['findings'],[])
 def test_actual_bytes_missing_corrupt_and_storage_identity_changes_hold_current_proof(self):
  f=self.f;self.configure();self.effect(f['backup']);a=self.ready();o=IntegrationObservation.objects.get(contract=f['contract'],payload__kind='receipt');self.assertTrue(o.payload['accepted_protection_receipt']['receipt']['file_verified'])
  from adapters import operator_protection as storage
  path=self.root/(f['backup'].operation_key+'.json')
  original=path.read_bytes()
  with TemporaryDirectory(prefix='changed-native-target-',dir=self.root) as other:
   target=Path(other);self.assertTrue(target.resolve().is_relative_to((settings.BASE_DIR/'.runtime').resolve()))
   with patch('adapters.operator_protection.storage_root',return_value=target):
    with self.assertRaises(ConnectionError):Adapter().health(f['backup'])
    with self.assertRaises(ConnectionError):Adapter().receipts(f['backup'])
    self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready'])
  self.assertEqual(path.read_bytes(),original)
  try:
   path.write_bytes(b'corrupt-owned-test-bytes')
   with self.assertRaises((ValidationError,ConnectionError)):Adapter().receipts(f['backup'])
   self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready'])
   path.unlink();self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready'])
  finally:path.write_bytes(original)
 def test_receipt_first_probe_recovery_after_revocation_and_original_attempt_budget(self):
  f=self.f;self.configure();j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'lost-health','health');lease=w.claim(f['case'].pk);self.assertEqual(lease[0],j.pk);v=w.execute(*lease,ReadinessAdapter());IntegrationProbe.objects.filter(pk=j.pk).update(status='unknown');Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  self.assertTrue(w.run_once(case_id=f['case'].pk));j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(j.attempts,2);self.assertEqual(IntegrationObservation.objects.filter(job=j).count(),1)
 def test_budget_exhaustion_and_revoked_independent_criteria_hold_new_work(self):
  f=self.f;p=self.configure();j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'budget','health');IntegrationProbe.objects.filter(pk=j.pk).update(status='held',attempts=j.intent['max_attempts'])
  with self.assertRaises(ValidationError):w.operate(f['actor'],f['case'].pk,j.pk,'retry','Do not reset native budget')
  transition(f['actor'],p.pk,'revoked')
  with self.assertRaises(ValidationError):self.probe(f['contract'],'health','revoked')
 def test_mixed_finance_and_af13_inventory_stays_explicit_and_old_selectors_reject(self):
  f=self.f;ow.operate(f['actor'],f['case'].pk,f['backup'].pk,'cancel','Use a separate mixed inventory test plan');plan(f,'mixed-native',mixed=True);j=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');self.effect(j);c=self.capture(j,'mixed-native');self.configure(dict(f['native_rules'],accepted_protection_job_ids=[j.pk]));a=self.ready(c,'mixed');b=n.binding(c)
  self.assertEqual(b.snapshot['finance_inventory'][0]['packet'],f['packet'].pk);self.assertEqual(b.snapshot['protection_inventory'][0]['packet'],f['protection_packet'].pk);self.assertNotIn('packets',b.snapshot)
  from adapters.private_file_readiness import PrivateFileReadinessAdapter
  with self.assertRaises(ValidationError):PrivateFileReadinessAdapter().job(f['case'],j.pk)

 def test_pending_native_sql_export_enrollment_and_receipt_successor(self):
  f=self.f;ow.operate(f['actor'],f['case'].pk,f['backup'].pk,'cancel','Use a pending native SQL export test plan');plan(f,'pending-native');j=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');c=self.capture(j,'pending-native');self.configure(dict(f['native_rules'],accepted_protection_job_ids=[j.pk]));a=self.ready(c,'pending-native');self.assertEqual(Adapter().receipts(j)['receipt']['state'],'not_found');r.select(f['actor'],f['case'].pk,c.pk,f['selection_evidence'].pk);artifact=self.effect(j);self.assertEqual(artifact.sha256,n.binding(c).snapshot['manifest_sha256']);self.assertEqual(Adapter().receipts(j)['receipt']['state'],'found');self.assertFalse(r.report(f['actor'],f['case'].pk,a.pk)['current_ready'])
 def test_human_capture_without_agent_authority_and_descriptive_source_filtered_choice(self):
  f=self.f;Grant.objects.filter(case=f['case'],user=f['actor'],action='agent.integrations').update(active=False);self.client.force_login(f['actor']);url=reverse('integration_readiness',args=[f['case'].pk]);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'AF13 protection operator job');self.assertContains(response,f"#{f['backup'].pk} backup / accepted-protection v1 / pending")
  f['case'].refresh_from_db();response=self.client.post(url,{'action':'capture','revision':f['case'].revision,'reference':'human-af13','payload':json.dumps(f['file_payload']),'evidence':f['contract_evidence'].pk,'native_accepted_protection_job':f['backup'].pk});self.assertEqual(response.status_code,302);c=r.IntegrationContract.objects.get(case=f['case'],reference='human-af13');self.assertEqual(n.binding(c).job_id,f['backup'].pk)
  with self.assertRaises(PermissionDenied):agent.prepare(f['actor'],f['case'].pk,'agent-denied',f['file_payload'],f['contract_evidence'].pk,f['backup'].pk)
 def test_sql_null_extra_health_receipt_and_missing_required_probe_fields_are_denied(self):
  f=self.f;self.configure();j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'shape-health','health')
  for index,change in enumerate([{'kind':None},{'body':'forbidden-private-body'},{'native_file':{}}]):
   v=dict(j.intent,**change)
   with self.subTest(change=change),self.assertRaisesMessage(DatabaseError,'Exact AF13 native probe'),transaction.atomic():IntegrationProbe.objects.create(contract=f['contract'],intent_key='bad-shape-'+str(index),operation_key=digest({'shape':index}),intent=v,actor=f['actor'])
  self.assertTrue(w.run_once(case_id=f['case'].pk));o=IntegrationObservation.objects.get(job=j)
  for index,change in enumerate([{'accepted_protection_receipt':{'body':'forbidden-private-body'}},{'observed_at':None},{'identity_match':False}]):
   v=dict(o.payload,**change)
   with self.subTest(change=change),self.assertRaisesMessage(DatabaseError,'Closed AF13 native observation'),transaction.atomic():IntegrationObservation.objects.create(contract=f['contract'],job=j,external_key='bad-health-'+str(index),payload=v,sha256=digest(v),actor=f['actor'])
  o=self.probe(f['contract'],'receipt','shape-receipt');v=copy.deepcopy(o.payload);v['accepted_protection_receipt']['receipt']['state']=None
  with self.assertRaisesMessage(DatabaseError,'Closed AF13 receipt provenance'),transaction.atomic():IntegrationObservation.objects.create(contract=f['contract'],job=o.job,external_key='null-state',payload=v,sha256=digest(v),actor=f['actor'])
 def test_enrolled_effect_waits_for_assessment_and_independent_human_review(self):
  f=self.f;self.configure();r.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk);lease=ow.claim();self.assertEqual(lease[0],f['backup'].pk)
  with self.assertRaisesMessage(ValidationError,'needs assessment'):ow.dispatch(*lease,NativeMetadataProtectionAdapter())
  ow.finish(*lease,'held');self.assertFalse((self.root/(f['backup'].operation_key+'.json')).exists());self.assertFalse(RecoveryArtifact.objects.filter(job=f['backup']).exists())
  self.probe(f['contract'],'health','human-health');self.probe(f['contract'],'receipt','human-receipt');a=r.assess(f['actor'],f['case'].pk,f['contract'].pk,'human-pending')
  with self.assertRaisesMessage(ValidationError,'human readiness review'):r.gate(f['case'],'protection',f['backup'].pk)
  r.review(f['reviewer'],f['case'].pk,a.pk,'confirm','human-confirm',f['review_evidence'].pk);self.assertEqual(r.gate(f['case'],'protection',f['backup'].pk)['assessment'],a.pk);ow.operate(f['actor'],f['case'].pk,f['backup'].pk,'retry','Current exact job proof reviewed');self.effect(f['backup'])
