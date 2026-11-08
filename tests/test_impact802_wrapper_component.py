from pathlib import Path
import unittest,json,runpy
ROOT=Path(__file__).resolve().parents[1]
class FactoryPlanningImpactWrapperTests(unittest.TestCase):
 def test_pending_inputs_fail_closed(self):
  v=json.loads((ROOT/'docs/design/impact802-selection.json').read_text())
  self.assertEqual(v['accepted_predecessor'],'9a660e73eff3dc778859d74d3cb4c8c317ed91ed')
  self.assertEqual(v['review_source'],'d462578a693780160a1062fa28bcbc58831ce5b0')
  self.assertEqual(v['review_status'],'BOUNDED_BASELINE_EXEMPTION_IMPACT16_PASS')
  self.assertTrue(all(x['path'] and len(x['sha256'])==64 for x in v['runtime_inputs'].values()))
  with self.assertRaisesRegex(RuntimeError,'predecessor pin pending'):runpy.run_path(str(ROOT/'scripts/impact802_inputs.py'))
 def test_exact_upgrade_and_bounded_lifecycle(self):
  from scripts.impact802_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
  self.assertEqual(TARGET,('policy','0031_factory_planning_policy_impact'))
  self.assertEqual(PREVIOUS,('policy','0030_baseline_exemption_policy_impact'));self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
  v=json.loads((ROOT/'docs/design/impact802-selection.json').read_text());self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(15,16,8))
  s=(ROOT/'scripts/impact802_run.sh').read_text();self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
  self.assertIn('seq 1 8',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
  self.assertIn('step test-restart-equality equal test-final test-restart',s)
 def test_prior_exemption_review_and_exact_audit_preserved(self):
  s=(ROOT/'scripts/impact802_upgrade_lifecycle.py').read_text()
  self.assertLess(s.index("['pmo.baseline_signature_exemptions']"),s.index('upgrade(connection,root)'))
  self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
  self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
  self.assertNotIn('active_recovery(',s);self.assertNotIn('finalize_recovery(',s)
