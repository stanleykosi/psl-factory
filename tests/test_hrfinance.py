import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import resolve,transition
from apps.policy.hrfinance_validators import AUTHORITY,DISCLOSURE
from apps.finance import hrfinance as domain
from apps.finance.models import HRFinanceNeed,HRDisclosure,HRReadSnapshot,HRHandoffRecord,Invoice,CashReceipt
from apps.agents.hrfinance import investigate
from adapters.hrfinance import LocalHRFinanceInbox
from .helpers import setup_case,rev
from .hrfinance_helpers import fixture,policy,capture,receive,body

class HRFinanceTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_requires_postgresql(self):self.assertEqual(connection.vendor,'postgresql')
 def test_F35_N01_minimal_exact_disclosure_snapshot_receipt(self):
  f=self.f;s=capture(f);r=receive(f,s);data=domain.read_snapshot(f['finance'],s)
  self.assertEqual(set(data['rows'][0]),{'employee_id','bu','effective_from','effective_until'});self.assertTrue(r.payload['receipt_only']);self.assertFalse(r.payload['hr_write'])
  self.assertEqual([x.pk for x in LocalHRFinanceInbox().read(f['finance'],f['case'])],[s.pk]);self.assertEqual(Invoice.objects.count(),0);self.assertEqual(CashReceipt.objects.count(),0)
 def test_F35_E01_medical_or_disciplinary_values_never_retained(self):
  f=self.f
  for field in ['medical','disciplinary']:
   v=json.loads(body(f));v['rows'][0][field]='SENSITIVE-REJECTED-SENTINEL';s=domain.capture(f['hr'],f['case'].pk,f['contract'].pk,'reject-'+field,json.dumps(v),rev(f['case']))
   self.assertEqual(s.status,'rejected');self.assertEqual(s.payload,{});self.assertEqual(s.manifest['findings'],['out_of_contract_fields'])
  self.assertFalse(Evidence.objects.filter(body__contains='SENSITIVE-REJECTED-SENTINEL').exists());self.assertNotIn('SENSITIVE-REJECTED-SENTINEL',json.dumps(list(Audit.objects.values_list('data',flat=True))));self.assertNotIn('SENSITIVE-REJECTED-SENTINEL',json.dumps(list(HRReadSnapshot.objects.values_list('payload',flat=True))))
 def test_shared_case_reader_and_admin_cannot_read_private_rows(self):
  f=self.f;s=capture(f);u=get_user_model().objects.create_user(username='case-reader',is_superuser=True)
  for action in ['case.read','hrfinance.read']:Grant.objects.create(case=f['case'],user=u,action=action)
  with self.assertRaises(PermissionDenied):domain.read_snapshot(u,s)
  self.client.force_login(u);res=self.client.get(reverse('hrfinance',args=[f['case'].pk]));self.assertEqual(res.status_code,200);self.assertNotContains(res,'private-staff-001');self.assertNotContains(res,'HR supply an authorised read-only export')
  self.assertEqual(self.client.get(reverse('hrfinance_snapshot',args=[f['case'].pk,s.pk])).status_code,403)
 def test_read_grant_alone_is_not_recipient_nomination(self):
  f=self.f;s=capture(f)
  with self.assertRaises(PermissionDenied):domain.read_snapshot(f['hr'],s)
 def test_missing_rules_hold_disclosure_not_finance_need(self):
  a,c=setup_case(username='unconfigured');e=add_evidence(a,c.pk,'hr_finance_need','Justified minimum field request','synthetic:test');p=deepcopy(self.f['config']['need']);p['recipient_ids']=[a.pk]
  n=domain.need(a,c.pk,'collect',p,e.pk,rev(c));self.assertTrue(n.pk);self.assertEqual(resolve(DISCLOSURE,c).status,'MISSING')
  source=add_evidence(a,c.pk,'hr_contract_source','Missing disclosure is not source authority','synthetic:test')
  with self.assertRaises(ValidationError):domain.contract(a,c.pk,n.pk,'missing',source.pk,rev(c))
 def test_explicit_HR_approval_required_before_capture(self):
  f=self.f;domain.decide(f['hr'],f['case'].pk,f['contract'].pk,'return','return',f['e']['hr_disclosure_decision'].pk,rev(f['case']))
  with self.assertRaises(ValidationError):capture(f)
 def test_finance_cannot_approve_disclosure_or_capture_with_role_claim(self):
  f=self.f
  for k in ['hrfinance.authorize','hrfinance.capture']:Grant.objects.create(user=f['finance'],case=f['case'],action=k)
  with self.assertRaises(PermissionDenied):domain.decide(f['finance'],f['case'].pk,f['contract'].pk,'approve','forged',f['e']['hr_disclosure_decision'].pk,rev(f['case']))
  with self.assertRaises(PermissionDenied):domain.capture(f['finance'],f['case'].pk,f['contract'].pk,'forged',body(f),rev(f['case']))
 def test_policy_validators_reject_wrong_roles_extra_fields_and_pay_without_currency(self):
  f=self.f
  for key,change in [(AUTHORITY,'role'),(AUTHORITY,'human'),(DISCLOSURE,'medical'),(DISCLOSURE,'pay')]:
   v=deepcopy(f['config']['authority' if key==AUTHORITY else 'disclosure'])
   if change=='role':v['assignments'][0]['role']='Finance'
   elif change=='human':v['human_only']=False
   elif change=='medical':v['allowed_fields'].append('medical')
   else:v['allowed_fields'].append('monthly_pay')
   with self.assertRaises(ValidationError):policy(f['hr'],f['case'],key,v,f['e']['owner'])
 def test_missing_field_justification_rejected(self):
  f=self.f;p=deepcopy(f['config']['need']);del p['justification']['bu']
  with self.assertRaises(ValidationError):domain.need(f['finance'],f['case'].pk,'bad',p,f['e']['hr_finance_need'].pk,rev(f['case']))
 def test_revoked_HR_approval_immediately_holds_read_and_receipt(self):
  f=self.f;s=capture(f);domain.decide(f['hr'],f['case'].pk,f['contract'].pk,'revoke','revoke',f['e']['hr_disclosure_decision'].pk,rev(f['case']))
  with self.assertRaises(ValidationError):domain.read_snapshot(f['finance'],s)
  with self.assertRaises(ValidationError):receive(f,s)
 def test_revoked_policy_and_HR_grant_hold_current_use(self):
  f=self.f;s=capture(f);transition(f['hr'],f['disclosure_policy'].pk,'revoked')
  with self.assertRaises(ValidationError):domain.read_snapshot(f['finance'],s)
 def test_revoked_actual_HR_authorizer_grant_holds_current_use(self):
  f=self.f;s=capture(f);Grant.objects.filter(case=f['case'],user=f['hr'],action='hrfinance.authorize').update(active=False)
  with self.assertRaises(PermissionDenied):domain.read_snapshot(f['finance'],s)
 def test_revoked_Finance_recipient_grant_holds_rows(self):
  f=self.f;s=capture(f);Grant.objects.filter(case=f['case'],user=f['finance'],action='hrfinance.snapshot.read').update(active=False)
  with self.assertRaises(PermissionDenied):domain.read_snapshot(f['finance'],s)
 def test_retention_expiry_restricts_rows_preserves_metadata(self):
  f=self.f;s=capture(f)
  with patch('apps.finance.hrfinance.timezone.now',return_value=s.retain_until+timedelta(seconds=1)):
   with self.assertRaises(ValidationError):domain.read_snapshot(f['finance'],s)
  self.assertEqual(HRReadSnapshot.objects.get(pk=s.pk).status,'accepted');self.assertEqual(s.contract.records.count(),1)
 def test_freshness_and_future_extract_rejected_without_rows(self):
  f=self.f
  for k,at in [('old',timezone.now()-timedelta(days=2)),('future',timezone.now()+timedelta(days=1))]:
   s=capture(f,k,extracted_at=at.isoformat());self.assertEqual(s.status,'rejected');self.assertEqual(s.payload,{})
 def test_duplicate_employees_and_ineffective_dates_rejected(self):
  f=self.f
  for k in ['duplicate','date']:
   v=json.loads(body(f))
   if k=='duplicate':v['rows'].append(v['rows'][0])
   else:v['rows'][0]['effective_from']='2999-01-01'
   s=domain.capture(f['hr'],f['case'].pk,f['contract'].pk,k,json.dumps(v),rev(f['case']));self.assertEqual(s.status,'rejected')
 def test_schema_view_period_and_unknown_source_version_exceptions(self):
  f=self.f
  for k,v in [('view_ref','other-view'),('period','2026-09'),('source_version',None),('rows',[{'employee_id':True}])]:
   s=capture(f,'bad-'+k,**{k:v});self.assertEqual(s.status,'rejected');self.assertEqual(s.payload,{})
 def test_capture_retry_once_and_changed_intent_rejected(self):
  f=self.f;raw=body(f);s=domain.capture(f['hr'],f['case'].pk,f['contract'].pk,'same',raw,rev(f['case']));r=domain.capture(f['hr'],f['case'].pk,f['contract'].pk,'same',raw,rev(f['case']));self.assertEqual(s.pk,r.pk)
  with self.assertRaises(ValidationError):domain.capture(f['hr'],f['case'].pk,f['contract'].pk,'same',raw+' ',rev(f['case']))
 def test_sql_guards_for_all_four_private_records(self):
  f=self.f;s=capture(f)
  for table,pk in [('finance_hrfinanceneed',f['need'].pk),('finance_hrdisclosure',f['contract'].pk),('finance_hrreadsnapshot',s.pk),('finance_hrhandoffrecord',f['approval'].pk)]:
   for statement in [f'UPDATE {table} SET id=id WHERE id=%s',f'DELETE FROM {table} WHERE id=%s']:
    with self.assertRaises(DatabaseError),transaction.atomic():
     with connection.cursor() as cursor:cursor.execute(statement,[pk])
 def test_need_and_policy_source_successors_require_new_disclosure(self):
  f=self.f;s=capture(f);domain.need(f['finance'],f['case'].pk,f['need'].reference,f['need'].payload,f['e']['hr_finance_need'].pk,rev(f['case']))
  with self.assertRaises(ValidationError):domain.read_snapshot(f['finance'],s)
 def test_source_view_evidence_revised_holds_old_disclosure(self):
  f=self.f;s=capture(f);add_evidence(f['hr'],f['case'].pk,'hr_contract_source','Revised supported view','synthetic:test')
  with self.assertRaises(ValidationError):domain.read_snapshot(f['finance'],s)
 def test_HR_correction_successor_new_receipt_without_source_write(self):
  f=self.f;s=capture(f);receive(f,s);q=domain.correction(f['finance'],f['case'].pk,s.pk,'correction',f['e']['hr_correction_request'].pk,rev(f['case']));v=deepcopy(f['config']['export']['rows']);v[0]['bu']='beta';new=capture(f,'corrected',source_version='synthetic-v2',rows=v)
  r=domain.respond(f['hr'],f['case'].pk,q.pk,new.pk,'response',f['e']['hr_correction_response'].pk,rev(f['case']));self.assertFalse(r.payload['source_write']);self.assertTrue(r.payload['new_finance_receipt_required'])
  with self.assertRaises(ValidationError):domain.read_snapshot(f['finance'],s)
  self.assertEqual(receive(f,new,'new-receipt').snapshot_id,new.pk)
 def test_cross_case_snapshot_and_source_contract_denied(self):
  f=self.f;s=capture(f);a,c=setup_case(username='other')
  with self.assertRaises(ValidationError):domain.receive(a,c.pk,s.pk,'foreign',f['e']['hr_disclosure_decision'].pk,rev(c))
  self.client.force_login(f['finance']);self.assertEqual(self.client.get(reverse('hrfinance_snapshot',args=[c.pk,s.pk])).status_code,404)
 def test_private_snapshot_endpoint_and_board_never_inline_rows(self):
  f=self.f;s=capture(f);self.client.force_login(f['finance']);res=self.client.get(reverse('hrfinance_snapshot',args=[f['case'].pk,s.pk]));self.assertEqual(res.status_code,200);self.assertEqual(res['Cache-Control'],'no-store');self.assertEqual(res.json()['data']['rows'][0]['employee_id'],'private-staff-001')
  board=self.client.get(reverse('hrfinance',args=[f['case'].pk]));self.assertNotContains(board,'private-staff-001');self.assertContains(board,'Read authorised period snapshot')
 def test_agent_uses_metadata_only_and_cannot_expand_disclosure(self):
  f=self.f;s=capture(f);r=investigate(f['hr'],f['case'].pk,rev(f['case']));self.assertFalse(r.result['private_rows_read']);self.assertFalse(r.result['disclosure_approved']);self.assertNotIn('private-staff-001',json.dumps(r.result));self.assertNotIn('monthly_pay',json.dumps(r.result));self.assertEqual(r.result['findings'][0]['contracts'][0]['snapshots'][0]['snapshot_id'],s.pk)
 def test_UI_rejects_extra_authority_claims_and_stale_revision(self):
  f=self.f;self.client.force_login(f['hr']);url=reverse('hrfinance',args=[f['case'].pk])
  self.assertContains(self.client.post(url,{'action':'investigate','revision':rev(f['case']),'role':'HR'},follow=True),'Unexpected command fields')
  self.assertContains(self.client.post(url,{'action':'investigate','revision':0},follow=True),'Stale revision')
 def test_UI_rejected_medical_export_does_not_reflect_values(self):
  f=self.f;self.client.force_login(f['hr']);v=json.loads(body(f));v['rows'][0]['medical']='SENSITIVE-RESPONSE-SENTINEL'
  response=self.client.post(reverse('hrfinance',args=[f['case'].pk]),{'action':'capture','revision':rev(f['case']),'contract':f['contract'].pk,'operation_key':'bad-ui','body':json.dumps(v)},follow=True)
  self.assertNotContains(response,'SENSITIVE-RESPONSE-SENTINEL');self.assertContains(response,'out_of_contract_fields');self.assertEqual(HRReadSnapshot.objects.get(operation_key='bad-ui').payload,{})

 def test_configured_effective_end_semantics_are_explicit(self):
  f=self.f;v=deepcopy(f['config']['export']['rows']);v[0]['effective_until']=f['config']['need']['as_of'];s=capture(f,'inclusive',rows=v);self.assertEqual(s.status,'accepted')
  rules=deepcopy(f['config']['disclosure']);rules['effective_until_semantics']='exclusive';policy(f['hr'],f['case'],DISCLOSURE,rules,f['e']['owner'])
  d=domain.contract(f['finance'],f['case'].pk,f['need'].pk,'exclusive',f['e']['hr_contract_source'].pk,rev(f['case']));domain.decide(f['hr'],f['case'].pk,d.pk,'approve','exclusive-approval',f['e']['hr_disclosure_decision'].pk,rev(f['case']));f['contract']=d
  s=capture(f,'exclusive',rows=v);self.assertEqual(s.status,'rejected');self.assertEqual(s.manifest['findings'],['employee_not_effective_at_snapshot'])
 def test_huge_retention_is_invalid_without_inventing_business_default(self):
  f=self.f;v=deepcopy(f['config']['disclosure']);v['retention_seconds']=10**100
  with self.assertRaises(ValidationError):policy(f['hr'],f['case'],DISCLOSURE,v,f['e']['owner'])
 def test_policy_draft_UI_then_shared_validation_and_activation(self):
  from apps.policy.models import Configuration
  f=self.f;self.client.force_login(f['hr']);res=self.client.post(reverse('hrfinance',args=[f['case'].pk]),{'action':'policy','revision':rev(f['case']),'component':DISCLOSURE,'content':json.dumps(f['config']['disclosure']),'evidence':f['e']['owner'].pk,'effective_from':(timezone.now()-timedelta(seconds=1)).isoformat()})
  self.assertEqual(res.status_code,302);r=Configuration.objects.filter(component=DISCLOSURE).latest('pk');transition(f['hr'],r.pk,'validated');transition(f['hr'],r.pk,'active');self.assertEqual(resolve(DISCLOSURE,f['case']).configuration.pk,r.pk)
 def test_schema_exception_message_never_contains_private_bad_value(self):
  f=self.f;v=json.loads(body(f));v['rows'][0]['bu']={'medical':'PRIVATE-BAD-VALUE'};s=domain.capture(f['hr'],f['case'].pk,f['contract'].pk,'bad-value',json.dumps(v),rev(f['case']))
  self.assertEqual(s.payload,{});self.assertEqual(s.manifest['findings'],['bu_identity_schema']);self.assertNotIn('PRIVATE-BAD-VALUE',str(s.manifest))
 def test_exact_snapshot_retention_expiry_endpoint_holds_without_rows(self):
  f=self.f;s=capture(f);self.client.force_login(f['finance'])
  with patch('apps.finance.hrfinance.timezone.now',return_value=s.retain_until+timedelta(seconds=1)):
   res=self.client.get(reverse('hrfinance_snapshot',args=[f['case'].pk,s.pk]));self.assertEqual(res.status_code,409);self.assertNotContains(res,'private-staff',status_code=409)

 def test_payroll_fields_need_separate_explicit_purpose_and_HR_approval(self):
  f=self.f;rules=deepcopy(f['config']['disclosure']);rules['allowed_fields']+=['monthly_pay','currency'];rules['purposes']+=['payroll_support'];policy(f['hr'],f['case'],DISCLOSURE,rules,f['e']['owner'])
  p=deepcopy(f['config']['need']);p['fields']+=['monthly_pay','currency'];p['purpose']='payroll_support';p['justification'].update(monthly_pay='Synthetic Finance-authorised reported-pay check only',currency='Preserve reported units without conversion')
  n=domain.need(f['finance'],f['case'].pk,'payroll-purpose',p,f['e']['hr_finance_need'].pk,rev(f['case']));d=domain.contract(f['finance'],f['case'].pk,n.pk,'payroll-contract',f['e']['hr_contract_source'].pk,rev(f['case']));domain.decide(f['hr'],f['case'].pk,d.pk,'approve','payroll-approval',f['e']['hr_disclosure_decision'].pk,rev(f['case']));f['contract']=d
  rows=deepcopy(f['config']['export']['rows'])
  for row in rows:row.update(monthly_pay=None,currency='NGN')
  rows[0]['monthly_pay']='123.45';s=capture(f,'payroll-copy',rows=rows);receive(f,s);data=domain.read_snapshot(f['finance'],s);self.assertEqual(data['rows'][0]['monthly_pay'],'123.45');self.assertIsNone(data['rows'][1]['monthly_pay'])
  with self.assertRaises(ValidationError):domain.draft_basis(f['finance'],f['case'].pk,s.pk,f['e']['owner'].pk,rev(f['case']))
  self.client.force_login(f['finance']);self.assertNotContains(self.client.get(reverse('hrfinance',args=[f['case'].pk])),'123.45')
 def test_disclosure_for_attribution_does_not_grant_project_costing(self):
  f=self.f;p=deepcopy(f['config']['need']);p['purpose']='project_costing';n=domain.need(f['finance'],f['case'].pk,'costing-request',p,f['e']['hr_finance_need'].pk,rev(f['case']))
  with self.assertRaises(ValidationError):domain.contract(f['finance'],f['case'].pk,n.pk,'not-authorised',f['e']['hr_contract_source'].pk,rev(f['case']))

 def test_metadata_agent_board_and_inbox_never_access_private_payload_attribute(self):
  f=self.f;capture(f)
  def forbidden(_):raise AssertionError('Metadata path must not load the private snapshot payload')
  with patch.object(HRReadSnapshot,'payload',new=property(forbidden)):
   run=investigate(f['hr'],f['case'].pk,rev(f['case']));self.assertFalse(run.result['private_rows_read'])
   self.client.force_login(f['finance']);self.assertEqual(self.client.get(reverse('hrfinance',args=[f['case'].pk])).status_code,200)
   self.assertEqual(len(LocalHRFinanceInbox().read(f['finance'],f['case'])),1)
