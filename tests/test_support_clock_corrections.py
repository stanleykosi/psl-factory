from datetime import timedelta
from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
from django.urls import reverse
from apps.baas import support_channel as channel,support_clock_corrections as d,support
from apps.identity.models import Grant
from apps.policy.support_channel_validators import CORRECTIONS,CLOCK,RECEIPTS
from apps.policy.support_validators import AUTH
from apps.policy.services import transition
from apps.core.evidence_access import public_evidence,public_timeline
from apps.agents.models import AgentRun
from .support_clock_helpers import fixture,attest,propose,confirm,successor
from .support_channel_helpers import gateway,reviewed,verify,output,claim
from .support_helpers import policy,act,report
from .readiness_helpers import endpoint
from .helpers import rev

class ClockCorrectionTests(TestCase):
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
 def test_renewed_receipt_review_needs_reviewed_clock_revalidation_and_preserves_events(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  original=list(support.SupportEvent.objects.values());historical=support.SupportCase.objects.get(case=f['case']).first_response_at
  channel.review(f['reviewer'],f['case'].pk,r.pk,'withdraw');self.assertIsNone(support.metrics(f['case'])['first_response_seconds'])
  channel.review(f['reviewer'],f['case'].pk,r.pk,'confirm');self.assertIsNone(support.metrics(f['case'])['first_response_seconds'])
  correction=propose(f,receipt=r);self.assertEqual(support.metrics(f['case'])['finding'],'clock_correction_not_current');confirm(f,correction)
  self.assertIsNotNone(support.metrics(f['case'])['first_response_seconds']);self.assertEqual(list(support.SupportEvent.objects.values()),original);self.assertEqual(support.SupportCase.objects.get(case=f['case']).first_response_at,historical)
 def test_source_revision_new_authenticated_observation_then_reviewed_replacement(self):
  f=self.f
  with gateway() as remote:
   old=attest(f,remote);old_claim=f['claim'];original=old.payload.copy();new=successor(f)
   self.assertEqual(new.predecessor_id,old_claim.pk);self.assertEqual(new.external_ref,old_claim.external_ref);self.assertEqual(new.packet_id,old_claim.packet_id)
   self.assertIsNone(support.metrics(f['case'])['first_response_seconds'])
   with self.assertRaises(ValidationError):channel.reserve(f['actor'],f['case'].pk,old_claim.pk,'old-source')
   r=reviewed(f,remote,'version2');correction=propose(f,'replace',r);confirm(f,correction)
   self.assertEqual(d.projection(f['case'])['time'],r.payload['delivered_at']);self.assertIsNotNone(support.metrics(f['case'])['first_response_seconds']);old.refresh_from_db();self.assertEqual(old.payload,original);self.assertEqual(remote['calls'],2)
   self.assertEqual(correction.snapshot['original_event'],f['event'].pk);summary=report(f);self.assertGreaterEqual(support.timestamp(summary.result['period_end']),support.timestamp(r.payload['delivered_at']))
 def test_late_delivery_reconciles_metric_without_backdating_a_support_event(self):
  f=self.f
  with gateway() as remote:
   r=reviewed(f,remote);act(f,'investigate')
   with self.assertRaises(ValidationError):channel.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk)
   events=list(support.SupportEvent.objects.values());correction=propose(f,'late',r);confirm(f,correction)
   self.assertIsNotNone(support.metrics(f['case'])['first_response_seconds']);self.assertEqual(list(support.SupportEvent.objects.values()),events);self.assertIsNone(support.SupportCase.objects.get(case=f['case']).first_response_at);self.assertFalse(channel.Attestation.objects.exists())
 def test_missing_correction_rule_holds_correction_not_original_verification(self):
  f=self.f;transition(f['actor'],f['correction_policy'].pk,'revoked')
  with gateway() as remote:r=attest(f,remote)
  with self.assertRaises(ValidationError):propose(f,receipt=r)
  with self.assertRaises(ValidationError):successor(f)
  self.assertIsNotNone(support.metrics(f['case'])['first_response_seconds'])
 def test_absent_rule_keeps_capture_verification_ui_and_original_clock_available(self):
  f=fixture('clock-missing',configured=False)
  with gateway() as remote:r=attest(f,remote)
  with self.assertRaises(ValidationError):propose(f,receipt=r)
  self.client.force_login(f['actor']);response=self.client.get(reverse('support_channels',args=[f['case'].pk]));self.assertContains(response,'MISSING');self.assertIsNotNone(support.metrics(f['case'])['first_response_seconds'])
 def test_typed_invalid_rule_unknowns_scope_independence_and_actual_grants(self):
  f=self.f
  for delta in [{'proposer_id':None},{'reviewer_id':f['actor'].pk},{'allowed_modes':['invent_time']},{'review_ttl_seconds':0},{'basis':'internal_storage'},{'history_handling':'rewrite_events'}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,CORRECTIONS,dict(f['correction_rules'],**delta))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.channel.correct_review').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,CORRECTIONS,f['correction_rules'])
 def test_disabled_source_revision_does_not_require_its_author_for_clock_correction(self):
  f=self.f;Grant.objects.filter(case=f['case'],user=f['actor'],action='support.channel.successor').update(active=False)
  policy(f,CORRECTIONS,dict(f['correction_rules'],source_author_id=None,allow_source_revision=False))
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);confirm(f,correction);self.assertIsNotNone(d.projection(f['case'])['time'])
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,CORRECTIONS,dict(f['correction_rules'],source_author_id=None,allow_source_revision=True))
 def test_mandatory_independence_survives_permissive_original_summary_policy(self):
  f=self.f;v=deepcopy(f['v']['authority']);v['independent_review']=False
  for row in v['assignments']:
   if row['user_id']==f['reviewer'].pk:row['purposes']+=['triage','transition']
   if row['user_id']==f['actor'].pk:row['purposes']+=['summary']
  policy(f,AUTH,v)
  with gateway() as remote:
   f['claim']=channel.capture(f['reviewer'],f['case'].pk,f['release_job'].packet_id,'self-prepared','self-prepared','v1');r=verify(f,remote)
   with self.assertRaises(PermissionDenied):channel.review(f['reviewer'],f['case'].pk,r.pk,'confirm')
  policy(f,CORRECTIONS,dict(f['correction_rules'],proposer_id=f['reviewer'].pk,reviewer_id=f['actor'].pk))
  with self.assertRaises(PermissionDenied):d.authority(f['actor'],f['case'],'reviewer',[f['actor'].pk])
 def test_independent_reviewer_cannot_be_proposer_or_claim_author(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r)
  with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,correction.pk,'confirm',f['e']['agent_private_clock_review'].pk)
  self.assertFalse(d.Review.objects.exists())
 def test_correction_withdrawal_is_explicit_reviewed_and_never_falls_back(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  first=propose(f,receipt=r);confirm(f,first);withdraw=propose(f,'withdraw',None,'withdraw',first.pk);self.assertIsNone(support.metrics(f['case'])['first_response_seconds']);confirm(f,withdraw)
  self.assertEqual(support.metrics(f['case'])['finding'],'customer_clock_withdrawn');self.assertEqual(channel.Attestation.objects.count(),1)
 def test_withdrawn_correction_review_holds_current_metric_and_stales_summary(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);confirm(f,correction);summary=report(f);support.read_report(f['actor'],f['case'].pk,summary.pk);confirm(f,correction,'withdraw')
  self.assertEqual(support.metrics(f['case'])['finding'],'clock_correction_not_current')
  with self.assertRaises(ValidationError):support.read_report(f['actor'],f['case'].pk,summary.pk)
  self.assertTrue(support.SupportReview.objects.filter(report=summary,verdict='approve').exists())
 def test_new_pending_correction_supersedes_prior_projection_and_requires_latest_predecessor(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  first=propose(f,receipt=r);confirm(f,first);second=propose(f,receipt=r,key='second',predecessor=first.pk)
  self.assertEqual(d.projection(f['case'])['correction'],second.pk);self.assertIsNone(support.metrics(f['case'])['first_response_seconds'])
  with self.assertRaises(ValidationError):propose(f,receipt=r,key='branch',predecessor=first.pk)
  with self.assertRaises(ValidationError):confirm(f,first)
 def test_policy_change_revoke_and_authority_revoke_make_current_projection_unknown(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);confirm(f,correction);transition(f['actor'],f['correction_policy'].pk,'revoked')
  self.assertEqual(support.metrics(f['case'])['finding'],'clock_correction_not_current');policy(f,CORRECTIONS,f['correction_rules'])
  self.assertEqual(support.metrics(f['case'])['finding'],'clock_correction_not_current')
  second=propose(f,receipt=r,key='new-policy',predecessor=correction.pk);confirm(f,second);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.channel.correct_review').update(active=False);self.assertIsNone(support.metrics(f['case'])['first_response_seconds'])
 def test_source_and_correction_review_expiry_hold_without_mutation(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);confirm(f,correction)
  with patch('apps.baas.support_clock_corrections.timezone.now',return_value=timezone.now()+timedelta(hours=2)):self.assertIsNone(d.projection(f['case'])['time'])
  self.assertEqual(d.Correction.objects.count(),1);self.assertEqual(d.Review.objects.count(),1)
 def test_source_successor_is_idempotent_no_branch_same_version_or_cross_case(self):
  f=self.f;claim(f);old=f['claim'];new=successor(f);self.assertEqual(successor(f,old=old).pk,new.pk)
  for version,key in [('v1','revert'),('v2','different-key')]:
   with self.assertRaises(ValidationError):successor(f,version,key,old)
  with self.assertRaises(ValidationError):d.successor(f['actor'],f['case'].pk,old.pk+100000,'x','v3',f['e']['agent_private_channel_successor'].pk)
 def test_revalidation_cannot_change_time_and_old_immutable_check_key_cannot_retarget(self):
  f=self.f
  with gateway() as remote:
   old=attest(f,remote);r=reviewed(f,remote,'new-check')
   with self.assertRaises(ValidationError):propose(f,receipt=r)
   correction=propose(f,'replace',r);confirm(f,correction)
   policy(f,RECEIPTS,f['channel_rules'])
   with self.assertRaises(ValidationError):channel.reserve(f['actor'],f['case'].pk,f['claim'].pk,'verify')
 def test_bot_pending_retracted_or_unreviewed_observation_cannot_correct(self):
  f=self.f
  with gateway() as remote:
   original=attest(f,remote)
   for n,delta in enumerate([{'human_response':False},{'status':'pending'},{'status':'retracted'}]):
    r=verify(f,remote,'bad'+str(n),delta)
    with self.assertRaises(ValidationError):propose(f,'replace',r,key='bad'+str(n))
 def test_correction_key_idempotence_conflict_and_narrow_allowed_mode(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  first=propose(f,receipt=r);self.assertEqual(propose(f,receipt=r).pk,first.pk)
  with self.assertRaises(ValidationError):propose(f,'replace',r)
  policy(f,CORRECTIONS,dict(f['correction_rules'],allowed_modes=['withdraw'],allow_source_revision=False))
  with self.assertRaises(ValidationError):successor(f)
  with self.assertRaises(ValidationError):propose(f,receipt=r,key='disallowed',predecessor=first.pk)
 def test_original_respond_and_manual_clock_bypass_stay_guarded_after_correction(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);confirm(f,correction)
  with self.assertRaises(ValidationError):act(f,'respond')
  with self.assertRaises(ValidationError):channel.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk)
 def test_actual_staff_successor_and_correction_forms_and_read_only_grants(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  self.client.force_login(f['actor']);url=reverse('support_channels',args=[f['case'].pk]);response=self.client.post(url,{'action':'correct','revision':rev(f['case']),'mode':'revalidate','receipt':r.pk,'reference':'ui','predecessor':'','evidence':f['e']['agent_private_clock_correction'].pk,'reason':'Human requests exact-time revalidation'});self.assertEqual(response.status_code,302);row=d.latest(f['case']);self.assertIsNotNone(row)
  self.client.force_login(f['reviewer']);response=self.client.post(url,{'action':'correct_review','revision':rev(f['case']),'correction':row.pk,'verdict':'confirm','evidence':f['e']['agent_private_clock_review'].pk});self.assertEqual(response.status_code,302);response=self.client.get(url);self.assertContains(response,'Current clock projection');self.assertEqual(response['Cache-Control'],'no-store');self.assertIsNotNone(d.projection(f['case'])['time'])
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.private.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403)
 def test_private_evidence_agents_and_public_history_never_apply_or_leak_corrections(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);before=AgentRun.objects.count()
  from apps.agents.support_channels import investigate
  result=investigate(f['actor'],f['case'].pk);self.assertEqual(result['current_clock']['correction'],correction.pk);self.assertFalse(result['clock_applied']);self.assertEqual(AgentRun.objects.count(),before);self.assertFalse(d.Review.objects.exists());self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.').exists());self.assertFalse(public_evidence(f['case'].evidence.all()).filter(kind__startswith='agent_private_').exists())
 def test_sql_guards_preserve_corrections_reviews_and_source_identity(self):
  f=self.f
  with gateway() as remote:r=attest(f,remote)
  correction=propose(f,receipt=r);review=confirm(f,correction);new=successor(f)
  for sql,pk in [('UPDATE baas_supportclockcorrection SET reason=\'rewrite\' WHERE id=%s',correction.pk),('DELETE FROM baas_supportclockcorrectionreview WHERE id=%s',review.pk),('UPDATE baas_supportchannelclaim SET payload=\'{}\' WHERE id=%s',new.pk)]:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cursor:cursor.execute(sql,[pk])
  value=dict(new.payload,receipt_version='v3')
  with self.assertRaises(DatabaseError),transaction.atomic():channel.Claim.objects.create(case=f['case'],packet=new.packet,tenant='another-tenant',channel=new.channel,account=new.account,external_ref=new.external_ref,reference='malformed-lineage',payload=value,sha256=channel.digest(value),actor=f['actor'],predecessor=new,evidence=f['e']['agent_private_channel_successor'])
