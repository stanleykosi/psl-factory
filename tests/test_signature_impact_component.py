import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(n):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(n+'*.py')).read_text())
 return ast.literal_eval(next(x.value for x in t.body if isinstance(x,ast.Assign) and x.targets[0].id=='SQL'))
class SignatureImpactComponentTests(unittest.TestCase):
 def test_additive_guard_preserves_all_prior_variants(self):
  self.assertEqual(sql('0028'),sql('0027').replace('BETWEEN 1 AND 23','BETWEEN 1 AND 24').replace("'pmo.signed_adoption_recovery_requests',","'pmo.signed_adoption_recovery_requests','pmo.signature_packets',"))
 def test_selected_packet_policy_only_no_currentness_or_effect_command(self):
  s=(ROOT/'adapters/signature_policy_impact.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertIn('validate_packet_policy',calls)
  self.assertFalse(calls & {'current_packet','assert_current_signed_baseline','capture_packet','record_use','sign_baseline','reaffirm_baseline','adopt_signed','convert'})
  self.assertIn('validate_packet_policy(row)',s);self.assertNotIn('native_current',s)
  self.assertIn('policy_id=config.pk',s);self.assertIn('authority_id=config.pk',s)
 def test_fixture_minimal_fresh_and_consumed_no_conversion_or_repair(self):
  s=(ROOT/'tests/test_signature_policy_impact.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertTrue({'prepared','packet_for','signed'}<=calls)
  self.assertFalse(calls & {'reaffirm_for','reaffirm_baseline','adopt_signed','convert','finalize_recovery'})
  self.assertIn('configure=False',s)
  self.assertIn('unchanged_except_capture_audit(before,self.facts()',s)
  self.assertIn("detached.signatures={'PRIVATE':'not typed'}",s)
 def test_native_packet_policy_does_not_select_latest(self):
  t=ast.parse((ROOT/'apps/pmo/signatures.py').read_text())
  fn=next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name=='validate_packet_policy')
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(fn) if isinstance(n,ast.Call)}
  self.assertFalse(calls & {'latest','current_packet','record_use','baseline_use'})
  self.assertIn('packet.actor',ast.unparse(fn))
