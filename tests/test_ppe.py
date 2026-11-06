import copy,json
from datetime import timedelta
from django.test import TestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from django.db import connection,transaction,DatabaseError
from apps.finance import ppe
from apps.finance.models import ScheduleWork
from apps.policy.ppe_validators import SOURCE,CALC,AUTH
from apps.policy.services import transition
from apps.identity.models import Grant
from apps.agents.ppe import investigate
from adapters.ppe import LocalPPEReportAdapter
from .ppe_helpers import fixture,prepare,capture,review,policy,owner_package
from .schedule_helpers import evidence
from .helpers import rev
class PPETests(TestCase):
 def setUp(self):self.f=fixture()
 def test_f07_n01_explicit_synthetic_oracle_and_reviewed_finance_note(self):
  f=self.f;self.assertEqual(connection.vendor,'postgresql');w=prepare(f);self.assertEqual(w.result['status'],'ready');self.assertEqual(w.result['totals'],{'cost':'1000','charge':'100.00','accumulated':'500.00','book_value':'500.00'});review(f,w);r=LocalPPEReportAdapter().read(f['reviewer'],w);self.assertFalse(r['ledger_posted']);self.assertFalse(r['native_source_verified'])
 def test_f07_e01_unknown_life_and_classification_hold_only_dependent_rows(self):
  f=self.f;body=copy.deepcopy(f['ppe']['body']);a=copy.deepcopy(body['assets'][0]);a.update(asset_id='A2',life=None,capitalisation='undecided');body['assets'].append(a);r=capture(f,body);review(f,r,'register');w=prepare(f,r);self.assertEqual(w.result['rows'][0]['charge'],'100.00');self.assertIsNone(w.result['rows'][1]['charge']);self.assertIsNone(w.result['totals']['book_value'])
  with self.assertRaises(ValidationError):review(f,w)
 def test_f07_e02_preserves_march_label_until_independent_basis_decision(self):
  f=self.f;source=copy.deepcopy(f['ppe']['source']);source['ledger_comparison']='not_required';policy(f,SOURCE,source);body=copy.deepcopy(f['ppe']['body']);body.update(period_start='2026-09-01',period_end='2026-09-30',label_as_of='2026-03-31');r=capture(f,body,reference='asset-register-sep');review(f,r,'register');held=prepare(f,r,reference='ppe-sep',ledger=False);self.assertIn('date_basis_explanation_required',held.result['findings']);self.assertEqual(held.result['scope']['label_as_of'],'2026-03-31');review(f,r,'basis')
  with self.assertRaises(ValidationError):ppe.current(held)
  ready=prepare(f,r,reference='ppe-sep',ledger=False);self.assertEqual(ready.result['status'],'ready');review(f,ready);review(f,r,'basis','revoke')
  with self.assertRaises(ValidationError):LocalPPEReportAdapter().read(f['reviewer'],ready)
 def test_addition_disposal_and_reclassification_events_need_full_reconciliation(self):
  f=self.f;body=copy.deepcopy(f['ppe']['body']);body['events']=[{'event_id':'ADD1','asset_id':'A1','date':'2026-10-10','kind':'addition','cost_delta':'100','accumulated_delta':'0','evidence_id':f['e']['ppe_event'].pk}];body['closing_controls']={'cost':'1100','accumulated':'511.11','book_value':'588.89'}
  r=capture(f,body);review(f,r,'register');w=prepare(f,r,ledger=False);self.assertEqual(w.result['totals']['charge'],'111.11');self.assertIn('ledger_note_required',w.result['findings']);self.assertEqual(w.result['rows'][0]['event_refs'],['ADD1'])
  body['events'][0].update(kind='reclassification');r=capture(f,body);review(f,r,'register');w=prepare(f,r);self.assertIn('reclassification_population_not_zero',w.result['findings'])
 def test_source_capture_survives_missing_rules_and_authority(self):
  f=self.f
  for key,value in [(CALC,f['ppe']['calculation']),(SOURCE,f['ppe']['source'])]:p=policy(f,key,value);transition(f['actor'],p.pk,'revoked')
  r=capture(f);self.assertEqual(r.result['status'],'captured');review(f,r,'register');w=prepare(f,r,ledger=False);self.assertEqual(w.result['status'],'held');self.assertIn('calculation_rules_missing',w.result['findings'])
 def test_unsupported_method_has_explicit_engineering_hold(self):
  f=self.f;rules=copy.deepcopy(f['ppe']['calculation']);r=rules['rules'][0];r['method']='unimplemented_method'
  for o in r['oracles']:o.update(expected_charge=None,expected_finding='method_implementation_missing')
  policy(f,CALC,rules);w=prepare(f);self.assertIn('method_implementation_missing',w.result['rows'][0]['findings'])
 def test_policy_oracle_numeric_and_unknown_validation(self):
  f=self.f
  for value in ['NaN','-1','0.000000001']:
   rules=copy.deepcopy(f['ppe']['calculation']);rules['rules'][0]['capitalisation_threshold']=value
   with self.assertRaises(ValidationError):policy(f,CALC,rules)
  rules=copy.deepcopy(f['ppe']['calculation']);rules['rules'][0]['oracles'][0]['expected_charge']='999'
  with self.assertRaises(ValidationError):policy(f,CALC,rules)
 def test_register_schema_duplicates_unknown_authority_and_scope(self):
  f=self.f
  for change in ['duplicate','extra','date','event']:
   body=copy.deepcopy(f['ppe']['body'])
   if change=='duplicate':body['assets'].append(copy.deepcopy(body['assets'][0]))
   elif change=='extra':body['approved_by']='Finance'
   elif change=='date':body['period_end']='2026-02-31'
   else:body['events']=[{'event_id':'BAD','asset_id':'absent','date':'2026-10-10','kind':'disposal','cost_delta':'-1','accumulated_delta':'0','evidence_id':f['e']['ppe_event'].pk}]
   with self.assertRaises(ValidationError):capture(f,body)
 def test_source_correction_policy_review_and_actor_grant_invalidate_reports(self):
  f=self.f;w=prepare(f);review(f,w);body=copy.deepcopy(f['ppe']['body']);body['completeness']='partial';capture(f,body)
  with self.assertRaises(ValidationError):LocalPPEReportAdapter().read(f['reviewer'],w)
  r=capture(f);review(f,r,'register');w=prepare(f,r);review(f,w);policy(f,CALC,f['ppe']['calculation'])
  with self.assertRaises(ValidationError):ppe.current(w)
 def test_independent_human_authority_and_report_access_are_required(self):
  f=self.f;w=prepare(f)
  with self.assertRaises(PermissionDenied):ppe.review(f['actor'],f['case'].pk,w.pk,'schedule','approve',f['e']['finance_review'].pk,'No self approval',rev(f['case']))
  review(f,w);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ppe.review').update(active=False)
  with self.assertRaises((PermissionDenied,ValidationError)):LocalPPEReportAdapter().read(f['reviewer'],w)
 def test_source_staleness_unknown_controls_and_ledger_mismatch_hold(self):
  f=self.f;body=copy.deepcopy(f['ppe']['body']);body['extracted_at']=(timezone.now()-timedelta(days=2)).isoformat();body['closing_controls']['book_value']=None;r=capture(f,body);review(f,r,'register');w=prepare(f,r);self.assertIn('source_stale',w.result['findings']);self.assertIn('closing_control_unreconciled:book_value',w.result['findings'])
  body=copy.deepcopy(f['ppe']['body']);body['assets'][0]['opening_accumulated']='300';body['closing_controls']['accumulated']='400';body['closing_controls']['book_value']='600';r=capture(f,body);review(f,r,'register');self.assertIn('ledger_note_difference',prepare(f,r).result['findings'])
 def test_prior_opening_roll_forward_and_missing_prior_hold(self):
  f=self.f;source=copy.deepcopy(f['ppe']['source']);source.update(opening_mode='prior_required',external_opening_period='2026-09',ledger_comparison='not_required');policy(f,SOURCE,source)
  body=copy.deepcopy(f['ppe']['body']);body.update(period_start='2026-09-01',period_end='2026-09-30',label_as_of='2026-09-30');r=capture(f,body,'register-sep');review(f,r,'register');previous=prepare(f,r,'ppe-sep',ledger=False);review(f,previous)
  body=copy.deepcopy(f['ppe']['body']);body['assets'][0]['opening_accumulated']='500';body['closing_controls'].update(accumulated='600',book_value='400');r=capture(f,body);review(f,r,'register');self.assertIn('prior_approved_schedule_required',prepare(f,r,ledger=False).result['findings']);w=prepare(f,r,prior=previous,ledger=False);self.assertEqual(w.result['status'],'ready');review(f,w)
  body['assets'][0]['opening_accumulated']='501';r=capture(f,body);review(f,r,'register');self.assertIn('opening_does_not_match_prior',prepare(f,r,prior=previous,ledger=False).result['rows'][0]['findings'])
 def test_human_ui_csrf_json_reports_agent_and_legacy_schedule_isolation(self):
  f=self.f;w=prepare(f);review(f,w);self.client.force_login(f['reviewer']);url=f'/cases/{f["case"].pk}/finance/assets/';response=self.client.get(url);self.assertContains(response,'Assets, depreciation');self.assertEqual(response['Cache-Control'],'no-store');report=self.client.get(url+str(w.pk)+'/report/');self.assertContains(report,'Reviewed asset');self.assertContains(report,'500.00');self.assertEqual(self.client.get(url+str(w.pk)+'/report/?format=json').json()['result']['totals']['book_value'],'500.00')
  a=investigate(f['actor'],f['case'].pk,rev(f['case']));self.assertFalse(a.result['financial_values_read']);self.assertNotIn('500.00',json.dumps(a.result));self.assertContains(self.client.get(f'/cases/{f["case"].pk}/finance/schedules/'),'Income detail');self.assertEqual(self.client.get(f'/cases/{f["case"].pk}/finance/schedules/{w.pk}/report/').status_code,404)
  client=Client(enforce_csrf_checks=True);client.force_login(f['actor']);self.assertEqual(client.post(url,{'action':'investigate','revision':rev(f['case'])}).status_code,403)
 def test_adapter_duplicate_json_and_shared_sql_guards(self):
  f=self.f;e=evidence(f,'ppe_register','{"entity":"a","entity":"b"}')
  with self.assertRaises(ValidationError):ppe.capture(f['actor'],f['case'].pk,'bad',e.pk,rev(f['case']))
  w=prepare(f);r=review(f,w)
  for table,pk in [('schedulework',w.pk),('schedulereview',r.pk)]:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cur:cur.execute(f'UPDATE finance_{table} SET id=id WHERE id=%s',[pk])
 def test_af13_method_definition_acceptance_and_revocation_are_current(self):
  from apps.documents import validation as av
  f=self.f;p=owner_package(f);w=prepare(f);self.assertEqual(w.result['status'],'ready');review(f,w)
  av.review(f['reviewer'],f['case'].pk,p.pk,'acceptance','revoke','ppe-revoke',f['e']['policy_decision'].pk,'Revoked exact method definition',rev(f['case']))
  with self.assertRaises(ValidationError):LocalPPEReportAdapter().read(f['reviewer'],w)
  held=prepare(f);self.assertIn('af13_owner_definition_acceptance_required',held.result['findings'])
 def test_required_af13_is_localized_and_missing_package_never_auto_accepts(self):
  f=self.f;source=copy.deepcopy(f['ppe']['source']);source.update(validation_requirement='af13_required',validation_package_id=None);policy(f,SOURCE,source);w=prepare(f);self.assertEqual(w.result['rows'][0]['charge'],'100.00');self.assertIn('af13_owner_definition_acceptance_required',w.result['findings']);self.assertTrue(capture(f).pk)
 def test_below_threshold_and_full_disposal_do_not_invent_asset_treatment(self):
  f=self.f;body=copy.deepcopy(f['ppe']['body']);body['events']=[{'event_id':'small','asset_id':'A1','date':'2026-10-10','kind':'addition','cost_delta':'1','accumulated_delta':'0.00','evidence_id':f['e']['ppe_event'].pk}];r=capture(f,body);review(f,r,'register');self.assertIn('capitalisation_below_threshold',prepare(f,r).result['rows'][0]['findings'])
  body['events'][0].update(event_id='dispose',kind='disposal',cost_delta='-1000',accumulated_delta='-400');body['assets'][0]['residual']='0';body['closing_controls']={'cost':'0','accumulated':'0','book_value':'0'};r=capture(f,body);review(f,r,'register');w=prepare(f,r,ledger=False);self.assertEqual(w.result['rows'][0]['charge'],'0.00')
 def test_legacy_services_and_inactive_cached_principals_cannot_cross_scope(self):
  from apps.finance import schedules
  f=self.f;w=prepare(f)
  with self.assertRaises(ValidationError):schedules.exact(f['case'],w.pk)
  f['reviewer'].is_active=False;f['reviewer'].save(update_fields=['is_active']);f['reviewer'].is_active=True
  with self.assertRaises(PermissionDenied):LocalPPEReportAdapter().read(f['reviewer'],w)
 def test_invalid_disposal_is_an_unknown_row_and_other_assets_continue(self):
  f=self.f;body=copy.deepcopy(f['ppe']['body']);other=copy.deepcopy(body['assets'][0]);other['asset_id']='A2';body['assets'].append(other);body['events']=[{'event_id':'bad-disposal','asset_id':'A2','date':'2026-10-10','kind':'disposal','cost_delta':'-2000','accumulated_delta':'-400','evidence_id':f['e']['ppe_event'].pk}];r=capture(f,body);review(f,r,'register');w=prepare(f,r);self.assertEqual(w.result['rows'][0]['charge'],'100.00');self.assertIn('closing_asset_basis_invalid',w.result['rows'][1]['findings']);self.assertIsNone(w.result['rows'][1]['closing_cost']);self.assertIsNone(w.result['totals']['cost'])
 def test_explicit_residual_cap_and_hold_have_distinct_configured_results(self):
  f=self.f;body=copy.deepcopy(f['ppe']['body']);body['assets'][0]['opening_accumulated']='899';body['closing_controls'].update(accumulated='900',book_value='100');r=capture(f,body);review(f,r,'register');w=prepare(f,r);self.assertEqual(w.result['rows'][0]['charge'],'1.00');self.assertEqual(w.result['rows'][0]['book_value'],'100.00')
  rule=copy.deepcopy(f['ppe']['calculation']);rule['rules'][0]['remaining_value']='hold';policy(f,CALC,rule);w=prepare(f,r);self.assertIsNone(w.result['rows'][0]['charge']);self.assertIn('charge_exceeds_remaining_value',w.result['rows'][0]['findings'])
 def test_typed_capture_and_policy_posts_do_not_approve_or_accept_extra_authority(self):
  f=self.f;self.client.force_login(f['actor']);url=f'/cases/{f["case"].pk}/finance/assets/';e=evidence(f,'ppe_register',json.dumps(f['ppe']['body']));response=self.client.post(url,{'action':'capture','revision':rev(f['case']),'reference':'posted-source','evidence':e.pk});self.assertEqual(response.status_code,302);w=ScheduleWork.objects.get(reference='posted-source');self.assertFalse(w.reviews.exists())
  count=ScheduleWork.objects.count();self.client.post(url,{'action':'capture','revision':rev(f['case']),'reference':'forged','evidence':e.pk,'approved_by':'Finance'});self.assertEqual(ScheduleWork.objects.count(),count)
  self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':SOURCE,'content':json.dumps(f['ppe']['source']),'evidence':f['e']['policy_decision'].pk,'effective_from':timezone.now().isoformat()}).status_code,302)
  from apps.policy.models import Configuration
  self.assertEqual(Configuration.objects.filter(case=f['case'],component=SOURCE).count(),2)
