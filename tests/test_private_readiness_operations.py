import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection,DatabaseError
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from apps.workflows import protection as d,operator_delivery as w,private_readiness_operations as private
from apps.workflows.operator_inventory import bundle,readable_manifest,jobs
from apps.workflows.operator_models import RecoveryPlan,RecoveryArtifact,RecoveryJob
from apps.workflows.operator_recovery import snapshot
from apps.identity.models import Grant
from apps.finance import readiness_acceptance as source
from apps.documents import validation as af
from apps.agents.models import AgentRun
from apps.agents.operations import investigate
from apps.agents import private_readiness_operations as agent
from apps.core.evidence_access import public_timeline
from apps.policy.operator_validators import PROTECTION,PRIVATE_SCHEMA
from adapters.operator_protection import TimeoutAfterMetadataAccept,restore_receipt,storage_root
from .private_operations_helpers import fixture,effect,plan
from .operator_helpers import policy,evidence,provision_test_database
from .readiness_helpers import endpoint
from .helpers import rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class PrivateReadinessOperationsTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());provision_test_database();cls.base=fixture()
 def setUp(self):
  self.f=dict(self.base);tmp=self.enterContext(TemporaryDirectory(prefix='accepted-private-ops-',dir=settings.BASE_DIR/'.runtime'));self.enterContext(patch('adapters.operator_protection.storage_root',return_value=Path(tmp)))
 def test_actual_export_backup_restore_and_independent_protection_review(self):
  f=self.f;export=effect(f,'export');backup=effect(f,'backup',export.pk);restore=effect(f,'restore',backup.pk)
  self.assertEqual(export.manifest,restore.manifest);self.assertFalse(restore.manifest['current_authority_restored']);self.assertEqual(restore.manifest['accepted_private_readiness'][0]['packet'],f['packet'].pk)
  self.assertNotIn('TX-001',json.dumps(restore.manifest));self.assertNotIn('sections',json.dumps(restore.manifest));self.assertFalse(restore.receipt['full_database_restore']);self.assertTrue(restore_receipt(restore.job)['native_isolated_postgres_write'])
  from adapters import operator_protection as native
  self.assertEqual((native.storage_root()/(backup.job.operation_key+'.json')).read_bytes(),native.encoded(backup.manifest))
  assessment=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'native-private-drill');self.assertTrue(assessment.result['documentary_complete']);self.assertTrue(assessment.result['native_metadata_drill_verified'])
  with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,assessment.pk,'confirm','self-review',f['ops_review_evidence'].pk)
  d.review(f['reviewer'],f['case'].pk,assessment.pk,'confirm','independent-ops',f['ops_review_evidence'].pk);value=d.report(f['actor'],f['case'].pk,assessment.pk);self.assertTrue(value['review_current']);self.assertFalse(value['operational_ready'])
 def test_missing_private_policy_holds_only_selected_private_effects(self):
  f=self.f;policy(f,PROTECTION,f['ops_values']['protection'])
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export')
  public=plan(f,'public-independent',selected=False);self.assertNotIn('accepted_private_readiness',effect(f,'export').manifest);self.assertNotEqual(public.pk,self.base['plan'].pk)
 def test_policy_and_plan_validate_exact_case_inventory_and_source_principals(self):
  f=self.f
  for change in [{'private_readiness_packet_ids':[999999]},{'private_disclosure':'all_bodies'},{'private_readiness_packet_ids':[]}]:
   with self.subTest(change=change),self.assertRaises(ValidationError):policy(f,PROTECTION,dict(f['protection_rules'],**change))
  payload=dict(f['plan'].payload,private_readiness_packet_ids=[999999])
  with self.assertRaises(ValidationError):d.capture_plan(f['actor'],f['case'].pk,'foreign-packet',payload,evidence(f,'ops_plan').pk)
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):policy(f,PROTECTION,f['protection_rules'])
 def test_owner_withdrawal_preserves_historical_download_but_holds_new_copy_and_current_review(self):
  f=self.f;export=effect(f,'export');assessment=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'before-withdrawal')
  af.review(f['acceptor'],f['case'].pk,f['owner_package'].pk,'acceptance','revoke','owner-withdraw',f['owner_evidence'].pk,'Withdrawing selected owner acceptance',None)
  readable_manifest(f['actor'],f['case'],export.manifest)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',export.pk)
  self.assertFalse(d.report(f['actor'],f['case'].pk,assessment.pk)['current_documentary_complete'])
  self.client.force_login(f['actor']);response=self.client.get(reverse('operator_artifact',args=[f['case'].pk,export.pk]));self.assertEqual(response.status_code,200);self.assertFalse(json.loads(response.content)['current_authority_restored'])
 def test_revoked_source_denies_cached_artifact_plan_inventory_and_http_choices(self):
  from apps.workflows.operator_views import visible_plans,commands
  f=self.f;export=effect(f,'export');record=snapshot(f['actor'],f['case'].pk,'with-private-protection')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):readable_manifest(f['actor'],f['case'],export.manifest)
  with self.assertRaises(PermissionDenied):snapshot(f['actor'],f['case'].pk,'with-private-protection')
  self.assertFalse(visible_plans(f['actor'],f['case']).filter(pk=f['plan'].pk).exists())
  self.client.force_login(f['actor'])
  for url in [reverse('operator_artifact',args=[f['case'].pk,export.pk]),reverse('operator_proof',args=[f['case'].pk,'plan',f['plan'].pk])]:self.assertEqual(self.client.get(url).status_code,403)
  for row in commands(f['actor'],f['case']):
   for field in row['form'].fields.values():
    q=getattr(field,'queryset',None)
    if q is not None and q.model is RecoveryPlan:self.assertFalse(q.filter(pk=f['plan'].pk).exists())
 def test_actual_backup_receipt_recovery_precedes_revoked_source_and_owner_authority(self):
  f=self.f;export=effect(f,'export');job=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',export.pk);w.run_once(TimeoutAfterMetadataAccept());job.refresh_from_db();self.assertEqual(job.status,'unknown')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);w.run_once();job.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(RecoveryArtifact.objects.filter(job=job).count(),1)
 def test_private_operator_retry_and_replacement_cannot_reset_original_budget(self):
  f=self.f;job=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');job.status='held';job.attempts=2;job.save(update_fields=['status','attempts']);w.operate(f['actor'],f['case'].pk,job.pk,'retry','Original intent only');job.refresh_from_db();self.assertEqual(job.attempts,2)
  job.status='held';job.save(update_fields=['status'])
  with self.assertRaises(ValidationError):w.operate(f['actor'],f['case'].pk,job.pk,'replace_intent','Do not reset unchanged context')
  job.status='unknown';job.save(update_fields=['status'])
  with self.assertRaises(ValidationError):w.operate(f['actor'],f['case'].pk,job.pk,'cancel','Cannot hide uncertain effects')
 def test_database_exact_private_plan_and_effect_lineage(self):
  from apps.core.models import Case
  f=self.f;c=Case.objects.create(tenant=f['case'].tenant,kind='project',title='Wrong private operator case',synthetic=True)
  with self.assertRaisesRegex(DatabaseError,'Exact private metadata plan'),transaction.atomic():RecoveryPlan.objects.create(case=c,reference='wrong-source',version=1,payload=f['plan'].payload,sha256=f['plan'].sha256,evidence=f['plan'].evidence,actor=f['actor'])
  job=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');m=copy.deepcopy(job.intent);m['manifest']['accepted_private_readiness'][0]['metadata']['acceptance_review']=999999
  with self.assertRaisesRegex(DatabaseError,'Exact accepted private metadata effect lineage'),transaction.atomic():RecoveryJob.objects.create(plan=f['plan'],kind='export',generation=2,operation_key='bad-private-effect',intent=m,actor=f['actor'])
 def test_generic_agent_and_timeline_omit_private_ops_and_live_guidance_has_no_effect_tools(self):
  f=self.f;effect(f,'export');before=AgentRun.objects.count();value=agent.investigate(f['actor'],f['case'].pk);self.assertTrue(value['findings']);self.assertEqual(value['effect_tools'],[]);self.assertEqual(AgentRun.objects.count(),before)
  run=investigate(f['actor'],f['case'].pk);self.assertNotIn('accepted_private_readiness',json.dumps(run.result));self.assertEqual(run.result['assessments'],[]);self.assertFalse(public_timeline(f['case']).filter(data__plan=f['plan'].pk).exists())
  rows,_,_=jobs(f['actor'],f['case'],include_private=False);self.assertFalse(any(x['family']=='protection' for x in rows))
 def test_http_selected_packet_plan_policy_ui_and_historical_artifact_download(self):
  from apps.policy.models import Configuration
  f=self.f;self.client.force_login(f['actor']);url=reverse('operations',args=[f['case'].pk]);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Accepted private readiness metadata');self.assertEqual(response['Cache-Control'],'no-store')
  response=self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':PROTECTION,'content':json.dumps(f['protection_rules']),'evidence':f['e'].pk,'effective_from':(timezone.now()-timedelta(seconds=1)).isoformat()});self.assertEqual(response.status_code,302);cfg=Configuration.objects.filter(case=f['case'],component=PROTECTION).latest('pk');self.assertEqual(cfg.envelope['value']['schema_ref'],PRIVATE_SCHEMA);self.assertEqual(cfg.states.latest('pk').state,'draft')
  payload=dict(f['plan'].payload);payload.pop(private.FIELD);before=AgentRun.objects.count();response=self.client.post(url,{'action':'plan','revision':rev(f['case']),'reference':'http-selected','payload':json.dumps(payload),'evidence':f['plan'].evidence_id,'predecessor':'','private_readiness_packets':[f['packet'].pk]});self.assertEqual(response.status_code,302);p=RecoveryPlan.objects.get(reference='http-selected');self.assertEqual(p.payload[private.FIELD],[f['packet'].pk]);self.assertEqual(AgentRun.objects.count(),before)
  self.assertEqual(self.client.get(reverse('operator_report',args=[f['case'].pk,999999])).status_code,404)

 def test_private_receipt_cannot_enter_a_public_readiness_contract(self):
  from apps.workflows import readiness as r,readiness_delivery as rw
  f=self.f;export=effect(f,'export');backup=effect(f,'backup',export.pk);restore=effect(f,'restore',backup.pk)
  payload=dict(f['contract_payload'],family='protection',target_key='internal:protection');contract=r.capture(f['actor'],f['case'].pk,'public-protection-capability',payload,evidence(f,'integration_contract').pk)
  count=r.IntegrationProbe.objects.count()
  with self.assertRaisesRegex(ValidationError,'exact private readiness binding'):rw.reserve(f['actor'],f['case'].pk,contract.pk,'private-receipt','receipt',restore.job_id)
  self.assertEqual(r.IntegrationProbe.objects.count(),count)
  job=rw.reserve(f['actor'],f['case'].pk,contract.pk,'public-health','health');rw.run_once(case_id=f['case'].pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed')

 def test_private_reference_cannot_be_downgraded_or_body_added_to_metadata(self):
  f=self.f;payload=dict(f['plan'].payload);payload.pop(private.FIELD)
  with self.assertRaises(ValidationError):d.capture_plan(f['actor'],f['case'].pk,f['plan'].reference,payload,f['plan'].evidence_id,predecessor=f['plan'].pk)
  export=effect(f,'export');forged=copy.deepcopy(export.manifest);forged['accepted_private_readiness'][0]['metadata']['body']='Do not export a body'
  with self.assertRaises(ValidationError):readable_manifest(f['actor'],f['case'],forged)
