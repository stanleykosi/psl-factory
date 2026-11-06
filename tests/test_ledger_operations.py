import json
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.urls import reverse
from apps.identity.models import Grant
from apps.workflows import operator_inventory as inv,operator_recovery as ops,readiness as rd,readiness_delivery as rw
from apps.workflows.readiness_models import IntegrationObservation
from apps.policy.operator_validators import OPERATOR
from apps.agents import boundary as gateway,boundary_delivery as worker
from apps.agents.models import AgentRun
from .ledger_agent_helpers import fixture,project,integration
from .ledger_operations_helpers import operators,enroll,plan,effect
from .operator_helpers import policy,provision_test_database
from .readiness_helpers import endpoint
from .helpers import rev

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class LedgerOperationsTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture('ledger-operations')
 def reserve(self):
  f=self.f;project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');return gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'private-extract')
 def test_native_inventory_metadata_and_local_receipt_probe_never_send(self):
  f=self.f
  with endpoint() as remote:
   j=self.reserve();rows,_,_=inv.jobs(f['actor'],f['case']);self.assertEqual([r['id'] for r in rows if r['family']=='ledgerdata'],[j.pk]);self.assertNotIn('TX-001',json.dumps(rows));self.assertIsNone(rd.lookup_source('ledgerdata',j));enroll(f,j)
   self.assertEqual(IntegrationObservation.objects.get(contract=f['native_contract'],payload__kind='receipt').payload['business_receipt'],'not_found');self.assertEqual(remote.get('private_inputs',[]),[]);worker.run_once(f['case'].pk);self.assertIsNotNone(rd.lookup_source('ledgerdata',j));self.assertEqual(len(remote['private_inputs']),1)
 def test_missing_operator_policy_only_holds_recovery(self):
  f=self.f
  with endpoint():
   j=self.reserve()
   with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'ledgerdata',j.pk,'retry','Unconfigured')
   worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed')
 def test_typed_operator_route_is_retry_only_and_requires_native_grants(self):
  f=self.f;v=operators(f,False)
  for action in ['cancel','replace_intent']:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,OPERATOR,dict(v['operator'],routes=[{'family':'ledgerdata','actions':[action]}]))
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,OPERATOR,v['operator'])
 def test_retry_keeps_key_intent_attempts_and_unknown_cannot_be_changed(self):
  f=self.f;operators(f)
  with endpoint() as remote:
   j=self.reserve();gateway.Job.objects.filter(pk=j.pk).update(status='held',attempts=1);j.refresh_from_db();original=(j.operation_key,j.intent,j.attempts)
   ops.recover(f['actor'],f['case'].pk,'ledgerdata',j.pk,'retry','Current original context');j.refresh_from_db();self.assertEqual((j.operation_key,j.intent,j.attempts),original)
   gateway.Job.objects.filter(pk=j.pk).update(status='unknown')
   for action in ['retry','cancel','replace_intent']:
    with self.assertRaises((ValidationError,PermissionDenied)):ops.recover(f['actor'],f['case'].pk,'ledgerdata',j.pk,action,'Reconcile original receipt first')
   worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
 def test_exhausted_budget_cannot_be_reset_by_operator(self):
  f=self.f;operators(f)
  with endpoint():
   j=self.reserve();gateway.Job.objects.filter(pk=j.pk).update(status='held',attempts=j.intent['max_attempts'])
   with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'ledgerdata',j.pk,'retry','No budget reset')
 def test_enrolled_unready_blocks_only_new_send(self):
  f=self.f
  with endpoint() as remote:
   j=self.reserve();enroll(f,j,False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(remote.get('private_inputs',[]),[]);self.assertFalse(gateway.Receipt.objects.filter(job=j).exists())
 def test_timeout_receipt_recovery_survives_revoked_native_readiness_and_source(self):
  f=self.f
  with endpoint() as remote:
   j=self.reserve();enroll(f,j);remote['lose_response']=True;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'unknown')
   Grant.objects.filter(case=f['case'],user=f['actor'],action__in=['ledger.private.read','integration.select']).update(active=False);remote['lose_response']=False;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1);self.assertEqual(gateway.Receipt.objects.filter(job=j).count(),1)
 def test_revocation_hides_cached_inventory_contract_probe_manifest_and_ui(self):
  f=self.f
  with endpoint():j=self.reserve();enroll(f,j,False)
  ops.snapshot(f['actor'],f['case'].pk,'cached');m=inv.bundle(f['actor'],f['case'],200);Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  self.assertFalse(any(x['family']=='ledgerdata' for x in inv.jobs(f['actor'],f['case'])[0]))
  for call in [lambda:ops.snapshot(f['actor'],f['case'].pk,'cached'),lambda:inv.readable_manifest(f['actor'],f['case'],m),lambda:rd.source_job(f['actor'],f['case'],'ledgerdata',j.pk),lambda:rw.reserve(f['actor'],f['case'].pk,f['native_contract'].pk,'denied','health')]:
   with self.assertRaises(PermissionDenied):call()
  self.client.force_login(f['actor']);response=self.client.get(reverse('operations',args=[f['case'].pk]));self.assertEqual(response.status_code,200);self.assertNotContains(response,'cached');self.assertEqual(self.client.get(reverse('integration_source',args=[f['case'].pk,'contract',f['native_contract'].pk])).status_code,403)
 def test_generic_agents_omit_private_jobs_and_native_guidance_has_no_effect(self):
  from apps.agents.operations import investigate
  from apps.agents.integrations import investigate as integrations
  from apps.agents.ledger_operations import investigate as private
  f=self.f
  with endpoint():j=self.reserve();enroll(f,j,False)
  gateway.Job.objects.filter(pk=j.pk).update(status='unknown');rw.reserve(f['actor'],f['case'].pk,f['native_contract'].pk,'health','health')
  self.assertFalse(investigate(f['actor'],f['case'].pk).result['job_findings']);self.assertFalse(integrations(f['actor'],f['case'].pk).result['probe_findings']);before=AgentRun.objects.count();self.assertEqual(private(f['actor'],f['case'].pk)['operator_checks'][0]['status'],'unknown');self.assertEqual(AgentRun.objects.count(),before)
 def test_http_operator_post_retries_exact_native_job_and_finance_links(self):
  f=self.f;operators(f)
  with endpoint():
   j=self.reserve();gateway.Job.objects.filter(pk=j.pk).update(status='held');self.client.force_login(f['actor']);url=reverse('operations',args=[f['case'].pk]);self.assertEqual(self.client.post(url,{'action':'recover','revision':rev(f['case']),'family':'ledgerdata','job_id':j.pk,'operation':'retry','reason':'Human checks original context'}).status_code,302);j.refresh_from_db();self.assertEqual(j.status,'pending');response=self.client.get(reverse('ledger_agents',args=[f['case'].pk]));self.assertContains(response,'Private operator recovery and readiness');self.assertEqual(response['Cache-Control'],'no-store')
 def test_historical_foreign_scope_revocation_blocks_cached_metadata_and_contract(self):
  from .ledger_resolution_helpers import second_case,propose,confirm,current
  from .ledger_helpers import capture,verify
  f=self.f;g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant']);w=capture(g);verify(g,w);verify(f,f['lineage']);confirm(f,propose(f,f['lineage'],[w]));current(f,f['lineage'])
  with endpoint():j=self.reserve();enroll(f,j,False)
  ops.snapshot(f['actor'],f['case'].pk,'foreign');m=inv.bundle(f['actor'],f['case'],200);Grant.objects.filter(case=g['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  self.assertFalse(any(x['family']=='ledgerdata' for x in inv.jobs(f['actor'],f['case'])[0]));self.assertFalse(rd.visible_contracts(f['actor'],f['case']).filter(pk=f['native_contract'].pk).exists())
  for call in [lambda:ops.snapshot(f['actor'],f['case'].pk,'foreign'),lambda:inv.readable_manifest(f['actor'],f['case'],m),lambda:rd.contract_access(f['actor'],f['native_contract']),lambda:rd.source_job(f['actor'],f['case'],'ledgerdata',j.pk)]:
   with self.assertRaises(PermissionDenied):call()
 def test_changed_source_context_cannot_be_retried_under_old_intent(self):
  from .ledger_helpers import verify,review
  f=self.f;operators(f)
  with endpoint():
   j=self.reserve();gateway.Job.objects.filter(pk=j.pk).update(status='held');review(f,verify(f,f['lineage'],{'incumbent_version':'sync-2'}))
   with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'ledgerdata',j.pk,'retry','Preserve original source pins')
   self.assertEqual(gateway.Job.objects.get(pk=j.pk).status,'held')
 def test_generic_private_extraction_cannot_be_relabelled_finance(self):
  from apps.core.services import add_evidence
  from .ledger_helpers import evidence
  f=self.f;fake=add_evidence(f['actor'],f['case'].pk,'agent_private_input','Synthetic unrelated private input','synthetic:test')
  p=gateway.Projection.objects.create(case=f['case'],evidence=fake,process_id='P13',purpose='other',version=1,payload={'quotes':['unrelated']},sha256='a'*64,actor=f['actor'])
  j=gateway.Job.objects.create(projection=p,intent_key='unrelated',operation_key='b'*64,intent={},actor=f['actor'])
  self.assertFalse(inv.source_query(f['case'],'ledgerdata').filter(pk=j.pk).exists())
  with self.assertRaises(ValidationError):rd.source_job(f['actor'],f['case'],'ledgerdata',j.pk)
 @override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators')
 def test_metadata_export_backup_restore_does_not_replay_private_jobs(self):
  f=self.f;operators(f)
  with endpoint():j=self.reserve()
  plan(f);provision_test_database();export=effect(f,'export');backup=effect(f,'backup',export.pk);restore=effect(f,'restore',backup.pk)
  from apps.workflows import protection
  assessment=protection.assess(f['actor'],f['case'].pk,f['plan'].pk,'metadata-assessed')
  self.assertTrue(protection.report(f['actor'],f['case'].pk,assessment.pk)['recorded_documentary_complete'])
  self.assertEqual(export.manifest,restore.manifest);self.assertTrue(any(x['family']=='ledgerdata' for x in restore.manifest['jobs']));self.assertFalse(gateway.Receipt.objects.exists());self.assertNotIn('TX-001',json.dumps(restore.manifest));self.assertNotIn('quotes',json.dumps(restore.manifest));j.refresh_from_db();self.assertEqual(j.status,'pending')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('operator_artifact',args=[f['case'].pk,restore.pk])).status_code,403)
  self.assertEqual(self.client.get(reverse('operator_report',args=[f['case'].pk,assessment.pk])).status_code,403)
