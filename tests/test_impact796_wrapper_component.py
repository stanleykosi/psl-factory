from pathlib import Path
import unittest,ast
ROOT=Path(__file__).resolve().parents[1]
class ApprovalImpactWrapperTests(unittest.TestCase):
    def test_exact_predecessor(self):
        from scripts.impact796_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0025_approval_routing_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0024_payment_assessment_policy_impact'))
        self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
        self.assertFalse(list((ROOT/'apps/policy/migrations').glob('0026*')))
    def test_caps_order_and_preserved_accepted_payment(self):
        s=(ROOT/'scripts/impact796_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 11',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
        s=(ROOT/'scripts/impact796_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['finance.payment_assessments']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index("f=routing_fixture("))
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
        self.assertIn('assert_predeployment_fixture(f)',s)
        self.assertNotIn('human(',s);self.assertNotIn('.ready()',s)
    def test_thread_shutdown_and_exact_first_job_lock_proof(self):
        s=(ROOT/'tests/test_approval_routing_policy_impact.py').read_text()
        self.assertIn('finally:release.set();thread.join(12)',s)
        self.assertIn('finally:connections.close_all()',s)
        self.assertIn('self.assertFalse(thread.is_alive())',s)
        self.assertIn('release.wait(10)',s);self.assertIn('ready.wait(5)',s)
        self.assertIn("self.assertIn('FOR UPDATE',selects[0])",s)
        self.assertIn("self.assertIn('NOWAIT',selects[0])",s)
