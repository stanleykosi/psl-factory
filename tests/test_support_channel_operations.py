import json
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.urls import reverse
from apps.baas import support_channel as d,support_channel_delivery as worker
from apps.identity.models import Grant
from apps.workflows import operator_inventory as inv,operator_recovery as ops,readiness as r,readiness_delivery as rw
from apps.workflows.readiness_models import IntegrationObservation
from apps.policy.operator_validators import OPERATOR
from apps.agents.models import AgentRun
from .support_clock_helpers import fixture
from .support_channel_helpers import claim,verify,output,gateway
from .support_response_operations_helpers import operators,enroll,plan
from .operator_helpers import policy,effect,provision_test_database
from .readiness_helpers import endpoint
from .helpers import rev

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class ChannelOperationsTests(TestCase):
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
 def setUpTestData(cls):cls.f=fixture('channel-ops')
 def test_private_metadata_inventory_and_source_lookup_do_not_infer_customer_delivery(self):
  f=self.f
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check');rows,_,grants=inv.jobs(f['actor'],f['case']);row=next(x for x in rows if x['family']=='supportchannel');self.assertEqual(row['id'],job.pk);self.assertNotIn('recipient',json.dumps(row));self.assertIn('support.channel.read',grants);self.assertIsNone(r.lookup_source('supportchannel',job))
   verify(f,remote,'check');self.assertIsNotNone(r.lookup_source('supportchannel',job));self.assertFalse(d.Attestation.objects.exists())
 def test_missing_operator_rule_holds_recovery_but_read_only_check_still_runs(self):
  f=self.f
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check')
   with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportchannel',job.pk,'cancel','No configured operator')
   remote['receipts'][f['claim'].payload['receipt_key']]=output(f);worker.run_once(f['case'].pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed')
 def test_operator_validator_source_grants_and_original_budget_no_replacement(self):
  f=self.f;v=operators(f,False,family='supportchannel')
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,OPERATOR,dict(v['operator'],routes=[{'family':'supportchannel','actions':['replace_intent']}]))
  Grant.objects.filter(case=f['case'],user=f['actor'],action='support.channel.operate').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,OPERATOR,v['operator'])
 def test_native_operator_recovery_keeps_attempts_and_unknown_requires_worker(self):
  f=self.f;operators(f,family='supportchannel')
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check');remote['receipts'][f['claim'].payload['receipt_key']]=output(f,{'recipient_ref':'wrong'});worker.run_once(f['case'].pk);job.refresh_from_db();self.assertEqual(job.status,'held');attempts=job.attempts;ops.recover(f['actor'],f['case'].pk,'supportchannel',job.pk,'retry','Known invalid remote frame corrected');job.refresh_from_db();self.assertEqual(job.attempts,attempts)
   remote['lose_response']=True;worker.run_once(f['case'].pk)
   for action in ['retry','cancel']:
    with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportchannel',job.pk,action,'Unknown must reconcile original read')
   remote['lose_response']=False;remote['receipts'][f['claim'].payload['receipt_key']]=output(f);worker.run_once(f['case'].pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1)
 def test_unknown_gateway_reads_stop_at_original_budget_and_operator_cannot_reset_it(self):
  f=self.f;operators(f,family='supportchannel')
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'bounded');remote['lose_response']=True
   for _ in range(job.intent['max_attempts']+1):worker.run_once(f['case'].pk)
   job.refresh_from_db();self.assertEqual(job.status,'held');self.assertEqual(remote['calls'],job.intent['max_attempts']);self.assertFalse(d.Receipt.objects.exists())
   with self.assertRaises(ValidationError):ops.recover(f['actor'],f['case'].pk,'supportchannel',job.pk,'retry','Cannot reset original exhausted budget')
 def test_enrolled_unready_holds_new_read_not_receipt_recovery(self):
  f=self.f
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check');enroll(f,job,False,family='supportchannel');remote['receipts'][f['claim'].payload['receipt_key']]=output(f);worker.run_once(f['case'].pk);job.refresh_from_db();self.assertEqual(job.status,'held');self.assertEqual(remote['calls'],0)
 def test_native_health_absent_receipt_review_then_gateway_read_and_recovery_after_revocation(self):
  f=self.f
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check');enroll(f,job,family='supportchannel');o=IntegrationObservation.objects.get(contract=f['response_contract'],payload__kind='receipt');self.assertEqual(o.payload['business_receipt'],'not_found');self.assertTrue(r.gate(f['case'],'supportchannel'));remote['receipts'][f['claim'].payload['receipt_key']]=output(f)
   pk,fence=worker.claim(f['case'].pk);worker.execute(pk,fence,__import__('adapters.support_channel',fromlist=['SupportChannelAdapter']).SupportChannelAdapter())
   from django.utils import timezone
   from datetime import timedelta
   d.Job.objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);worker.run_once(f['case'].pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(remote['calls'],1);self.assertFalse(d.Attestation.objects.exists())
 def test_read_grant_revocation_hides_private_channel_even_when_response_visible(self):
  f=self.f
  with gateway():claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check')
  cached=ops.snapshot(f['actor'],f['case'].pk,'cached');m=inv.bundle(f['actor'],f['case'],200);enroll(f,job,False,family='supportchannel');Grant.objects.filter(case=f['case'],user=f['actor'],action='support.channel.read').update(active=False)
  self.assertTrue(inv.can_private(f['actor'],f['case']));self.assertFalse(inv.can_private(f['actor'],f['case'],'supportchannel'));self.assertFalse(any(x['family']=='supportchannel' for x in inv.jobs(f['actor'],f['case'])[0]))
  for call in [lambda:ops.snapshot(f['actor'],f['case'].pk,'cached'),lambda:inv.readable_manifest(f['actor'],f['case'],m),lambda:r.source_job(f['actor'],f['case'],'supportchannel',job.pk),lambda:r.capture(f['actor'],f['case'].pk,f['response_contract'].reference,dict(f['response_contract'].payload,family='handoff',target_key='internal:handoff'),f['response_contract'].evidence_id,predecessor=f['response_contract'].pk)]:
   with self.assertRaises(PermissionDenied):call()
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('integration_readiness',args=[f['case'].pk])).status_code,200);self.assertEqual(self.client.get(reverse('integration_source',args=[f['case'].pk,'contract',f['response_contract'].pk])).status_code,403)
 def test_actual_operator_post_uses_configured_channel_route_and_never_dispatches(self):
  f=self.f;operators(f,family='supportchannel')
  with gateway() as remote:
   claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check');self.client.force_login(f['actor']);response=self.client.post(reverse('operations',args=[f['case'].pk]),{'action':'recover','revision':rev(f['case']),'family':'supportchannel','job_id':job.pk,'operation':'cancel','reason':'Human cancels unstarted lookup'});self.assertEqual(response.status_code,302);job.refresh_from_db();self.assertEqual(job.status,'cancelled');self.assertEqual(remote['calls'],0)
 def test_generic_agents_exclude_channel_jobs_and_private_guidance_is_live_only(self):
  f=self.f
  with gateway():claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check')
  d.Job.objects.filter(pk=job.pk).update(status='unknown');enroll(f,job,False,family='supportchannel');rw.reserve(f['actor'],f['case'].pk,f['response_contract'].pk,'private-health','health')
  from apps.agents.operations import investigate
  from apps.agents.integrations import investigate as integrations
  from apps.agents.support_channels import investigate as private
  self.assertFalse(investigate(f['actor'],f['case'].pk).result['job_findings']);self.assertFalse(integrations(f['actor'],f['case'].pk).result['probe_findings']);before=AgentRun.objects.count();value=private(f['actor'],f['case'].pk);self.assertEqual(value['operator_checks'][0]['status'],'unknown');self.assertEqual(AgentRun.objects.count(),before)
 @override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators')
 def test_channel_metadata_backup_restore_never_replays_receipt_or_clock(self):
  f=self.f;operators(f,family='supportchannel')
  with gateway():claim(f);job=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'check')
  plan(f);provision_test_database();_,export=effect(f,'export');_,backup=effect(f,'backup',export.pk);_,restore=effect(f,'restore',backup.pk)
  self.assertEqual(export.manifest,restore.manifest);self.assertTrue(any(x['family']=='supportchannel' for x in restore.manifest['jobs']));self.assertNotIn('recipient',json.dumps(restore.manifest));self.assertFalse(d.Receipt.objects.exists());self.assertFalse(d.Attestation.objects.exists());Grant.objects.filter(case=f['case'],user=f['actor'],action='support.channel.read').update(active=False)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('operator_artifact',args=[f['case'].pk,restore.pk])).status_code,403)
