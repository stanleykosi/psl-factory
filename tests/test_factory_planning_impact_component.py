import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(prefix):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(prefix+'*.py')).read_text());return ast.literal_eval(next(n.value for n in t.body if isinstance(n,ast.Assign) and n.targets[0].id=='SQL'))
class FactoryPlanningImpactComponentTests(unittest.TestCase):
 def test_exact_additive_sql(self):
  self.assertEqual(sql('0031'),sql('0030').replace('BETWEEN 1 AND 26','BETWEEN 1 AND 27').replace("'pmo.baseline_signature_exemptions',","'pmo.baseline_signature_exemptions','workflows.factory_planning_profiles',"))
 def test_closed_projection_no_commands_or_private_hydration(self):
  s=(ROOT/'adapters/factory_planning_policy_impact.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertFalse(calls & {'profile','snapshot','execution_actor','claim','run_once','adopt_profile','packet','transport','bind'})
  self.assertIn("definition=DEFINITION",s);self.assertIn("policy_id=config.pk",s);self.assertIn(".only('id','case_id','definition','status','revision','policy_id')",s)
  projection=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='project')
  self.assertFalse({'request','finding','source_head','business_key','budget_limit'} & {n.attr for n in ast.walk(projection) if isinstance(n,ast.Attribute)})
  self.assertIn('configuration(actor,case.pk,row.policy_id)',s)
 def test_lock_precedes_hydration_and_real_competing_row_lock(self):
  s=(ROOT/'apps/policy/impact.py').read_text();fn=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='observation');body=ast.unparse(fn)
  self.assertIn('workflows.factory_planning_profiles',body);self.assertLess(body.index('query.select_for_update'),body.index('rows = list(query'))
  tests=(ROOT/'tests/test_factory_planning_policy_impact.py').read_text()
  self.assertIn('FactoryWork.objects.select_for_update().get(pk=self.job.pk)',tests);self.assertIn('thread.join(12)',tests);self.assertIn('connections.close_all()',tests)
 def test_fresh_synthetic_native_setup_without_worker(self):
  s=(ROOT/'tests/factory_planning_impact802_helpers.py').read_text();calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call)}
  self.assertTrue({'start','adopt_profile','planning_fixture'}<=calls)
  self.assertFalse(calls & {'claim','run_once','run_until_wait','bind','observe','sign_baseline','adopt_signed','reaffirm_for'})
  self.assertIn('configured=False',s);self.assertIn("value['provider']!='synthetic_factory_v1'",s)
  self.assertLess(s.index("factory_planning.start("),s.index('factory.adopt_profile('))

 def test_followup_proofs_keep_actual_budget_contract(self):
  s=(ROOT/'tests/test_factory_planning_policy_impact.py').read_text()
  self.assertIn("engagement.capture(f['a'],f['c'].pk,'B'",s)
  self.assertIn("cursor=first['next_cursor']",s)
  self.assertIn('for call in (impact.inspect,investigate)',s)
  d=(ROOT/'docs/design/factory-planning-impact802.md').read_text()
  self.assertIn('NO separate serialized-byte cap',d)
  self.assertNotIn('MAX_BYTES',(ROOT/'adapters/factory_planning_policy_impact.py').read_text())
