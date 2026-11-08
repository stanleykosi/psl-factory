from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class ComparisonImpactWrapperTests(TestCase):
    def test_exact_predecessor(self):
        from scripts.impact794_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0023_planning_comparison_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0022_planning_readiness_policy_impact'))
        self.assertEqual(FUNCTION_PREVIOUS,'0022_planning_readiness_policy_impact')
    def test_caps_and_populated_before_primary(self):
        s=(ROOT/'scripts/impact794_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 11',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_old_readiness_assessment_and_review_preserved(self):
        s=(ROOT/'scripts/impact794_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['pmo.planning_readiness']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index("comparison_fixture(username="))
        self.assertIn('review_before)',s)
