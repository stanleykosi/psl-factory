from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class ImpactWrapperTests(TestCase):
    def test_distinct_function_and_migration_predecessors(self):
        from scripts.impact792_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS,FUNCTION
        self.assertEqual(TARGET,('policy','0021_recognition_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0020_recognition_attestation_preview'))
        self.assertEqual(FUNCTION_PREVIOUS,'0010_private_impact_contracts')
        self.assertEqual(FUNCTION,'psl_policy_impact_guard()')
    def test_populated_test_precedes_primary_and_caps_unchanged(self):
        s=(ROOT/'scripts/impact792_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step primary-upgrade-test-equal'))
        self.assertLess(s.index('step primary-upgrade-test-equal'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 7',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_populated_old_review_preserved_before_new_fixture(self):
        s=(ROOT/'scripts/impact792_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index('before_review='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index('f=fixture()'))
        self.assertIn('before_review)',s)
