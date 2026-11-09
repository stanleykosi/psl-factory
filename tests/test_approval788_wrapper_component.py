import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class WrapperContractTests(unittest.TestCase):
    def test_launch_token_and_prestart_inputs_match(self):
        shell=(ROOT/'scripts/approval788_run.sh').read_text()
        harness=(ROOT/'scripts/approval788_harness.py').read_text()
        for token in ['RUN788_RUNTIME_CLEARANCE','coordinator-cleared-approval788','RUN788_EXPECTED_HEAD']:
            self.assertIn(token,shell)
        self.assertIn('coordinator-cleared-approval788',harness)
        self.assertLess(shell.index('scripts/approval788_inputs.py'),shell.index('start > "$E/start.log"'))
        self.assertLess(shell.index('test-baseline-compare'),shell.index('step upgrade-primary'))
        self.assertLess(shell.index('step upgrade-test'),shell.index('step upgrade-primary'))
        self.assertLess(shell.index('step primary-upgrade-test-equal'),shell.index('step upgrade-primary'))
        self.assertIn('equal pre-seed primary-after-upgrade-test',shell)

    def test_owned_cleanup_and_restart_budgets_preserved(self):
        shell=(ROOT/'scripts/approval788_run.sh').read_text()
        self.assertIn("trap '' TERM INT",shell)
        self.assertIn("trap 'exit 93' TERM INT",shell)
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',shell)
        self.assertLess(shell.index('groups-final-verification'),shell.index('"$PG/pg_ctl" -D "$DATA" -m fast -w stop'))
        self.assertIn('step test-restart-equality equal test-final test-restart',shell)
        self.assertIn('step restart-equality equal after-tests after-restart',shell)

    def test_upgrade_fixture_is_one_way_native_transaction_case(self):
        source=(ROOT/'scripts/approval788_upgrade_lifecycle.py').read_text()
        tree=ast.parse(source)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        self.assertEqual(cls.bases[0].id,'TransactionTestCase')
        self.assertIn("fixture(username='approval788-upgrade',reviewer_username='approval788-reviewer')",source)
        self.assertNotIn('call_command(',source)
        self.assertNotIn('flush(',source)
        migration=(ROOT/'scripts/approval788_upgrade.py').read_text()
        self.assertIn("[(*TARGET, False)]",migration)
        self.assertNotIn('reverse_sql',migration)

    def test_final_ledger_inputs_are_pinned_and_env_mismatch_fails_closed(self):
        import json,runpy,os
        from unittest.mock import patch
        value=json.loads((ROOT/'docs/design/approval788-selection.json').read_text())
        self.assertEqual(value['accepted_predecessor'],'44d867ea8549bf16d85dc781380dda06336f59b9')
        self.assertTrue(all(x['path'] and len(x['sha256'])==64 for x in value['runtime_inputs'].values()))
        with patch.dict(os.environ,{'RUN788_PREDECESSOR':'wrong'}):
            with self.assertRaisesRegex(RuntimeError,'predecessor pin pending'):
                runpy.run_path(str(ROOT/'scripts/approval788_inputs.py'))

    def test_one_shot_is_not_default_discovery_and_uses_real_ledger_binding(self):
        self.assertFalse((ROOT/'tests/test_approval788_upgrade_lifecycle.py').exists())
        source=(ROOT/'scripts/approval788_upgrade_lifecycle.py').read_text()
        self.assertIn("pilot_bindings.configure(a,c.pk,contract.pk,selected)",source)
        self.assertIn("'operation':'ledger.review'",source)
        self.assertIn('before = dict(PilotBinding.objects.values().get(pk=binding.pk))',source)

    def test_new_variant_proven_after_exact_upgrade_before_primary(self):
        source=(ROOT/'scripts/approval788_upgrade_lifecycle.py').read_text()
        self.assertLess(source.index('result = upgrade(connection, root)'),source.index("approval_fixture('approval788-post-upgrade')"))
        self.assertLess(source.index('self.assertEqual(dict(PilotBinding.objects.values().get(pk=binding.pk)), before)'),source.index('new_binding=pilot_bindings.configure'))
        self.assertIn("self.assertEqual(observed['state'],'READY_AT_OBSERVATION')",source)
        self.assertIn('self.assertEqual(before_observation,',source)
