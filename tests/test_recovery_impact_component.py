import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(n):
 t=ast.parse(next((ROOT/'apps/policy/migrations').glob(n+'*.py')).read_text())
 return ast.literal_eval(next(x.value for x in t.body if isinstance(x,ast.Assign) and x.targets[0].id=='SQL'))
class RecoveryImpactComponentTests(unittest.TestCase):
 def test_exact_additive_guard(self):
  self.assertEqual(sql('0027'),sql('0026').replace('BETWEEN 1 AND 22','BETWEEN 1 AND 23').replace("'pmo.delivery_prerequisites',","'pmo.delivery_prerequisites','pmo.signed_adoption_recovery_requests',"))
 def test_signed_target_typed_paths_and_no_active_authority_commands(self):
  s=(ROOT/'adapters/recovery_policy_impact.py').read_text();t=ast.parse(s)
  self.assertIn('adoption__isnull=False,outcome__isnull=True',s);self.assertIn("+'__1'",s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertIn('current_request',calls)
  self.assertFalse(calls & {'active_recovery','request_recovery','decide_recovery','finalize_recovery','read'})
 def test_initial_fixture_no_reaffirm_emergency_change_or_recovery_finalization(self):
  s=(ROOT/'tests/recovery_impact798_helpers.py').read_text();t=ast.parse(s)
  self.assertIn('existing=False',s)
  calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
  self.assertTrue({'packet_for','adopt_signed','request_recovery'}<=calls)
  self.assertFalse(calls & {'reaffirm_for','reaffirm_baseline','authorize_change','capture_outcome','active_recovery','decide_recovery','finalize_recovery'})
  self.assertLess(s.index('packet_for(a,c,e,v)'),s.index('adoption=commercial.adopt_signed'))
 def test_exact_audit_and_signature_history_assertions_exist(self):
  fixture=(ROOT/'tests/recovery_impact798_helpers.py').read_text()
  self.assertIn('CommercialSignatureReaffirmation.objects.filter(packet__case=c).exists()',fixture)
  source=(ROOT/'tests/test_recovery_policy_impact.py').read_text()
  self.assertIn("self.assertEqual(len(added),1)",source)
  self.assertIn('self.assertEqual(expected,after)',source)
  self.assertIn('self.assertEqual(original,history())',source)
  self.assertIn("'policy.impact.captured'",source);self.assertIn("'policy.impact.reviewed'",source)

 def test_optional_matrix_fixture_obeys_native_v1_action_schema(self):
  tree=ast.parse((ROOT/'tests/test_recovery_policy_impact.py').read_text())
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
