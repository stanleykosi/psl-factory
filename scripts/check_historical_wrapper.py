"""Explicit unchanged historical audits; no database/lifecycle execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest

def verify_root(root, revision):
    root=Path(root).resolve(strict=True)
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    if git('rev-parse','HEAD')!=revision:
        raise RuntimeError('Historical source commit differs')
    if git('diff','--name-only') or git('diff','--cached','--name-only'):
        raise RuntimeError('Historical tracked source/index is dirty')
    return root

def run_audit(repository, entry, root):
    root=verify_root(root,entry['frozen_source'])  # Before historical source imports.
    source=(Path(repository)/entry['check_path']).read_bytes()
    if hashlib.sha256(source).hexdigest()!=entry['sha256']:
        raise RuntimeError('Historical audit bytes changed')
    module=types.ModuleType('_explicit_historical_wrapper_audit')
    module.__file__=str(root/entry['original_path'])
    # Non-__main__ execution preserves original bytes without double-running guards.
    old_path=list(sys.path)
    prior=sys.modules.get(module.__name__)
    try:
        sys.path.insert(0,str(root));sys.modules[module.__name__]=module
        exec(compile(source,module.__file__,'exec'),module.__dict__)
        loader=unittest.TestLoader();suite=loader.loadTestsFromModule(module)
        if loader.errors or suite.countTestCases()!=entry['test_count'] or entry['test_count']<=0:
            raise RuntimeError('Historical audit count differs or is zero')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if result.testsRun!=entry['test_count'] or result.skipped or not result.wasSuccessful():
            raise RuntimeError('Historical audit failed or did not execute every test')
        return result.testsRun
    finally:
        sys.path[:]=old_path
        if prior is None:sys.modules.pop(module.__name__,None)
        else:sys.modules[module.__name__]=prior

def main():
    repository=Path(__file__).resolve().parents[1]
    entries=json.loads((repository/'docs/design/historical-wrapper786.json').read_text())['audits']
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit',choices=sorted(entries));parser.add_argument('--source-root',type=Path,required=True)
    args=parser.parse_args()
    run_audit(repository,entries[args.audit],args.source_root)

if __name__=='__main__':main()
