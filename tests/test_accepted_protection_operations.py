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
from apps.workflows import protection as d,operator_delivery as w,private_readiness_operations as private,accepted_protection_operations as domain
from apps.workflows.operator_models import RecoveryPlan,RecoveryJob,RecoveryArtifact
from apps.workflows.operator_inventory import bundle,readable_manifest,jobs
from apps.workflows.operator_recovery import snapshot
from apps.documents import protection_acceptance as source,validation as af
from apps.identity.models import Grant
from apps.agents import private_readiness_operations as agent
from apps.agents.operations import investigate
from apps.agents.models import AgentRun
from apps.core.evidence_access import public_timeline
from apps.policy.services import transition,resolve
from apps.policy.models import Configuration
from adapters.operator_protection import NativeMetadataProtectionAdapter,TimeoutAfterMetadataAccept,restore_receipt,file_receipt
from adapters.accepted_protection_operations import AcceptedProtectionOperatorAdapter as Adapter
from .file_acceptance_helpers import fixture,owners,configure,reviews
from .operator_helpers import policy,evidence,provision_test_database
from .readiness_helpers import endpoint
from .helpers import rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class AcceptedProtectionOperationsTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());cls.root=Path(cls.enterClassContext(TemporaryDirectory(prefix='accepted-protection-ops-',dir=settings.BASE_DIR/'.runtime')));cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=cls.root));provision_test_database()
  f=fixture('accepted-protection-ops');owners(f);configure(f);reviews(f)
  w.operate(f['actor'],f['case'].pk,f['file_backup'].pk,'cancel','Keep original not-found evidence; use a distinct export plan')
  f['source_plan']=f['plan'];f['rules']={domain.FIELD:[f['protection_packet'].pk],'private_disclosure':'accepted_metadata_only'};f['ops_policy']=policy(f,domain.COMPONENT,f['rules'])
  cls.base=f;cls.now=timezone.now()
 def setUp(self):
  self.f=dict(self.base);self.enterContext(patch('django.utils.timezone.now',return_value=self.now))
 def plan(self,reference='accepted-protection',mixed=False):
  f=self.f;selected=[f['protection_packet'].pk];old=[f['packet'].pk] if mixed else []
  m=bundle(f['actor'],f['case'],200,old,selected);v=dict(f['source_plan'].payload,**{domain.FIELD:selected},expected_manifest_sha256=__import__('apps.documents.contracts',fromlist=['digest']).digest(m),expected_record_count=len(m['evidence'])+len(m['jobs'])+private.count(m))
  if not mixed:v.pop(private.FIELD,None)
  f['plan']=d.capture_plan(f['actor'],f['case'].pk,reference,v,evidence(f,'ops_plan').pk);return f['plan']
 def effect(self,kind,input_id=None):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,kind,input_id);lease=w.claim();self.assertEqual(lease[0],j.pk);r=w.dispatch(*lease,NativeMetadataProtectionAdapter());w.finish(*lease,'confirmed',r);return RecoveryArtifact.objects.get(job=j)
 def test_connected_file_acceptance_export_backup_isolated_restore_and_independent_review(self):
  f=self.f;p=self.plan();e=self.effect('export');b=self.effect('backup',e.pk);r=self.effect('restore',b.pk)
  self.assertTrue(file_receipt(b.job));self.assertTrue(restore_receipt(r.job));self.assertEqual(e.manifest,b.manifest);self.assertEqual(b.manifest,r.manifest)
  row=e.manifest[domain.ROWS][0];self.assertEqual(row['metadata'],source.export(f['actor'],f['case'].pk,f['protection_packet'].pk));self.assertFalse(row['current_authority_restored']);self.assertEqual(row['metadata']['evidence']['job_kind'],'backup')
  self.assertNotIn('accepted_private_readiness',e.manifest);self.assertNotIn(str(self.root),json.dumps(e.manifest));self.assertNotIn('TX-001',json.dumps(e.manifest))
  a=d.assess(f['actor'],f['case'].pk,p.pk,'complete');self.assertTrue(a.result['documentary_complete']);self.assertEqual(a.snapshot['accepted_protection_policy'],f['ops_policy'].pk)
  d.review(f['reviewer'],f['case'].pk,a.pk,'confirm','independent',evidence(f,'ops_review').pk);self.assertTrue(d.report(f['actor'],f['case'].pk,a.pk)['review_current'])
  self.assertTrue(source.export(f['actor'],f['case'].pk,f['protection_packet'].pk));self.assertFalse(a.result['full_database_restore_verified'])
 def test_missing_invalid_revised_revoked_policy_holds_only_new_effect_and_preserves_source(self):
  f=self.f;p=self.plan();transition(f['actor'],f['ops_policy'].pk,'revoked')
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,p.pk,'export')
  self.assertTrue(source.export(f['actor'],f['case'].pk,f['protection_packet'].pk))
  for value in [{domain.FIELD:[],'private_disclosure':'accepted_metadata_only'},{domain.FIELD:[999999],'private_disclosure':'accepted_metadata_only'},dict(f['rules'],private_disclosure='all_bodies')]:
   with self.subTest(value=value),self.assertRaises(ValidationError):policy(f,domain.COMPONENT,value)
  f['ops_policy']=policy(f,domain.COMPONENT,f['rules']);j=w.reserve(f['actor'],f['case'].pk,p.pk,'export');policy(f,domain.COMPONENT,f['rules']);lease=w.claim()
  with self.assertRaisesMessage(ValidationError,'Reserved protection intent changed'):w.dispatch(*lease,NativeMetadataProtectionAdapter())
  self.assertEqual(RecoveryArtifact.objects.filter(job=j).count(),0);self.assertTrue(source.export(f['actor'],f['case'].pk,f['protection_packet'].pk))
 def test_owner_withdrawal_preserves_sealed_history_but_holds_new_copy(self):
  f=self.f;self.plan();e=self.effect('export');af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','withdraw',f['protection_owner_evidence'].pk,'Separate human withdrawal',None)
  readable_manifest(f['actor'],f['case'],e.manifest)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',e.pk)
  self.client.force_login(f['actor']);response=self.client.get(reverse('operator_artifact',args=[f['case'].pk,e.pk]));self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store')
 def test_source_revocation_denies_cached_download_plan_inventory_ui_and_agent(self):
  from apps.workflows.operator_views import visible_plans,commands
  f=self.f;self.plan();e=self.effect('export');snapshot(f['actor'],f['case'].pk,'cached')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  for action in [lambda:readable_manifest(f['actor'],f['case'],e.manifest),lambda:snapshot(f['actor'],f['case'].pk,'cached'),lambda:agent.prepare(f['actor'],f['case'].pk,'denied',f['plan'].payload,f['plan'].evidence_id)]:
   with self.assertRaises(PermissionDenied):action()
  self.assertFalse(visible_plans(f['actor'],f['case']).filter(pk=f['plan'].pk).exists());self.assertEqual(agent.investigate(f['actor'],f['case'].pk)['findings'],[])
  self.client.force_login(f['actor'])
  for url in [reverse('operator_artifact',args=[f['case'].pk,e.pk]),reverse('operator_proof',args=[f['case'].pk,'plan',f['plan'].pk])]:self.assertEqual(self.client.get(url).status_code,403)
  form=next(x['form'] for x in commands(f['actor'],f['case']) if x['form']['action'].value()=='plan');self.assertFalse(form.fields['private_protection_packets'].queryset.exists())
 def test_actual_committed_backup_receipt_recovery_precedes_revocation_and_preserves_budget(self):
  f=self.f;self.plan();e=self.effect('export');j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',e.pk);w.run_once(TimeoutAfterMetadataAccept());j.refresh_from_db();self.assertEqual(j.status,'unknown');before=file_receipt(j);files=set(self.root.iterdir())
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);transition(f['reviewer'],f['ops_policy'].pk,'revoked');w.run_once();j.refresh_from_db()
  self.assertEqual(j.status,'confirmed');self.assertEqual(j.attempts,2);self.assertEqual(set(self.root.iterdir()),files);self.assertEqual(file_receipt(j),before);self.assertEqual(RecoveryArtifact.objects.filter(job=j).count(),1)
 def test_retry_budget_source_cycle_and_no_public_downgrade(self):
  f=self.f;p=self.plan();payload=dict(p.payload)
  with self.assertRaisesMessage(ValidationError,'own source closure'):d.capture_plan(f['actor'],f['case'].pk,f['source_plan'].reference,payload,p.evidence_id,predecessor=f['source_plan'].pk)
  payload.pop(domain.FIELD)
  with self.assertRaisesMessage(ValidationError,'public reference'):d.capture_plan(f['actor'],f['case'].pk,p.reference,payload,p.evidence_id,predecessor=p.pk)
  j=w.reserve(f['actor'],f['case'].pk,p.pk,'export');j.status='held';j.attempts=2;j.save(update_fields=['status','attempts']);w.operate(f['actor'],f['case'].pk,j.pk,'retry','Original intent');j.refresh_from_db();self.assertEqual(j.attempts,2)
  j.status='held';j.save(update_fields=['status'])
  with self.assertRaisesMessage(ValidationError,'cannot be reset'):w.operate(f['actor'],f['case'].pk,j.pk,'replace_intent','Cannot reset')
 def test_raw_sql_case_scope_cycle_effect_lineage_and_closed_fields(self):
  f=self.f;p=self.plan()
  from apps.core.models import Case
  c=Case.objects.create(tenant=f['case'].tenant,kind='project',title='Wrong protection metadata case',synthetic=True)
  with self.assertRaisesRegex(DatabaseError,'case/process scope'),transaction.atomic():RecoveryPlan.objects.create(case=c,reference='wrong-case',version=1,payload=p.payload,sha256=p.sha256,evidence=p.evidence,actor=f['actor'])
  with self.assertRaisesRegex(DatabaseError,'own source closure'),transaction.atomic():RecoveryPlan.objects.create(case=f['case'],reference=f['source_plan'].reference,version=f['source_plan'].version+1,payload=p.payload,sha256=p.sha256,evidence=p.evidence,actor=f['actor'])
  value=dict(p.payload,process_ids=['P13'])
  with self.assertRaisesRegex(DatabaseError,'case/process scope'),transaction.atomic():RecoveryPlan.objects.create(case=f['case'],reference='bad-scope',version=1,payload=value,sha256=p.sha256,evidence=p.evidence,actor=f['actor'])
  j=w.reserve(f['actor'],f['case'].pk,p.pk,'export')
  for field,value,message in [('acceptance_review',999999,'effect lineage'),('evidence',{},'effect lineage'),('body','private body','metadata fields'),('current_authority_restored',True,'restore authority')]:
   bad=copy.deepcopy(j.intent);bad['manifest'][domain.ROWS][0]['metadata'][field]=value
   with self.subTest(field=field),self.assertRaisesRegex(DatabaseError,message),transaction.atomic():RecoveryJob.objects.create(plan=p,kind='export',generation=2,operation_key='forged-'+field,intent=bad,actor=f['actor'])
 def test_live_agent_http_selected_inventory_policy_draft_and_generic_privacy(self):
  f=self.f;p=self.plan();e=self.effect('export');before=AgentRun.objects.count();v=agent.investigate(f['actor'],f['case'].pk);self.assertEqual(v['effect_tools'],[]);self.assertTrue(v['findings']);self.assertEqual(AgentRun.objects.count(),before)
  self.assertFalse(public_timeline(f['case']).filter(data__plan=p.pk).exists());self.assertFalse(any(x['family']=='protection' for x in jobs(f['actor'],f['case'],include_private=False)[0]));self.assertNotIn(domain.ROWS,json.dumps(investigate(f['actor'],f['case'].pk).result))
  self.client.force_login(f['actor']);url=reverse('operations',args=[f['case'].pk]);response=self.client.get(url);self.assertContains(response,'Accepted private protection metadata');self.assertEqual(response['Cache-Control'],'no-store')
  payload=dict(p.payload);payload.pop(domain.FIELD);response=self.client.post(url,{'action':'plan','revision':rev(f['case']),'reference':'http-protection','payload':json.dumps(payload),'evidence':p.evidence_id,'predecessor':'','private_protection_packets':[f['protection_packet'].pk]});self.assertEqual(response.status_code,302);self.assertEqual(RecoveryPlan.objects.get(reference='http-protection').payload[domain.FIELD],[f['protection_packet'].pk])
  response=self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':domain.COMPONENT,'content':json.dumps(f['rules']),'evidence':f['e'].pk,'effective_from':(timezone.now()-timedelta(seconds=1)).isoformat()});self.assertEqual(response.status_code,302);cfg=Configuration.objects.filter(case=f['case'],component=domain.COMPONENT).latest('pk');self.assertEqual(cfg.states.latest('pk').state,'draft')
 def test_mixed_inventories_retain_distinct_models_and_closed_historical_rows(self):
  f=self.f;self.plan(mixed=True);e=self.effect('export');self.assertEqual(len(e.manifest[domain.ROWS]),1);self.assertEqual(len(e.manifest['accepted_private_readiness']),1);self.assertEqual(private.count(e.manifest),2)
  bad=copy.deepcopy(e.manifest);bad[domain.ROWS][0]['metadata']['body']='Forbidden'
  with self.assertRaisesMessage(ValidationError,'Closed accepted protection fields'):readable_manifest(f['actor'],f['case'],bad)
  self.assertEqual(e.manifest['private_metadata_schema'],'accepted_private_readiness_v1');self.assertEqual(e.manifest['protection_metadata_schema'],domain.SCHEMA)
  bad=copy.deepcopy(e.manifest);bad[domain.ROWS]=bad['accepted_private_readiness']
  with self.assertRaisesMessage(ValidationError,'Closed accepted protection fields'):readable_manifest(f['actor'],f['case'],bad)
 def test_original_private_grants_required_for_configuration_and_expired_source_holds_new_effect(self):
  f=self.f;p=self.plan();e=self.effect('export')
  with transaction.atomic():
   Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False)
   with self.assertRaisesMessage(ValidationError,'original protection source/export grants'):policy(f,domain.COMPONENT,f['rules'])
   transaction.set_rollback(True) # Isolate permission rejection from the separate expiry proof.
  self.assertTrue(source.export(f['actor'],f['case'].pk,f['protection_packet'].pk))
  with patch('django.utils.timezone.now',return_value=self.now+timedelta(seconds=3601)):
   readable_manifest(f['actor'],f['case'],e.manifest)
   with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,p.pk,'backup',e.pk)

 def test_agent_holds_superseded_plan_and_does_not_cache_authority_across_commands(self):
  f=self.f;p=self.plan();payload=dict(p.payload,build_ref='explicit-successor-build');new=d.capture_plan(f['actor'],f['case'].pk,p.reference,payload,p.evidence_id,predecessor=p.pk)
  value=agent.investigate(f['actor'],f['case'].pk);rows={r['plan']:r for r in value['findings']};self.assertFalse(rows[p.pk]['new_effect_ready']);self.assertTrue(rows[new.pk]['new_effect_ready']);self.assertEqual(rows[new.pk]['readiness_scope'],'current_plan_and_selected_metadata_only');self.assertIn('OPS.accepted_protection_rules',rows[p.pk]['question'])
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);self.assertEqual(agent.investigate(f['actor'],f['case'].pk)['findings'],[])
 def test_missing_and_corrupt_actual_backup_hold_new_restore_despite_cached_artifact(self):
  f=self.f;self.plan();e=self.effect('export');b=self.effect('backup',e.pk);path=self.root/(b.job.operation_key+'.json');self.assertEqual(path.parent.resolve(),self.root.resolve());self.assertTrue(self.root.resolve().is_relative_to((settings.BASE_DIR/'.runtime').resolve()));path.write_bytes(b'Conflicting owned synthetic metadata bytes')
  with self.assertRaisesMessage(ValidationError,'bytes differ'):w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk)
  path.unlink()
  with self.assertRaisesMessage(ValidationError,'backup bytes unavailable'):w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk)
  readable_manifest(f['actor'],f['case'],b.manifest);self.assertEqual(RecoveryArtifact.objects.get(pk=b.pk).manifest,e.manifest);self.assertTrue(source.export(f['actor'],f['case'].pk,f['protection_packet'].pk))
 def test_af13_operator_job_cannot_masquerade_as_old_native_or_public_receipt_inventory(self):
  from apps.workflows import readiness as r,readiness_delivery as rw
  from adapters.private_file_readiness import PrivateFileReadinessAdapter
  from adapters.private_protection_readiness import PrivateProtectionReadinessAdapter
  f=self.f;self.plan();e=self.effect('export');contract=r.capture(f['actor'],f['case'].pk,'public-af13-boundary',f['file_payload'],evidence(f,'integration_contract').pk);before=r.IntegrationProbe.objects.count()
  with self.assertRaisesRegex(ValidationError,'exact private readiness binding'):rw.reserve(f['actor'],f['case'].pk,contract.pk,'no-public-receipt','receipt',e.job_id)
  self.assertEqual(r.IntegrationProbe.objects.count(),before)
  with self.assertRaises(ValidationError):PrivateFileReadinessAdapter().job(f['case'],e.job_id)
  b=self.effect('backup',e.pk);restore=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk)
  with self.assertRaises(ValidationError):PrivateProtectionReadinessAdapter().job(f['case'],restore.pk)

 def test_mixed_inventory_native_choices_and_raw_sql_bindings_are_rejected(self):
  from apps.workflows import readiness as r,readiness_delivery as rw,private_file_readiness as file_scope,private_protection_readiness as restore_scope
  from apps.workflows.readiness_models import IntegrationProbe,PrivateFileReadiness,PrivateProtectionReadiness
  from adapters.private_file_readiness import PrivateFileReadinessAdapter
  from adapters.private_protection_readiness import PrivateProtectionReadinessAdapter
  from apps.documents.contracts import digest
  f=self.f;self.plan(mixed=True);e=self.effect('export');b=self.effect('backup',e.pk);restore=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk)
  for adapter,job in [(PrivateFileReadinessAdapter(),e.job),(PrivateProtectionReadinessAdapter(),restore)]:
   with self.assertRaises(ValidationError):adapter.job(f['case'],job.pk)
   with self.assertRaises(ValidationError):adapter.access(f['actor'],job)
  self.assertFalse(file_scope.visible_jobs(f['actor'],f['case']).filter(pk=e.job_id).exists());self.assertFalse(restore_scope.visible_jobs(f['actor'],f['case']).filter(pk=restore.pk).exists())
  contract=r.capture(f['actor'],f['case'].pk,'mixed-native-boundary',f['file_payload'],evidence(f,'integration_contract').pk)
  with self.assertRaisesRegex(ValidationError,'exact private readiness binding'):rw.reserve(f['actor'],f['case'].pk,contract.pk,'no-mixed-receipt','receipt',e.job_id)
  intent=rw.intent(f['actor'],contract,'health',None);intent=dict(intent,kind='receipt',source_job=e.job_id)
  for source_id in [e.job_id,'00'+str(e.job_id)]:
   with self.subTest(source_id=source_id),self.assertRaisesRegex(DatabaseError,'AF13 protection inventory requires an explicit native readiness contract'),transaction.atomic():IntegrationProbe.objects.create(contract=contract,intent_key='raw-mixed-probe',operation_key=digest({'synthetic':'raw-mixed-probe','case':str(f['case'].pk)}),intent=dict(intent,source_job=source_id),actor=f['actor'])
  for model,job in [(PrivateFileReadiness,e.job),(PrivateProtectionReadiness,restore)]:
   with self.subTest(model=model.__name__),self.assertRaisesRegex(DatabaseError,'AF13 protection inventory requires an explicit native readiness contract'),transaction.atomic():model.objects.create(contract=contract,job=job,snapshot={},sha256=digest({}),actor=f['actor'])
  public=rw.reserve(f['actor'],f['case'].pk,contract.pk,'public-health-still-available','health');self.assertEqual(public.intent['source_job'],None)

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class AcceptedRestoreOperationsTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  from .accepted_protection_operations_helpers import fixture as restore_fixture
  cls.enterClassContext(endpoint());cls.root=Path(cls.enterClassContext(TemporaryDirectory(prefix='accepted-restore-ops-',dir=settings.BASE_DIR/'.runtime')));cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=cls.root));provision_test_database();cls.base=restore_fixture('accepted-restore-ops',kind='restore',configured=False);cls.now=timezone.now()
 def test_restore_acceptance_plan_before_missing_policy_then_distinct_metadata_effect(self):
  from .accepted_protection_operations_helpers import plan
  with patch('django.utils.timezone.now',return_value=self.now):
   f=dict(self.base);p=plan(f);self.assertEqual(resolve(domain.COMPONENT,f['case']).status,'MISSING')
   with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,p.pk,'export')
   self.assertTrue(source.export(f['actor'],f['case'].pk,f['protection_packet'].pk));policy(f,domain.COMPONENT,f['rules']);j=w.reserve(f['actor'],f['case'].pk,p.pk,'export');w.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');e=RecoveryArtifact.objects.get(job=j)
   self.assertIn('restore_job',e.manifest[domain.ROWS][0]['metadata']['evidence']);self.assertNotIn('job_kind',e.manifest[domain.ROWS][0]['metadata']['evidence']);readable_manifest(f['actor'],f['case'],e.manifest);self.assertFalse(e.manifest[domain.ROWS][0]['metadata']['full_database_restore'])
