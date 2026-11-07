import copy,json
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.finance import schedules as d,analysis
from apps.finance.models import FinanceAdjustment,ScheduleWork,ScheduleReview,ScheduleAdjustment
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.schedule_validators import INCOME,INVENTORY,AUTH,scale
from apps.policy.schedule_drafts import draft_schedule_policy
from apps.agents.schedules import investigate
from adapters.schedules import LocalScheduleReportAdapter,SuppliedScheduleAdapter
from apps.documents import validation as v
from .schedule_helpers import fixture,policy,evidence,parent_amount,row,detail,review,inventory,accepted_equity
from .helpers import rev,setup_case

class IncomeTests(TestCase):
 def setUp(self):self.f=fixture()
 def test_postgresql_and_f12_n02_children_do_not_double_parent(self):
  f=self.f;self.assertEqual(connection.vendor,'postgresql');parent_amount(f,'100');w=detail(f,[row(f,'a','60'),row(f,'b','40')]);self.assertEqual(w.result['status'],'ready');self.assertEqual(w.result['adjusted_total'],'100');self.assertEqual(w.result['child_total'],'100');review(f,w);self.assertEqual(LocalScheduleReportAdapter().read(f['reviewer'],w)['result']['adjusted_total'],'100');self.assertFalse(FinanceAdjustment.objects.exists())
 def test_f12_n01_additive_and_controlled_adjustment_bridge(self):
  f=self.f;parent_amount(f,'100');w=detail(f,[row(f,'supplement','20','additive',lines=[{'account':'sales','amount':'20'}])]);self.assertEqual(w.result['adjusted_total'],'120')
  with self.assertRaises(ValidationError):d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']))
  review(f,w);link=d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']));self.assertEqual(d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case'])).pk,link.pk)
  with self.assertRaises(ValidationError):analysis.map_source(f['actor'],f['case'].pk,f['source'].pk,[link.adjustment_id],rev(f['case']))
  analysis.review(f['reviewer'],f['case'].pk,'adjustment',link.adjustment_id,'Finance','approve',f['e']['finance_review'].pk,'Separate exact reporting adjustment approval',rev(f['case']))
  mapped=analysis.map_source(f['actor'],f['case'].pk,f['source'].pk,[link.adjustment_id],rev(f['case']));self.assertEqual(sum(Decimal(x['amount']) for x in mapped.result['rows'] if x['account']=='sales'),120);self.assertFalse(mapped.result['ledger_posted'])
 def test_f12_e01_source_overlap_requires_human_resolution(self):
  f=self.f;r=row(f,'duplicate','20','additive',['sales']);w=detail(f,[r]);self.assertIn('source_overlap_requires_resolution:duplicate',w.result['findings'])
  with self.assertRaises(ValidationError):review(f,w)
  r['duplicate_resolution_evidence_id']=evidence(f,'income_detail','Explicit synthetic separately justified supplement despite same account').pk;w=detail(f,[r]);review(f,w);self.assertEqual(w.result['status'],'ready')
 def test_already_represented_and_unassessed_additions_hold(self):
  f=self.f
  for state in ['not_assessed','already_represented']:
   r=row(f,'duplicate','20','additive');r['duplicate_state']=state;w=detail(f,[r]);self.assertEqual(w.result['status'],'held')
 def test_f12_n03_single_explicit_conversion(self):
  f=self.f;parent_amount(f,'2');rule=f['values']['income_rule'];rule.update(target_unit='detail_units',factor='1000',oracles=[{'input':'2','expected':'2000'},{'input':None,'expected':None}]);policy(f,INCOME,rule)
  w=detail(f,[row(f,'a','1200'),row(f,'b','800')]);self.assertEqual(w.result['converted_parent'],'2000');self.assertEqual(w.result['adjusted_total'],'2000');review(f,w)
 def test_converted_adjustment_only_export_is_held(self):
  f=self.f;rule=f['values']['income_rule'];rule.update(target_unit='detail_units',factor='1000',oracles=[{'input':'2','expected':'2000'},{'input':None,'expected':None}]);policy(f,INCOME,rule)
  w=detail(f,[row(f,'add','20','additive',lines=[{'account':'sales','amount':'20'}])]);self.assertEqual(w.result['status'],'ready');review(f,w)
  with self.assertRaises(ValidationError):d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']))
 def test_reclassification_conserves_and_does_not_add(self):
  f=self.f;rows=[row(f,'out','-20','reclassification',lines=[{'account':'sales','amount':'-20'}]),row(f,'in','20','reclassification',lines=[{'account':'direct_cost','amount':'20'}])];w=detail(f,rows);self.assertEqual(w.result['adjusted_total'],'-1000');review(f,w);self.assertEqual(d.export_adjustment(f['actor'],f['case'].pk,w.pk,'reclassification',f['e']['finance_adjustment'].pk,rev(f['case'])).adjustment.kind,'reclassification')
  rows[1]['amount']='21';rows[1]['adjustment_lines'][0]['amount']='21';w=detail(f,rows);self.assertIn('reclassification_not_zero',w.result['findings'])
 def test_unknowns_and_child_residual_cannot_be_approved(self):
  f=self.f
  for values in [('a',None),('b','-999')]:
   w=detail(f,[row(f,*values)]);self.assertEqual(w.result['status'],'held')
   with self.assertRaises(ValidationError):review(f,w)
 def test_exact_validation_scope_duplicates_nonfinite_and_precision(self):
  f=self.f
  for amount in ['NaN','1e100','0.000000001',1.0]:
   with self.assertRaises(ValidationError):detail(f,[row(f,'bad',amount)])
  with self.assertRaises(ValidationError):detail(f,[row(f,'same','-500'),row(f,'same','-500')])
  r=row(f,'bad','-1000');r['unit']='unconfigured_unit'
  with self.assertRaises(ValidationError):detail(f,[r])
 def test_policy_missing_holds_only_dependent_result(self):
  f=self.f;p=policy(f,INCOME,f['values']['income_rule']);transition(f['actor'],p.pk,'revoked');w=detail(f);self.assertEqual(w.result['findings'],['income_rule_unconfigured']);self.assertTrue(inventory(f).pk)
 def test_review_independence_revocation_and_access_rechecked(self):
  f=self.f;w=detail(f)
  with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,w.pk,'approve',f['e']['finance_review'].pk,'Cannot self approve',rev(f['case']))
  review(f,w);review(f,w,'revoke')
  with self.assertRaises(ValidationError):LocalScheduleReportAdapter().read(f['reviewer'],w)
  review(f,w);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.review').update(active=False)
  with self.assertRaises(PermissionDenied):LocalScheduleReportAdapter().read(f['reviewer'],w)
 def test_supersession_policy_changes_and_source_reviews_invalidate(self):
  f=self.f;w=detail(f);review(f,w);new=detail(f,[row(f,'changed','-1000')]);self.assertNotEqual(new.pk,w.pk)
  with self.assertRaises(ValidationError):d.current(w)
  review(f,new);policy(f,INCOME,f['values']['income_rule'])
  with self.assertRaises(ValidationError):d.current(new)
  fresh=detail(f,[row(f,'changed','-1000')]);analysis.review(f['actor'],f['case'].pk,'source',f['source'].pk,'Finance','return',f['e']['finance_review'].pk,'Source review returned',rev(f['case']))
  with self.assertRaises(ValidationError):d.current(fresh)
 def test_duplicate_exports_across_references_and_corrected_lineage(self):
  f=self.f;r=row(f,'supplement','20','additive',lines=[{'account':'sales','amount':'20'}]);w=detail(f,[r]);review(f,w);link=d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']))
  other=detail(f,[r],reference='other');review(f,other)
  with self.assertRaises(ValidationError):d.export_adjustment(f['actor'],f['case'].pk,other.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']))
  r['amount']='25';r['adjustment_lines'][0]['amount']='25';new=detail(f,[r]);review(f,new);second=d.export_adjustment(f['actor'],f['case'].pk,new.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']));self.assertEqual(second.adjustment.reference,link.adjustment.reference);self.assertEqual(second.adjustment.number,2)
 def test_ui_csrf_scope_policy_form_report_and_agent(self):
  f=self.f;w=detail(f);review(f,w);self.client.force_login(f['reviewer']);url=f'/cases/{f["case"].pk}/finance/schedules/'
  response=self.client.get(url);self.assertContains(response,'Income detail and schedule validation');self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Review exact income');self.assertEqual(self.client.get(url+str(w.pk)+'/report/').status_code,200)
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.report').update(active=False);self.assertEqual(self.client.get(url+str(w.pk)+'/report/').status_code,403)
  response=self.client.post(url,{'action':'investigate','revision':rev(f['case'])});self.assertEqual(response.status_code,302)
  a=investigate(f['actor'],f['case'].pk,rev(f['case']));self.assertFalse(a.result['financial_values_read']);self.assertTrue(a.result['findings'][0]['owner_questions']);self.assertNotIn('adjusted_total',json.dumps(a.result))
 def test_post_extra_fields_stale_revision_and_cross_case(self):
  f=self.f;w=detail(f);self.client.force_login(f['actor']);url=f'/cases/{f["case"].pk}/finance/schedules/';n=ScheduleWork.objects.count();self.client.post(url,{'action':'investigate','revision':rev(f['case']),'role':'Finance'});self.assertEqual(ScheduleWork.objects.count(),n)
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,'income','stale',f['parent'].pk,f['values']['detail'],f['e']['income_detail'].pk,0)
  a,c=setup_case(username='outsider')
  with self.assertRaises(ValidationError):d.review(a,c.pk,w.pk,'approve',f['e']['finance_review'].pk,'Wrong case',rev(c))
 def test_policy_semantic_oracles_and_unknown_fields(self):
  f=self.f
  for changes in [{'factor':'0'},{'factor':'1000'},{'child_tolerance':'-1'},{'oracles':[{'input':None,'expected':'0'},{'input':'2','expected':'2'}]},{'approver':'Finance'}]:
   value=copy.deepcopy(f['values']['income_rule']);value.update(changes)
   with self.assertRaises(ValidationError):policy(f,INCOME,value)
 def test_relationship_and_overlap_policy_slots_hold_only_selected_treatment(self):
  f=self.f;rule=copy.deepcopy(f['values']['income_rule']);rule.update(allowed_relationships=['disaggregation'],source_overlap='hold');policy(f,INCOME,rule)
  self.assertEqual(detail(f).result['status'],'ready')
  r=row(f,'add','20','additive',['sales']);r['duplicate_resolution_evidence_id']=f['e']['income_detail'].pk;w=detail(f,[r]);self.assertIn('relationship_not_configured:add',w.result['findings']);self.assertIn('source_overlap_requires_resolution:add',w.result['findings'])
 def test_read_report_adapter_checks_its_own_permission_and_changed_export_intent(self):
  f=self.f;w=detail(f,[row(f,'add','20','additive',lines=[{'account':'sales','amount':'20'}])]);review(f,w);d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']))
  with self.assertRaises(ValidationError):d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',evidence(f,'finance_adjustment','Changed export intent').pk,rev(f['case']))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.report').update(active=False)
  with self.assertRaises(PermissionDenied):LocalScheduleReportAdapter().read(f['reviewer'],w)
 def test_post_policy_draft_and_actual_csrf_enforcement(self):
  from django.test import Client
  f=self.f;url=f'/cases/{f["case"].pk}/finance/schedules/';self.client.force_login(f['actor'])
  response=self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':INCOME,'content':json.dumps(f['values']['income_rule']),'evidence':f['e']['policy_decision'].pk,'effective_from':timezone.now().isoformat()});self.assertEqual(response.status_code,302)
  from apps.policy.models import Configuration
  self.assertEqual(Configuration.objects.filter(case=f['case'],component=INCOME).count(),2)
  client=Client(enforce_csrf_checks=True);client.force_login(f['actor']);self.assertEqual(client.post(url,{'action':'investigate','revision':rev(f['case'])}).status_code,403)
 def test_sql_guards_and_unique_immutability(self):
  f=self.f;w=detail(f,[row(f,'add','20','additive',lines=[{'account':'sales','amount':'20'}])]);r=review(f,w);link=d.export_adjustment(f['actor'],f['case'].pk,w.pk,'additive',f['e']['finance_adjustment'].pk,rev(f['case']))
  for table,pk in [('schedulework',w.pk),('schedulereview',r.pk),('scheduleadjustment',link.pk)]:
   for statement in [f'DELETE FROM finance_{table} WHERE id=%s',f'UPDATE finance_{table} SET id=id WHERE id=%s']:
    with self.assertRaises(DatabaseError),transaction.atomic():
     with connection.cursor() as cur:cur.execute(statement,[pk])

class ScheduleInventoryTests(TestCase):
 def setUp(self):self.f=fixture()
 def test_f13_e01_named_schedules_excluded_without_invented_rules(self):
  f=self.f;w=inventory(f);self.assertEqual(w.result['status'],'ready');self.assertFalse(w.result['complete_inventory']);self.assertTrue(all(not x['included'] for x in w.result['schedules']));self.assertIn('monthly_performance_decision_pending',w.result['findings']);review(f,w)
 def test_f13_n01_exact_definition_acceptance_and_remaining_exclusion(self):
  f=self.f;body=accepted_equity(f);w=inventory(f,body);self.assertTrue(w.result['schedules'][0]['included']);self.assertEqual(w.result['schedules'][0]['acceptance_level'],'definition');self.assertFalse(w.result['schedules'][1]['included']);self.assertFalse(w.result['native_workbook_verified']);review(f,w)
  report=LocalScheduleReportAdapter().read(f['reviewer'],w);self.assertEqual(report['review_id'],w.reviews.get().pk);self.assertFalse(report['native_workbook_verified'])
 def test_revoked_af13_review_invalidates_exact_inventory(self):
  f=self.f;body=accepted_equity(f);w=inventory(f,body);review(f,w);v.review(f['reviewer'],f['case'].pk,f['package'].pk,'acceptance','revoke','revoke-equity',f['e']['policy_decision'].pk,'Owner revoked acceptance',rev(f['case']))
  with self.assertRaises(ValidationError):d.current(w)
  new=inventory(f,body);self.assertFalse(new.result['schedules'][0]['included'])
 def test_missing_required_dependency_exclusion_and_cycles(self):
  f=self.f;body=accepted_equity(f);body['schedules'][0]['dependencies']=['intercompany'];w=inventory(f,body);self.assertFalse(w.result['schedules'][0]['included']);self.assertIn('upstream_excluded:intercompany',w.result['schedules'][0]['gaps'])
  body['schedules'][1]['dependencies']=['equity']
  with self.assertRaises(ValidationError):inventory(f,body)
  body['schedules']=body['schedules'][:1];body['schedules'][0]['dependencies']=['missing'];w=inventory(f,body);self.assertEqual(w.result['missing_required'],['intercompany'])
 def test_acceptance_must_bind_all_schedule_sources_and_actual_owner(self):
  f=self.f;body=accepted_equity(f);body['schedules'][0]['owner_id']=f['reviewer'].pk;body['schedules'][0]['formula_evidence_ids']=[evidence(f,'procedure_source','Unreviewed changed formula').pk];w=inventory(f,body);gaps=w.result['schedules'][0]['gaps'];self.assertIn('acceptance_does_not_bind_schedule_sources',gaps);self.assertIn('meaning_review_not_actual_schedule_owner',gaps)
 def test_explicit_monthly_decision_and_bounded_complete_inventory(self):
  f=self.f;body=accepted_equity(f);body['schedules']=body['schedules'][:1];body['coverage']='declared_complete';rule=copy.deepcopy(f['values']['inventory_rule']);rule.update(required_keys=['equity'],monthly_performance='existing_output',decision_evidence_id=f['e']['policy_decision'].pk);policy(f,INVENTORY,rule);w=inventory(f,body);self.assertTrue(w.result['complete_inventory']);self.assertFalse(w.result['native_workbook_verified']);self.assertEqual(w.result['monthly_performance'],'existing_output')
 def test_missing_policy_does_not_block_inventory_capture(self):
  f=self.f;p=policy(f,INVENTORY,f['values']['inventory_rule']);transition(f['actor'],p.pk,'revoked');w=inventory(f);self.assertEqual(w.result['status'],'held')
  with self.assertRaises(ValidationError):review(f,w)
 def test_strict_adapter_duplicate_fields_nonfinite_and_extra_authority(self):
  f=self.f
  for body in ['{"coverage":"partial","coverage":"declared_complete"}','{"x":NaN}']:
   e=evidence(f,'schedule_inventory',body)
   with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,'inventory','bad',None,None,e.pk,rev(f['case']))
  body=copy.deepcopy(f['values']['inventory']);body['approved_by']='Finance'
  with self.assertRaises(ValidationError):inventory(f,body)
 def test_changed_discovery_source_requires_revised_package(self):
  f=self.f;body=accepted_equity(f);w=inventory(f,body);source=f['discovery_source'];v.capture_source(f['actor'],f['case'].pk,source.reference,source.evidence_id,dict(source.metadata,source_version='synthetic-2'),rev(f['case']))
  with self.assertRaises(ValidationError):d.current(w)
 def test_another_schedule_cannot_reuse_equity_acceptance(self):
  f=self.f;body=accepted_equity(f);body['schedules'][0]['key']='different-schedule'
  with self.assertRaises(ValidationError):inventory(f,body)


class CostOfSalesExactCatalogueTests(TestCase):
 def test_cost_of_sales_explicit_conversion__F15_N02(self):
  """Supplied cells/units, not XLSX execution or a PSL mapping oracle.

  TST is the schema-compatible spelling of catalogue TEST. The mapping
  storage unit major_currency is explicitly an alias for TEST note-units in
  this fixture; it does not prove general typed note-unit ingestion.
  """
  from datetime import timedelta
  from apps.core.services import add_evidence
  from apps.finance.services import capture_import,validate_import
  from .finance_analysis_helpers import policy as finance_policy
  f=fixture();a,c=f['actor'],f['case']
  supplied={'fixture_scope':'synthetic_test','workbook':'PSL MGT.ACCOUNT AS AT SEP 2026.xlsx',
   'workbook_version':'synthetic-F15-N02-v1','sheet':'Notes 1-4','cell':'G18',
   'value':'3','source_unit':'TEST note-units','stored_unit_alias':'major_currency',
   'target_sheet':'BU M-o-M','target_cell':'J5','target_unit':'TEST detailed-units',
   'classification':'cost_of_sales','factor':'1000','native_workbook_verified':False}
  workbook=add_evidence(a,c.pk,'finance_source',json.dumps(supplied,sort_keys=True),'synthetic:F15-N02:external-workbook-v1')
  finance_policy(a,c,'D06.unit_sign_currency_period',dict(f['base']['conventions'],currency='TST'),f['e']['policy_decision'])
  maps=[dict(f['base']['mapping'][1],key='G18-cost-of-sales',account='G18',report_line='cost_of_sales',treatment='company',bu=None,pool=None)]
  cfg=finance_policy(a,c,'D06.account_bu_maps',maps,f['e']['policy_decision'])
  analysis.review(a,c.pk,'mapping',cfg.pk,'Finance','approve',f['e']['finance_review'].pk,'Synthetic G18 cost classification, never revenue',rev(c))
  raw=add_evidence(a,c.pk,'financial_input','account,amount,currency,period\nG18,3,TST,2026-10\n','synthetic:F15-N02:external-workbook-v1:Notes-1-4:G18')
  batch=capture_import(a,c.pk,raw.pk,rev(c));validate_import(a,c.pk,batch.pk,rev(c))
  source=analysis.capture_source(a,c.pk,batch.pk,'synthetic-company','accrual',timezone.now()-timedelta(minutes=1),'complete','3',workbook.pk,rev(c))
  analysis.review(a,c.pk,'source',source.pk,'Finance','approve',f['e']['finance_review'].pk,'Synthetic supplied workbook/version and note unit alias',rev(c))
  parent=analysis.map_source(a,c.pk,source.pk,[],rev(c));f['parent']=parent
  rule=dict(f['values']['income_rule'],currency='TST',report_line='cost_of_sales',target_unit='TEST_detailed_units',factor='1000',oracles=[{'input':'3','expected':'3000'},{'input':None,'expected':None}])
  policy(f,INCOME,rule)
  cell={'key':'J5','relationship':'disaggregation','amount':'3000','unit':'TEST_detailed_units','source_accounts':['G18'],'evidence_id':workbook.pk,'duplicate_state':'already_represented','duplicate_resolution_evidence_id':None,'adjustment_lines':[]}
  body=dict(f['values']['detail'],currency='TST',report_line='cost_of_sales',target_unit='TEST_detailed_units',rows=[cell])
  detail_source=evidence(f,'income_detail',json.dumps(supplied,sort_keys=True))
  w=d.prepare(a,c.pk,'income','F15-N02-J5',parent.pk,body,detail_source.pk,rev(c));review(f,w)
  self.assertEqual(connection.vendor,'postgresql')
  self.assertEqual(parent.result['status'],'complete')
  self.assertEqual([(r['account'],r['amount'],r['report_line'],r['metric']) for r in parent.result['rows']],[('G18','3','cost_of_sales','direct_cost')])
  self.assertNotIn('revenue',{r['report_line'] for r in parent.result['rows']})
  self.assertEqual((w.result['status'],w.result['parent_amount'],w.result['factor'],w.result['converted_parent'],w.result['adjusted_total']),('ready','3','1000','3000','3000'))
  self.assertEqual((w.result['report_line'],w.result['target_unit']),('cost_of_sales','TEST_detailed_units'))
  self.assertEqual((w.result['rows'][0]['key'],w.result['rows'][0]['amount']),('J5','3000'))
  self.assertEqual((w.parent_id,w.evidence_id,w.result['rows'][0]['evidence_id']),(parent.pk,detail_source.pk,workbook.pk))
  self.assertEqual((parent.source_id,parent.result['rows'][0]['source_evidence']),(source.pk,raw.pk))
  self.assertEqual(json.loads(w.evidence.body),supplied)
  self.assertEqual(json.loads(parent.source.evidence.body),supplied)
  self.assertFalse(w.result['ledger_posted']);self.assertFalse(w.result['source_written'])
