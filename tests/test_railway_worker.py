"""Check the queue supervisor with a deliberately blocked model process."""
from pathlib import Path
import shutil
import subprocess
import os
import tempfile
from unittest import skipUnless

from django.test import SimpleTestCase


SHELL = shutil.which('sh') if os.name == 'posix' else None
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'railway-worker.sh'
if not SCRIPT.is_file():
    SCRIPT = ROOT / 'railway-worker.sh'
FAKE_PYTHON = '''#!/bin/sh
case "$2" in
    migrate) exit 0 ;;
    work_specialist_readings) exec sleep 30 ;;
    work_agent_uploads|work_assistant)
        : > "$2"
        exec sleep 30
        ;;
    work_outbox|work_factory_progress) : > "$2" ;;
esac
'''
PROBE = '''
set -eu
export PATH="$PWD/bin:$PATH"
sh "$1" &
worker=$!
trap 'kill "$worker" 2>/dev/null || true; wait "$worker" || true' EXIT
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if [ -f work_agent_uploads ] && [ -f work_assistant ] &&
       [ -f work_outbox ] && [ -f work_factory_progress ]; then
        exit 0
    fi
    sleep 1
done
exit 1
'''


@skipUnless(SHELL, 'A POSIX shell is required to exercise the Railway worker entrypoint.')
class RailwayWorkerTests(SimpleTestCase):
    def test_native_work_advances_while_both_model_queues_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            fake = root / 'bin' / 'python'
            fake.write_text(FAKE_PYTHON, encoding='utf-8', newline='\n')
            fake.chmod(0o755)
            result = subprocess.run([SHELL, '-c', PROBE, 'probe', SCRIPT.as_posix()], cwd=root,
                                    capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
