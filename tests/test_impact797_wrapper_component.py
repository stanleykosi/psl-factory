from pathlib import Path
import unittest,json
ROOT=Path(__file__).resolve().parents[1]
class DeliveryImpactWrapperTests(unittest.TestCase):
    def test_exact_predecessor(self):
        from scripts.impact797_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0026_delivery_prerequisite_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0025_approval_routing_policy_impact'))
        self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
    def test_caps_order_and_populated_routing(self):
        s=(ROOT/'scripts/impact797_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 11',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
        s=(ROOT/'scripts/impact797_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['pmo.approval_routing_jobs']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index('f=DeliveryFixture()'))
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
        self.assertIn("'documents'",s);self.assertIn("'finance'",s)
    def test_expensive_contrasts_singleton_not_budget_exception(self):
        v=json.loads((ROOT/'docs/design/impact797-selection.json').read_text())
        self.assertEqual((v['count'],v['total_native_count']),(19,20))
        self.assertEqual(len(v['batches']),11)
        for marker in ('DeliveryImpactClosedHistoryTests','DeliveryImpactBaselineReplacementTests'):
            batches=[b for b in v['batches'] if any(marker in i for i in b['ids'])]
            self.assertEqual(len(batches),1);self.assertEqual(len(batches[0]['ids']),1)
            self.assertEqual(batches[0]['outer_timeout_seconds'],300)
