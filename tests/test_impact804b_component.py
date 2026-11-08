import ast,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ContinuationTests(unittest.TestCase):
    def test_no_migration_action(self):
        for name in ['impact804b_harness.py','impact804b_compatibility.py']:
            t=ast.parse((ROOT/'scripts'/name).read_text())
            calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
            self.assertFalse(calls & {'migrate','upgrade','upgrade_test'})
    def test_prewrite_checks_and_unchanged_limits(self):
        s=(ROOT/'scripts/impact804b_run.sh').read_text()
        for stage in ('baseline-compare','test-baseline-compare','primary-declared-compare','schema-primary','schema-test'):
            self.assertLess(s.index('step '+stage),s.index('for batch in'))
        self.assertIn('seq 1 7',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('equal_index(',s)
    def test_exact_fresh_selection_and_partial_pin(self):
        v=json.loads((ROOT/'docs/design/impact804b-selection.json').read_text())
        self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(12,12,7))
        self.assertEqual(v['batches'][0]['ids'],[v['compatibility_id']])
        self.assertEqual(v['runtime_inputs']['partial804a_review_manifest']['sha256'],'08f8d49a77e25f96c6f8ba95fdfdbe83b88cce3917541b7809b506a8be210717')
        self.assertEqual(v['runtime_inputs']['primary']['sha256'],'acd4671a5e24104d203c76206d1e2d75f6ed2cc5fd1a400edb753c6f244fbb18')
        self.assertEqual(v['runtime_inputs']['test']['sha256'],'87f0176b9a53bd997b634098426ff936e5aec17f2cc8336ef69d3387115e8f00')
    def test_compatibility_old_review_preserved_and_setup_before_capture(self):
        s=(ROOT/'scripts/impact804b_compatibility.py').read_text()
        self.assertIn('verify_schema(connection)',s)
        self.assertLess(s.index("f=fixture(username='impact804-new')"),s.index('baseline=effects()'))
        self.assertIn('unchanged_except_capture_audit(',s)
        self.assertIn('review_before)',s)
