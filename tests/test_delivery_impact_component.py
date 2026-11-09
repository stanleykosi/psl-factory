import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(n):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(n+'*.py')).read_text())
 return ast.literal_eval(next(x.value for x in t.body if isinstance(x,ast.Assign) and x.targets[0].id=='SQL'))
class DeliveryImpactComponentTests(unittest.TestCase):
 def test_exact_additive_guard(self):
  self.assertEqual(sql('0026'),sql('0025').replace('BETWEEN 1 AND 21','BETWEEN 1 AND 22').replace("'pmo.approval_routing_jobs',","'pmo.approval_routing_jobs','pmo.delivery_prerequisites',"))
 def test_only_native_read_prerequisites_no_command(self):
  s=(ROOT/'adapters/delivery_policy_impact.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertTrue({'qualified_hypercare','current_archive','dossier_for'}<=calls)
  self.assertFalse(calls & {'evaluate_hypercare','archive_artifacts','finalize_closure','decide_closure','guard_evaluate_hypercare','accept_go_live','reaffirm_go_live','run_once'})
  self.assertIn('native_closure_prerequisite_current',s);self.assertNotIn('native_current',s)
 def test_fixture_uses_typed_new_attestation_not_conversion(self):
  s=(ROOT/'tests/go_live_helpers.py').read_text()
  self.assertIn('subject_pins',s);self.assertIn('synthetic-local-test',s)
  self.assertNotIn('convert',s)
 def test_closed_history_fixture_then_read_only_baseline(self):
  t=ast.parse((ROOT/'tests/test_delivery_policy_impact.py').read_text())
  cls=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=='DeliveryImpactClosedHistoryTests')
  fn=next(x for x in cls.body if isinstance(x,ast.FunctionDef))
  s=ast.unparse(fn)
  self.assertLess(s.index('native.finalize_closure('),s.index('before = facts()'))
  self.assertLess(s.index('before = facts()'),s.index('value = project(row)'))
  self.assertIn('self.assertEqual(before, facts())',s)
  self.assertNotIn('reaffirm',s);self.assertNotIn('convert',s)
  self.assertIn("'finance'",s)
  self.assertIn('self.assertEqual(historical,',s)
 def test_replacement_fixture_roles_precede_fresh_signature_no_reaffirmation(self):
  s=(ROOT/'tests/delivery_impact797_helpers.py').read_text();t=ast.parse(s)
  cls=next(x for x in t.body if isinstance(x,ast.ClassDef))
  setup=ast.unparse(next(x for x in cls.body if isinstance(x,ast.FunctionDef)))
  self.assertLess(setup.index('change_roles('),setup.index('sign_baseline('))
  self.assertLess(setup.index('change_roles('),setup.index('packet_for('))
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertFalse(calls & {'reaffirm_for','reaffirm_baseline','signed','prepared','convert'})
  self.assertTrue({'authorize_change','adopt_signed','packet_for'}<=calls)
