import copy,json
from types import SimpleNamespace
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.pmo import approvals as d,approval_routing as routing
from apps.pmo.models import ApprovalRequest,ApprovalSourceReceipt,ApprovalObservation,ApprovalRouteReceipt,ApprovalRouteJob,GateRecord,GateVerification
from apps.pmo.gates import gate_summary,gate_manifest,verify_gate
from apps.pmo.delivery import verified_gates
from apps.agents.approvals import investigate
from apps.policy.approval_validators import ROUTES,CONTRACTS
from adapters.approvals import InternalApprovalRoutingAdapter
from .approval_helpers import fixture,evidence,policy,capture,observe
from .helpers import rev

class ApprovalTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_department_reference_is_not_a_pmo_approval(self):
  f=self.f;s=capture(f);self.assertEqual(d.visibility(f['actor'],f['request'])['status'],'received_unverified')
  o=observe(f,s);b=d.export_gate(f['owner'],f['case'].pk,o.pk);self.assertEqual(b.verification.result['decision'],'accepted')
  self.assertEqual(d.visibility(f['actor'],f['request'])['status'],'referenced_accepted')
  self.assertFalse(d.visibility(f['actor'],f['request'])['approval_granted_by_hub']);self.assertFalse(d.visibility(f['actor'],f['request'])['native_verified'])
  with self.assertRaises(PermissionDenied):d.export_gate(f['actor'],f['case'].pk,o.pk)
  with self.assertRaises(PermissionDenied):d.review_contract(f['actor'],f['case'].pk,'qa_exit',f['e']['approval_contract_review'].pk)
  with self.assertRaises(PermissionDenied):observe(f,s,actor=f['actor'])
  self.assertEqual(d.export_gate(f['owner'],f['case'].pk,o.pk).pk,b.pk)
 def test_access_failure_retains_history_and_invalidates_delivery_and_manifest(self):
  f=self.f;s=capture(f);o=observe(f,s);b=d.export_gate(f['owner'],f['case'].pk,o.pk);before=gate_manifest(f['candidate']);dossier=SimpleNamespace(candidate=f['candidate'],case=f['case'])
  self.assertEqual(verified_gates(dossier,['qa_exit']),[[b.verification.record_id,b.verification_id]])
  failure=observe(f,s,'unavailable',actor=f['actor']);self.assertEqual(failure.status,'unavailable');self.assertTrue(ApprovalSourceReceipt.objects.filter(pk=s.pk,sha256=s.sha256).exists())
  self.assertNotEqual(gate_manifest(f['candidate']),before);self.assertIn('verification_unavailable',gate_summary(f['candidate'])[0])
  with self.assertRaises(ValidationError):verified_gates(dossier,['qa_exit'])
  with self.assertRaises(ValidationError):verify_gate(f['owner'],f['case'].pk,b.verification.record_id,None)
  fresh=observe(f,s);new=d.export_gate(f['owner'],f['case'].pk,fresh.pk);self.assertNotEqual(new.pk,b.pk);self.assertEqual(GateRecord.objects.count(),1);verified_gates(dossier,['qa_exit'])
 def test_unknown_defects_and_negative_decisions_do_not_become_accepted(self):
  f=self.f
  for version,changes,result in [('1',{'critical_defects':None},'unknown'),('2',{'critical_defects':1},'rejected'),('3',{'decision':'withdrawn'},'rejected'),('4',{'decision':'unknown'},'unknown')]:
   s=capture(f,dict(changes,source_version=version));o=observe(f,s);b=d.export_gate(f['owner'],f['case'].pk,o.pk);self.assertEqual(b.verification.result['decision'],result)
   with self.assertRaises(ValidationError):verified_gates(SimpleNamespace(candidate=f['candidate'],case=f['case']),['qa_exit'])
 def test_duplicate_receipt_is_idempotent_and_conflicts_are_held(self):
  f=self.f;s=capture(f);self.assertEqual(d.capture(f['actor'],f['case'].pk,f['request'].pk,s.evidence_id).pk,s.pk)
  with self.assertRaises(ValidationError):capture(f,{'decision':'rejected'})
  self.assertEqual(ApprovalSourceReceipt.objects.count(),1)
 def test_exact_subject_and_clock_correlation(self):
  f=self.f
  for changes in [{'request_id':999},{'subject':dict(f['request'].subject,build_ref='wrong')},{'decided_at':(timezone.now()+timedelta(hours=1)).isoformat()}]:
   with self.assertRaises(ValidationError):capture(f,changes)
  s=capture(f)
  for changes in [{'receipt_id':999},{'external_ref':'wrong'},{'observed_at':(timezone.now()+timedelta(hours=1)).isoformat()}]:
   with self.assertRaises(ValidationError):observe(f,s,changes=changes)
  self.assertEqual(observe(f,s,changes={'payload_sha256':'0'*64}).status,'conflicting')
 def test_current_owner_source_access_and_contract_withdrawal(self):
  f=self.f;s=capture(f);o=observe(f,s);d.current_observation(o)
  g=Grant.objects.get(user=f['owner'],case=f['case'],action='approval.source.read:synthetic-qa');g.active=False;g.save()
  with self.assertRaises(PermissionDenied):d.current_observation(o)
  g.active=True;g.save();d.review_contract(f['owner'],f['case'].pk,'qa_exit',f['e']['approval_contract_review'].pk,'withdraw')
  with self.assertRaises(ValidationError):d.current_observation(o)
 def test_successor_request_invalidates_older_receipts(self):
  f=self.f;s=capture(f);o=observe(f,s)
  with self.assertRaises(ValidationError):d.create_request(f['actor'],f['case'].pk,f['request'].reference,f['candidate'].pk,'qa_exit','B2','R2',f['e']['approval_request'].pk)
  newer=d.create_request(f['actor'],f['case'].pk,f['request'].reference,f['candidate'].pk,'qa_exit','B2','R2',f['e']['approval_request'].pk,predecessor=f['request'].pk)
  self.assertEqual(newer.version,2)
  with self.assertRaises(ValidationError):d.current_observation(o)
 def test_invalid_owner_policy_cannot_transfer_qa_to_pmo(self):
  f=self.f;v=copy.deepcopy(f['v']['routes']);v['routes'][0]['owner_role']='PM';v['routes'][0]['owner_id']=f['actor'].pk
  with self.assertRaises(ValidationError):policy(f,ROUTES,v)
 def test_invalid_and_duplicate_contract_values(self):
  f=self.f
  for key,value in [('max_age_seconds',0),('signature_assurance','native_verified'),('reminders_enabled',True)]:
   v=copy.deepcopy(f['v']['contracts']);v['contracts'][0][key]=value
   with self.assertRaises(ValidationError):
    with transaction.atomic():policy(f,CONTRACTS,v)
 def test_supplied_and_native_modes_remain_distinct(self):
  f=self.f;s=capture(f);v=copy.deepcopy(f['v']['contracts']);v['contracts'][0]['mode']='native_read_v1';policy(f,CONTRACTS,v);d.review_contract(f['owner'],f['case'].pk,'qa_exit',f['e']['approval_contract_review'].pk)
  with self.assertRaises(ValidationError):observe(f,s)
 def test_operational_reference_visible_but_synthetic_bridge_held(self):
  f=self.f;s=capture(f);o=observe(f,s)
  from apps.core.models import Case
  Case.objects.filter(pk=f['case'].pk).update(synthetic=False)
  with self.assertRaises(ValidationError):d.export_gate(f['owner'],f['case'].pk,o.pk)
 def test_routing_is_idempotent_and_receipt_is_not_approval(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk);self.assertEqual(routing.reserve(f['actor'],f['case'].pk,f['request'].pk).pk,j.pk);routing.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed')
  r=ApprovalRouteReceipt.objects.get();self.assertEqual(r.recipient,f['owner']);self.assertFalse(r.payload['approval_granted']);self.assertFalse(GateVerification.objects.exists())
  with self.assertRaises(ValidationError):routing.reserve(f['actor'],f['case'].pk,f['request'].pk,'reminder')
 def test_committed_unknown_receipt_reconciles_before_revoked_authority(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
  class Crash(InternalApprovalRoutingAdapter):
   def deliver(self,pk,fence):super().deliver(pk,fence);raise TimeoutError()
  routing.run_once(Crash());j.refresh_from_db();self.assertEqual(j.status,'unknown')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.route').update(active=False)
  routing.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(ApprovalRouteReceipt.objects.count(),1)
 def test_unknown_without_receipt_requires_worker_lookup_and_current_authority(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
  class Crash(InternalApprovalRoutingAdapter):
   def deliver(self,pk,fence):raise TimeoutError()
  routing.run_once(Crash())
  with self.assertRaises(ValidationError):routing.operate(f['actor'],f['case'].pk,j.pk,'retry','recover')
  Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.route').update(active=False);routing.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(ApprovalRouteReceipt.objects.exists())
 def test_fencing_and_intent_immutability(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk);pk,fence=routing.claim()
  with self.assertRaises(ValidationError):routing.deliver_local(pk,fence-1)
  with self.assertRaises(DatabaseError):
   with transaction.atomic():ApprovalRouteJob.objects.filter(pk=j.pk).update(intent={})
  routing.deliver_local(pk,fence);routing.finish(pk,fence,'confirmed')
 def test_receipt_and_observation_sql_history_cannot_be_updated(self):
  f=self.f;s=capture(f);o=observe(f,s)
  for model,pk in [(ApprovalSourceReceipt,s.pk),(ApprovalObservation,o.pk),(ApprovalRequest,f['request'].pk)]:
   with self.assertRaises(DatabaseError):
    with transaction.atomic():
     with connection.cursor() as cursor:cursor.execute('UPDATE '+model._meta.db_table+' SET '+('subject' if model is ApprovalRequest else 'payload')+"='{}'::jsonb WHERE id=%s",[pk])
 def test_ui_agent_source_redaction_and_inbox(self):
  f=self.f;s=capture(f);observe(f,s);routing.reserve(f['actor'],f['case'].pk,f['request'].pk);routing.run_once();run=investigate(f['actor'],f['case'].pk);self.assertFalse(run.result['source_body_read']);self.assertFalse(run.result['approval_granted'])
  self.client.force_login(f['owner']);self.assertContains(self.client.get('/approvals/inbox/'),f['request'].reference)
  self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/approvals/";self.assertContains(self.client.get(url),'referenced_accepted');self.assertEqual(self.client.get(url+f'source/{s.pk}/').status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.source.read:synthetic-qa').update(active=False)
  self.assertNotContains(self.client.get(url),s.external_ref);self.assertEqual(self.client.get(url+f'source/{s.pk}/').status_code,403);self.assertNotIn(s.external_ref,self.client.get(url+'report/').content.decode())
  self.assertNotContains(self.client.get(f"/cases/{f['case'].pk}/"),s.payload['signature_ref']);self.assertNotContains(self.client.get(f"/cases/{f['case'].pk}/"),'source_decision')
 def test_read_only_ui_cannot_post_commands(self):
  f=self.f;Grant.objects.filter(case=f['case'],user=f['actor']).exclude(action__in=['case.read','approval.read']).update(active=False);self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/approvals/"
  self.assertContains(self.client.get(url),'Read-only access.');self.assertEqual(self.client.post(url,{'action':'route','request':f['request'].pk,'purpose':'request','revision':rev(f['case'])}).status_code,302);self.assertFalse(ApprovalRouteJob.objects.exists())
 def test_missing_policy_holds_routing_not_capture(self):
  f=fixture('unconfigured',configured=False);s=capture(f);self.assertEqual(s.request_id,f['request'].pk)
  with self.assertRaises(ValidationError):routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
 def test_successor_on_another_candidate_holds_old_candidate_gate(self):
  f=self.f;s=capture(f);o=observe(f,s);b=d.export_gate(f['owner'],f['case'].pk,o.pk)
  from apps.pmo.gates import register_candidate
  candidate=register_candidate(f['actor'],f['case'].pk,'replacement-candidate',f['e']['requirements'].pk,None)
  d.create_request(f['actor'],f['case'].pk,f['request'].reference,candidate.pk,'qa_exit','B2','R2',f['e']['approval_request'].pk,predecessor=f['request'].pk)
  with self.assertRaises(ValidationError):d.gate_current(f['candidate'],'qa_exit',b.verification)
 def test_new_contract_version_holds_routing_until_owner_accepts_it(self):
  f=self.f;j=routing.reserve(f['actor'],f['case'].pk,f['request'].pk);v=copy.deepcopy(f['v']['routes']);v['lease_seconds']=45;policy(f,ROUTES,v);routing.run_once();j.refresh_from_db();self.assertEqual(j.status,'held')
  d.review_contract(f['owner'],f['case'].pk,'qa_exit',f['e']['approval_contract_review'].pk)
  with self.assertRaises(ValidationError):routing.operate(f['actor'],f['case'].pk,j.pk,'retry','Changed policy intent')
  routing.operate(f['actor'],f['case'].pk,j.pk,'replace_intent','Explicit replacement');routing.run_once();self.assertEqual(ApprovalRouteReceipt.objects.count(),1);self.assertEqual(routing.reserve(f['actor'],f['case'].pk,f['request'].pk).status,'confirmed')
 def test_configured_reminder_interval_and_budget(self):
  f=self.f;v=copy.deepcopy(f['v']['contracts']);v['contracts'][0].update(reminders_enabled=True,maximum_reminders=1,minimum_reminder_interval_seconds=1);policy(f,CONTRACTS,v);d.review_contract(f['owner'],f['case'].pk,'qa_exit',f['e']['approval_contract_review'].pk)
  routing.reserve(f['actor'],f['case'].pk,f['request'].pk);routing.run_once()
  with self.assertRaises(ValidationError):routing.reserve(f['actor'],f['case'].pk,f['request'].pk,'reminder')
  from unittest.mock import patch
  later=timezone.now()+timedelta(seconds=2)
  with patch('apps.pmo.approval_routing.timezone.now',return_value=later):
   routing.reserve(f['actor'],f['case'].pk,f['request'].pk,'reminder');routing.run_once()
  with patch('apps.pmo.approval_routing.timezone.now',return_value=later+timedelta(seconds=2)):
   with self.assertRaises(ValidationError):routing.reserve(f['actor'],f['case'].pk,f['request'].pk,'reminder')
  self.assertEqual(ApprovalRouteReceipt.objects.count(),2)
 def test_strict_payload_and_owner_source_correlation(self):
  f=self.f
  with self.assertRaises(ValidationError):d.capture(f['actor'],f['case'].pk,f['request'].pk,evidence(f,'approval_source','{"request_id":1,"request_id":1}').pk)
  s=capture(f,{'source_actor_ref':'other-actor'})
  with self.assertRaises(ValidationError):observe(f,s)
 def test_older_source_decision_cannot_replace_current_reference(self):
  f=self.f;s=capture(f);observe(f,s);older=capture(f,{'source_version':'older','decided_at':(timezone.now()-timedelta(hours=1)).isoformat()});self.assertEqual(observe(f,older).status,'conflicting')
 def test_source_expiry_and_role_revocation_hold_current_observation(self):
  f=self.f;s=capture(f);o=observe(f,s)
  from unittest.mock import patch
  with patch('apps.pmo.approvals.timezone.now',return_value=timezone.now()+timedelta(days=2)):
   with self.assertRaises(ValidationError):d.current_observation(o)
  Grant.objects.filter(user=f['owner'],case=f['case'],action='approval.contract').update(active=False)
  with self.assertRaises(PermissionDenied):d.current_observation(o)
 def test_scoped_documents_and_generic_agents_do_not_disclose_source(self):
  f=self.f;s=capture(f);o=observe(f,s);d.export_gate(f['owner'],f['case'].pk,o.pk);Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.source.read:synthetic-qa').update(active=False)
  self.client.force_login(f['actor']);self.assertNotContains(self.client.get(f"/cases/{f['case'].pk}/documents/"),s.external_ref)
  from apps.agents.services import extract_evidence
  with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,s.evidence_id,'P02')
 def test_ui_capture_source_and_route_commands(self):
  f=self.f;s=capture(f);self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/approvals/"
  response=self.client.post(url,{'action':'capture','request':f['request'].pk,'evidence':s.evidence_id,'revision':rev(f['case'])});self.assertEqual(response.status_code,302);self.assertEqual(ApprovalSourceReceipt.objects.count(),1)
  self.assertEqual(self.client.post(url,{'action':'route','request':f['request'].pk,'purpose':'request','revision':rev(f['case'])}).status_code,302);self.assertEqual(ApprovalRouteJob.objects.count(),1)
 def test_source_change_invalidates_an_actual_controlled_packet(self):
  f=self.f;s=capture(f);o=observe(f,s);d.export_gate(f['owner'],f['case'].pk,o.pk)
  from apps.documents.controlled import register_template,preflight
  from apps.pmo.gates import draft_gate_packet
  from .document_helpers import DEFINITION
  t=register_template(f['actor'],f['case'].pk,'P02 packet',DEFINITION,f['e']['policy_decision'].pk,None)
  version=draft_gate_packet(f['actor'],f['case'].pk,f['candidate'].pk,t.pk,'internal',None);self.assertEqual(preflight(version),[])
  observe(f,s,'unavailable',actor=f['actor']);self.assertIn('Candidate gate evidence changed; draft and review a new packet',preflight(version))
