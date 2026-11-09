import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(n):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(n+'*.py')).read_text())
 return ast.literal_eval(next(x.value for x in t.body if isinstance(x,ast.Assign) and x.targets[0].id=='SQL'))
class ExemptionImpactComponentTests(unittest.TestCase):
 def test_additive_exact_guard(self):
  self.assertEqual(sql('0030'),sql('0029').replace('BETWEEN 1 AND 25','BETWEEN 1 AND 26').replace("'pmo.emergency_recovery_requests',","'pmo.emergency_recovery_requests','pmo.baseline_signature_exemptions',"))
 def test_selected_validation_not_policy_only_or_latest_assurance(self):
  s=(ROOT/'adapters/exemption_policy_impact.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertIn('validate_exemption',calls)
  self.assertFalse(calls & {'latest','owner_requirement','assert_current_baseline_assurance','record_exemption','sign_baseline','adopt_signed','reaffirm_baseline'})
  self.assertIn('validate_exemption(row)',s);self.assertIn('selected_exemption_valid_now',s)
  self.assertIn('policy_id=config.pk',s);self.assertIn('authority_id=config.pk',s)
  native=ast.parse((ROOT/'apps/pmo/signature_exemptions.py').read_text())
  fn=next(n for n in native.body if isinstance(n,ast.FunctionDef) and n.name=='validate_exemption')
  self.assertIn('signed__isnull=True',ast.unparse(fn));self.assertIn('row.actor',ast.unparse(fn))
  self.assertNotIn('latest(',ast.unparse(fn))
 def test_unsigned_fixture_no_signing_adoption_repair_or_publication(self):
  s=(ROOT/'tests/exemption_impact801_helpers.py').read_text();t=ast.parse(s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertTrue({'prepare_baseline','decide','record_exemption'}<=calls)
  self.assertFalse(calls & {'signed','sign_baseline','packet_for','capture_packet','adopt_signed','reaffirm_for','reaffirm_baseline','reserve_publication','run_once','convert'})
  self.assertLess(s.index("roles(a,c,"),s.index('prepare_baseline(a,c.'))
  fixture=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='fixture')
  evidence=next(n for n in ast.walk(fixture) if isinstance(n,ast.DictComp))
  self.assertEqual(set(ast.literal_eval(evidence.generators[0].iter)),{'requirements','engineering_estimate','security_estimate','plan','costing','sow','policy_decision'})
  self.assertIn('setup_case(username=username,synthetic=True)',s)
  self.assertIn("if not c.synthetic:raise AssertionError",s)
  self.assertIn("'signature_requirement':requirement",s)
  self.assertIn("'scope_evidence_id':(scope or f['scope']).pk",s)
 def test_both_fk_nonnull_and_no_effect_test_assertions(self):
  t=ast.parse((ROOT/'apps/pmo/signature_models.py').read_text());cls=next(c for c in t.body if isinstance(c,ast.ClassDef) and c.name=='BaselineSignatureExemption')
  fields={n.targets[0].id:n.value for n in cls.body if isinstance(n,ast.Assign)}
  for field in ('policy','authority'):
   self.assertFalse(any(k.arg=='null' and ast.literal_eval(k.value) for k in fields[field].keywords))
  s=(ROOT/'tests/test_exemption_policy_impact.py').read_text()
  self.assertIn('unchanged_except_capture_audit(before,self.facts()',s)
  self.assertIn("self.assertEqual(len(added),1)",s)
  self.assertIn('self.assertNotEqual(old.costing_id,current.costing_id)',s)
