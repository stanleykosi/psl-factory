import copy,json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.core.evidence_access import public_evidence,restricted
from apps.agents.services import extract_evidence
from apps.agents.models import AgentRun
from apps.agents import boundary as d,boundary_delivery as w
from apps.policy.services import transition
from .readiness_helpers import endpoint,evidence
from .agent_data_helpers import fixture_data,data_policy,ready_data
from .helpers import rev

class AgentDataTests(TestCase):
 def setUp(self):self.f=fixture_data()
 def job(self):return ready_data(self.f)
 def work(self,j):w.run_once(self.f['case'].pk);j.refresh_from_db();return j
 def test_reviewed_authenticated_projection_and_independent_correction(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();self.work(j);self.assertEqual(j.status,'confirmed');self.assertEqual(remote['private_inputs'][0]['input'],['Milestone evidence reviewed.']);self.assertNotIn('EXCLUDED',json.dumps(remote['private_inputs']))
   r=d.Receipt.objects.get(job=j);self.assertFalse(d.inspect(f['actor'],f['case'].pk,r.pk)['currently_accepted'])
   with self.assertRaises(PermissionDenied):d.review_result(f['actor'],f['case'].pk,r.pk,'confirm')
   result={'facts':[{'quote':'evidence reviewed'}],'uncertainties':['Human correction, exact projected quote.'],'proposed_actions':[]};rr=d.review_result(f['reviewer'],f['case'].pk,r.pk,'correct',result);self.assertEqual(rr.result['provenance']['source_sha256'],f['input'].sha256);self.assertTrue(d.inspect(f['actor'],f['case'].pk,r.pk)['currently_accepted']);d.review_result(f['reviewer'],f['case'].pk,r.pk,'withdraw');self.assertFalse(d.inspect(f['actor'],f['case'].pk,r.pk)['currently_accepted']);self.assertEqual(AgentRun.objects.count(),0)
 def test_missing_policy_allows_capture_but_holds_egress(self):
  f=fixture_data('unconfigured-private',False)
  with self.assertRaises(ValidationError):d.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm')
  self.assertTrue(d.Projection.objects.filter(pk=f['projection'].pk).exists());self.assertFalse(d.Job.objects.exists())
 def test_policy_rejects_role_source_process_tools_and_unknown_values(self):
  f=self.f
  for change in [{'reviewer_role':'CEO'},{'process_ids':['UNKNOWN']},{'evidence_ids':[f['sources']['policy_decision'].pk]},{'tools':['pay']},{'max_requests':None},{'contract_id':999999},{'sender_id':f['reviewer'].pk,'reviewer_id':f['reviewer'].pk}]:
   with self.subTest(change=change),self.assertRaises(ValidationError),transaction.atomic():data_policy(f,dict(f['data_rules'],**change))
 def test_private_input_excluded_from_generic_reader_and_agent(self):
  f=self.f;self.assertTrue(restricted(f['input']));self.assertFalse(public_evidence(f['case'].evidence.all()).filter(pk=f['input'].pk).exists())
  with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,f['input'].pk,'P34')
 def test_source_projection_rejects_raw_domains_wrong_case_and_nonquotes(self):
  f=self.f;e=evidence(f,'migration_proof','Private raw operational proof')
  for source,quotes in [(e.pk,['Private raw operational proof']),(999999,['x']),(f['input'].pk,['invented'])]:
   with self.assertRaises(ValidationError):d.project(f['actor'],f['case'].pk,source,'P34','purpose',quotes)
  p=d.project(f['actor'],f['case'].pk,f['input'].pk,'P34','synthetic-progress-summary',['Milestone evidence reviewed.']);self.assertEqual(p.pk,f['projection'].pk)
  with self.assertRaises(ValidationError):d.project(f['actor'],f['case'].pk,f['input'].pk,'P34','synthetic-progress-summary',['Milestone evidence'],predecessor=None)
 def test_no_ready_provider_or_projection_review_no_send(self):
  f=self.f;d.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm')
  with self.assertRaises(ValidationError):d.reserve(f['actor'],f['case'].pk,f['projection'].pk,'missing')
  with endpoint():
   j=self.job();d.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'withdraw');self.work(j);self.assertEqual(j.status,'held');self.assertFalse(d.Receipt.objects.exists())
 def test_strict_outputs_and_no_business_effects(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();remote['private_output']={'facts':[{'quote':'DO NOT SEND THIS EXCLUDED PRIVATE NOTE.'}],'uncertainties':[],'proposed_actions':[]};self.work(j);r=d.Receipt.objects.get(job=j);self.assertEqual(j.status,'rejected');self.assertFalse(r.valid);self.assertEqual(r.result,{})
   with self.assertRaises(ValidationError):d.review_result(f['reviewer'],f['case'].pk,r.pk,'confirm')
  for v in [{'facts':[],'uncertainties':[],'proposed_actions':['approve']},{'facts':[{'quote':'Milestone evidence reviewed.','evidence':f['input'].pk}],'uncertainties':[],'proposed_actions':[]},{'facts':[],'uncertainties':['x'*2001],'proposed_actions':[]},{'facts':[],'uncertainties':[],'proposed_actions':[],'tool_calls':[]}]:
   with self.assertRaises(ValidationError):d.output(f['projection'],v,4000)
 def test_unknown_response_reconciles_after_sender_revocation_and_exhaustion(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();remote['lose_response']=True;self.work(j);self.assertEqual(j.status,'unknown');self.assertEqual(len(remote['private_inputs']),1);Grant.objects.filter(case=f['case'],user=f['actor'],action__startswith='agent.data.').update(active=False);d.Job.objects.filter(pk=j.pk).update(attempts=30);remote['lose_response']=False;self.work(j);self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
   self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('private_result',args=[f['case'].pk,d.Receipt.objects.get(job=j).pk])).status_code,403)
 def test_current_permissions_checked_before_send_and_private_read(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();Grant.objects.filter(case=f['case'],user=f['actor'],action='agent.data.source').update(active=False);self.work(j);self.assertEqual(j.status,'held');self.assertNotIn('private_inputs',remote)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,f['projection'].pk])).status_code,403);self.assertNotContains(self.client.get(reverse('private_evidence',args=[f['case'].pk])),'Milestone evidence reviewed.')
 def test_source_policy_and_provider_changes_invalidate_reserved_send(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();add_evidence(f['actor'],f['case'].pk,'agent_private_input','Replacement source','synthetic:replacement');self.work(j);self.assertEqual(j.status,'held');self.assertNotIn('private_inputs',remote)
 def test_review_expiry_and_budget_are_explicit(self):
  f=self.f
  with endpoint() as remote:
   j=self.job()
   for n in [2,3]:d.reserve(f['actor'],f['case'].pk,f['projection'].pk,'request-'+str(n))
   with self.assertRaises(ValidationError):d.reserve(f['actor'],f['case'].pk,f['projection'].pk,'request-4')
   self.assertEqual(d.reserve(f['actor'],f['case'].pk,f['projection'].pk,'extract-1').pk,j.pk)
   future=timezone.now()+timedelta(seconds=3601)
   from unittest.mock import patch
   with patch('apps.agents.boundary.timezone.now',return_value=future):
    with self.assertRaises(ValidationError):d.context(f['actor'],f['projection'])
 def test_valid_receipt_preserved_but_acceptance_stales_after_policy_replacement(self):
  f=self.f
  with endpoint():
   j=self.job();self.work(j);r=d.Receipt.objects.get(job=j);d.review_result(f['reviewer'],f['case'].pk,r.pk,'confirm');old=copy.deepcopy(r.result);data_policy(f,dict(f['data_rules'],max_requests=4));v=d.inspect(f['reviewer'],f['case'].pk,r.pk);self.assertFalse(v['currently_accepted']);r.refresh_from_db();self.assertEqual(r.result,old)
 def test_append_only_sql_and_job_intent_guards(self):
  f=self.f
  with self.assertRaises(DatabaseError),transaction.atomic():d.Projection.objects.filter(pk=f['projection'].pk).update(payload={})
  with endpoint():
   j=self.job();self.work(j);r=d.Receipt.objects.get(job=j)
   with self.assertRaises(DatabaseError),transaction.atomic():d.Job.objects.filter(pk=j.pk).update(intent={})
   with self.assertRaises(DatabaseError),transaction.atomic():d.Receipt.objects.filter(pk=r.pk).delete()
   with self.assertRaises(DatabaseError),transaction.atomic():d.ProjectionReview.objects.filter(projection=f['projection']).update(verdict='withdraw')
 def test_actual_ui_commands_capture_review_send_result_and_private_post_controls(self):
  f=self.f;url=reverse('private_evidence',args=[f['case'].pk]);self.client.force_login(f['actor']);self.assertContains(self.client.get(url),'Reviewed private evidence')
  with endpoint():
   j=self.job();self.work(j);r=d.Receipt.objects.get(job=j);self.client.force_login(f['reviewer']);response=self.client.post(url,{'action':'result_review','revision':rev(f['case']),'receipt':r.pk,'verdict':'confirm','corrected':''});self.assertEqual(response.status_code,302);self.assertEqual(d.Review.objects.count(),1);self.assertTrue(self.client.get(reverse('private_result',args=[f['case'].pk,r.pk])).json()['currently_accepted'])
  self.client.force_login(f['actor']);self.assertEqual(self.client.post(url,{'action':'capture','revision':rev(f['case']),'body':'New private note','source':'synthetic:ui'}).status_code,302);self.assertTrue(f['case'].evidence.filter(kind='agent_private_input',body='New private note').exists())
  self.client.post(url,{'action':'capture','revision':rev(f['case']),'body':'rogue','source':'synthetic:ui','role':'CEO'});self.assertFalse(f['case'].evidence.filter(body='rogue').exists())
 def test_case_scope_cannot_read_or_dispatch_foreign_projection(self):
  f=self.f;other=fixture_data('foreign-private');self.client.force_login(other['actor'])
  self.assertEqual(self.client.get(reverse('private_projection',args=[f['case'].pk,f['projection'].pk])).status_code,404)
  with self.assertRaises(ValidationError):d.reserve(f['actor'],f['case'].pk,other['projection'].pk,'foreign')
 def test_rotation_holds_uncertain_job_instead_of_querying_new_provider(self):
  import os
  f=self.f
  with endpoint() as remote:
   j=self.job();remote['lose_response']=True;self.work(j);self.assertEqual(j.status,'unknown');old=os.environ['PSL_TEST_READINESS_TOKEN'];os.environ['PSL_TEST_READINESS_TOKEN']='OTHER-SYNTHETIC-ROTATED-TOKEN'
   try:self.work(j);self.assertEqual(j.status,'unknown');self.assertEqual(len(remote['private_inputs']),1)
   finally:os.environ['PSL_TEST_READINESS_TOKEN']=old
   remote['lose_response']=False;self.work(j);self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
 def test_output_and_input_budget_holds_and_correction_validation(self):
  f=self.f
  with endpoint():
   j=self.job();self.work(j);r=d.Receipt.objects.get(job=j)
   with self.assertRaises(ValidationError):d.review_result(f['reviewer'],f['case'].pk,r.pk,'correct',{'facts':[{'quote':'not projected'}],'uncertainties':[],'proposed_actions':[]})
   with self.assertRaises(ValidationError):d.output(f['projection'],{'facts':[],'uncertainties':['x'*200],'proposed_actions':[]},100)
  data_policy(f,dict(f['data_rules'],max_input_chars=1))
  with self.assertRaises(ValidationError):d.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm')
 def test_database_deactivated_sender_is_held_despite_cached_active_actor(self):
  from django.contrib.auth import get_user_model
  f=self.f
  with endpoint() as remote:
   j=self.job();get_user_model().objects.filter(pk=f['actor'].pk).update(is_active=False);self.assertTrue(f['actor'].is_active);self.work(j);self.assertEqual(j.status,'held');self.assertNotIn('private_inputs',remote)
 def test_generic_timeline_and_subject_do_not_expose_private_input_hash_or_activity(self):
  from apps.core.evidence_access import public_timeline
  from apps.pmo.services import subject
  from apps.documents.services import review_document
  f=self.f
  with self.assertRaises(ValidationError):subject(f['case'],f['input'].pk)
  with self.assertRaises(ValidationError):review_document(f['actor'],f['case'].pk,f['input'].pk,'accepted','Cannot turn private source into a generic review',rev(f['case']))
  timeline=public_timeline(f['case']);self.assertFalse(timeline.filter(data__evidence=f['input'].pk).exists());self.assertTrue(timeline.filter(action='evidence.added',data__evidence=f['sources']['plan'].pk).exists());self.assertTrue(timeline.filter(data__has_key='component').exists())
  self.client.force_login(f['actor']);response=self.client.get(reverse('case',args=[f['case'].pk]));self.assertEqual(response.status_code,200);self.assertNotContains(response,f['input'].sha256);self.assertNotContains(response,'agent.data.projected');self.assertContains(response,f['sources']['plan'].sha256)
 def test_malformed_utf8_response_is_unknown_and_recovers_original_receipt(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();remote['private_wire']=b'\xff';self.work(j);self.assertEqual(j.status,'unknown');self.assertFalse(d.Receipt.objects.exists());del remote['private_wire'];self.work(j);self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
 def test_nonfinite_response_stays_unknown_without_resending_private_input(self):
  f=self.f
  with endpoint() as remote:
   j=self.job();remote['private_output']={'facts':[],'uncertainties':[float('nan')],'proposed_actions':[]};self.work(j);self.assertEqual(j.status,'unknown');self.work(j);self.assertEqual(j.status,'unknown');self.assertEqual(len(remote['private_inputs']),1);self.assertFalse(d.Receipt.objects.exists());remote['receipts'][j.operation_key]['result']={'facts':[{'quote':'Milestone evidence reviewed.'}],'uncertainties':[],'proposed_actions':[]};self.work(j);self.assertEqual(j.status,'confirmed');self.assertEqual(len(remote['private_inputs']),1)
