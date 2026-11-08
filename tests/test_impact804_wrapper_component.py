import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PlanningBindingWrapperTests(unittest.TestCase):
    def test_exact_predecessor_selection_and_lifecycle(self):
        v=json.loads((ROOT/'docs/design/impact804-selection.json').read_text())
        self.assertEqual(v['accepted_predecessor'],'8aaaecc7752543bc78cf3afdfce621b3c70cfebc')
        self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(11,12,6))
        from scripts.impact804_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0032_factory_planning_binding_impact'))
        self.assertEqual(PREVIOUS,('policy','0031_factory_planning_policy_impact'));self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
    def test_bind_setup_before_noeffect_baseline(self):
        s=(ROOT/'scripts/impact804_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['workflows.factory_planning_profiles']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index("f=fixture(username='impact804-new')"),s.index('baseline=effects()'))
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
        self.assertIn("'agents'",s)
    def test_guards_and_two_restart_equalities(self):
        s=(ROOT/'scripts/impact804_run.sh').read_text()
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('sz>183500800 || wf<234881024 || tf<440401920',s)
        self.assertIn('seq 1 6',s)
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
        self.assertIn('step restart-equality equal after-tests after-restart',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
