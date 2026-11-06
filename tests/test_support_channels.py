from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
from django.urls import reverse
from apps.baas import support_channel as d,support_channel_delivery as worker,support
from apps.baas.models import SupportCase
from apps.baas.support_models import SupportEvent
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.support_channel_validators import RECEIPTS,CLOCK
from apps.core.evidence_access import public_evidence,public_timeline
from apps.agents.models import AgentRun
from adapters.support_channel import SupportChannelAdapter
from .support_channel_helpers import fixture,claim,verify,reviewed,gateway,output
from .support_helpers import policy,act,report
from .readiness_helpers import endpoint
from .helpers import rev

class SupportChannelTests(TestCase):
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
 def setUpTestData(cls):cls.f=fixture()
 def test_released_packet_authenticated_gateway_independent_review_explicit_human_clock(self):
  f=self.f;before=SupportEvent.objects.count()
  with gateway() as remote:
   r=verify(f,remote);self.assertIsNone(SupportCase.objects.get(case=f['case']).first_response_at);self.assertEqual(SupportEvent.objects.count(),before)
   with self.assertRaises(ValidationError):d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk)
   d.review(f['reviewer'],f['case'].pk,r.pk,'confirm');event=d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk)
   self.assertEqual(event.occurred_at,support.timestamp(r.payload['delivered_at']));self.assertEqual(SupportCase.objects.get(case=f['case']).first_response_at,event.occurred_at);self.assertEqual(d.Attestation.objects.get().event_id,event.pk);self.assertIsNotNone(support.metrics(f['case'])['first_response_seconds']);self.assertEqual(remote['calls'],1);self.assertTrue(remote['paths'][0].startswith('/support-receipts/'));self.assertNotIn(f['draft'].body,remote['paths'][0]);self.assertFalse(d.inspect(f['actor'],f['case'].pk,f['claim'].pk)['checks'][0]['live_customer_channel_evaluated']);self.assertFalse(AgentRun.objects.exists())
 def test_typed_policy_invalid_scope_roles_unknowns_and_clock_semantics(self):
  f=self.f
  for changes in [{'customer_ref':'wrong'},{'reviewer_id':f['actor'].pk},{'sender_ref':None},{'target_key':'https://unreviewed.example'},{'contract_evidence_id':f['e']['support_response'].pk},{'max_attempts':0}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,RECEIPTS,dict(f['channel_rules'],**changes))
  for changes in [{'attestor_id':None},{'basis':'internal_storage'},{'late_event_handling':'rewrite_history'}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,CLOCK,dict(f['clock_rules'],**changes))
 def test_missing_or_revoked_policy_holds_dependent_actions_only(self):
  f=self.f;transition(f['actor'],f['channel_policy'].pk,'revoked')
  with self.assertRaises(ValidationError):claim(f)
  act(f,'investigate');self.client.force_login(f['actor']);self.assertContains(self.client.get(reverse('support_channels',args=[f['case'].pk])),'REVOKED');self.assertTrue(SupportEvent.objects.exists())
 def test_clock_enrollment_cannot_be_bypassed_by_manual_response_or_policy_revocation(self):
  f=self.f
  with self.assertRaises(ValidationError):act(f,'respond')
  transition(f['actor'],f['clock_policy'].pk,'revoked')
  with self.assertRaises(ValidationError):act(f,'respond')
  self.assertIsNone(SupportCase.objects.get(case=f['case']).first_response_at)
 def test_claim_idempotency_and_external_namespace_conflict(self):
  f=self.f;r=claim(f);self.assertEqual(claim(f).pk,r.pk)
  with self.assertRaises(ValidationError):d.capture(f['actor'],f['case'].pk,f['release_job'].packet_id,'new-reference',r.external_ref,'different-version')
  self.assertEqual(d.Claim.objects.count(),1)
 def test_wrong_principal_recipient_case_message_or_contract_cannot_verify(self):
  f=self.f;claim(f)
  with gateway() as remote:
   for i,change in enumerate([{'principal_ref':'principal:wrong'},{'recipient_ref':'other'},{'case_ref':'other'},{'message_sha256':'0'*64},{'contract_version':'other'},{'human_response':'true'},{'unknown':'field'}]):
    remote['receipts'][f['claim'].payload['receipt_key']]=output(f,change);j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'invalid-'+str(i));worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held')
  self.assertFalse(d.Receipt.objects.exists())
 def test_unknown_malformed_utf8_and_redirects_never_become_delivered_clocks(self):
  f=self.f;claim(f)
  with gateway() as remote:
   remote['wire']=b'\xff';j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'bad-wire');worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'unknown');self.assertFalse(d.Receipt.objects.exists())
   remote['wire']=None;remote['redirect']=True;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertIn(j.status,['held','unknown']);self.assertIsNone(SupportCase.objects.get(case=f['case']).first_response_at)
 def test_pending_retracted_and_bot_observations_are_retained_without_clock_qualification(self):
  f=self.f
  with gateway() as remote:
   for i,change in enumerate([{'status':'pending','sent_at':None,'delivered_at':None},{'status':'retracted'},{'human_response':False}]):
    r=verify(f,remote,'nonqualifying-'+str(i),change)
    with self.assertRaises(ValidationError):d.review(f['reviewer'],f['case'].pk,r.pk,'confirm')
  self.assertEqual(d.Receipt.objects.count(),3);self.assertFalse(d.Attestation.objects.exists())
 def test_unauthorised_historical_send_observation_is_preserved_but_clock_held(self):
  f=self.f
  with gateway() as remote:
   r=verify(f,remote,changes={'sent_at':(f['release_job'].decision.created_at-timedelta(seconds=1)).isoformat()})
   with self.assertRaises(ValidationError):d.review(f['reviewer'],f['case'].pk,r.pk,'confirm')
   self.assertTrue(d.Receipt.objects.filter(pk=r.pk).exists());self.assertFalse(d.Attestation.objects.exists())
 def test_future_unknown_delivery_and_time_reversal_hold(self):
  f=self.f;claim(f)
  with gateway() as remote:
   for i,change in enumerate([{'delivered_at':None},{'delivered_at':(timezone.now()+timedelta(days=1)).isoformat()},{'sent_at':(timezone.now()+timedelta(seconds=10)).isoformat()}]):
    remote['receipts'][f['claim'].payload['receipt_key']]=output(f,change);j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'bad-time-'+str(i));worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held')
 def test_source_revocation_prevents_new_gateway_checks_and_private_reads(self):
  f=self.f;claim(f)
  with gateway() as remote:
   remote['receipts'][f['claim'].payload['receipt_key']]=output(f);j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'revoked');Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(remote['calls'],0)
  with self.assertRaises(PermissionDenied):d.inspect(f['actor'],f['case'].pk,f['claim'].pk)
 def test_independence_withdrawal_stales_metrics_and_reviewed_report_without_erasing_history(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);event=d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk);summary=report(f)
   d.review(f['reviewer'],f['case'].pk,r.pk,'withdraw');self.assertEqual([x['verdict'] for x in d.inspect(f['actor'],f['case'].pk,f['claim'].pk)['checks'][0]['review_history']],['withdraw','confirm']);self.assertIsNone(support.metrics(f['case'])['first_response_seconds']);self.assertEqual(support.metrics(f['case'])['finding'],'customer_clock_evidence_not_current');self.assertEqual(SupportCase.objects.get(case=f['case']).first_response_at,event.occurred_at)
   with self.assertRaises(ValidationError):support.read_report(f['reviewer'],f['case'].pk,summary.pk)
   with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,r.pk,'confirm')
 def test_late_delivery_before_current_head_holds_only_clock_application(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);act(f,'investigate')
   with self.assertRaises(ValidationError):d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk)
   self.assertTrue(d.inspect(f['actor'],f['case'].pk,f['claim'].pk)['checks'][0]['currently_reviewed_delivery']);self.assertFalse(d.Attestation.objects.exists())
 def test_latest_pending_recheck_stales_old_delivery_review(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);d.reserve(f['actor'],f['case'].pk,f['claim'].pk,'new-check')
   with self.assertRaises(ValidationError):d.accepted(r)
 def test_sql_immutability_and_check_intent_guards(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);event=d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk)
   for table,pk,field,value in [('supportchannelclaim',f['claim'].pk,'reference','changed'),('supportchannelreceipt',r.pk,'sha256','changed'),('supportchannelreview',d.Review.objects.get(receipt=r).pk,'verdict','withdraw'),('supportclockattestation',d.Attestation.objects.get().pk,'snapshot','{}'),('supportchannelcheck',r.job_id,'intent_key','changed')]:
    with self.assertRaises(DatabaseError),transaction.atomic():
     with connection.cursor() as cursor:cursor.execute('UPDATE baas_'+table+' SET '+field+'=%s WHERE id=%s',[value,pk])
 def test_actual_staff_claim_check_review_attest_forms_and_private_ui(self):
  f=self.f;self.client.force_login(f['actor']);url=reverse('support_channels',args=[f['case'].pk]);self.assertContains(self.client.get(url),'Customer-channel evidence')
  self.client.post(url,{'action':'claim','revision':rev(f['case']),'packet':f['release_job'].packet_id,'reference':'ui','external_ref':'customer-ui','receipt_version':'v1'});self.assertEqual(d.Claim.objects.count(),1);f['claim']=d.Claim.objects.get()
  with gateway() as remote:
   remote['receipts'][f['claim'].payload['receipt_key']]=output(f);self.client.post(url,{'action':'check','revision':rev(f['case']),'claim':f['claim'].pk,'reference':'ui-check'});worker.run_once(f['case'].pk);r=d.Receipt.objects.get();self.client.force_login(f['reviewer']);self.client.post(url,{'action':'review','revision':rev(f['case']),'receipt':r.pk,'verdict':'confirm'});self.client.force_login(f['actor']);self.client.post(url,{'action':'attest','revision':rev(f['case']),'receipt':r.pk,'evidence':f['e']['support_response'].pk});self.assertEqual(d.Attestation.objects.count(),1)
  response=self.client.get(reverse('support_channel_report',args=[f['case'].pk,f['claim'].pk]));self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403)
 def test_generic_readers_hide_contracts_and_private_channel_history(self):
  f=self.f;claim(f);self.assertFalse(public_evidence(f['case'].evidence.all()).filter(pk=f['channel_rules']['contract_evidence_id']).exists());self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.').exists())
  from apps.agents.support_channels import investigate
  before=AgentRun.objects.count();result=investigate(f['actor'],f['case'].pk);self.assertFalse(result['clock_applied']);self.assertIn('supplied identity',result['claims'][0]['question']);self.assertEqual(AgentRun.objects.count(),before)

 def test_duplicate_customer_receipt_alias_cannot_attest_the_same_released_message_twice(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk);claim(f,'alias','customer-receipt-alias');other=reviewed(f,remote,'alias-check')
   with self.assertRaises(ValidationError):d.attest(f['actor'],f['case'].pk,other.pk,f['e']['support_response'].pk)
   self.assertEqual(d.Attestation.objects.count(),1);self.assertEqual(SupportEvent.objects.filter(action='respond').count(),1)
 def test_inactive_verifier_and_revoked_clock_authority_hold_current_metric_truth(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);d.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.channel.attest').update(active=False);self.assertIsNone(support.metrics(f['case'])['first_response_seconds']);self.assertTrue(d.Attestation.objects.exists())
 def test_internal_storage_receipt_cannot_forge_a_customer_clock(self):
  f=self.f
  from apps.baas import support_release_delivery as release_worker
  release_worker.run_once(f['case'].pk)
  with self.assertRaises(ValidationError):d.attest(f['actor'],f['case'].pk,999999,f['e']['support_response'].pk)
  self.assertIsNone(SupportCase.objects.get(case=f['case']).first_response_at)
