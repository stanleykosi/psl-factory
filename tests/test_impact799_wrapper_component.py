from pathlib import Path
import unittest,json,os,runpy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
class SignatureImpactWrapperTests(unittest.TestCase):
    def test_exact_predecessor_and_pending_inputs_fail_closed(self):
        from scripts.impact799_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0028_signature_packet_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0027_signed_adoption_recovery_policy_impact'))
        self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
        v=json.loads((ROOT/'docs/design/impact799-selection.json').read_text())
        self.assertEqual(v['accepted_predecessor'],'b7dadb82aad7aae474a5f531d910f6ed15f7a044');self.assertEqual(v['review_status'],'BOUNDED_RECOVERY_IMPACT_CONTINUATION17_PASS');self.assertEqual(v['review_source'],'93b13b0d30ca8cda3f8e68915bc0197cf1122f0d')
        self.assertTrue(all(i['path'] and len(i['sha256'])==64 for i in v['runtime_inputs'].values()))
        self.assertTrue({'prior798a_review_manifest','prior797a_review_manifest','prior797b_review_manifest'} <= set(v['runtime_inputs']))
        with patch.dict(os.environ,{'RUN799_PREDECESSOR':'not-accepted'}):
            with self.assertRaisesRegex(RuntimeError,'accepted impact798 predecessor pin pending'):
                runpy.run_path(str(ROOT/'scripts/impact799_inputs.py'))
    def test_caps_exact_selection_and_populated_request(self):
        s=(ROOT/'scripts/impact799_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 9',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
        v=json.loads((ROOT/'docs/design/impact799-selection.json').read_text());self.assertEqual((v['count'],v['total_native_count']),(17,18))
        self.assertEqual(len(v['batches']),9);self.assertTrue(all(len(b['ids'])<=2 and b['outer_timeout_seconds']==300 for b in v['batches']))
        s=(ROOT/'scripts/impact799_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['pmo.signed_adoption_recovery_requests']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index("a,c=setup_case("))
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
    def test_no_signature_or_private_source_authority_claim(self):
        s=(ROOT/'scripts/impact799_upgrade_lifecycle.py').read_text()
        self.assertIn("self.assertFalse(rows[0]['packet_policy_valid_now'])",s)
        self.assertIn("('signature_authenticity_verified','signing_authorized','effects_performed')",s)
        self.assertIn('CommercialSignatureUse.objects.filter(packet__case=c).exists()',s)
        self.assertNotIn('reaffirm_baseline(',s);self.assertNotIn('current_packet(',s)
        s=(ROOT/'tests/test_signature_policy_impact.py').read_text()
        self.assertIn("self.assertEqual(len(added),1)",s)
        self.assertIn("'policy.impact.reviewed'",s)
