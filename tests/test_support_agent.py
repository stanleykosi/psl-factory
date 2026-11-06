import json
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.urls import reverse
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.agents import boundary as gateway,boundary_delivery as worker
from apps.agents.models import AgentRun
from apps.baas import support_agent as d
from apps.baas.support_models import SupportEvent
from apps.baas.models import SupportCase
from apps.policy.support_agent_validators import COMPONENT
from apps.policy.services import transition
from .support_agent_helpers import fixture,project,extracted,integration
from .support_helpers import policy,act
from .readiness_helpers import endpoint
from .helpers import rev

class SupportAgentTests(TestCase):
 def setUp(self):self.f=fixture()
 def test_exact_native_fields_reviewed_result_reuse_and_human_revision(self):
  f=self.f;events=SupportEvent.objects.count();before=SupportCase.objects.get(case=f['case']);first=before.first_response_at
  with endpoint() as remote:
   r=extracted(f);expected=[f['intake'].payload[k] for k in f['native_rules']['fields']];self.assertEqual(remote['private_inputs'][0]['input'],expected);self.assertNotIn('customer_ref',json.dumps(remote['private_inputs']));draft=d.reuse(f['actor'],f['case'].pk,r.pk,'draft');self.assertEqual(d.reuse(f['actor'],f['case'].pk,r.pk,'draft').pk,draft.pk);self.assertFalse(d.report(f['reviewer'],f['case'].pk,draft.pk)['currently_approved']);d.review(f['reviewer'],f['case'].pk,draft.pk,'approve');self.assertTrue(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved']);edited=d.revise(f['actor'],f['case'].pk,draft.pk,'Human-owned clarification; still unsent.');self.assertFalse(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved']);self.assertFalse(d.report(f['actor'],f['case'].pk,edited.pk)['currently_approved']);d.review(f['reviewer'],f['case'].pk,edited.pk,'approve');self.assertTrue(d.report(f['actor'],f['case'].pk,edited.pk)['currently_approved']);d.review(f['reviewer'],f['case'].pk,edited.pk,'withdraw');self.assertFalse(d.report(f['actor'],f['case'].pk,edited.pk)['currently_approved'])
  before.refresh_from_db();self.assertEqual(before.first_response_at,first);self.assertEqual(SupportEvent.objects.count(),events);self.assertFalse(AgentRun.objects.exists())
 def test_missing_native_policy_holds_only_projection_not_support_or_configuration(self):
  f=fixture('native-missing',False)
  with self.assertRaises(ValidationError):project(f)
  self.assertTrue(SupportEvent.objects.filter(case=f['case']).exists());self.client.force_login(f['actor']);self.assertContains(self.client.get(reverse('support_agents',args=[f['case'].pk])),'MISSING')
 def test_native_policy_validators_fields_principals_unknowns_and_case_scope(self):
  f=self.f
  for change in [{'fields':['arbitrary_body']},{'projector_id':f['specialist'].pk},{'reviewer_id':f['actor'].pk},{'max_draft_chars':None},{'intake_ids':[999999]}]:
   with self.subTest(change=change),self.assertRaises(ValidationError),transaction.atomic():policy(f,COMPONENT,dict(f['native_rules'],**change))
 def test_unknown_selected_field_holds_and_excluded_field_is_not_fetched(self):
  f=self.f
  from .support_helpers import capture
  from apps.baas import support
  i=capture(f,{'message_ref':'NULL-REF','transaction_ref':None,'customer_ref':'OTHER-CUSTOMER'})
  policy(f,COMPONENT,dict(f['native_rules'],intake_ids=[i.pk],fields=['transaction_ref']))
  with self.assertRaises(ValidationError):d.project(f['actor'],f['case'].pk,i.pk,'unlinked')
  from adapters.support_projection import SupportProjectionAdapter
  with self.assertRaises(ValidationError):SupportProjectionAdapter().project(i,['transaction_ref'])
  self.assertEqual(SupportProjectionAdapter().project(i,['case_type'])['fields'],{'case_type':i.payload['case_type']})
 def test_forged_private_kind_and_generic_reprojection_cannot_bypass_native_service(self):
  f=self.f;e=add_evidence(f['actor'],f['case'].pk,d.KIND,'forged','synthetic:forged');self.assertFalse(gateway.permitted_source(e))
  with self.assertRaises(ValidationError):gateway.project(f['actor'],f['case'].pk,e.pk,'B14','purpose',['forged'])
  p=project(f).projection
  with self.assertRaises(ValidationError):gateway.project(f['actor'],f['case'].pk,p.evidence_id,'B14',p.purpose,p.payload['quotes'])
 def test_current_native_permission_required_before_provider_send_and_cached_reads(self):
  f=self.f
  with endpoint() as remote:
   project(f);integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'held');Grant.objects.filter(case=f['case'],user=f['actor'],action='support.private.read').update(active=False);worker.run_once(f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertNotIn('private_inputs',remote)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,f['projection'].pk])).status_code,403)
 def test_flow_event_and_native_policy_changes_invalidate_projection_and_reuse(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'before');d.review(f['reviewer'],f['case'].pk,draft.pk,'approve');act(f,'investigate');self.assertFalse(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved'])
   with self.assertRaises(ValidationError):d.reuse(f['actor'],f['case'].pk,r.pk,'after')
 def test_result_review_withdrawal_and_source_grant_revocation_hold_reuse(self):
  f=self.f
  with endpoint():
   r=extracted(f);gateway.review_result(f['reviewer'],f['case'].pk,r.pk,'withdraw')
   with self.assertRaises(ValidationError):d.reuse(f['actor'],f['case'].pk,r.pk,'withdrawn')
   Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.private.read').update(active=False)
   with self.assertRaises(PermissionDenied):gateway.inspect(f['reviewer'],f['case'].pk,r.pk)
 def test_policy_replacement_requires_fresh_source_and_review(self):
  f=self.f;project(f);policy(f,COMPONENT,dict(f['native_rules'],fields=['case_type']))
  with self.assertRaises(ValidationError):d.current(f['projection'])
  new=d.project(f['actor'],f['case'].pk,f['intake'].pk,'replacement');self.assertNotEqual(new.pk,f['binding'].pk);self.assertEqual(new.projection.payload['quotes'],[f['intake'].payload['case_type']])
 def test_draft_owner_independence_budgets_and_cross_case_source(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'owned')
   with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,draft.pk,'approve')
   with self.assertRaises(ValidationError):d.revise(f['actor'],f['case'].pk,draft.pk,'x'*2001)
   with self.assertRaises(PermissionDenied):d.revise(f['reviewer'],f['case'].pk,draft.pk,'Not my draft')
  other=fixture('other-source')
  with self.assertRaises(ValidationError):d.project(f['actor'],f['case'].pk,other['intake'].pk,'foreign')
 def test_native_missing_data_policy_preserves_source_capture_and_read_interface(self):
  f=self.f;source=project(f);self.assertTrue(d.current(source.projection))
  with self.assertRaises(ValidationError):gateway.review_projection(f['reviewer'],f['case'].pk,source.projection_id,'confirm')
 def test_sql_immutability_for_source_draft_and_review(self):
  f=self.f;source=project(f)
  with self.assertRaises(DatabaseError),transaction.atomic():d.SupportProjection.objects.filter(pk=source.pk).update(snapshot={})
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'sql');review=d.review(f['reviewer'],f['case'].pk,draft.pk,'approve')
   with self.assertRaises(DatabaseError),transaction.atomic():d.Draft.objects.filter(pk=draft.pk).update(body='rewrite')
   with self.assertRaises(DatabaseError),transaction.atomic():d.Review.objects.filter(pk=review.pk).delete()
 def test_actual_ui_source_reuse_revision_review_and_private_access(self):
  f=self.f;url=reverse('support_agents',args=[f['case'].pk]);self.client.force_login(f['actor']);self.assertContains(self.client.get(url),'Private support projections and drafts');self.assertEqual(self.client.post(url,{'action':'project','revision':rev(f['case']),'intake':f['intake'].pk,'reference':'ui'}).status_code,302);self.assertEqual(d.SupportProjection.objects.count(),1);f['binding']=d.SupportProjection.objects.get();f['projection']=f['binding'].projection
  with endpoint():
   r=extracted(f);self.client.post(url,{'action':'reuse','revision':rev(f['case']),'receipt':r.pk,'reference':'ui-draft'});draft=d.Draft.objects.get();self.client.force_login(f['reviewer']);self.client.post(url,{'action':'review','revision':rev(f['case']),'draft':draft.pk,'verdict':'approve'});self.assertTrue(self.client.get(reverse('support_agent_report',args=[f['case'].pk,draft.pk])).json()['currently_approved']);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.private.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403)
 def test_original_summary_independence_cannot_be_disabled_by_projection_policy(self):
  f=fixture('independent-native',owner_summary=True)
  policy(f,COMPONENT,dict(f['native_rules'],reviewer_id=f['actor'].pk,independent_review=False))
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'independent')
   with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,draft.pk,'approve')
 def test_linked_unknown_selected_field_is_held_without_partial_projection(self):
  f=fixture('linked-null',message_changes={'transaction_ref':None});policy(f,COMPONENT,dict(f['native_rules'],fields=['transaction_ref']))
  with self.assertRaises(ValidationError):project(f)
  self.assertFalse(d.SupportProjection.objects.filter(case=f['case']).exists());self.assertFalse(f['case'].evidence.filter(kind=d.KIND).exists())
 def test_native_revocation_preserves_history_but_blocks_reuse_and_new_sends(self):
  f=self.f
  with endpoint():
   r=extracted(f);draft=d.reuse(f['actor'],f['case'].pk,r.pk,'revoked');d.review(f['reviewer'],f['case'].pk,draft.pk,'approve');transition(f['actor'],f['native_policy'].pk,'revoked');self.assertFalse(d.report(f['actor'],f['case'].pk,draft.pk)['currently_approved'])
   with self.assertRaises(ValidationError):d.reuse(f['actor'],f['case'].pk,r.pk,'cannot-reuse')
 def test_source_field_labels_are_private_and_historical_projection_remains_inspectable(self):
  f=self.f;project(f);self.client.force_login(f['reviewer']);value=self.client.get(reverse('private_projection',args=[f['case'].pk,f['projection'].pk])).json();self.assertEqual(set(value['domain_source']['packet']['fields']),set(f['native_rules']['fields']));self.assertFalse(value['domain_source']['packet']['content_reference_dereferenced'])
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.private.read').update(active=False);self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,f['projection'].pk])).status_code,403)
 def test_current_reviewed_flow_requires_explicit_case_adoption_before_new_projection(self):
  from apps.baas import support
  f=self.f;support.review_flow(f['reviewer'],f['case'].pk,f['e']['support_review'].pk,'approve')
  with self.assertRaises(ValidationError):project(f)
  self.assertFalse(d.SupportProjection.objects.filter(case=f['case']).exists())
 def test_native_tenant_mismatch_holds_projection(self):
  from apps.core.models import Case
  f=self.f;Case.objects.filter(pk=f['case'].pk).update(tenant='changed-tenant')
  with self.assertRaises(ValidationError):project(f)
 def test_distinct_packets_do_not_silently_supersede_unchanged_native_sources(self):
  f=self.f;p=project(f).projection;second=d.project(f['actor'],f['case'].pk,f['intake'].pk,'second-packet');self.assertNotEqual(p.pk,second.projection_id);self.assertTrue(d.current(p));self.assertTrue(d.current(second.projection));self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('support_agent_report',args=[f['case'].pk,999999])).status_code,404)
