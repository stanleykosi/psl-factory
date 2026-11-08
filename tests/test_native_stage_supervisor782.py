"""Synthetic process/session supervision only; no Django or database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SUPERVISOR=Path(__file__).parents[1]/'scripts/native_stage_supervisor782.py'


class StageSupervisorTests(unittest.TestCase):
    def command(self,path,body,timeout=3):
        return [sys.executable,str(SUPERVISOR),'--proof',str(path),'--timeout',str(timeout),'--',sys.executable,'-c',body]

    def check(self,path):
        result=json.loads((path/'result.json').read_text())
        self.assertTrue(result['group_empty'])
        self.assertEqual(result['owner']['pid'],result['owner']['pgid'])
        self.assertEqual(result['owner']['pid'],result['owner']['sid'])
        self.assertNotEqual(result['owner']['pgid'],os.getpgrp())
        verified=subprocess.run([sys.executable,str(SUPERVISOR),'--verify',str(path.parent)],capture_output=True,text=True,timeout=5)
        self.assertEqual(verified.returncode,0,verified.stderr)
        return result

    def test_normal_stage_owns_distinct_session(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'normal';run=subprocess.run(self.command(path,'print("synthetic")'),capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr);self.check(path)

    def test_timeout_terminates_and_reaps_descendant_group(self):
        body='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);time.sleep(30)'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'timeout';run=subprocess.run(self.command(path,body,.3),capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,124,run.stderr);result=self.check(path)
            self.assertEqual(result['reason'],'timeout')
            self.assertGreaterEqual(len([e for e in result['events'] if 'reaped_pid' in e]),2)

    def test_lingering_child_is_failure_not_silent_success(self):
        body='import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'lingering';run=subprocess.run(self.command(path,body),capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,125,run.stderr);self.assertEqual(self.check(path)['reason'],'lingering_descendants')

    def test_external_termination_cleans_only_owned_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'signal';process=subprocess.Popen(self.command(path,'import time;time.sleep(30)'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            deadline=time.monotonic()+5
            while not (path/'owner.json').exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue((path/'owner.json').exists());process.terminate()
            _,error=process.communicate(timeout=20)
            self.assertEqual(process.returncode,143,error);self.assertEqual(self.check(path)['reason'],'signal')

    def test_session_escape_is_detected_without_signalling_foreign_group(self):
        body='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(.3)"],start_new_session=True);time.sleep(30)'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'escape';run=subprocess.run(self.command(path,body),capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,125,run.stderr);result=self.check(path)
            self.assertEqual(result['reason'],'escaped_descendant')
            escaped=[e['escaped_reaped_pid'] for e in result['events'] if 'escaped_reaped_pid' in e]
            self.assertEqual(len(escaped),1)
            signalled=[p['pid'] for event in result['events'] if 'signal' in event for p in event['members']]
            self.assertNotIn(escaped[0],signalled)
