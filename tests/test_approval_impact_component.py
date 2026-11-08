import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(n):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(n+'*.py')).read_text())
 return ast.literal_eval(next(x.value for x in t.body if isinstance(x,ast.Assign) and x.targets[0].id=='SQL'))
class ApprovalImpactComponentTests(unittest.TestCase):
 def test_additive_exact_guard(self):
  self.assertEqual(sql('0025'),sql('0024').replace('BETWEEN 1 AND 20','BETWEEN 1 AND 21').replace("'finance.payment_assessments',","'finance.payment_assessments','pmo.approval_routing_jobs',"))
 def test_no_effect_call_and_closed_direct_matching(self):
  s=(ROOT/'adapters/approval_routing_policy_impact.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertFalse(calls & {'reserve','deliver','deliver_local','run_once','claim','finish','operate','guard_reserve','export_gate'})
  self.assertIn('intent__policies__0',s);self.assertIn('intent__policies__1',s)
  self.assertIn("'factory_execution'",s);self.assertIn('native_intent_current',s)
 def test_capture_locks_before_row_hydration(self):
  t=ast.parse((ROOT/'apps/policy/impact.py').read_text())
  fn=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='observation')
  s=ast.unparse(fn)
  self.assertIn("'pmo.approval_routing_jobs'",s)
  self.assertLess(s.index('query = query.select_for_update'),s.index('rows = list'))
