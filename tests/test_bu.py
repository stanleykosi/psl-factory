import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from django.urls import reverse
from apps.identity.models import Grant
from apps.core.models import Evidence,Audit
from apps.core.services import add_evidence
from apps.policy.services import resolve,transition
from apps.policy.bu_validators import STAFF,SOURCE,MAPPING,AUTH,DISCLOSE
from apps.finance import bu as domain
from apps.finance.models import BUWork,BUReview,BUReport,BUReceipt,BUEventClaim,PayrollInput,PayrollRun,PayrollPublication,Invoice,CashReceipt
from apps.agents.bu import investigate
from adapters.bu import LocalBUReportAdapter
from .bu_helpers import fixture,policy,rule,staff,source,event,publish,review,body
from .helpers import rev,setup_case

class BUTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_F21_N01_70_30_exact_E900_excluded_from_standard_pool(self):
  f=self.f;w=staff(f);r=domain.read_private(f['preparer'],f['case'].pk,w.pk);self.assertEqual(connection.vendor,'postgresql');self.assertEqual(r['by_bu'],{'BU-A':'220.00','BU-B':'30.00'});self.assertEqual(r['source_total'],'250');self.assertTrue(r['conserved'])
  special=next(x for x in r['rows'] if x['employee_id']=='E900');self.assertEqual(special['allocations'],{'BU-A':'70.00','BU-B':'30.00'});self.assertTrue(special['excluded_from_standard_pool']);self.assertEqual(len(r['rows']),2)
  p=publish(f,w);out=LocalBUReportAdapter().read(f['manager'],p.pk);self.assertNotIn('E900',json.dumps(out));self.assertNotIn('staff_counts',out);self.assertFalse(out['ledger_posted']);self.assertEqual(Invoice.objects.count(),0);self.assertEqual(CashReceipt.objects.count(),0)
 def test_F21_E01_missing_current_ratio_does_not_infer_or_reuse(self):
  f=self.f;w=staff(f,rules=[]);self.assertIn('missing_or_ambiguous_exception_rule',w.metadata['codes'])
  with self.assertRaises(ValidationError):review(f,w)
  with self.assertRaises(ValidationError):rule(f,period='2026-08')
 def test_duplicate_exception_and_wrong_pool_cannot_double_allocate(self):
  f=self.f;r=rule(f);review(f,r);w=staff(f,rules=[r.pk],declared=[['E900','BASIC'],['E900','BASIC']]);self.assertIn('duplicate_exception_subject',w.metadata['codes'])
  with self.assertRaises(ValidationError):rule(f,key='wrongpool',standard_pool_ref='ANOTHER-POOL')
 def test_unapproved_rule_stays_held_and_parent_reviews_must_be_current(self):
  f=self.f;r=rule(f);w=staff(f,rules=[r.pk]);self.assertIn('exception_rule_unapproved',w.metadata['codes'])
  with self.assertRaises(ValidationError):review(f,w)
  review(f,r);w=staff(f,key='reviewed',rules=[r.pk]);p=publish(f,w);review(f,r,verdict='revoke')
  with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)
 def test_superseded_private_ratio_invalidates_without_rewriting_history(self):
  f=self.f;w=staff(f);p=publish(f,w);rule(f,key='changed-rule',weights=[{'bu':'BU-A','weight':'1'}])
  with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)
  self.assertEqual(BUReport.objects.get(pk=p.pk).payload['by_bu']['BU-B'],'30.00')
 def test_rule_cannot_approve_a_subject_absent_from_exact_payroll(self):
  f=self.f
  with self.assertRaises(ValidationError):rule(f,employee_id='NOT-IN-SOURCE')
 def test_small_group_holds_whole_staff_publication(self):
  f=self.f;v=deepcopy(f['bu_config']['disclosure']);v['minimum_staff']=2;policy(f,DISCLOSE,v);w=staff(f);review(f,w)
  with self.assertRaises(ValidationError):domain.publish(f['preparer'],f['case'].pk,w.pk,'small',rev(f['case']))
  self.assertEqual(BUReport.objects.count(),0)
 def test_F44_N01_E1_direct_once_rolls_up_100_no_ledger_write(self):
  f=self.f;w=event(f);self.assertEqual(w.payload['by_bu'],{'BU-A':'100.00'});self.assertEqual(w.payload['source_total'],'100');self.assertTrue(w.payload['conserved']);p=publish(f,w);out=domain.read_report(f['manager'],p.pk);self.assertEqual(out['company_source_total'],'100');self.assertNotIn('event_id',out);self.assertEqual(BUEventClaim.objects.count(),1)
 def test_F44_E01_shared_uses_explicit_weights_and_conflicting_tags_hold(self):
  f=self.f;s=source(f,rows=[{'event_id':'E1','amount':'100','tags':['SHARED']}]);w=event(f,s=s);self.assertEqual(w.payload['by_bu'],{'BU-A':'70.00','BU-B':'30.00'});publish(f,w)
  s=source(f,key='conflict',source_version='v2',rows=[{'event_id':'E1','amount':'100','tags':['DIRECT-A','SHARED']}]);w=event(f,key='conflict-event',s=s);self.assertIn('ambiguous_event_tags',w.metadata['codes'])
  with self.assertRaises(ValidationError):review(f,w)
 def test_company_only_is_not_assigned_to_a_BU(self):
  f=self.f;s=source(f,rows=[{'event_id':'E1','amount':'100','tags':['COMPANY']}]);w=event(f,s=s);self.assertEqual(w.payload['by_bu'],{});self.assertEqual(w.payload['company_only'],'100');self.assertTrue(w.payload['conserved']);publish(f,w)
 def test_duplicate_event_rows_rejected_without_values_or_claims(self):
  f=self.f;rows=[{'event_id':'PRIVATE-DUPLICATE','amount':'100','tags':['DIRECT-A']}]*2;s=source(f,rows=rows,control_total='200');self.assertFalse(s.metadata['accepted']);self.assertEqual(s.payload,{});self.assertIn('duplicate_event_identity',s.metadata['codes']);self.assertEqual(BUEventClaim.objects.count(),0)
 def test_event_identity_cannot_be_claimed_by_another_batch_reference(self):
  f=self.f;source(f);s=source(f,key='other-batch',reference='other-batch');self.assertFalse(s.metadata['accepted']);self.assertEqual(s.metadata['codes'],['event_identity_owned_elsewhere']);self.assertEqual(BUEventClaim.objects.count(),1)
 def test_unknown_event_amount_and_partial_inventory_do_not_become_zero(self):
  f=self.f;s=source(f,control_total=None,completeness='partial',rows=[{'event_id':'E1','amount':None,'tags':['DIRECT-A']}]);w=domain.attribute(f['preparer'],f['case'].pk,s.pk,'unknown','unknown',rev(f['case']));self.assertIsNone(w.payload['source_total']);self.assertIn('unknown_event_amount',w.metadata['codes']);self.assertIn('event_inventory_incomplete',w.metadata['codes'])
  with self.assertRaises(ValidationError):review(f,s)
 def test_source_controls_and_unknown_tags_hold_report(self):
  f=self.f;s=source(f,control_total='101',rows=[{'event_id':'E1','amount':'100','tags':['UNMAPPED']}]);w=domain.attribute(f['preparer'],f['case'].pk,s.pk,'unmapped','unmapped',rev(f['case']));self.assertIn('event_control_unresolved',w.metadata['codes']);self.assertIn('unmapped_event',w.metadata['codes'])
 def test_source_scope_and_malformed_extra_fields_retained_only_as_codes(self):
  f=self.f
  for key,value in [('currency','OTHER'),('extracted_at',(timezone.now()-timedelta(days=2)).isoformat()),('medical','PRIVATE-REJECTED-EVENT')]:
   s=source(f,key='bad-'+key,**{key:value});self.assertFalse(s.metadata['accepted']);self.assertEqual(s.payload,{})
  self.assertFalse(Evidence.objects.filter(body__contains='PRIVATE-REJECTED-EVENT').exists());self.assertNotIn('PRIVATE-REJECTED-EVENT',json.dumps(list(Audit.objects.values_list('data',flat=True))))
 def test_closed_period_hold_then_explicit_reviewed_reference_only(self):
  f=self.f;v=deepcopy(f['bu_config']['source']);v['closed_periods']=['2026-09'];policy(f,SOURCE,v);w=event(f);self.assertIn('closed_period_reference_hold',w.metadata['codes'])
  with self.assertRaises(ValidationError):review(f,w)
  v['closed_period_treatment']='reviewed_reference_only';policy(f,SOURCE,v);w=event(f,key='closed-allowed',s=source(f,key='closed-allowed-source'));review(f,w)
  with self.assertRaises(ValidationError):domain.publish(f['preparer'],f['case'].pk,w.pk,'no-historical-review',rev(f['case']))
  review(f,w,purpose='historical');p=domain.publish(f['preparer'],f['case'].pk,w.pk,'with-review',rev(f['case']));self.assertFalse(domain.read_report(f['manager'],p.pk)['source_written'])
 def test_corrected_event_source_invalidates_prior_report_requires_historical_review(self):
  f=self.f;w=event(f);p=publish(f,w);s=source(f,key='v2',source_version='v2',control_total='120',rows=[{'event_id':'E1','amount':'120','tags':['DIRECT-A']}]);w2=event(f,key='event-v2',s=s)
  with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)
  review(f,w2)
  with self.assertRaises(ValidationError):domain.publish(f['preparer'],f['case'].pk,w2.pk,'historical-pending',rev(f['case']))
  review(f,w2,purpose='historical');p2=domain.publish(f['preparer'],f['case'].pk,w2.pk,'historical-approved',rev(f['case']));self.assertEqual(domain.read_report(f['manager'],p2.pk)['company_source_total'],'120');self.assertEqual(BUReport.objects.get(pk=p.pk).payload['company_source_total'],'100');self.assertEqual(BUEventClaim.objects.count(),1)
 def test_prospective_only_policy_holds_historical_rework_not_source_capture(self):
  f=self.f;publish(f,event(f));v=deepcopy(f['bu_config']['mapping']);v['historical_treatment']='prospective_only';policy(f,MAPPING,v);s=source(f,key='corrected');self.assertTrue(s.metadata['accepted']);w=event(f,key='historical',s=s);self.assertIn('historical_rework_policy_hold',w.metadata['codes'])
 def test_missing_financial_and_authority_policy_holds_dependent_steps_only(self):
  f=self.f;transition(f['preparer'],f['bu_policies'][STAFF].pk,'revoked');r=rule(f);self.assertIn('staff_policy_missing',r.metadata['codes']);self.assertTrue(source(f).metadata['accepted'])
  transition(f['preparer'],f['bu_policies'][AUTH].pk,'revoked');s=source(f,key='source-no-auth');self.assertTrue(s.metadata['accepted'])
  with self.assertRaises(ValidationError):review(f,s)
 def test_missing_company_comparison_holds_only_rollup(self):
  f=self.f;v=deepcopy(f['bu_config']['source']);v['company_comparison']='finance_allocation_required';policy(f,SOURCE,v);s=source(f);self.assertTrue(s.metadata['accepted']);w=event(f,s=s);self.assertIn('finance_company_comparison_missing',w.metadata['codes'])
 def test_metadata_UI_agent_never_read_private_work_or_payroll(self):
  f=self.f;publish(f,staff(f));publish(f,event(f))
  def forbidden(_):raise AssertionError('Private JSON accessed on metadata path')
  with patch.object(BUWork,'payload',new=property(forbidden)),patch.object(BUReport,'payload',new=property(forbidden)),patch.object(PayrollRun,'result',new=property(forbidden)),patch.object(PayrollInput,'payload',new=property(forbidden)):
   a=investigate(f['preparer'],f['case'].pk,rev(f['case']));self.assertFalse(a.result['private_payloads_read']);self.assertNotIn('E900',json.dumps(a.result));self.client.force_login(f['manager']);r=self.client.get(reverse('bu',args=[f['case'].pk]));self.assertEqual(r.status_code,200);self.assertNotContains(r,'E900');self.assertNotContains(r,'70.00')
 def test_private_named_readers_independent_actual_humans_and_case_scope(self):
  f=self.f;w=staff(f)
  with self.assertRaises(PermissionDenied):domain.read_private(f['manager'],f['case'].pk,w.pk)
  with self.assertRaises(PermissionDenied):domain.review(f['preparer'],f['case'].pk,w.pk,'staff','approve','self',f['e']['bu_review'].pk,rev(f['case']))
  a,c=setup_case(username='foreign-bu')
  with self.assertRaises(ValidationError):domain.read_private(a,c.pk,w.pk)
 def test_retention_policies_grants_and_HR_recipient_revocation_invalidate(self):
  f=self.f;w=staff(f);p=publish(f,w);Grant.objects.filter(case=f['case'],user=f['preparer'],action='hrfinance.snapshot.read').update(active=False)
  with self.assertRaises(PermissionDenied):domain.read_report(f['manager'],p.pk)
  w=event(f);p=publish(f,w)
  with patch('apps.finance.bu.timezone.now',return_value=timezone.now()+timedelta(days=8)):
   with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)
  transition(f['preparer'],f['bu_policies'][DISCLOSE].pk,'revoked')
  with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)
 def test_exact_retry_changed_intent_and_receipt_idempotence(self):
  f=self.f;raw=body(f);scope={k:f['bu_config']['export'][k] for k in ['entity','period','currency']};s=domain.capture(f['preparer'],f['case'].pk,'events','same',scope,raw,rev(f['case']));self.assertEqual(domain.capture(f['preparer'],f['case'].pk,'events','same',scope,raw,rev(f['case'])).pk,s.pk)
  with self.assertRaises(ValidationError):domain.capture(f['preparer'],f['case'].pk,'events','same',scope,raw+' ',rev(f['case']))
  p=publish(f,event(f,s=s));r=domain.receive(f['manager'],f['case'].pk,p.pk,rev(f['case']));v=rev(f['case']);self.assertEqual(domain.receive(f['manager'],f['case'].pk,p.pk,v).pk,r.pk);self.assertEqual(rev(f['case']),v)
 def test_no_store_human_report_UI_private_denial_and_safe_capture(self):
  f=self.f;p=publish(f,staff(f));self.client.force_login(f['manager']);r=self.client.get(reverse('bu_inspect',args=[f['case'].pk,'report',p.pk]));self.assertContains(r,'220.00');self.assertNotContains(r,'E900');self.assertEqual(r['Cache-Control'],'no-store');self.assertEqual(self.client.get(reverse('bu_inspect',args=[f['case'].pk,'work',p.work_id])).status_code,403)
  self.client.force_login(f['preparer']);r=self.client.get(reverse('bu_inspect',args=[f['case'].pk,'work',p.work_id]));self.assertContains(r,'E900');self.assertEqual(r['Cache-Control'],'no-store')
  v=json.loads(body(f));v['medical']='PRIVATE-UI-REJECT';r=self.client.post(reverse('bu',args=[f['case'].pk]),{'action':'capture','revision':rev(f['case']),'reference':'events','operation_key':'bad-UI','scope':json.dumps({k:v[k] for k in ['entity','period','currency']}),'body':json.dumps(v)},follow=True);self.assertNotContains(r,'PRIVATE-UI-REJECT');self.assertContains(r,'event_schema_rejected')
 def test_typed_oracles_actual_actors_residuals_and_superseded_evidence(self):
  f=self.f
  for key,name in [(STAFF,'staff'),(MAPPING,'mapping')]:
   v=deepcopy(f['bu_config'][name]);v['oracles'][0]['expected']['BU-A']='999'
   with self.assertRaises(ValidationError):policy(f,key,v)
  v=deepcopy(f['bu_config']['authority']);v['assignments'][0]['user_id']=999999
  with self.assertRaises(ValidationError):policy(f,AUTH,v)
  add_evidence(f['preparer'],f['case'].pk,'bu_source_contract','New synthetic source contract','synthetic:changed')
  with self.assertRaises(ValidationError):source(f)
 def test_SQL_guards_all_five_history_types(self):
  f=self.f;s=source(f);w=event(f,s=s);p=publish(f,w);r=domain.receive(f['manager'],f['case'].pk,p.pk,rev(f['case']))
  for table,pk in [('buwork',w.pk),('bureview',p.review_id),('bureport',p.pk),('bureceipt',r.pk),('bueventclaim',BUEventClaim.objects.first().pk)]:
   for sql in [f'UPDATE finance_{table} SET id=id WHERE id=%s',f'DELETE FROM finance_{table} WHERE id=%s']:
    with self.assertRaises(DatabaseError),transaction.atomic():
     with connection.cursor() as cursor:cursor.execute(sql,[pk])

 def test_zero_cost_employee_still_counts_for_small_group_protection(self):
  f=self.f
  from .payroll_helpers import capture as payroll_capture,combined,approve
  from apps.finance import payroll
  f['inputs'][0]=payroll_capture(f,0,'zero-cost',source_version='zero-cost',control_total='0',rows=[{'row_ref':'A1','employee_id':'E900','component':'BASIC','amount':'0'}]);c=combined(f,'zero-combine');approve(f,c);m=payroll.match(f['preparer'],f['case'].pk,c.pk,f['hr'].pk,'zero-match',rev(f['case']));approve(f,m);f['match']=m
  v=deepcopy(f['bu_config']['disclosure']);v['minimum_staff']=2;policy(f,DISCLOSE,v);w=staff(f);self.assertEqual(w.payload['staff_counts']['BU-B'],1);self.assertEqual(w.payload['by_bu']['BU-B'],'0.00');review(f,w)
  with self.assertRaises(ValidationError):domain.publish(f['preparer'],f['case'].pk,w.pk,'protected-zero',rev(f['case']))
 def test_empty_selected_staff_population_is_unknown_and_unpublishable(self):
  f=self.f;v=deepcopy(f['bu_config']['staff']);v['components']=['BONUS'];v['standard_weights']=[];policy(f,STAFF,v);w=staff(f,rules=[],declared=[]);self.assertIn('empty_staff_population',w.metadata['codes']);self.assertIsNone(w.payload['source_total'])
  with self.assertRaises(ValidationError):review(f,w)
 def test_missing_event_mapping_does_not_block_source_capture(self):
  f=self.f;transition(f['preparer'],f['bu_policies'][MAPPING].pk,'revoked');s=source(f);self.assertTrue(s.metadata['accepted'])
  with self.assertRaises(ValidationError):domain.attribute(f['preparer'],f['case'].pk,s.pk,'unconfigured','unconfigured',rev(f['case']))

 def test_approved_exception_cannot_be_omitted_into_standard_pool(self):
  f=self.f;r=rule(f);review(f,r);w=staff(f,rules=[],declared=[]);self.assertIn('known_exception_omitted',w.metadata['codes'])
  with self.assertRaises(ValidationError):review(f,w)
 def test_pending_exception_requires_explicit_withdrawal_before_standard_treatment(self):
  f=self.f;r=rule(f);w=staff(f,rules=[],declared=[]);self.assertIn('known_exception_omitted',w.metadata['codes']);review(f,r,verdict='revoke')
  w=staff(f,key='withdrawn',rules=[],declared=[]);self.assertEqual(w.metadata['status'],'complete');self.assertEqual(w.payload['by_bu'],{'BU-A':'250.00'});p=publish(f,w)
  review(f,r,key='reapproved')
  with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)
 def test_new_classification_after_output_review_invalidates_old_staff_work(self):
  f=self.f;w=staff(f,rules=[],declared=[]);review(f,w);r=rule(f);review(f,r)
  with self.assertRaises(ValidationError):domain.publish(f['preparer'],f['case'].pk,w.pk,'must-reassess',rev(f['case']))
  def forbidden(_):raise AssertionError('Inventory metadata check loaded private values')
  with patch.object(BUWork,'payload',new=property(forbidden)):
   a=investigate(f['preparer'],f['case'].pk,rev(f['case']));self.assertFalse(a.result['private_payloads_read']);self.assertTrue(any(x['work_id']==w.pk and x['state']=='reassessment required' for x in a.result['findings']))
