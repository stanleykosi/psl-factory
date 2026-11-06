from copy import deepcopy
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.support_release_validators import COMPONENT
from apps.baas import support_agent as native,support_release as d,support_release_delivery as worker
from apps.baas.support_models import SupportEvent
from apps.baas.models import SupportCase
from apps.agents.models import AgentRun
from adapters.support_response import InternalSupportResponseAdapter
from .support_release_helpers import ready,packet,release
from .support_helpers import policy,act
from .readiness_helpers import endpoint
from .helpers import rev

class SupportReleaseTests(TestCase):
 @classmethod
 def setUpClass(cls):
  cls.endpoint=endpoint();cls.remote=cls.endpoint.__enter__()
  try:super().setUpClass()
  except BaseException:cls.endpoint.__exit__(None,None,None);raise
 @classmethod
 def tearDownClass(cls):
  try:super().tearDownClass()
  finally:cls.endpoint.__exit__(None,None,None)
 @classmethod
 def setUpTestData(cls):cls.f=ready()
 def test_connected_projection_human_release_receipt_and_no_clock_or_funds(self):
  f=self.f;c=f['case'];before=SupportEvent.objects.filter(case=c).count();p=packet(f)
  self.assertEqual(set(p.payload),{'body','issue_ref'});self.assertNotIn('case_type',p.payload)
  self.assertFalse(worker.run_once(c.pk));self.assertFalse(d.Receipt.objects.exists())
  j=release(f,p);self.assertTrue(worker.run_once(c.pk));j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertFalse(worker.run_once(c.pk))
  r=d.Receipt.objects.get(job=j);self.assertEqual(d.receive(f['actor'],c.pk,r.pk)['payload'],p.payload);report=d.inspect(f['reviewer'],c.pk,p.pk);self.assertEqual(report['receipt_classification'],'internal_storage_only');self.assertFalse(report['customer_delivery_verified']);self.assertFalse(report['response_clock_attested']);self.assertFalse(report['financial_effect']);self.assertIsNone(SupportCase.objects.get(case=c).first_response_at);self.assertEqual(SupportEvent.objects.filter(case=c).count(),before);self.assertFalse(AgentRun.objects.exists())
 def test_missing_release_policy_holds_packet_but_leaves_draft_and_support(self):
  f=self.f;transition(f['actor'],f['release_policy'].pk,'revoked')
  with self.assertRaises(ValidationError):packet(f)
  self.assertTrue(native.report(f['actor'],f['case'].pk,f['draft'].pk)['currently_approved']);act(f,'investigate');self.client.force_login(f['actor']);self.assertContains(self.client.get(reverse('support_responses',args=[f['case'].pk])),'REVOKED')
 def test_typed_invalid_policy_and_actual_principal_validation(self):
  f=self.f
  for change in [{'recipient_id':None},{'fields':['customer_ref']},{'fields':[]},{'route':'whatsapp'},{'receipt_meaning':'customer_response'},{'max_attempts':0},{'release_ttl_seconds':None},{'lease_seconds':1},{'releaser_id':f['specialist'].pk}]:
   with self.subTest(change=change),self.assertRaises(ValidationError),transaction.atomic():policy(f,COMPONENT,dict(f['release_rules'],**change))
  Grant.objects.filter(case=f['case'],user=f['actor'],action='support.response.receive').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,COMPONENT,f['release_rules'])
 def test_owner_cannot_grant_own_release_and_tool_does_not_release(self):
  f=self.f
  from apps.agents.support_responses import prepare
  p=prepare(f['actor'],f['case'].pk,f['draft'].pk,'tool')
  self.assertFalse(d.Decision.objects.exists());self.assertFalse(d.Job.objects.exists())
  with self.assertRaises(PermissionDenied):d.decide(f['actor'],f['case'].pk,p.pk,'release')
 def test_unreviewed_or_superseded_draft_cannot_be_projected(self):
  f=self.f;p=packet(f);native.revise(f['actor'],f['case'].pk,f['draft'].pk,'A newer human version')
  with self.assertRaises(ValidationError):d.decide(f['reviewer'],f['case'].pk,p.pk,'release')
  self.assertFalse(d.Job.objects.exists())
 def test_withdrawal_blocks_send_but_history_is_retained(self):
  f=self.f;j=release(f);d.decide(f['reviewer'],f['case'].pk,j.packet_id,'withdraw');worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists());self.assertEqual(d.Decision.objects.count(),2)
 def test_revoked_source_or_recipient_blocks_effect(self):
  f=self.f;j=release(f);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.response.receive').update(active=False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists())
 def test_native_context_changes_hold_without_mutating_existing_packet(self):
  f=self.f;j=release(f);old=deepcopy(j.packet.payload);act(f,'investigate');worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(d.Packet.objects.get(pk=j.packet_id).payload,old)
 def test_changed_policy_stales_prepared_release(self):
  f=self.f;j=release(f);policy(f,COMPONENT,dict(f['release_rules'],fields=['body']));worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists())
 def test_expired_release_holds(self):
  from unittest.mock import patch
  f=self.f;j=release(f)
  with patch('apps.baas.support_release.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
   with self.assertRaises(ValidationError):d.releasable(j)
 def test_unknown_receipt_recovers_after_revocation_without_resending(self):
  f=self.f;j=release(f)
  class LoseReply(InternalSupportResponseAdapter):
   def deliver(self,*args):super().deliver(*args);raise TimeoutError('secret transport body')
  worker.run_once(f['case'].pk,LoseReply());j.refresh_from_db();self.assertEqual(j.status,'unknown');self.assertNotIn('secret',j.error);self.assertEqual(d.Receipt.objects.count(),1)
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.response.release').update(active=False)
  class NoResend(InternalSupportResponseAdapter):
   def deliver(self,*args):raise AssertionError('Must recover receipt first')
  worker.run_once(f['case'].pk,NoResend());j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(d.Receipt.objects.count(),1);self.assertFalse(d.inspect(f['actor'],f['case'].pk,j.packet_id)['currently_releasable'])
 def test_adapter_success_without_receipt_does_not_confirm(self):
  f=self.f;j=release(f)
  class FalseSuccess(InternalSupportResponseAdapter):
   def deliver(self,*args):return {'delivered':True}
  worker.run_once(f['case'].pk,FalseSuccess());j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists());d.operate(f['actor'],f['case'].pk,j.pk,'retry','Retry known absent local effect');worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed')
 def test_intent_idempotency_case_scope_and_sql_guards(self):
  f=self.f;p=packet(f);self.assertEqual(packet(f).pk,p.pk)
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,999999,'x')
  j=release(f,p)
  with self.assertRaises(ValidationError):d.decide(f['reviewer'],f['case'].pk,p.pk,'release')
  worker.run_once(f['case'].pk);r=d.Receipt.objects.get(job=j)
  for sql,args in [('UPDATE baas_supportresponsepacket SET payload=%s WHERE id=%s',['{}',p.pk]),('DELETE FROM baas_supportresponsedecision WHERE id=%s',[j.decision_id]),('UPDATE baas_supportresponsereceipt SET classification=%s WHERE id=%s',['customer',r.pk]),('UPDATE baas_supportresponsejob SET packet_id=%s WHERE id=%s',[p.pk+1,j.pk])]:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cursor:cursor.execute(sql,args)
 def test_private_ui_forms_report_receipt_and_revoked_access(self):
  f=self.f;c=f['case'];self.client.force_login(f['actor']);url=reverse('support_responses',args=[c.pk]);self.assertContains(self.client.get(url),'Human-controlled support response release')
  response=self.client.post(url,{'action':'prepare','revision':rev(c),'draft':f['draft'].pk,'reference':'ui'});self.assertEqual(response.status_code,302);p=d.Packet.objects.get(reference='ui');self.client.force_login(f['reviewer']);response=self.client.post(url,{'action':'decide','revision':rev(c),'packet':p.pk,'verdict':'release'});self.assertEqual(response.status_code,302);self.assertTrue(d.Job.objects.exists());worker.run_once(c.pk);r=d.Receipt.objects.get();self.assertEqual(self.client.get(reverse('support_response_receipt',args=[c.pk,r.pk])).status_code,404)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('support_response_receipt',args=[c.pk,r.pk])).status_code,200);report=self.client.get(reverse('support_response_report',args=[c.pk,p.pk]));self.assertEqual(report['Cache-Control'],'no-store');Grant.objects.filter(case=c,user=f['actor'],action='support.private.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403);self.assertEqual(self.client.get(reverse('support_response_receipt',args=[c.pk,r.pk])).status_code,403)
 def test_stale_revision_and_unknown_fields_are_atomic(self):
  f=self.f;self.client.force_login(f['actor']);url=reverse('support_responses',args=[f['case'].pk]);self.client.post(url,{'action':'prepare','revision':rev(f['case']),'draft':f['draft'].pk,'reference':'ui','release':True});self.assertFalse(d.Packet.objects.exists())
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['draft'].pk,'stale',0)

 def test_fenced_worker_and_attempt_budget_hold_before_effect(self):
  f=self.f;j=release(f);pk,fence=worker.claim(f['case'].pk)
  with self.assertRaises(ValidationError):worker.deliver_internal(pk,fence+1)
  self.assertFalse(d.Receipt.objects.exists());worker.finish(pk,fence,'held');d.Job.objects.filter(pk=j.pk).update(attempts=f['release_rules']['max_attempts']);j.refresh_from_db()
  with self.assertRaises(ValidationError):d.operate(f['actor'],f['case'].pk,j.pk,'retry','Exhausted budget must not reset')
  self.assertFalse(d.Receipt.objects.exists())
 def test_metadata_only_projection_excludes_reviewed_body(self):
  f=self.f;policy(f,COMPONENT,dict(f['release_rules'],fields=['case_type']));p=packet(f);self.assertEqual(p.payload,{'case_type':f['intake'].payload['case_type']});j=release(f,p);worker.run_once(f['case'].pk);self.assertNotIn('body',d.Receipt.objects.get(job=j).payload)
 def test_current_source_revocation_holds_new_send_and_historical_read(self):
  f=self.f;j=release(f);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists())
  with self.assertRaises(PermissionDenied):d.inspect(f['actor'],f['case'].pk,j.packet_id)
 def test_protected_receipt_rejects_changed_destination(self):
  f=self.f;j=release(f);worker.run_once(f['case'].pk);r=d.Receipt.objects.get(job=j);policy(f,COMPONENT,dict(f['release_rules'],recipient_id=f['reviewer'].pk))
  with self.assertRaises(PermissionDenied):d.receive(f['actor'],f['case'].pk,r.pk)
  with self.assertRaises(ValidationError):d.receive(f['reviewer'],f['case'].pk,r.pk)
 def test_duplicate_key_changed_selected_fields_and_cancellation(self):
  f=self.f;p=packet(f);policy(f,COMPONENT,dict(f['release_rules'],fields=['body']))
  with self.assertRaises(ValidationError):packet(f)
  p=packet(f,'new-policy');j=release(f,p);d.operate(f['actor'],f['case'].pk,j.pk,'cancel','Human cancelled unsent packet');self.assertFalse(worker.run_once(f['case'].pk));self.assertFalse(d.Receipt.objects.exists())
