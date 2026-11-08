import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class WrapperContractTests(unittest.TestCase):
    def test_launch_token_and_prestart_inputs_match(self):
        shell=(ROOT/'scripts/ledger786_run.sh').read_text()
        harness=(ROOT/'scripts/ledger786_harness.py').read_text()
        for token in ['RUN786_RUNTIME_CLEARANCE','coordinator-cleared-ledger786','RUN786_EXPECTED_HEAD']:
            self.assertIn(token,shell)
        self.assertIn('coordinator-cleared-ledger786',harness)
        self.assertLess(shell.index('scripts/ledger786_inputs.py'),shell.index('start > "$E/start.log"'))
        self.assertLess(shell.index('test-baseline-compare'),shell.index('step upgrade-primary'))
        self.assertLess(shell.index('step upgrade-test'),shell.index('step upgrade-primary'))
        self.assertLess(shell.index('step primary-upgrade-test-equal'),shell.index('step upgrade-primary'))
        self.assertIn('equal pre-seed primary-after-upgrade-test',shell)

    def test_owned_cleanup_and_restart_budgets_preserved(self):
        shell=(ROOT/'scripts/ledger786_run.sh').read_text()
        self.assertIn("trap '' TERM INT",shell)
        self.assertIn("trap 'exit 93' TERM INT",shell)
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',shell)
        self.assertLess(shell.index('groups-final-verification'),shell.index('"$PG/pg_ctl" -D "$DATA" -m fast -w stop'))
        self.assertIn('step test-restart-equality equal test-final test-restart',shell)
        self.assertIn('step restart-equality equal after-tests after-restart',shell)

    def test_upgrade_fixture_is_one_way_native_transaction_case(self):
        source=(ROOT/'scripts/ledger786_upgrade_lifecycle.py').read_text()
        tree=ast.parse(source)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        self.assertEqual(cls.bases[0].id,'TransactionTestCase')
        self.assertIn("fixture(prefix='ledger786-upgrade')",source)
        self.assertNotIn('call_command(',source)
        self.assertNotIn('flush(',source)
        migration=(ROOT/'scripts/ledger786_upgrade.py').read_text()
        self.assertIn("[(*TARGET, False)]",migration)
        self.assertNotIn('reverse_sql',migration)
