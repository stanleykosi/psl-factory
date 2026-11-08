from pathlib import Path
import ast,json,unittest
ROOT=Path(__file__).resolve().parents[1]
class Impact798bWrapperTests(unittest.TestCase):
 def test_no_migration_and_exact17(self):
  v=json.loads((ROOT/'docs/design/impact798b-selection.json').read_text())
  self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(16,17,8))
  for name in ('harness','compatibility'):
   s=(ROOT/f'scripts/impact798b_{name}.py').read_text();calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call)}
   self.assertFalse(calls & {'migrate','upgrade','call_command'})
   self.assertIn('migration_plan',s);self.assertIn('body(TARGET[1])',s)
 def test_fresh_equalities_before_compatibility_and_resource_bounds(self):
  s=(ROOT/'scripts/impact798b_run.sh').read_text()
  for stage in ('baseline-compare','test-baseline-compare','primary-declared-compare'):self.assertLess(s.index('step '+stage),s.index('step compatibility'))
  self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
  self.assertIn('step test-restart-equality equal test-final test-restart',s)
 def test_both_failed_histories_preserved(self):
  v=json.loads((ROOT/'docs/design/impact798b-selection.json').read_text())
  self.assertEqual(v['failed_prior_status'],'PARTIAL_798A_FAILED_NOT_ACCEPTED')
  self.assertIn('prior797a_review_manifest',v['runtime_inputs'])
  for name in ('impact798-selection.json',):self.assertIn('docs/design/'+name,v['historical_source_pins'])
  self.assertIn('PARTIAL_798A_FAILED_NOT_ACCEPTED',(ROOT/'scripts/impact798b_inputs.py').read_text())
