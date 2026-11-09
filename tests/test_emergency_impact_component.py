import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(n):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(n+'*.py')).read_text())
 return ast.literal_eval(next(x.value for x in t.body if isinstance(x,ast.Assign) and x.targets[0].id=='SQL'))
class EmergencyImpactComponentTests(unittest.TestCase):
 def test_exact_additive_guard(self):
  self.assertEqual(sql('0029'),sql('0028').replace('BETWEEN 1 AND 24','BETWEEN 1 AND 25').replace("'pmo.signed_adoption_recovery_requests',","'pmo.signed_adoption_recovery_requests','pmo.emergency_recovery_requests',"))
 def test_closed_readonly_emergency_only(self):
  s=(ROOT/'adapters/emergency_recovery_policy_impact.py').read_text();t=ast.parse(s)
  self.assertIn('adoption__isnull=True,outcome__isnull=False',s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertIn('current_request',calls);self.assertFalse(calls & {'active_recovery','request_recovery','finalize_recovery','decide_recovery'})
 def test_presign_roster_and_real_chronology_no_repair(self):
  s=(ROOT/'tests/emergency_impact800_helpers.py').read_text();t=ast.parse(s)
  self.assertLess(s.index("activate(a,c,'D05.role_principal_assignments'"),s.index('sign_baseline('))
  self.assertLess(s.index('native.authorize_emergency('),s.index('actual=actual_before or timezone.now()'))
  self.assertLess(s.index('actual=actual_before or timezone.now()'),s.index('native.capture_outcome('))
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertFalse(calls & {'reaffirm_for','reaffirm_baseline','finalize_recovery','decide_recovery','update','freeze_time'})
  self.assertIn('candidate_requests(candidate,kind)',s);self.assertIn('adapter=SyntheticGateAdapter()',s)
 def test_fixture_asserts_original_snapshot_and_excluded_effects(self):
  s=(ROOT/'tests/emergency_impact800_helpers.py').read_text()
  for model in ('RFPCase','BaselineAdoption','EmergencyRetrospectiveRecord','EmergencyFollowup','CommercialSignatureReaffirmation','AuthorityRecoveryDecision','AuthorityRecoveryRecord'):
   self.assertIn(model+'.objects.filter(',s)
  self.assertIn('c.synthetic is not True',s)
  self.assertIn('auth.snapshot!=native.preauthorization_inputs(c,profile,check_authority=False,historical=True)',s)

 def test_optional_matrix_fixture_obeys_native_v1_action_schema(self):
  tree=ast.parse((ROOT/'tests/test_emergency_recovery_policy_impact.py').read_text())
  fixture=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='test_configured_optional_authority_positive_and_typed_negatives')
  call=next(n for n in ast.walk(fixture) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='artifact')
  self.assertEqual(ast.literal_eval(call.args[2]),'D05.decision_action_matrix')
  self.assertEqual(ast.literal_eval(call.args[3]),'schema:psl/decision-actions/v1')
  content=ast.literal_eval(call.args[4])
  native=ast.parse((ROOT/'apps/policy/document_validators.py').read_text())
  branch=next(n for n in ast.walk(native) if isinstance(n,ast.If) and ast.unparse(n.test)=="component == 'D05.decision_action_matrix'")
  props=next(n.value for n in branch.body if isinstance(n,ast.Assign) and n.targets[0].id=='props')
  def field(node,key):
   return next(value for k,value in zip(node.keys,node.values) if ast.literal_eval(k)==key)
  schema=field(field(field(field(field(props,'rules'),'items'),'properties'),'actions'),'items')
  allowed=ast.literal_eval(field(schema,'enum'))
  for rule in content['rules']:
   self.assertTrue(rule['actions']);self.assertEqual(len(rule['actions']),len(set(rule['actions'])))
   self.assertTrue(set(rule['actions'])<=set(allowed))
  self.assertNotIn('approve',allowed)
