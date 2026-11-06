import json
from copy import deepcopy
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.urls import reverse
from apps.core.models import Case
from apps.core.evidence_access import public_timeline
from apps.identity.models import Grant
from apps.baas import support_release as d,support_release_delivery as worker
from apps.workflows import operator_inventory as inventory,operator_recovery as ops,readiness as r,readiness_delivery as rw
from apps.workflows.operator_models import OperatorInventory,RecoveryArtifact
from apps.workflows.readiness_models import IntegrationObservation
from apps.policy.operator_validators import OPERATOR
from apps.policy.readiness_validators import ADAPTER
from apps.policy.services import transition
from apps.agents.models import AgentRun
from adapters.support_response import InternalSupportResponseAdapter
from .support_release_helpers import ready,packet,release
from .support_response_operations_helpers import operators,enroll,plan
from .support_agent_helpers import activate
from .operator_helpers import policy,effect,provision_test_database
from .readiness_helpers import endpoint
from .helpers import rev

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class SupportResponseOperationsTests(TestCase):
 @classmethod
 def setUpClass(cls):
  cls.endpoint=endpoint();cls.endpoint.__enter__()
  try:super().setUpClass()
  except BaseException:cls.endpoint.__exit__(None,None,None);raise
 @classmethod
 def tearDownClass(cls):
  try:super().tearDownClass()
  finally:cls.endpoint.__exit__(None,None,None)
 @classmethod
 def setUpTestData(cls):cls.f=ready('response-ops')
 def test_previous_release_implementation_is_real_and_inventory_contains_only_metadata(self):
  f=self.f;j=release(f);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.get(job=j).classification,'internal_storage_only')
  rows,omitted,grants=inventory.jobs(f['actor'],f['case']);row=next(x for x in rows if x['family']=='supportresponse');self.assertEqual(row['id'],j.pk);self.assertIn('/support/responses/',row['source_url']);self.assertNotIn('body',row);self.assertNotIn('recipient',row);self.assertTrue(set(inventory.PRIVATE_GRANTS)<=set(grants));self.assertEqual(r.lookup_source('supportresponse',j).job_id,j.pk)
 def test_native_revocation_omits_inventory_and_denies_manifest_and_cached_receipt_probe(self):
  f=self.f;j=release(f);m=inventory.bundle(f['actor'],f['case'],200);enroll(f,j);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
  rows,omitted,_=inventory.jobs(f['actor'],f['case']);self.assertFalse(any(x['family']=='supportresponse' for x in rows));self.assertIn('supportresponse',omitted)
  for call in [lambda:inventory.readable_manifest(f['actor'],f['case'],m),lambda:r.source_job(f['actor'],f['case'],'supportresponse',j.pk),lambda:r.report(f['actor'],f['case'].pk,f['assessment'].pk)]:
   with self.assertRaises(PermissionDenied):call()
 def test_operator_policy_requires_native_grants_and_forbids_intent_replacement(self):
  f=self.f;v=operators(f,False)
  for change in [{'routes':[{'family':'supportresponse','actions':['replace_intent']}]},{'routes':[{'family':'arbitrary','actions':['retry']}]}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,OPERATOR,dict(v['operator'],**change))
  Grant.objects.filter(case=f['case'],user=f['actor'],action='support.response.operate').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,OPERATOR,v['operator'])
 def test_missing_operator_rules_hold_recovery_only(self):
  f=self.f;j=release(f)
  with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportresponse',j.pk,'cancel','Missing operator authority')
  self.assertTrue(inventory.jobs(f['actor'],f['case'])[0]);self.assertTrue(worker.run_once(f['case'].pk));self.assertEqual(d.Receipt.objects.count(),1)
 def test_operator_recovery_delegates_and_keeps_original_attempt_budget(self):
  f=self.f;operators(f);j=release(f)
  class FalseSuccess(InternalSupportResponseAdapter):
   def deliver(self,*args):return True
  worker.run_once(f['case'].pk,FalseSuccess());j.refresh_from_db();self.assertEqual(j.status,'held');attempts=j.attempts
  ops.recover(f['actor'],f['case'].pk,'supportresponse',j.pk,'retry','Known absent local receipt');j.refresh_from_db();self.assertEqual(j.attempts,attempts);self.assertEqual(j.status,'pending');worker.run_once(f['case'].pk);self.assertEqual(d.Receipt.objects.count(),1)
  with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportresponse',j.pk,'cancel','Cannot cancel actual receipt')
 def test_unknown_effect_cannot_be_forced_through_operator(self):
  f=self.f;operators(f);j=release(f)
  class Lose(InternalSupportResponseAdapter):
   def deliver(self,*args):super().deliver(*args);raise TimeoutError()
  worker.run_once(f['case'].pk,Lose())
  for action in ['retry','cancel']:
   with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportresponse',j.pk,action,'Unknown requires original receipt lookup')
  worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
 def test_enrolled_missing_readiness_holds_delivery_but_draft_and_capture_work(self):
  f=self.f;j=release(f);enroll(f,j,False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists());self.assertTrue(d.Packet.objects.exists());self.assertIsNone(__import__('apps.baas.models',fromlist=['SupportCase']).SupportCase.objects.get(case=f['case']).first_response_at)
 def test_native_health_and_absent_receipt_capability_independent_review_then_delivery(self):
  f=self.f;j=release(f);enroll(f,j);health=IntegrationObservation.objects.get(contract=f['response_contract'],payload__kind='health');receipt=IntegrationObservation.objects.get(contract=f['response_contract'],payload__kind='receipt');self.assertTrue(health.payload['identity_match']);self.assertFalse(health.payload['password_authentication_proven']);self.assertEqual(receipt.payload['business_receipt'],'not_found');self.assertNotIn('body',json.dumps(receipt.payload));self.assertTrue(r.gate(f['case'],'supportresponse'));worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
 def test_readiness_does_not_replace_human_release_and_current_review_withdrawal_holds(self):
  f=self.f;p=packet(f);self.assertFalse(worker.run_once(f['case'].pk));j=release(f,p);enroll(f,j);r.review(f['reviewer'],f['case'].pk,f['assessment'].pk,'withdraw','withdraw',__import__('tests.support_helpers',fromlist=['evidence']).evidence(f,'integration_review').pk);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists())
 def test_committed_receipt_recovers_even_when_enrolled_readiness_is_missing_and_source_revoked(self):
  f=self.f;j=release(f)
  class Lose(InternalSupportResponseAdapter):
   def deliver(self,*args):super().deliver(*args);raise TimeoutError()
  worker.run_once(f['case'].pk,Lose());enroll(f,j,False);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
 def test_adapter_policy_stays_configurable_but_native_private_review_checks_source_grants(self):
  f=self.f;j=release(f);enroll(f,j,False);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='agent.data.source').update(active=False)
  activate(f,ADAPTER,f['adapter_rules'])
  with self.assertRaises(PermissionDenied):r.authority(f['reviewer'],f['response_contract'],'review')
 def test_cross_case_and_wrong_kind_cannot_be_probed_or_recovered(self):
  f=self.f;operators(f);j=release(f);enroll(f,j,False)
  with self.assertRaises(ValidationError):r.source_job(f['actor'],f['case'],'supportresponse',j.pk+10000)
  with self.assertRaises(ValidationError):rw.reserve(f['actor'],f['case'].pk,f['response_contract'].pk,'wrong-case','receipt',j.pk+10000)
  with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportresponse',j.pk+10000,'cancel','Wrong source')
  other=Case.objects.create(tenant=f['case'].tenant,kind='project',title='Not Support',synthetic=True)
  with self.assertRaises(PermissionDenied):inventory.family_access(f['actor'],other,'supportresponse')
 def test_live_private_agent_guidance_does_not_enter_generic_agent_history(self):
  f=self.f;j=release(f);d.Job.objects.filter(pk=j.pk).update(status='unknown');before=AgentRun.objects.count()
  from apps.agents.support_response_operations import investigate
  value=investigate(f['actor'],f['case'].pk);self.assertEqual(value['jobs'][0]['status'],'unknown');self.assertIn('reconcile',value['jobs'][0]['question']);self.assertFalse(value['recovery_executed']);self.assertEqual(AgentRun.objects.count(),before)
  from apps.agents.operations import investigate as generic_ops
  from apps.agents.integrations import investigate as generic_integrations
  run=generic_ops(f['actor'],f['case'].pk);self.assertEqual(run.result['job_findings'],[]);enroll(f,j,False);rw.reserve(f['actor'],f['case'].pk,f['response_contract'].pk,'private-probe','health');run=generic_integrations(f['actor'],f['case'].pk);self.assertEqual(run.result['probe_findings'],[])
 def test_staff_operator_and_readiness_ui_and_private_revocation(self):
  f=self.f;operators(f);j=release(f);enroll(f,j);self.client.force_login(f['actor']);c=f['case'];self.assertContains(self.client.get(reverse('operations',args=[c.pk])),'supportresponse');self.assertContains(self.client.get(reverse('integration_readiness',args=[c.pk])),'supportresponse / enrollment')
  self.assertEqual(self.client.get(reverse('support_response_operations',args=[c.pk])).status_code,200);self.assertEqual(self.client.get(reverse('integration_source',args=[c.pk,'contract',f['response_contract'].pk])).status_code,200)
  Grant.objects.filter(case=c,user=f['actor'],action='support.private.read').update(active=False)
  response=self.client.get(reverse('integration_readiness',args=[c.pk]));self.assertEqual(response.status_code,200);self.assertNotContains(response,'supportresponse / enrollment');self.assertEqual(self.client.get(reverse('integration_source',args=[c.pk,'contract',f['response_contract'].pk])).status_code,403);self.assertEqual(self.client.get(reverse('support_response_operations',args=[c.pk])).status_code,403)
 @override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators')
 def test_metadata_export_backup_restore_preserves_privacy_and_never_replays_response(self):
  f=self.f;operators(f);j=release(f);plan(f);provision_test_database();_,export=effect(f,'export');_,backup=effect(f,'backup',export.pk);_,restore=effect(f,'restore',backup.pk)
  self.assertEqual(restore.manifest,export.manifest);self.assertFalse(restore.manifest['business_jobs_reenacted']);self.assertFalse(restore.manifest['evidence_bodies_included']);self.assertNotIn('recipient',json.dumps(restore.manifest));self.assertTrue(any(x['family']=='supportresponse' for x in restore.manifest['jobs']));self.assertEqual(d.Job.objects.count(),1);self.assertFalse(d.Receipt.objects.exists())
  self.client.force_login(f['actor']);url=reverse('operator_artifact',args=[f['case'].pk,restore.pk]);self.assertEqual(self.client.get(url).status_code,200);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403);self.assertEqual(self.client.get(reverse('operations',args=[f['case'].pk])).status_code,200)
 def test_private_readiness_and_recovery_events_do_not_leak_into_generic_timeline(self):
  f=self.f;operators(f);j=release(f);enroll(f,j,False);ops.snapshot(f['actor'],f['case'].pk,'private-inventory');self.assertTrue(f['case'].audit.filter(action__startswith='agent.data.support_').exists());self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.').exists());self.assertFalse(public_timeline(f['case']).filter(data__evidence=f['response_contract'].evidence_id).exists())

 def test_cached_inventory_and_contract_relabelling_cannot_bypass_source_revocation(self):
  f=self.f;j=release(f);enroll(f,j,False);old=ops.snapshot(f['actor'],f['case'].pk,'cached');Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):ops.snapshot(f['actor'],f['case'].pk,'cached')
  body=deepcopy(f['response_contract'].payload);body.update(family='handoff',target_key='internal:handoff')
  with self.assertRaises(PermissionDenied):r.capture(f['actor'],f['case'].pk,f['response_contract'].reference,body,f['response_contract'].evidence_id,predecessor=f['response_contract'].pk)
 def test_actual_staff_recovery_post_and_scoped_forms_are_enforced(self):
  f=self.f;operators(f);j=release(f);self.client.force_login(f['actor']);url=reverse('operations',args=[f['case'].pk]);response=self.client.post(url,{'action':'recover','revision':rev(f['case']),'family':'supportresponse','job_id':j.pk,'operation':'cancel','reason':'Human cancels known uncommitted response'});self.assertEqual(response.status_code,302);j.refresh_from_db();self.assertEqual(j.status,'cancelled');self.assertFalse(d.Receipt.objects.exists())
 def test_inactive_private_principal_cannot_read_cached_metadata_or_probe(self):
  f=self.f;j=release(f);enroll(f,j,False);f['actor'].is_active=False;f['actor'].save(update_fields=['is_active'])
  self.assertFalse(inventory.can_private(f['actor'],f['case']))
  with self.assertRaises(PermissionDenied):r.source_job(f['actor'],f['case'],'supportresponse',j.pk)
