"""Static source/launch contracts only; no database or provider."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class RecognitionWrapperTests(unittest.TestCase):
    def test_test_upgrade_precedes_primary_and_restart(self):
        s=(ROOT/'scripts/recognition790_run.sh').read_text()
        for a,b in [('test-baseline-compare','step upgrade-test'),('step upgrade-test','step primary-upgrade-test-equal'),('step primary-upgrade-test-equal','step upgrade-primary')]:self.assertLess(s.index(a),s.index(b))
        self.assertIn('equal pre-seed primary-after-upgrade-test',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_clearance_and_through_stop_caps_remain(self):
        s=(ROOT/'scripts/recognition790_run.sh').read_text();h=(ROOT/'scripts/recognition790_harness.py').read_text()
        for text in [s,h]:self.assertIn('coordinator-cleared-recognition790',text)
        self.assertIn("trap '' TERM INT",s)
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
    def test_additive_upgrade_exact_old_planning_before_new_recognition(self):
        from scripts.recognition790_upgrade import TARGET,PREVIOUS
        self.assertEqual(TARGET,('policy','0020_recognition_attestation_preview'))
        self.assertEqual(PREVIOUS,('policy','0019_planning_readiness_preview'))
        self.assertFalse((ROOT/'tests/test_recognition790_upgrade_lifecycle.py').exists())
        s=(ROOT/'scripts/recognition790_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index('before=dict(PilotBinding'),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index('f=fixture()'))
