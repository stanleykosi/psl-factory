import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import timedelta
from uuid import uuid4
from django.test import TestCase,override_settings
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.utils import timezone
from django.urls import reverse
from apps.documents import protection_acceptance as d,validation as af
from apps.documents.protection_models import PrivateProtectionPacket as Packet
from apps.policy.protection_acceptance_validators import COMPONENT,OWNER,FILE_SCHEMA,SCHEMA
from apps.policy.services import transition
from apps.policy.models import Configuration
from apps.workflows import readiness as r,operator_delivery as ow
from apps.identity.models import Grant
from apps.agents import protection_acceptance as agent
from apps.agents.models import AgentRun
from apps.core.evidence_access import public_timeline
from adapters.protection_acceptance import ProtectionAcceptanceAdapter as Adapter
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .file_acceptance_helpers import fixture,prepare,rules,owners,configure,reviews,package
from .private_file_helpers import assessed,capture
from .readiness_helpers import endpoint
from .helpers import rev
from .validation_helpers import policy
from .operator_helpers import evidence

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class FileAcceptanceTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());cls.root=Path(cls.enterClassContext(TemporaryDirectory(prefix='file-owner-',dir=settings.BASE_DIR/'.runtime')));cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=cls.root));cls.base=fixture()
 def setUp(self):self.f=dict(self.base)
 def ready(self):
  f=self.f;f['protection_owner_policy']=owners(f);f['protection_policy']=configure(f);f['protection_reviews']=reviews(f);return f
 def test_exact_backup_evidence_three_owner_decisions_and_original_source_independence(self):
  f=self.ready();v=d.export(f['actor'],f['case'].pk,f['protection_packet'].pk);e=v['evidence']
  self.assertEqual(e['job_kind'],'backup');self.assertEqual(e['file_job'],f['file_backup'].pk);self.assertEqual(e['receipt_state'],'not_found');self.assertEqual(e['schema_ref'],'schema:psl/private-file-acceptance-evidence/v1');self.assertEqual(v['acceptance_review'],f['protection_reviews'][-1].pk)
  for field in ['current_authority_restored','full_database_backup','full_database_export','operational_acceptance','whole_product_accepted','deployment_authorized']:self.assertFalse(v[field])
  for forbidden in ['TX-001','accepted_private_readiness',str(self.root),'operation_key','review rationale']:self.assertNotIn(forbidden,json.dumps(v))
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk));self.assertTrue(r.report(f['actor'],f['case'].pk,f['file_assessment'].pk)['review_current'])
 def test_missing_criteria_holds_only_positive_owner_use_and_keeps_negative_decision(self):
  f=self.f;self.assertFalse(d.report(f['actor'],f['case'].pk,f['protection_packet'].pk)['evidence_current']);owners(f)
  af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'meaning','return','missing-criteria',f['protection_owner_evidence'].pk,'Configured human asks for criteria',None)
  with self.assertRaises(ValidationError):af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'meaning','approve','no-positive',f['protection_owner_evidence'].pk,'Cannot invent criteria',None)
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk));self.assertTrue(Packet.objects.filter(pk=f['protection_packet'].pk).exists())
 def test_v1_rejects_file_inventory_and_v2_validates_exact_kind_scope_and_principals(self):
  f=self.f;owners(f)
  old=rules(f);old['private_protection']['inventory'][0].pop('native_kind')
  with self.assertRaisesMessage(ValidationError,'v1 is restore only'):configure(f,old)
  for changes in [{'inventory':[]},{'inventory':[dict(rules(f)['private_protection']['inventory'][0],native_kind='restore')]},{'inventory':[dict(rules(f)['private_protection']['inventory'][0],assessment_id=999999)]},{'freshness_seconds':None},{'receipt_requirement':'invented'}]:
   with self.subTest(changes=changes),self.assertRaises(ValidationError):configure(f,rules(f,**changes))
  pairs=rules(f)['private_protection']['inventory'];pairs=pairs+[dict(pairs[0],native_kind='export')]
  with self.assertRaises(ValidationError):configure(f,rules(f,inventory=pairs))
  Grant.objects.filter(case=f['case'],user=f['acceptor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):configure(f)
 def test_explicit_prepare_kind_and_fresh_package_preserve_historical_restore_api(self):
  f=self.f;p=package(f,'explicit-file-package')
  with self.assertRaisesMessage(ValidationError,'Explicit matching native evidence kind'):d.prepare(f['actor'],f['case'].pk,f['file_assessment'].pk,p.pk,'no-silent-file')
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['file_assessment'].pk,p.pk,'wrong-file',native_kind='export')
  b=prepare(f,'explicit-file',kind='backup');self.assertEqual(b.snapshot['evidence']['job_kind'],'backup')
  with self.assertRaises(ValidationError):prepare(f,'another-file')
 def test_owner_withdrawal_and_criteria_revision_revocation_expiry_preserve_history(self):
  f=self.ready();old=f['protection_packet'];af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','owner-withdraw',f['protection_owner_evidence'].pk,'Withdraw selected file evidence only',None)
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,old.pk)
  configure(f,rules(f,receipt_requirement='found'));self.assertFalse(d.report(f['actor'],f['case'].pk,old.pk)['evidence_current'])
  package(f,'fresh-file-expiry-package');fresh=prepare(f,'fresh-file-expiry');p=configure(f,rules(f,freshness_seconds=300));reviews(f,'fresh-review')
  self.assertTrue(d.report(f['actor'],f['case'].pk,fresh.pk)['evidence_current'])
  future=timezone.now()+timedelta(seconds=301)
  with patch('apps.documents.protection_acceptance.timezone.now',return_value=future):self.assertFalse(d.report(f['actor'],f['case'].pk,fresh.pk)['evidence_current'])
  transition(f['actor'],p.pk,'revoked');af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','criteria-revoked',f['protection_owner_evidence'].pk,'Owner authority remains separate',None)
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk))
 def test_transport_withdrawal_and_source_grant_revocation_deny_cached_and_idempotent_paths(self):
  f=self.ready();r.review(f['reviewer'],f['case'].pk,f['file_assessment'].pk,'withdraw','transport-withdraw',f['file_review_evidence'].pk)
  self.assertFalse(d.report(f['actor'],f['case'].pk,f['protection_packet'].pk)['evidence_current']);af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','transport-held',f['protection_owner_evidence'].pk,'Withdraw held proof',None)
  self.client.force_login(f['actor']);url=reverse('protection_acceptance_report',args=[f['case'].pk,f['protection_packet'].pk]);self.assertEqual(self.client.get(url).status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  for call in [lambda:d.report(f['actor'],f['case'].pk,f['protection_packet'].pk),lambda:d.export(f['actor'],f['case'].pk,f['protection_packet'].pk),lambda:prepare(f),lambda:package(f,'file-owner-package')]:
   with self.assertRaises(PermissionDenied):call()
  self.assertEqual(self.client.get(url).status_code,403);self.assertFalse(d.visible(f['actor'],f['case']).exists());self.assertEqual(agent.investigate(f['actor'],f['case'].pk)['findings'],[])
  response=self.client.get(reverse('protection_acceptance',args=[f['case'].pk]));self.assertEqual(response.context['rows'],[]);self.assertFalse(next(x['form'] for x in response.context['commands'] if x['key']=='prepare').fields['assessment'].queryset.exists())
 def test_acceptor_independent_of_packet_transport_and_expectations(self):
  f=self.f;v=copy.deepcopy(f['owner_rules']);v['assignments'][1]['user_id']=f['reviewer'].pk;owners(f,v);configure(f)
  for kind in ['meaning','expectations']:af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,kind,'approve',kind,f['protection_owner_evidence'].pk,'Synthetic independent owner '+kind,None)
  with self.assertRaisesMessage(PermissionDenied,'independent of packet and transport'):af.review(f['reviewer'],f['case'].pk,f['protection_package'].pk,'acceptance','approve','transport-acceptor',f['protection_owner_evidence'].pk,'Cannot accept own transport review',None)
 def test_successor_requires_explicit_parent_fresh_package_and_new_owner_reviews(self):
  f=self.ready();old=f['protection_packet'];package(f,'next-file-package')
  with self.assertRaises(ValidationError):prepare(f)
  b=prepare(f,predecessor=old.pk);self.assertEqual(b.parent_id,old.pk)
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,old.pk)
  configure(f);reviews(f,'successor');self.assertEqual(d.export(f['actor'],f['case'].pk,b.pk)['packet'],b.pk)
 def test_sql_closed_file_lineage_immutability_and_bidirectional_source_cycle_guards(self):
  f=self.f;b=f['protection_packet']
  with self.assertRaises(DatabaseError),transaction.atomic():Packet.objects.filter(pk=b.pk).update(snapshot={})
  p=package(f,'raw-file-package');base=dict(b.snapshot,package=p.pk,package_sha256=p.sha256)
  for changes in [{'job_kind':'restore'},{'file_job':f['file_export'].pk},{'payload_bodies_included':True},{'classification':'native_private_restore_capability_metadata'},{'source_packets':[]},{'observations':[]},{'raw_manifest':{}}]:
   value=dict(base,evidence=dict(base['evidence'],**changes))
   with self.subTest(changes=changes),self.assertRaises(DatabaseError),transaction.atomic():Packet.objects.create(case=f['case'],reference='bad-file',version=1,package=p,assessment=f['file_assessment'],actor=f['actor'],snapshot=value,sha256=d.digest(value))
  from apps.finance import readiness_acceptance as source
  with self.assertRaises(ValidationError):source.prepare(f['actor'],f['case'].pk,f['assessment'].pk,b.package_id,'cycle-file')
  from apps.finance.acceptance_models import PrivateReadinessPacket,FinanceHandoff
  source_value=dict(f['packet'].snapshot,package=b.package_id,package_sha256=b.package.sha256)
  with self.assertRaisesMessage(DatabaseError,'Protection evidence cannot become its own Finance source'),transaction.atomic():PrivateReadinessPacket.objects.create(case=f['case'],reference='raw-cycle-file',version=1,package=b.package,assessment=f['assessment'],actor=f['actor'],snapshot=source_value,sha256=d.digest(source_value))
  h=f['handoff'];values={field.name:getattr(h,field.name) for field in h._meta.fields if field.name not in ['id','created_at','package','reference','version']}
  values['snapshot']=dict(h.snapshot,package=b.package_id,package_sha256=b.package.sha256);values['sha256']=d.digest(values['snapshot'])
  with self.assertRaisesMessage(DatabaseError,'Protection evidence cannot become its own Finance source'),transaction.atomic():FinanceHandoff.objects.create(**values,package=b.package,reference='raw-file-cycle-handoff',version=1)
 def test_live_agent_generic_omissions_and_actual_http_typed_file_prepare_policy_and_review(self):
  f=self.ready();before=AgentRun.objects.count();v=agent.investigate(f['actor'],f['case'].pk);self.assertEqual(v['findings'][0]['native_kind'],'backup');self.assertEqual(AgentRun.objects.count(),before)
  from apps.agents.validation import investigate
  run=investigate(f['actor'],f['case'].pk,None);self.assertFalse(any(x['package']==f['protection_package'].pk for x in run.result['packages']));self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.protection_acceptance').exists())
  self.client.force_login(f['actor']);url=reverse('protection_acceptance',args=[f['case'].pk]);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'native kind backup');self.assertContains(response,'v2 acceptance inventory')
  p=package(f,'http-file-package');count=Packet.objects.count();self.assertEqual(self.client.post(url,{'action':'prepare','revision':rev(f['case']),'assessment':f['file_assessment'].pk,'native_kind':'backup','package':p.pk,'reference':'http-file'}).status_code,302);self.assertEqual(Packet.objects.count(),count+1)
  old=Configuration.objects.filter(component=COMPONENT).count();self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':COMPONENT,'content':json.dumps(rules(f)),'evidence':f['e'].pk,'effective_from':timezone.now().isoformat()}).status_code,302);self.assertEqual(Configuration.objects.filter(component=COMPONENT).count(),old+1);self.assertEqual(Configuration.objects.filter(component=COMPONENT).latest('pk').envelope['value']['schema_ref'],FILE_SCHEMA)
  b=Packet.objects.get(reference='http-file');self.client.force_login(f['recipient']);self.assertEqual(self.client.post(url,{'action':'review','revision':rev(f['case']),'packet':b.pk,'kind':'meaning','verdict':'return','operation_key':'http-file-return','reason':'Actual configured synthetic owner returns evidence','evidence':f['protection_owner_evidence'].pk}).status_code,302);self.assertTrue(b.package.reviews.filter(operation_key='http-file-return',verdict='return').exists())
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('protection_acceptance_report',args=[uuid4(),1])).status_code,404);Grant.objects.filter(case=f['case'],user=f['actor'],action__in=['validation.review','validation.accept']).update(active=False);response=self.client.get(url);self.assertNotContains(response,'Record separate AF13 owner decision');self.assertEqual(self.client.post(url,{'action':'review'}).status_code,403)
 def test_export_kind_found_sql_artifact_requires_its_own_packet_and_criteria(self):
  f=self.f;f['file_contract']=capture(f,job=f['file_export'],reference='sql-export-owner');assessed(f,'export-owner');package(f,'sql-export-package');prepare(f,'sql-export-owner',kind='export');owners(f);configure(f,rules(f,receipt_requirement='found'));reviews(f,'sql-export-owner')
  v=d.export(f['actor'],f['case'].pk,f['protection_packet'].pk);self.assertEqual(v['evidence']['job_kind'],'export');self.assertEqual(v['evidence']['receipt_state'],'found');self.assertFalse(v['full_database_export'])
 def test_explicit_v2_restore_criteria_retain_restore_snapshot_shape(self):
  f=self.f
  from .private_file_helpers import extra_jobs,configure as native_configure
  from .private_protection_helpers import assessed as restore_assessed
  from .operator_helpers import provision_test_database
  from apps.workflows.operator_models import RecoveryArtifact
  provision_test_database();extra_jobs(f,'v2-restore-criteria');lease=ow.claim();v=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',v);a=RecoveryArtifact.objects.get(job=f['file_backup']);f['restore']=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',a.pk)
  native_configure(f,dict(f['file_rules'],private_file_job_ids=[f['file_export'].pk,f['file_backup'].pk],private_protection_job_ids=[f['restore'].pk]));f['private_contract']=r.capture(f['actor'],f['case'].pk,'restore-owner-v2',f['file_payload'],f['file_contract_evidence'].pk,native_protection_job=f['restore'].pk);f['private_review_evidence']=f['file_review_evidence'];restore_assessed(f);p=package(f,'restore-owner-v2');b=d.prepare(f['actor'],f['case'].pk,f['private_assessment'].pk,p.pk,'restore-owner-v2');f['protection_packet']=b
  owners(f);value=rules(f,inventory=[{'package_id':p.pk,'assessment_id':f['private_assessment'].pk,'native_kind':'restore'}]);configure(f,value);reviews(f,'restore-owner-v2');v=d.export(f['actor'],f['case'].pk,b.pk);self.assertEqual(v['evidence']['restore_job'],f['restore'].pk);self.assertEqual(v['evidence']['classification'],'native_private_restore_capability_metadata');self.assertNotIn('file_job',v['evidence'])
 def test_selected_four_process_synthetic_evidence_needs_comparisons_and_independent_tester(self):
  f=self.f;ids=['F01','B13','P13','P15'];src=af.DiscoverySource.objects.get(pk=f['package'].payload['source_ids'][0]);metadata=copy.deepcopy(src.metadata);metadata['process_ids']=ids
  for row in metadata['clauses']:row['process_ids']=ids
  source=af.capture_source(f['actor'],f['case'].pk,'file-synthetic-scope',src.evidence_id,metadata,None);examples=[]
  for kind,value in [('normal',{'file_metadata_only':True}),('exception',{'restored_authority':False})]:examples.append(af.capture_example(f['actor'],f['case'].pk,'file-example-'+kind,ids,kind,value,f['e'].pk,None))
  p=package(f,'file-synthetic-package',dict(f['package'].payload,process_ids=ids,source_ids=[source.pk],example_ids=[e.pk for e in examples],level='synthetic_implementation',role_list=['Finance','Process owners'],manual_fallback='Preserve uncertain receipts',rollout_plan='Synthetic selected scope only',migration_plan='No production migration',support_owner_id=f['actor'].pk));prepare(f,'file-synthetic-packet');owners(f);configure(f)
  for kind in ['meaning','expectations']:af.review(f['recipient'],f['case'].pk,p.pk,kind,'approve','file-synthetic-'+kind,f['protection_owner_evidence'].pk,'Selected synthetic '+kind,None)
  with self.assertRaises(ValidationError):af.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','missing-comparison',f['protection_owner_evidence'].pk,'Need independent comparisons',None)
  from django.contrib.auth import get_user_model
  from apps.core.management.commands.seed_demo import ACTIONS
  tester=get_user_model().objects.create_user(username='file-independent-tester');Grant.objects.bulk_create([Grant(case=f['case'],user=tester,action=x) for x in ACTIONS]);rows=[]
  for e in examples:
   value={'example_id':e.pk,'actual':e.expected,'build_ref':p.payload['build_ref'],'run_ref':'synthetic:file:'+e.scenario,'environment':'isolated-postgresql-tests','evidence_class':'synthetic_fixture'};ev=evidence(f,'validation_result',json.dumps(value));rows.append(af.record_replay(tester,f['case'].pk,p.pk,ev.pk,'file-compare-'+e.scenario,None))
  accepted=af.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','selected-file-synthetic',f['protection_owner_evidence'].pk,'Selected synthetic file capability evidence only',None);v=d.export(f['actor'],f['case'].pk,f['protection_packet'].pk);self.assertEqual(v['process_ids'],ids);self.assertEqual(v['acceptance_review'],accepted.pk);self.assertTrue(all(not x.result['underlying_workflow_executed'] for x in rows));self.assertFalse(v['operational_acceptance'])
  Grant.objects.filter(case=f['case'],user=tester,action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):af.record_replay(tester,f['case'].pk,p.pk,ev.pk,'file-compare-exception',None)
 def test_z_actual_backup_found_change_new_packet_and_corrupt_missing_bytes_hold_current(self):
  f=self.ready();old=f['protection_packet'];lease=ow.claim();self.assertEqual(lease[0],f['file_backup'].pk);value=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value)
  self.assertFalse(d.report(f['actor'],f['case'].pk,old.pk)['evidence_current']);assessed(f,'found-file');package(f,'found-file-package');b=prepare(f,predecessor=old.pk);configure(f,rules(f,receipt_requirement='found'));reviews(f,'found-file');self.assertEqual(d.export(f['actor'],f['case'].pk,b.pk)['evidence']['receipt_state'],'found')
  path=self.root/(f['file_backup'].operation_key+'.json');body=path.read_bytes()
  try:
   path.write_bytes(b'{}');self.assertFalse(d.report(f['actor'],f['case'].pk,b.pk)['evidence_current'])
   with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,b.pk)
  finally:path.write_bytes(body)
  moved=path.with_suffix('.fixture-held');path.rename(moved)
  try:self.assertFalse(d.report(f['actor'],f['case'].pk,b.pk)['evidence_current'])
  finally:moved.rename(path)
  self.assertEqual(d.export(f['actor'],f['case'].pk,b.pk)['packet'],b.pk)
