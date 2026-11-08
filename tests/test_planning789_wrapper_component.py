"""Portable static launch-contract tests; no retained artifact or DB dependency."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PlanningWrapperTests(unittest.TestCase):
    def test_order_is_test_upgrade_then_primary_check_then_primary_upgrade(self):
        s=(ROOT/'scripts/planning789_run.sh').read_text()
        self.assertLess(s.index('test-baseline-compare'),s.index('step upgrade-test'))
        self.assertLess(s.index('step upgrade-test'),s.index('step primary-upgrade-test-equal'))
        self.assertLess(s.index('step primary-upgrade-test-equal'),s.index('step upgrade-primary'))
        self.assertIn('equal pre-seed primary-after-upgrade-test',s)
    def test_tokens_cleanup_restart_and_caps_match(self):
        s=(ROOT/'scripts/planning789_run.sh').read_text();h=(ROOT/'scripts/planning789_harness.py').read_text()
        for text in [s,h]:self.assertIn('coordinator-cleared-planning789',text)
        self.assertIn("trap '' TERM INT",s);self.assertIn("trap 'exit 93' TERM INT",s)
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_upgrade_is_explicit_one_shot_not_default_discovery(self):
        from scripts.planning789_upgrade import TARGET,PREVIOUS
        self.assertEqual(TARGET,('policy','0019_planning_readiness_preview'))
        self.assertEqual(PREVIOUS,('policy','0018_approval_route_preview'))
        self.assertFalse((ROOT/'tests/test_planning789_upgrade_lifecycle.py').exists())
        s=(ROOT/'scripts/planning789_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index('result = upgrade('),s.index('planning_fixture(username='))
        self.assertIn("binding.payload['guards'][0]['operation'],'approval.route'",s)
