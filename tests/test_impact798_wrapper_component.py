from pathlib import Path
import json,unittest
ROOT=Path(__file__).resolve().parents[1]
class RecoveryImpactWrapperTests(unittest.TestCase):
    def test_exact_accepted_inputs_and_predecessor(self):
        v=json.loads((ROOT/'docs/design/impact798-selection.json').read_text())
        self.assertEqual(v['accepted_predecessor'],'849f4b6e7f81adfd95ab222253ba702d60760df2')
        self.assertEqual(v['review_source'],'242546a332169d5ee04c3a54565a74d2f9cb46d9')
        self.assertEqual(v['review_status'],'BOUNDED_DELIVERY_IMPACT_CONTINUATION20_PASS')
        self.assertTrue(all(x['path'] and len(x['sha256'])==64 for x in v['runtime_inputs'].values()))
        self.assertIn('prior797a_review_manifest',v['runtime_inputs']);self.assertIn('prior797b_review_manifest',v['runtime_inputs'])
        from scripts.impact798_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0027_signed_adoption_recovery_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0026_delivery_prerequisite_policy_impact'));self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
    def test_bounded_selection_and_unchanged_guards(self):
        v=json.loads((ROOT/'docs/design/impact798-selection.json').read_text());self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(16,17,8))
        s=(ROOT/'scripts/impact798_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'));self.assertIn('seq 1 8',s)
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_populated_delivery_and_exact_audit(self):
        s=(ROOT/'scripts/impact798_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['pmo.delivery_prerequisites']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',s);self.assertIn("'documents'",s)
        self.assertNotIn('active_recovery(',s);self.assertNotIn('finalize_recovery(',s)
