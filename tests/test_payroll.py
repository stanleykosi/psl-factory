import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.identity.models import Grant
from apps.policy.services import transition,resolve
from apps.policy.payroll_validators import ACCESS,MERGE,MATCH,REPORT,AUTH
from apps.finance import payroll as domain,hrfinance as hr
from apps.finance.models import PayrollRequest,PayrollInput,PayrollRun,PayrollReview,PayrollPublication,PayrollReportReceipt,PayrollHRFollowup,Invoice,CashReceipt
from apps.agents.payroll import investigate
from adapters.payroll import LocalPayrollReportAdapter
from .helpers import setup_case,rev
from .payroll_helpers import fixture,capture,body,policy,approve,combined,pipeline

class PayrollTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_PostgreSQL_and_F16_N01_exact_controls_and_provenance(self):
  self.assertEqual(connection.vendor,'postgresql');f=self.f;r=combined(f);data=domain.private_run(f['preparer'],f['case'].pk,r.pk)
  self.assertEqual(data['combined_total'],'250');self.assertEqual(len(data['rows']),2);self.assertEqual({c['calculated'] for c in data['controls'].values()},{'100','150'});self.assertEqual(data['intentional_overlap_difference'],'0');self.assertTrue(all(x['provenance'][0]['input_id'] for x in data['rows']))
 def test_F17_N01_and_F18_N01_reviewed_current_aggregate_250(self):
  f=self.f;c,m,a,p=pipeline(f);self.assertEqual(a.result['by_bu'],{'BU-A':'250.00'});self.assertTrue(all(r['bu']=='BU-A' for r in m.result['rows']))
  out=LocalPayrollReportAdapter().read(f['manager'],p.pk);self.assertEqual(out['by_bu'],{'BU-A':'250.00'});self.assertNotIn('E001',json.dumps(out));self.assertNotIn('rows',out);self.assertFalse(out['ledger_posted']);self.assertFalse(out['hr_written']);self.assertEqual(Invoice.objects.count(),0);self.assertEqual(CashReceipt.objects.count(),0)
  r=domain.receive_report(f['manager'],f['case'].pk,p.pk,rev(f['case']));self.assertEqual(domain.receive_report(f['manager'],f['case'].pk,p.pk,rev(f['case'])).pk,r.pk)
 def test_F16_E01_overlap_held_without_summing_or_name_dedup(self):
  f=self.f;v=[{'row_ref':'B1','employee_id':'E001','component':'BASIC','amount':'150'}];f['inputs'][1]=capture(f,1,'overlap',rows=v,source_version='B-v2');r=combined(f,'overlap-combine')
  self.assertIn('overlap_unresolved',r.metadata['codes']);self.assertIsNone(r.result['combined_total']);self.assertIsNone(r.result['rows'][0]['amount'])
  with self.assertRaises(ValidationError):approve(f,r)
 def test_explicit_provider_precedence_preserves_intentional_difference(self):
  f=self.f;v=deepcopy(f['config']['merge']);v['method']='prefer_provider';v['oracles'][1]['expected']='100';policy(f,MERGE,v)
  f['inputs'][1]=capture(f,1,'overlap',rows=[{'row_ref':'B1','employee_id':'E001','component':'BASIC','amount':'150'}],source_version='B-v2');r=combined(f,'prefer');self.assertEqual(r.result['combined_total'],'100');self.assertEqual(r.result['intentional_overlap_difference'],'150');self.assertEqual(len(r.result['rows'][0]['provenance']),2)
 def test_explicit_sum_is_not_implicit_union(self):
  f=self.f;v=deepcopy(f['config']['merge']);v['method']='sum_explicit';v['oracles'][1]['expected']='250';policy(f,MERGE,v)
  f['inputs'][1]=capture(f,1,'overlap',rows=[{'row_ref':'B1','employee_id':'E001','component':'BASIC','amount':'150'}],source_version='B-v2');r=combined(f,'sum');self.assertEqual(r.result['combined_total'],'250');self.assertEqual(r.result['intentional_overlap_difference'],'0')
 def test_missing_merge_holds_values_only_and_missing_authority_does_not_stop_capture(self):
  f=self.f;transition(f['owner'],f['policies'][MERGE].pk,'revoked');transition(f['owner'],f['policies'][AUTH].pk,'revoked')
  r=domain.combine(f['preparer'],f['case'].pk,f['request'].pk,[i.pk for i in f['inputs']],'unconfigured',rev(f['case']));self.assertIn('merge_policy_missing',r.metadata['codes']);self.assertIsNone(r.result['combined_total'])
  self.assertTrue(capture(f,1,'fresh',source_version='B-v2').metadata['accepted'])
 def test_unknown_amount_and_control_total_are_not_zero(self):
  f=self.f;i=capture(f,1,'unknown',rows=[{'row_ref':'B1','employee_id':'E002','component':'BASIC','amount':None}],control_total=None,source_version='B-v2');self.assertEqual(i.metadata['status'],'held');self.assertIsNone(i.payload['control_total'])
  f['inputs'][1]=i;r=domain.combine(f['preparer'],f['case'].pk,f['request'].pk,[x.pk for x in f['inputs']],'unknown-run',rev(f['case']));self.assertIsNone(r.result['combined_total'])
  with self.assertRaises(ValidationError):approve(f,i)
 def test_source_control_mismatch_preserves_source_and_prevents_review(self):
  f=self.f;i=capture(f,1,'bad-total',control_total='151',source_version='B-v2');self.assertEqual(i.payload['control_total'],'151');self.assertIn('source_control_unresolved',i.metadata['codes'])
  with self.assertRaises(ValidationError):approve(f,i)
 def test_duplicate_source_and_extra_medical_fields_rejected_without_retention(self):
  f=self.f
  for k in ['duplicate','medical']:
   v=json.loads(body(f,1))
   if k=='duplicate':v['rows'].append(v['rows'][0])
   else:v['rows'][0]['medical']='PRIVATE-REJECTED-VALUE'
   i=domain.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B',k,json.dumps(v),rev(f['case']));self.assertFalse(i.metadata['accepted']);self.assertEqual(i.payload,{})
  self.assertFalse(Evidence.objects.filter(body__contains='PRIVATE-REJECTED-VALUE').exists());self.assertNotIn('PRIVATE-REJECTED-VALUE',json.dumps(list(Audit.objects.values_list('data',flat=True))))
 def test_wrong_period_currency_provider_and_stale_extract_rejected(self):
  f=self.f
  for key,value in [('period','2026-10'),('currency','NGN'),('provider','OTHER'),('extracted_at',(timezone.now()-timedelta(days=2)).isoformat())]:self.assertFalse(capture(f,1,'bad-'+key,**{key:value}).metadata['accepted'])
 def test_explicit_adjustment_component_and_exclusion_tie_out(self):
  f=self.f;v=deepcopy(f['config']['report']);v['components']=[{'component':'BASIC','coefficient':'1'}];policy(f,REPORT,v)
  f['inputs'][1]=capture(f,1,'adjusted-B',source_version='B2',control_total='140',rows=[{'row_ref':'B1','employee_id':'E002','component':'BASIC','amount':'150'},{'row_ref':'B2','employee_id':'E002','component':'ADJUSTMENT','amount':'-10'}])
  c,m,a,p=pipeline(f);self.assertEqual(c.result['combined_total'],'240');self.assertEqual(a.result['excluded_total'],'-10');self.assertEqual(a.result['eligible_total'],'250.00');self.assertEqual(domain.read_publication(f['manager'],p.pk)['by_bu'],{'BU-A':'250.00'})
 def test_owner_configured_as_of_membership_does_not_prorate_pay(self):
  f=self.f;v=deepcopy(f['config']['match']);v['membership']='as_of_snapshot';policy(f,MATCH,v);r=combined(f);approve(f,r)
  h=deepcopy(f['hr_config']['export']);h['rows'][1]['effective_from']='2026-09-15';h['extracted_at']=timezone.now().isoformat();s=hr.capture(f['owner'],f['case'].pk,f['hr_contract'].pk,'asof-HR',json.dumps(h),rev(f['case']))
  for u in [f['preparer'],f['reviewer']]:hr.receive(u,f['case'].pk,s.pk,'asof-receipt-'+str(u.pk),f['e']['hr_disclosure_decision'].pk,rev(f['case']))
  m=domain.match(f['preparer'],f['case'].pk,r.pk,s.pk,'asof-match',rev(f['case']));self.assertEqual(m.metadata['status'],'complete');self.assertEqual(m.result['rows'][1]['amount'],'150');approve(f,m)
 def test_report_rounding_oracle_and_changed_rule_invalidate_old_report(self):
  f=self.f;c,m,a,p=pipeline(f);v=deepcopy(f['config']['report']);v['rounding']='half_up';v['oracles'].append({'amounts':[{'component':'BASIC','amount':'1.005'}],'expected':'1.01'});policy(f,REPORT,v)
  with self.assertRaises(ValidationError):domain.read_publication(f['manager'],p.pk)
 def test_metadata_manager_cannot_draft_policy_or_nominate_self(self):
  f=self.f;self.client.force_login(f['manager']);res=self.client.post(reverse('payroll',args=[f['case'].pk]),{'action':'policy','revision':rev(f['case']),'component':ACCESS,'content':json.dumps(f['config']['access']),'evidence':f['e']['policy_decision'].pk},follow=True);self.assertEqual(res.status_code,200);self.assertContains(res,'Choose a permitted command');self.assertEqual(resolve(ACCESS,f['case']).configuration.pk,f['policies'][ACCESS].pk)
 def test_source_owner_and_admin_claims_do_not_grant_capture_or_review(self):
  f=self.f
  with self.assertRaises(PermissionDenied):domain.capture(f['preparer'],f['case'].pk,f['request'].pk,'PAY-A','fake-owner',body(f,0),rev(f['case']))
  r=combined(f);f['preparer'].is_superuser=True;f['preparer'].save()
  with self.assertRaises(PermissionDenied):domain.review(f['preparer'],f['case'].pk,'run',r.pk,'approve','admin',f['e']['payroll_review'].pk,rev(f['case']))
 def test_review_is_bound_to_exact_version_and_requires_source_acceptance(self):
  f=self.f;r=domain.combine(f['preparer'],f['case'].pk,f['request'].pk,[i.pk for i in f['inputs']],'unreviewed',rev(f['case']))
  with self.assertRaises(ValidationError):approve(f,r)
  for i in f['inputs']:approve(f,i)
  a=approve(f,r);self.assertEqual(domain.current_review(r).pk,a.pk);approve(f,r,'revoke',verdict='revoke')
  with self.assertRaises(ValidationError):domain.current_review(r)
 def test_F17_E01_duplicate_HR_source_holds_matching_no_HR_write(self):
  f=self.f;r=combined(f);approve(f,r);v=deepcopy(f['hr_config']['export']);v['rows'].append(v['rows'][0]);v['extracted_at']=timezone.now().isoformat()
  bad=hr.capture(f['owner'],f['case'].pk,f['hr_contract'].pk,'ambiguous-HR',json.dumps(v),rev(f['case']));self.assertEqual(bad.status,'rejected')
  m=domain.match(f['preparer'],f['case'].pk,r.pk,bad.pk,'ambiguous-match',rev(f['case']));self.assertIn('ambiguous_hr_source',m.metadata['codes']);self.assertTrue(all(x['bu'] is None for x in m.result['rows']));self.assertFalse(m.metadata['source_write'])
 def test_midperiod_membership_holds_without_invented_proration(self):
  f=self.f;r=combined(f);approve(f,r);v=deepcopy(f['hr_config']['export']);v['rows'][1]['effective_from']='2026-09-15';v['extracted_at']=timezone.now().isoformat();s=hr.capture(f['owner'],f['case'].pk,f['hr_contract'].pk,'transfer-HR',json.dumps(v),rev(f['case']))
  for u in [f['preparer'],f['reviewer']]:hr.receive(u,f['case'].pk,s.pk,'transfer-receipt-'+str(u.pk),f['e']['hr_disclosure_decision'].pk,rev(f['case']))
  m=domain.match(f['preparer'],f['case'].pk,r.pk,s.pk,'transfer-match',rev(f['case']));self.assertIn('midperiod_transfer_requires_treatment',m.metadata['codes'])
  with self.assertRaises(ValidationError):approve(f,m)
 def test_HR_purpose_scope_not_inherited_from_an_attribution_view(self):
  f=self.f;r=combined(f);approve(f,r)
  from apps.finance.hrfinance_models import HRReadSnapshot
  # A different case/source cannot be substituted even if identifiers look alike.
  a,c=setup_case(username='foreign')
  with self.assertRaises(ValidationError):domain.match(a,c.pk,r.pk,f['hr'].pk,'cross',rev(c))
 def test_missing_HR_membership_routes_a_real_correction_reference(self):
  f=self.f;r=combined(f);approve(f,r);v=deepcopy(f['hr_config']['export']);v['rows']=v['rows'][:1];v['extracted_at']=timezone.now().isoformat();s=hr.capture(f['owner'],f['case'].pk,f['hr_contract'].pk,'missing-HR',json.dumps(v),rev(f['case']))
  for u in [f['preparer'],f['reviewer']]:hr.receive(u,f['case'].pk,s.pk,'missing-receipt-'+str(u.pk),f['e']['hr_disclosure_decision'].pk,rev(f['case']))
  m=domain.match(f['preparer'],f['case'].pk,r.pk,s.pk,'missing-match',rev(f['case']));link=domain.hr_correction(f['preparer'],f['case'].pk,m.pk,'ask-HR',f['e']['hr_correction_request'].pk,rev(f['case']));self.assertEqual(link.record.kind,'correction');self.assertEqual(link.record.snapshot_id,s.pk);self.assertFalse(link.record.payload['source_write']);self.assertEqual(domain.hr_correction(f['preparer'],f['case'].pk,m.pk,'ask-HR',f['e']['hr_correction_request'].pk,rev(f['case'])).pk,link.pk)
  for sql in ['UPDATE finance_payrollhrfollowup SET id=id WHERE id=%s','DELETE FROM finance_payrollhrfollowup WHERE id=%s']:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cursor:cursor.execute(sql,[link.pk])
 def test_small_group_hold_blocks_all_publication_and_eligible_total(self):
  f=self.f;v=deepcopy(f['config']['report']);v['minimum_employees']=3;policy(f,REPORT,v);r=combined(f);approve(f,r);m=domain.match(f['preparer'],f['case'].pk,r.pk,f['hr'].pk,'m',rev(f['case']));approve(f,m);a=domain.aggregate(f['preparer'],f['case'].pk,m.pk,'a',rev(f['case']));self.assertIn('small_group_disclosure_hold',a.metadata['codes'])
  with self.assertRaises(ValidationError):approve(f,a)
  with self.assertRaises(ValidationError):domain.publish(f['preparer'],f['case'].pk,a.pk,'p',rev(f['case']))
  self.assertEqual(PayrollPublication.objects.count(),0)
 def test_F18_E01_source_v2_invalidates_old_report_without_overwrite(self):
  f=self.f;c,m,a,p=pipeline(f);capture(f,1,'B-v2',source_version='B-v2',control_total='200',rows=[{'row_ref':'B1','employee_id':'E002','component':'BASIC','amount':'200'}])
  with self.assertRaises(ValidationError):domain.read_publication(f['manager'],p.pk)
  self.assertEqual(PayrollPublication.objects.get(pk=p.pk).payload['eligible_total'],'250.00')
 def test_raw_rows_and_salary_values_are_private_to_named_readers(self):
  f=self.f;c,m,a,p=pipeline(f)
  with self.assertRaises(PermissionDenied):domain.private_input(f['manager'],f['case'].pk,f['inputs'][0].pk)
  with self.assertRaises(PermissionDenied):domain.private_run(f['manager'],f['case'].pk,m.pk)
  self.assertFalse(Evidence.objects.filter(body__contains='E001').exists());self.assertNotIn('E001',json.dumps(list(Audit.objects.values_list('data',flat=True))))
 def test_policy_and_retention_revocation_hold_current_read_and_report(self):
  f=self.f;c,m,a,p=pipeline(f)
  with patch('apps.finance.payroll.timezone.now',return_value=a.retain_until+timedelta(seconds=1)):
   with self.assertRaises(ValidationError):domain.private_run(f['preparer'],f['case'].pk,a.pk)
  transition(f['owner'],f['policies'][REPORT].pk,'revoked')
  with self.assertRaises(ValidationError):domain.read_publication(f['manager'],p.pk)
 def test_recipient_grant_revocation_and_HR_approval_revocation_hold_use(self):
  f=self.f;c,m,a,p=pipeline(f);Grant.objects.filter(case=f['case'],user=f['preparer'],action='hrfinance.snapshot.read').update(active=False)
  with self.assertRaises(PermissionDenied):domain.read_publication(f['manager'],p.pk)
 def test_source_and_working_idempotency_rejects_changed_intent(self):
  f=self.f;raw=body(f,1);i=domain.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','same',raw,rev(f['case']));self.assertEqual(domain.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','same',raw,rev(f['case'])).pk,i.pk)
  with self.assertRaises(ValidationError):domain.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','same',raw+' ',rev(f['case']))
 def test_metadata_UI_and_agent_never_load_private_payloads(self):
  f=self.f;pipeline(f)
  def forbidden(_):raise AssertionError('Metadata path loaded private data')
  with patch.object(PayrollInput,'payload',new=property(forbidden)),patch.object(PayrollRun,'result',new=property(forbidden)),patch.object(PayrollPublication,'payload',new=property(forbidden)):
   a=investigate(f['preparer'],f['case'].pk,rev(f['case']));self.assertFalse(a.result['private_payloads_read']);self.assertNotIn('E001',json.dumps(a.result))
   self.client.force_login(f['manager']);response=self.client.get(reverse('payroll',args=[f['case'].pk]));self.assertEqual(response.status_code,200);self.assertNotContains(response,'E001');self.assertNotContains(response,'250.00')
 def test_no_store_endpoints_check_exact_case_and_reader(self):
  f=self.f;c,m,a,p=pipeline(f);self.client.force_login(f['manager']);report=self.client.get(reverse('payroll_data',args=[f['case'].pk,'report',p.pk]));self.assertEqual(report.status_code,200);self.assertEqual(report['Cache-Control'],'no-store');self.assertEqual(self.client.get(reverse('payroll_data',args=[f['case'].pk,'input',f['inputs'][0].pk])).status_code,403)
  u,c2=setup_case(username='other-case');self.assertEqual(self.client.get(reverse('payroll_data',args=[c2.pk,'report',p.pk])).status_code,404)
 def test_human_report_and_private_inspection_enforce_same_boundary(self):
  f=self.f;c,m,a,p=pipeline(f);self.client.force_login(f['manager'])
  response=self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'report',p.pk]));self.assertContains(response,'Reviewed BU staff-cost report');self.assertContains(response,'250.00');self.assertNotContains(response,'E001');self.assertEqual(response['Cache-Control'],'no-store')
  self.assertEqual(self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'run',m.pk])).status_code,403)
  self.client.force_login(f['preparer']);response=self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'run',m.pk]));self.assertContains(response,'E001');self.assertContains(response,'Source lineage');self.assertEqual(response['Cache-Control'],'no-store')
  capture(f,1,'new-source-human',source_version='B2')
  self.client.force_login(f['manager']);response=self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'report',p.pk]));self.assertEqual(response.status_code,409);self.assertNotContains(response,'250.00',status_code=409)
 def test_large_eight_place_coefficient_tieout_stays_exact(self):
  f=self.f;v=deepcopy(f['config']['access']);v['source_decimal_places']=8;policy(f,ACCESS,v)
  f['inputs']=[capture(f,0,'precise-A',control_total='12345678901234567890.12345678',rows=[{'row_ref':'A1','employee_id':'E001','component':'BASIC','amount':'12345678901234567890.12345678'}]),capture(f,1,'precise-B')]
  v=deepcopy(f['config']['report']);v['decimal_places']=8
  for row in v['components']:row['coefficient']='2'
  v['oracles'][0]['expected']='500.00000000';policy(f,REPORT,v)
  c,m,a,p=pipeline(f);self.assertEqual(a.result['eligible_total'],'24691357802469136080.24691356');self.assertEqual(a.result['coefficient_effect'],'12345678901234568040.12345678')
 def test_UI_capture_rejection_never_reflects_bad_source_values(self):
  f=self.f;self.client.force_login(f['owner']);v=json.loads(body(f,1));v['rows'][0]['medical']='PRIVATE-UI-SENTINEL';res=self.client.post(reverse('payroll',args=[f['case'].pk]),{'action':'capture','revision':rev(f['case']),'request_record':f['request'].pk,'provider':'PAY-B','operation_key':'bad-ui','body':json.dumps(v)},follow=True);self.assertNotContains(res,'PRIVATE-UI-SENTINEL');self.assertContains(res,'out_of_contract_fields')
 def test_validators_require_actual_authority_and_exact_numerical_oracles(self):
  f=self.f
  for key,name in [(MERGE,'merge'),(REPORT,'report')]:
   v=deepcopy(f['config'][name]);v['oracles'][0]['expected']='999'
   with self.assertRaises(ValidationError):policy(f,key,v)
  v=deepcopy(f['config']['authority']);v['assignments'][0]['user_id']=999999
  with self.assertRaises(ValidationError):policy(f,AUTH,v)
 def test_SQL_history_guards(self):
  f=self.f;c,m,a,p=pipeline(f);receipt=domain.receive_report(f['manager'],f['case'].pk,p.pk,rev(f['case']))
  for table,pk in [('payrollrequest',f['request'].pk),('payrollinput',f['inputs'][0].pk),('payrollrun',a.pk),('payrollreview',p.review_id),('payrollpublication',p.pk),('payrollreportreceipt',receipt.pk)]:
   for statement in [f'UPDATE finance_{table} SET id=id WHERE id=%s',f'DELETE FROM finance_{table} WHERE id=%s']:
    with self.assertRaises(DatabaseError),transaction.atomic():
     with connection.cursor() as cursor:cursor.execute(statement,[pk])
