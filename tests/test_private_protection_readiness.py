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
from apps.workflows import readiness as r,readiness_delivery as w,private_protection_readiness as n,operator_delivery as ow
from apps.workflows.readiness_models import IntegrationObservation,IntegrationProbe,PrivateProtectionReadiness
from apps.policy.readiness_validators import PRIVATE_COMPONENT,PRIVATE_SCHEMA
from apps.policy.services import transition
from apps.identity.models import Grant
from apps.documents import validation as af
from apps.agents.models import AgentRun
from apps.agents.integrations import investigate
from apps.agents import private_protection_readiness as agent
from apps.core.evidence_access import public_timeline
from adapters.operator_protection import NativeMetadataProtectionAdapter
from adapters.readiness import ReadinessAdapter
from .private_protection_helpers import fixture,capture,configure,probe,assessed
from .readiness_helpers import endpoint,policy
from .operator_helpers import provision_test_database
from .helpers import rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class PrivateProtectionReadinessTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());provision_test_database()
  tmp=cls.enterClassContext(TemporaryDirectory(prefix='private-protection-',dir=settings.BASE_DIR/'.runtime'))
  cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=Path(tmp)))
  cls.base=fixture()
 def setUp(self):self.f=dict(self.base)
 def ready(self):
  f=self.f;f['private_contract']=capture(f);f['private_policy']=configure(f);assessed(f);return f
 def test_exact_native_health_receipt_independent_review_and_restore_changes_provenance(self):
  f=self.ready();b=n.binding(f['private_contract']);self.assertEqual(b.job_id,f['restore'].pk)
  self.assertTrue(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['review_current'])
  obs=IntegrationObservation.objects.filter(contract=f['private_contract']);receipt=obs.get(payload__kind='receipt')
  self.assertEqual(receipt.payload['receipt_provenance']['state'],'not_found')
  self.assertFalse(receipt.payload['native_protection']['source']['current_authority_restored'])
  self.assertNotIn('accepted_private_readiness',json.dumps(receipt.payload));self.assertNotIn('TX-001',json.dumps(receipt.payload))
  r.select(f['actor'],f['case'].pk,f['private_contract'].pk,f['private_selection_evidence'].pk)
  lease=ow.claim();self.assertEqual(lease[0],f['restore'].pk);value=ow.dispatch(*lease,NativeMetadataProtectionAdapter())
  try:ow.finish(*lease,'confirmed',value)
  except ValidationError as exc:
   self.assertIn('Expired protection worker fence',str(exc));f['restore'].refresh_from_db();self.assertLessEqual(f['restore'].lease_until,timezone.now())
   from adapters.operator_protection import restore_receipt
   self.assertIsNotNone(restore_receipt(f['restore']));ow.run_once()
  self.assertFalse(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['current_ready'])
  assessed(f,'after-actual-restore');latest=IntegrationObservation.objects.filter(contract=f['private_contract'],payload__kind='receipt').latest('pk')
  self.assertEqual(latest.payload['receipt_provenance']['state'],'found');self.assertFalse(latest.payload['receipt_provenance']['full_database_restore'])
  self.assertTrue(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['review_current'])
 def test_independent_policy_does_not_stale_source_acceptance_and_missing_holds_only_private(self):
  f=self.f;f['private_contract']=capture(f)
  with self.assertRaises(ValidationError):probe(f,'health')
  with self.assertRaises(ValidationError):r.select(f['actor'],f['case'].pk,f['private_contract'].pk,f['private_selection_evidence'].pk)
  public=r.capture(f['actor'],f['case'].pk,'public-health',f['private_payload'],f['private_contract_evidence'].pk)
  j=w.reserve(f['actor'],f['case'].pk,public.pk,'health','health');w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed')
  configure(f);assessed(f)
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk))
 def test_policy_validates_inventory_roles_independence_and_original_private_grants(self):
  f=self.f
  for change in [{'private_protection_job_ids':[]},{'private_protection_job_ids':[999999]},{'private_protection_job_ids':[f['restore'].pk,f['restore'].pk]},{'independent_review':False},{'require_receipt_probe':False},{'reviewer_id':f['actor'].pk}]:
   with self.subTest(change=change),self.assertRaises(ValidationError):policy(f,PRIVATE_COMPONENT,dict(f['private_rules'],**change))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):configure(f)
 def test_public_contract_and_wrong_job_cannot_probe_private_receipt_or_downgrade_reference(self):
  f=self.ready();public=r.capture(f['actor'],f['case'].pk,'public',f['private_payload'],f['private_contract_evidence'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,public.pk,'launder','receipt',f['restore'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,'wrong','receipt',999999)
  with self.assertRaises(ValidationError):r.capture(f['actor'],f['case'].pk,'private-restore',f['private_payload'],f['private_contract_evidence'].pk,predecessor=f['private_contract'].pk)
 def test_revoked_source_denies_cached_reads_forms_and_private_guidance(self):
  f=self.ready();obs=IntegrationObservation.objects.filter(contract=f['private_contract']).first()
  self.client.force_login(f['actor']);url=reverse('integration_source',args=[f['case'].pk,'observation',obs.pk]);self.assertEqual(self.client.get(url).status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)
  self.assertEqual(self.client.get(url).status_code,403);self.assertEqual(agent.investigate(f['actor'],f['case'])['findings'],[])
  self.assertFalse(n.visible_jobs(f['actor'],f['case']).exists());self.assertFalse(r.visible_contracts(f['actor'],f['case']).filter(pk=f['private_contract'].pk).exists())
 def test_owner_withdrawal_preserves_historical_report_but_holds_current_probe_and_review(self):
  f=self.ready();af.review(f['acceptor'],f['case'].pk,f['owner_package'].pk,'acceptance','revoke','withdraw',f['owner_evidence'].pk,'Withdraw current acceptance',None)
  report=r.report(f['actor'],f['case'].pk,f['private_assessment'].pk);self.assertTrue(report['recorded_ready']);self.assertFalse(report['current_ready'])
  with self.assertRaises(ValidationError):probe(f,'health','after-withdraw')
  r.review(f['reviewer'],f['case'].pk,f['private_assessment'].pk,'withdraw','withdraw',f['private_review_evidence'].pk)
 def test_policy_revocation_holds_new_use(self):
  f=self.ready();transition(f['actor'],f['private_policy'].pk,'revoked')
  self.assertFalse(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['current_ready'])
  with self.assertRaises(ValidationError):probe(f,'health','revoked')
 def test_lost_finish_reconciles_committed_observation_after_source_revocation_and_keeps_budget(self):
  f=self.ready();j=w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,'lost-finish','health');lease=w.claim(f['case'].pk);value=w.execute(*lease,ReadinessAdapter())
  IntegrationProbe.objects.filter(pk=j.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(IntegrationObservation.objects.filter(job=j).count(),1)
  self.assertFalse(Grant.objects.get(case=f['case'],user=f['actor'],action='ledger.private.read').active)
 def test_retry_cannot_reset_private_original_budget(self):
  f=self.ready();j=w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,'budget','health');IntegrationProbe.objects.filter(pk=j.pk).update(status='held',attempts=j.intent['max_attempts'])
  with self.assertRaises(ValidationError):w.operate(f['actor'],f['case'].pk,j.pk,'retry','Preserve exhausted original budget')
 def test_sql_immutable_binding_wrong_probe_and_observation_lineage(self):
  f=self.ready();b=n.binding(f['private_contract'])
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateProtectionReadiness.objects.filter(pk=b.pk).update(snapshot={})
  original=IntegrationProbe.objects.filter(contract=f['private_contract']).first()
  with self.assertRaises(DatabaseError),transaction.atomic():IntegrationProbe.objects.create(contract=f['private_contract'],actor=f['actor'],operation_key='a'*64,intent_key='sql-wrong',intent=dict(original.intent,source_job=999999,kind='receipt'))
  j=w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,'sql-observation','health')
  with self.assertRaises(DatabaseError),transaction.atomic():IntegrationObservation.objects.create(contract=f['private_contract'],job=j,actor=f['actor'],external_key='native:bad',payload={'kind':'health','native_protection':{}},sha256='a'*64)
 def test_generic_agent_timeline_omit_private_and_typed_ui_agent_capture(self):
  f=self.ready();before=AgentRun.objects.count();value=agent.investigate(f['actor'],f['case']);self.assertTrue(value['findings']);self.assertEqual(value['effect_tools'],[]);self.assertEqual(AgentRun.objects.count(),before)
  IntegrationProbe.objects.filter(contract=f['private_contract']).update(status='held')
  run=investigate(f['actor'],f['case'].pk);self.assertEqual(run.result['probe_findings'],[]);self.assertNotIn('private-restore',json.dumps(run.result))
  self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.private_protection').exists())
  self.client.force_login(f['actor']);url=reverse('integration_readiness',args=[f['case'].pk]);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Private protection readiness')
  self.assertEqual(self.client.post(url,{'action':'capture','revision':rev(f['case']),'reference':'ui-private','payload':json.dumps(f['private_payload']),'evidence':f['private_contract_evidence'].pk,'native_protection_job':f['restore'].pk}).status_code,302)
  self.assertTrue(PrivateProtectionReadiness.objects.filter(contract__reference='ui-private').exists())
  from apps.policy.models import Configuration
  before=Configuration.objects.filter(component=PRIVATE_COMPONENT).count()
  self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':PRIVATE_COMPONENT,'content':json.dumps(f['private_rules']),'evidence':f['sources']['policy_decision'].pk,'effective_from':timezone.now().isoformat()}).status_code,302)
  self.assertEqual(Configuration.objects.filter(component=PRIVATE_COMPONENT).count(),before+1)
  from apps.policy.readiness_drafts import draft_readiness_policy
  draft=draft_readiness_policy(f['actor'],f['case'].pk,PRIVATE_COMPONENT,f['private_rules'],f['sources']['policy_decision'].pk,timezone.now())
  self.assertEqual(draft.envelope['value']['schema_ref'],PRIVATE_SCHEMA)

 def test_exact_private_enrollment_holds_only_selected_restore_and_receipts_reconcile_first(self):
  f=self.f;f['private_contract']=capture(f);configure(f)
  r.select(f['actor'],f['case'].pk,f['private_contract'].pk,f['private_selection_evidence'].pk)
  self.assertIsNone(r.gate(f['case'],'protection'))
  lease=ow.claim()
  with self.assertRaises(ValidationError):ow.dispatch(*lease,NativeMetadataProtectionAdapter())
  from apps.workflows.operator_models import RecoveryJob,RecoveryArtifact
  assessed(f);RecoveryJob.objects.filter(pk=f['restore'].pk).update(lease_until=timezone.now()-timedelta(seconds=1));lease=ow.claim();receipt=ow.dispatch(*lease,NativeMetadataProtectionAdapter())
  # Actual isolated commit before local finish: the original receipt survives changed source/readiness controls.
  IntegrationProbe.objects.filter(contract=f['private_contract']).update(status='held')
  from apps.workflows.operator_models import RecoveryJob,RecoveryArtifact
  RecoveryJob.objects.filter(pk=f['restore'].pk).update(lease_until=timezone.now()-timedelta(seconds=1))
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  ow.run_once();self.assertEqual(RecoveryArtifact.objects.filter(job=f['restore']).count(),1)
 def test_private_policy_supersession_and_expiry_are_current_use_holds(self):
  f=self.ready();old=f['private_policy'];policy(f,PRIVATE_COMPONENT,dict(f['private_rules'],freshness_seconds=300))
  self.assertFalse(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['current_ready'])
  assessed(f,'new-policy');future=timezone.now()+timedelta(seconds=301)
  with patch('apps.workflows.readiness.timezone.now',return_value=future):
   self.assertFalse(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['current_ready'])
 def test_sql_rejects_public_receipt_laundering_and_retroactive_assessment_binding(self):
  f=self.ready();b=n.binding(f['private_contract'])
  public=r.capture(f['actor'],f['case'].pk,'sql-public',f['private_payload'],f['private_contract_evidence'].pk)
  original=IntegrationProbe.objects.filter(contract=f['private_contract'],intent__kind='receipt').first()
  value=dict(original.intent);value.pop('native_protection')
  with self.assertRaises(DatabaseError),transaction.atomic():IntegrationProbe.objects.create(contract=public,actor=f['actor'],operation_key='b'*64,intent_key='launder',intent=value)
  # A direct SQL caller cannot relabel a public assessment's old contract as private later.
  r.assess(f['actor'],f['case'].pk,public.pk,'public-no-evidence')
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateProtectionReadiness.objects.create(contract=public,job=f['restore'],actor=f['actor'],snapshot=b.snapshot,sha256=b.sha256)
