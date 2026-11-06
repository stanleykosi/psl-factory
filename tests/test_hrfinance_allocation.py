from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.finance import analysis,hrfinance as domain
from apps.finance.allocation import headcount_weights
from .finance_analysis_helpers import fixture as finance_fixture,METRICS
from .hrfinance_helpers import fixture,capture,receive
from .helpers import rev

class HRFinanceAllocationTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  a,c,e,cfg,configs,source,t,recipient=finance_fixture();cls.a=a;cls.c=c;cls.e=e;cls.configs=configs;cls.source=source
  cls.f=fixture(base=(a,c,e['policy_decision']))
  # New actual HR/Finance role assignments require new exact Finance reviews.
  analysis.review(a,c.pk,'source',source.pk,'Finance','approve',e['finance_review'].pk,'Current source under new role assignment',rev(c))
  for key,purpose in analysis.PURPOSE.items():analysis.review(a,c.pk,purpose,configs[key].pk,'Finance','approve',e['finance_review'].pk,'Current rule under new role assignment',rev(c))
 def configure(self):
  f=self.f;s=capture(f);receive(f,s);drafts=domain.draft_basis(self.a,self.c.pk,s.pk,self.e['policy_decision'].pk,rev(self.c))
  for d in drafts:transition(self.a,d.pk,'validated');transition(self.a,d.pk,'active')
  return s,{d.component:d for d in drafts}
 def test_real_HR_snapshot_to_existing_Finance_allocation_no_staff_master_copy(self):
  s,configs=self.configure();m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));run=analysis.allocate(self.a,self.c.pk,m.pk,METRICS,rev(self.c));staff=next(r for r in run.result['rows'] if r['account']=='staff_pool')
  self.assertEqual(staff['status'],'allocated');self.assertEqual(staff['allocations'],{'alpha':'60.00','beta':'30.00'});self.assertEqual(staff['basis']['hr_snapshot_id'],s.pk);self.assertEqual(run.snapshot['hr_basis_access']['status'],'available');analysis.ensure_current(run)
  import json
  self.assertNotIn('private-staff',json.dumps(run.result));self.assertFalse(self.c.evidence.filter(body__contains='private-staff').exists())
 def test_recipient_revocation_holds_only_headcount_pool_and_invalidates_old_run(self):
  s,_=self.configure();m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));old=analysis.allocate(self.a,self.c.pk,m.pk,METRICS,rev(self.c));Grant.objects.filter(case=self.c,user=self.a,action='hrfinance.snapshot.read').update(active=False)
  with self.assertRaises(ValidationError):analysis.ensure_current(old)
  run=analysis.allocate(self.a,self.c.pk,m.pk,METRICS,rev(self.c));by={r['account']:r for r in run.result['rows']};self.assertEqual(by['staff_pool']['status'],'held');self.assertEqual(by['staff_pool']['unallocated'],'90');self.assertEqual(by['shared_opex']['status'],'allocated')
 def test_Finance_receipt_required_before_input_binding(self):
  f=self.f;s=capture(f)
  with self.assertRaises(ValidationError):domain.draft_basis(self.a,self.c.pk,s.pk,self.e['policy_decision'].pk,rev(self.c))
 def test_partial_inventory_and_unknown_BU_are_not_zero(self):
  f=self.f;s=capture(f,completeness='partial');receive(f,s)
  with self.assertRaises(ValidationError):domain.draft_basis(self.a,self.c.pk,s.pk,self.e['policy_decision'].pk,rev(self.c))
 def test_corrected_successor_does_not_silently_restate_old_Finance_result(self):
  s,_=self.configure();m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));old=analysis.allocate(self.a,self.c.pk,m.pk,METRICS,rev(self.c));capture(self.f,'successor',source_version='v2')
  with self.assertRaises(ValidationError):analysis.ensure_current(old)

 def test_unknown_BU_holds_headcount_pool_without_erasing_source(self):
  f=self.f;rows=[dict(r) for r in f['config']['export']['rows']];rows[0]['bu']=None;s=capture(f,rows=rows);receive(f,s);drafts=domain.draft_basis(self.a,self.c.pk,s.pk,self.e['policy_decision'].pk,rev(self.c))
  for d in drafts:transition(self.a,d.pk,'validated');transition(self.a,d.pk,'active')
  m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));run=analysis.allocate(self.a,self.c.pk,m.pk,METRICS,rev(self.c));staff=next(r for r in run.result['rows'] if r['account']=='staff_pool');self.assertEqual(staff['status'],'held');self.assertEqual(staff['unallocated'],'90');self.assertIsNone(domain.read_snapshot(self.a,s)['rows'][0]['bu'])
 def test_HR_read_only_unit_inventory_cannot_invent_FTE(self):
  from .finance_analysis_helpers import policy as finance_policy
  from apps.policy.services import reference_values
  self.configure();v=reference_values(self.configs['D07.join_overlap_rule_id'])[0];v=dict(v,weight_semantics='explicit_fte');finance_policy(self.a,self.c,'D07.join_overlap_rule_id',v,self.e['policy_decision'])
  m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));run=analysis.allocate(self.a,self.c.pk,m.pk,METRICS,rev(self.c));staff=next(r for r in run.result['rows'] if r['account']=='staff_pool');self.assertEqual(staff['status'],'held');self.assertTrue(any('FTE is not inferred' in x for x in run.result['findings']))
