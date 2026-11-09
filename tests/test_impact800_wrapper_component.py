from pathlib import Path
import unittest,json,runpy
ROOT=Path(__file__).resolve().parents[1]
class EmergencyImpactWrapperTests(unittest.TestCase):
 def test_pending_inputs_fail_closed(self):
  v=json.loads((ROOT/'docs/design/impact800-selection.json').read_text())
  self.assertEqual(v['accepted_predecessor'],'d83640009d246272186442f7bb6e1ededb3b1cac')
  self.assertEqual(v['review_source'],'6cadd904f822bab21a70b6f413fdff4e6658c843')
  self.assertEqual(v['review_status'],'BOUNDED_SIGNATURE_PACKET_IMPACT18_PASS')
  self.assertTrue(all(x['path'] and len(x['sha256'])==64 for x in v['runtime_inputs'].values()))
  with self.assertRaisesRegex(RuntimeError,'predecessor pin pending'):runpy.run_path(str(ROOT/'scripts/impact800_inputs.py'))
 def test_exact_upgrade_and_bounded_lifecycle(self):
  from scripts.impact800_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
  self.assertEqual(TARGET,('policy','0029_emergency_recovery_policy_impact'))
  self.assertEqual(PREVIOUS,('policy','0028_signature_packet_policy_impact'));self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
  v=json.loads((ROOT/'docs/design/impact800-selection.json').read_text());self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(21,22,11))
  s=(ROOT/'scripts/impact800_run.sh').read_text();self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
  self.assertIn('seq 1 11',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
  self.assertIn('step test-restart-equality equal test-final test-restart',s)
 def test_prior_packet_review_and_exact_audit_preserved(self):
  s=(ROOT/'scripts/impact800_upgrade_lifecycle.py').read_text()
  self.assertLess(s.index("['pmo.signature_packets']"),s.index('upgrade(connection,root)'))
  self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
  self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
  self.assertNotIn('active_recovery(',s);self.assertNotIn('finalize_recovery(',s)
