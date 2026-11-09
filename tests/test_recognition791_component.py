"""Portable source-only checks for the no-migration791 candidate."""
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PolicyReplay791ComponentTests(unittest.TestCase):
    def test_wrapper_has_no_migration_or_upgrade_stage(self):
        wrapper=(ROOT/'scripts/recognition791_run.sh').read_text()
        harness=(ROOT/'scripts/recognition791_harness.py').read_text()
        for text in [wrapper,harness]:
            self.assertNotIn('upgrade-test',text);self.assertNotIn('upgrade-primary',text)
        self.assertIn("choices=['preflight','snapshot','tests']",harness)
        self.assertIn('untouched-primary-equal equal pre-seed declared-primary',wrapper)
        self.assertIn('step test-restart-equality equal test-final test-restart',wrapper)
    def test_existing_safety_caps_and_clearance_retained(self):
        wrapper=(ROOT/'scripts/recognition791_run.sh').read_text()
        self.assertIn('coordinator-cleared-recognition791',wrapper)
        self.assertIn("trap '' TERM INT",wrapper)
        self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',wrapper)
    def test_contrasts_include_original_immutability_and_downstream_hold(self):
        tree=ast.parse((ROOT/'tests/test_recognition_policy_replay791.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        self.assertEqual(len([n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]),2)
        s=ast.unparse(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='assert_contrast'))
        for item in ['EXACT_RECORDED_REPLAY_ONLY','native.record_current',"'request791'",'Operation key reused for changed intent','self.assertEqual(self.state(), before)']:
            self.assertIn(item,s)
