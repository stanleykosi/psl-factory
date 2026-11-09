"""Pure explicit-audit launcher contracts, no DB or historical module imports."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('historical_launcher',Path(__file__).resolve().parents[1]/'scripts/check_historical_wrapper.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

class HistoricalLauncherTests(unittest.TestCase):
    def fixture(self,root,body,count):
        source=('import unittest\n'+body).encode();(root/'audit.py').write_bytes(source)
        return {'check_path':'audit.py','original_path':'tests/old_audit.py','sha256':hashlib.sha256(source).hexdigest(),'frozen_source':'a'*40,'test_count':count}
    def invoke(self,body,count):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);entry=self.fixture(root,body,count)
            with patch.object(launcher,'verify_root',return_value=root):
                return launcher.run_audit(root,entry,root)
    def test_both_no_main_audits_execute_all_tests(self):
        for count in (4,3):
            body='class Audit(unittest.TestCase):\n'+''.join(f' def test_{i}(self): self.assertTrue(True)\n' for i in range(count))
            self.assertEqual(self.invoke(body,count),count)
    def test_existing_main_guard_not_double_run(self):
        self.assertEqual(self.invoke("class Audit(unittest.TestCase):\n def test_one(self): self.assertTrue(True)\nif __name__=='__main__': raise RuntimeError('must not run main guard')\n",1),1)
    def test_zero_or_missing_tests_fail(self):
        for body,count in [('',0),('',1),('class Audit(unittest.TestCase):\n def test_one(self): pass\n',2)]:
            with self.assertRaisesRegex(RuntimeError,'count'):self.invoke(body,count)
    def test_failure_or_skip_never_counts_as_success(self):
        for action in ['self.fail("synthetic")','self.skipTest("synthetic")']:
            with self.assertRaisesRegex(RuntimeError,'failed'):self.invoke('class Audit(unittest.TestCase):\n def test_one(self): '+action+'\n',1)
    def test_wrong_commit_rejected_before_source_read(self):
        with tempfile.TemporaryDirectory() as name,patch.object(launcher.subprocess,'check_output',return_value='b'*40+'\n'):
            with self.assertRaisesRegex(RuntimeError,'commit'):launcher.run_audit(Path(name),{'frozen_source':'a'*40},Path(name))
    def test_dirty_worktree_or_index_rejected_before_source_read(self):
        for outputs in [('a'*40+'\n','changed.py\n'),('a'*40+'\n','','changed.py\n')]:
            with tempfile.TemporaryDirectory() as name,patch.object(launcher.subprocess,'check_output',side_effect=outputs):
                with self.assertRaisesRegex(RuntimeError,'dirty'):launcher.run_audit(Path(name),{'frozen_source':'a'*40},Path(name))
    def test_exact_clean_root_accepted(self):
        with tempfile.TemporaryDirectory() as name,patch.object(launcher.subprocess,'check_output',side_effect=['a'*40+'\n','','']):
            self.assertEqual(launcher.verify_root(name,'a'*40),Path(name).resolve())
    def test_changed_audit_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);entry=self.fixture(root,'',1);(root/'audit.py').write_text('changed')
            with patch.object(launcher,'verify_root',return_value=root):
                with self.assertRaisesRegex(RuntimeError,'bytes'):launcher.run_audit(root,entry,root)
