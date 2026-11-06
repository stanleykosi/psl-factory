import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.db import connection,transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.core.evidence_access import public_evidence,public_timeline
from apps.agents import boundary as gateway,boundary_delivery as worker
from apps.agents.services import extract_evidence
from apps.finance import ledger,ledger_agents as d
from apps.policy.ledger_validators import PROJECTION
from apps.policy.services import transition
from .ledger_agent_helpers import fixture,project,extracted,integration,activate
from .ledger_helpers import policy,capture,verify,review
from .ledger_resolution_helpers import second_case,propose,confirm,current
from .readiness_helpers import endpoint
from .helpers import rev

class LedgerAgentTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_selected_quotes_reviewed_result_reuse_human_revision_and_independent_review(self):
  f=self.f
  with endpoint() as remote:
   r=extracted(f);self.assertEqual(remote['private_inputs'][0]['input'],['TX-001','QB-101','sync-1']);self.assertNotIn('Synthetic reviewed treatment',json.dumps(remote['private_inputs']));self.assertNotIn('source_reference',json.dumps(remote['private_inputs']))
   draft=d.reuse(f['actor'],f['case'].pk,r.pk,'draft');self.assertEqual(d.reuse(f['actor'],f['case'].pk,r.pk,'draft').pk,draft.pk);self.assertFalse(d.report(f['reviewer'],f['case'].pk,draft.pk)['currently_approved']);d.review(f['reviewer'],f['case'].pk,draft.pk,'approve');self.assertTrue(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved'])
   new=d.revise(f['actor'],f['case'].pk,draft.pk,'Human Finance evidence note; no accounting change.');self.assertFalse(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved']);self.assertFalse(d.report(f['actor'],f['case'].pk,new.pk)['currently_approved']);d.review(f['reviewer'],f['case'].pk,new.pk,'approve');self.assertTrue(d.report(f['actor'],f['case'].pk,new.pk)['currently_approved']);d.review(f['reviewer'],f['case'].pk,new.pk,'withdraw');self.assertFalse(d.report(f['actor'],f['case'].pk,new.pk)['currently_approved'])
  self.assertEqual(ledger.LedgerLineage.objects.count(),1);self.assertEqual(ledger.LedgerDecision.objects.count(),1)
 def test_missing_native_rule_holds_projection_only(self):
  f=fixture('ledger-native-missing',False)
  # Isolate the new fixture's economic identity from the class fixture before verification.
  with self.assertRaises(ValidationError):project(f)
  self.assertTrue(f['lineage'].checks.exists())
 def test_typed_native_policy_principals_scope_fields_and_mandatory_independence(self):
  f=self.f
  for change in [{'fields':['treatment_body']},{'projector_id':None},{'reviewer_id':f['actor'].pk},{'independent_review':False},{'lineage_ids':[999999]},{'max_draft_chars':0},{'review_ttl_seconds':None}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,PROJECTION,dict(f['native_rules'],**change))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,PROJECTION,f['native_rules'])
 def test_only_reviewed_current_unambiguous_lineage_can_be_projected(self):
  f=self.f;verify(f,f['lineage'],{'state':'unknown'})
  with self.assertRaises(ValidationError):project(f)
  self.assertFalse(d.LedgerProjection.objects.exists())
 def test_new_incumbent_read_and_finance_review_stale_prior_projection(self):
  f=self.f;source=project(f);review(f,verify(f,f['lineage']))
  with self.assertRaises(ValidationError):d.current(source.projection)
  self.assertNotEqual(d.project(f['actor'],f['case'].pk,f['lineage'].pk,'new-proof').pk,source.pk)
 def test_exact_source_inventory_and_no_generic_private_kind_forgery(self):
  f=self.f;e=add_evidence(f['actor'],f['case'].pk,d.KIND,'forged','synthetic:forged');self.assertFalse(gateway.permitted_source(e))
  with self.assertRaises(ValidationError):gateway.project(f['actor'],f['case'].pk,e.pk,'F01','purpose',['forged'])
  p=project(f).projection
  with self.assertRaises(ValidationError):gateway.project(f['actor'],f['case'].pk,p.evidence_id,'F01',p.purpose,p.payload['quotes'])
 def test_private_grant_revocation_blocks_new_send_and_cached_result_and_ui(self):
  f=self.f
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'revoked');Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertNotIn('private_inputs',remote)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,f['projection'].pk])).status_code,403);self.assertEqual(self.client.get(reverse('ledger_agents',args=[f['case'].pk])).status_code,403);response=self.client.get(reverse('private_evidence',args=[f['case'].pk]));self.assertNotContains(response,'QB-101');self.assertNotContains(response,'Projection #'+str(f['projection'].pk))
 def test_generic_case_timeline_agent_and_export_cannot_read_native_bodies(self):
  f=self.f;p=project(f);self.assertFalse(public_evidence(f['case'].evidence.all()).filter(kind__in=[d.KIND,'ledger_source','quickbooks_verification']).exists());self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.ledger').exists())
  for e in [f['lineage'].evidence,p.projection.evidence]:
   with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,e.pk,'F01')
  from apps.workflows.operator_inventory import bundle
  self.assertNotIn('QB-101',json.dumps(bundle(f['actor'],f['case'],100)))
 def test_result_withdrawal_policy_revocation_and_ttl_hold_reuse(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'before');d.review(f['reviewer'],f['case'].pk,draft.pk,'approve');gateway.review_result(f['reviewer'],f['case'].pk,r.pk,'withdraw');self.assertFalse(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved'])
   with self.assertRaises(ValidationError):d.reuse(f['actor'],f['case'].pk,r.pk,'withdrawn')
   transition(f['actor'],f['native_policy'].pk,'revoked')
   with self.assertRaises(ValidationError):project(f,'revoked')
 def test_draft_owner_reviewer_and_size_are_enforced(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'owner')
   with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,draft.pk,'approve')
   with self.assertRaises(PermissionDenied):d.revise(f['reviewer'],f['case'].pk,draft.pk,'Not my draft')
   with self.assertRaises(ValidationError):d.revise(f['actor'],f['case'].pk,draft.pk,'x'*2001)
 def test_optional_generic_independence_cannot_disable_native_finance_review(self):
  f=self.f
  with endpoint():
   project(f);integration(f);activate(f,'INT.agent_data',dict(f['data_rules'],independent_review=False,reviewer_id=f['actor'].pk))
   with self.assertRaises(PermissionDenied):gateway.review_projection(f['actor'],f['case'].pk,f['projection'].pk,'confirm')
 def test_native_policy_replacement_keeps_old_projection_inspectable_but_not_current(self):
  f=self.f;p=project(f).projection;policy(f,PROJECTION,dict(f['native_rules'],fields=['source_reference']))
  with self.assertRaises(ValidationError):d.current(p)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,p.pk])).status_code,200)
 def test_cross_case_resolution_requires_every_historical_private_scope_on_reuse(self):
  f=self.f;g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant']);b=capture(g);verify(g,b);verify(f,f['lineage']);r=propose(f,f['lineage'],[b]);confirm(f,r);current(f,f['lineage']);p=project(f)
  self.assertEqual(set(p.snapshot['participant_cases']),{str(f['case'].pk),str(g['case'].pk)})
  Grant.objects.filter(case=g['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):d.projection_access(f['actor'],p.projection)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,p.projection_id])).status_code,403)
 def test_pending_resolution_successor_invalidates_existing_projection(self):
  f=self.f;b=capture(f);verify(f,f['lineage']);verify(f,b);r=propose(f,f['lineage'],[b]);confirm(f,r);current(f,f['lineage']);p=project(f);propose(f,f['lineage'],[b],reference='pending')
  with self.assertRaises(ValidationError):d.current(p.projection)
 def test_actual_http_forms_project_reuse_revision_review_and_no_store(self):
  f=self.f;url=reverse('ledger_agents',args=[f['case'].pk]);self.client.force_login(f['actor']);self.assertContains(self.client.get(url),'Private Finance projections and drafts');self.assertEqual(self.client.post(url,{'action':'project','revision':rev(f['case']),'lineage':f['lineage'].pk,'reference':'ui'}).status_code,302);f['binding']=d.LedgerProjection.objects.get();f['projection']=f['binding'].projection
  with endpoint():
   r=extracted(f);self.client.post(url,{'action':'reuse','revision':rev(f['case']),'receipt':r.pk,'reference':'ui-draft'});draft=d.Draft.objects.get();self.client.force_login(f['reviewer']);self.client.post(url,{'action':'review','revision':rev(f['case']),'draft':draft.pk,'verdict':'approve'});response=self.client.get(reverse('ledger_agent_report',args=[f['case'].pk,draft.pk]));self.assertTrue(response.json()['currently_approved']);self.assertEqual(response['Cache-Control'],'no-store')
 def test_unknown_selected_adapter_field_never_becomes_zero_or_empty(self):
  from adapters.ledger_projection import LedgerProjectionAdapter
  f=self.f;report=ledger.report(f['actor'],f['case'].pk,f['lineage'].pk);report['incumbent']['incumbent_version']=None
  with self.assertRaises(ValidationError):LedgerProjectionAdapter().project(report,['incumbent_version'])
  self.assertEqual(LedgerProjectionAdapter().project(report,['source_reference'])['fields'],{'source_reference':'TX-001'})
 def test_sql_immutable_history_exact_source_and_draft_version_guards(self):
  f=self.f;p=project(f)
  with self.assertRaises(DatabaseError),transaction.atomic():d.LedgerProjection.objects.filter(pk=p.pk).update(snapshot={})
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'sql');rr=d.review(f['reviewer'],f['case'].pk,draft.pk,'approve')
   for model,pk in [(d.Draft,draft.pk),(d.Review,rr.pk)]:
    with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).delete()
   with self.assertRaises(DatabaseError),transaction.atomic():d.Draft.objects.create(case=f['case'],reference='wrong-version',version=2,source=p,result_review_id=draft.result_review_id,owner=f['actor'],actor=f['actor'],body='No implicit predecessor',sha256='0'*64,snapshot=draft.snapshot)
 def test_timeout_recovery_reconciles_one_provider_effect_after_source_revocation(self):
  f=self.f
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'unknown');remote['lose_response']=True;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'unknown');Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);remote['lose_response']=False;worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
   with self.assertRaises(PermissionDenied):gateway.inspect(f['actor'],f['case'].pk,gateway.Receipt.objects.get(job=j).pk)

 def test_result_and_draft_review_lifetimes_expire_without_mutating_source(self):
  f=self.f;policy(f,PROJECTION,dict(f['native_rules'],review_ttl_seconds=30))
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'ttl');d.review(f['reviewer'],f['case'].pk,draft.pk,'approve')
   with patch('django.utils.timezone.now',return_value=timezone.now()+timedelta(seconds=60)):
    self.assertFalse(gateway.inspect(f['actor'],f['case'].pk,r.pk)['currently_accepted']);self.assertFalse(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved'])
   self.assertEqual(d.Review.objects.filter(draft=draft).count(),1)

 def test_approved_reuse_is_separate_from_historical_inspection_and_is_owner_controlled(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'export')
   with self.assertRaises(ValidationError):d.approved_evidence(f['actor'],f['case'].pk,draft.pk)
   d.review(f['reviewer'],f['case'].pk,draft.pk,'approve');value=d.approved_evidence(f['actor'],f['case'].pk,draft.pk);self.assertEqual(value['body'],draft.body);self.assertFalse(value['posted']);self.assertFalse(value['owner_acceptance_granted'])
   with self.assertRaises(PermissionDenied):d.approved_evidence(f['reviewer'],f['case'].pk,draft.pk)
   self.client.force_login(f['actor']);url=reverse('ledger_approved_evidence',args=[f['case'].pk,draft.pk]);self.assertEqual(self.client.get(url).status_code,200);d.review(f['reviewer'],f['case'].pk,draft.pk,'withdraw');self.assertEqual(self.client.get(url).status_code,409);self.assertEqual(d.report(f['actor'],f['case'].pk,draft.pk)['body'],draft.body)
 def test_adversarial_provider_actions_rejected_and_safe_human_correction_remains_cited(self):
  f=self.f
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');remote['private_output']={'facts':[{'quote':'TX-001'}],'uncertainties':[],'proposed_actions':['post_again']};j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'bad');worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'rejected');r=gateway.Receipt.objects.get(job=j)
   gateway.review_result(f['reviewer'],f['case'].pk,r.pk,'correct',{'facts':[{'quote':'TX-001'}],'uncertainties':['Supplied incumbent read evidence only'],'proposed_actions':[]});draft=d.reuse(f['actor'],f['case'].pk,r.pk,'corrected');self.assertEqual(draft.body,'TX-001');self.assertEqual(ledger.LedgerDecision.objects.count(),1)
