"""DB-free continuation guards; prior failed upgrade never becomes a pass."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PaymentContinuationTests(unittest.TestCase):
    def test_no_test_upgrade_path_and_exact_order(self):
        h=(ROOT/'scripts/impact795c_harness.py').read_text()
        self.assertNotIn('def upgrade_test(',h);self.assertNotIn("elif args.command == 'upgrade-test'",h)
        s=(ROOT/'scripts/impact795c_run.sh').read_text()
        for a,b in [('step test-schema-identity','step compatibility'),('step failed-primary-compare','step compatibility'),('step compatibility','step primary-compatibility-equal'),('step primary-compatibility-equal','step upgrade-primary'),('step upgrade-primary','seq 2 9')]:
            self.assertLess(s.index(a),s.index(b))
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_postmigration_case_never_runs_migration(self):
        s=(ROOT/'scripts/impact795c_compatibility.py').read_text()
        self.assertNotIn('upgrade(connection',s);self.assertIn('self.assertIn(TARGET,applied)',s)
        self.assertIn('from tests.payment_impact795_helpers import fixture',s)
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',s)
    def test_exact_asymmetric_schema_and_failed_proof_pins(self):
        s=(ROOT/'scripts/impact795c_harness.py').read_text()
        self.assertIn("plan==([] if args.target==TEST else [(*TARGET,False)])",s)
        self.assertIn("actual==body(target[1])",s)
        self.assertIn("selection()['function_pins']",s)
        s=(ROOT/'scripts/impact795c_inputs.py').read_text()
        self.assertIn("v['historical_source_pins']",s)
        self.assertIn("result['status']!=v['failed_prior_status']",s)
