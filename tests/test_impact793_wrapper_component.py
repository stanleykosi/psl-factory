from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class PlanningImpactWrapperTests(TestCase):
    def test_exact_migration_and_function_predecessor(self):
        from scripts.impact793_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS,FUNCTION
        self.assertEqual(TARGET,('policy','0022_planning_readiness_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0021_recognition_policy_impact'))
        self.assertEqual(FUNCTION_PREVIOUS,'0021_recognition_policy_impact')
        self.assertEqual(FUNCTION,'psl_policy_impact_guard()')
    def test_populated_upgrade_precedes_primary_and_restarts(self):
        s=(ROOT/'scripts/impact793_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step primary-upgrade-test-equal'))
        self.assertLess(s.index('step primary-upgrade-test-equal'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 12',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_prior_recognition_assessment_and_review_before_new_planning(self):
        s=(ROOT/'scripts/impact793_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['finance.recognition_records']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index("f=h.fixture(username="))
        self.assertIn('review_before)',s)
        self.assertIn("['pmo.planning_readiness']",s)
