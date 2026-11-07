"""Offline synthetic registry and exact intake credential-function regression tests."""
import ast
import copy
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
from config import integration_runtime as runtime

CASE = '12345678-1234-4234-8234-123456789abc'

def fixture():
    return {'endpoints': {'endpoint:test': {'url': 'https://gateway.invalid', 'classification': 'synthetic'}},
            'secrets': {'secret:test': {'env': 'SYNTHETIC_TEST_KEY', 'revision': 'v1'}},
            'finance_senders': {'sender:test': {'credential_ref': 'secret:test', 'credential_revision': 'v1',
                'destination_ref': 'inbox:test', 'case_ids': [CASE], 'classification': 'synthetic'}}}

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'registry.json'
        self.path.write_text(json.dumps(fixture()))
        self.net = patch('socket.socket', side_effect=AssertionError('network prohibited'))
        self.net.start(); self.addCleanup(self.net.stop)

    def test_valid_and_unconfigured(self):
        self.assertEqual(runtime.load_file(self.path), fixture())
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runtime.load(), {'endpoints': {}, 'secrets': {}, 'finance_senders': {}})
            self.assertEqual(runtime.preflight()['status'], 'unconfigured')
        with patch.dict(os.environ, {'PSL_INTEGRATION_PROFILE': str(self.path)}, clear=True):
            self.assertEqual(runtime.load(), fixture())

    def test_origins(self):
        for url in ['https://gateway.invalid', 'http://localhost:9000', 'http://127.0.0.1', 'http://[::1]:9000/']:
            value = fixture(); value['endpoints']['endpoint:test']['url'] = url
            self.assertEqual(runtime.validate_registry(value), value)
        for url in ['http://gateway.invalid', 'https://a.invalid/path', 'https://a.invalid?', 'https://a.invalid#', 'https://u:p@a.invalid', 'https://a.invalid:0', 'https://a.invalid:99999', 'https://a.invalid:', 'https://a.invalid\\bad', 'https://a.invalid\n', 'https://%61.invalid', 'https://[bad]']:
            with self.subTest(url=url):
                value = fixture(); value['endpoints']['endpoint:test']['url'] = url
                with self.assertRaisesRegex(RuntimeError, runtime.INVALID): runtime.validate_registry(value)
        value = fixture(); value['endpoints']['endpoint:test'].update(url='http://localhost', classification='operational')
        with self.assertRaises(RuntimeError): runtime.validate_registry(value)

    def test_shapes_and_references(self):
        values = [None, [], {}, {'endpoints': [], 'secrets': {}, 'finance_senders': {}}]
        for section in fixture():
            for bad in [None, [], 'private-marker', 1]:
                value = fixture(); value[section][next(iter(value[section]))] = bad; values.append(value)
        for field, bad in [('case_ids', [CASE, CASE]), ('case_ids', [CASE.upper()]), ('case_ids', CASE), ('case_ids', [None]), ('credential_ref', 'secret:missing'), ('credential_revision', 'v2'), ('destination_ref', ''), ('classification', 'unknown')]:
            value = fixture(); value['finance_senders']['sender:test'][field] = bad; values.append(value)
        for field, bad in [('env', 'bad name'), ('env', 'X'*129), ('revision', ''), ('revision', [])]:
            value = fixture(); value['secrets']['secret:test'][field] = bad; values.append(value)
        value = fixture(); value['secrets']['secret:test']['extra'] = 'private-marker'; values.append(value)
        value = fixture(); value['endpoints']['bad'] = value['endpoints'].pop('endpoint:test'); values.append(value)
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError) as caught: runtime.validate_registry(value)
                self.assertEqual(str(caught.exception), runtime.INVALID)

    def test_collection_limits_and_inert_sender(self):
        value = fixture(); value['finance_senders']['sender:test']['case_ids'] = []
        self.assertEqual(runtime.validate_registry(value), value)
        for section in fixture():
            value = fixture(); value[section] = {str(i): {} for i in range(1025)}
            with self.assertRaises(RuntimeError): runtime.validate_registry(value)
        value = fixture(); value['finance_senders']['sender:test']['case_ids'] = [CASE]*1025
        with self.assertRaises(RuntimeError): runtime.validate_registry(value)
        value = fixture(); value['endpoints']['endpoint:test']['url'] = 'https://'+'a'*2048
        with self.assertRaises(RuntimeError): runtime.validate_registry(value)

    def test_json_and_file_boundaries(self):
        for raw in [b'{"endpoints":{},"endpoints":{},"secrets":{},"finance_senders":{}}', b'{"endpoints":{"x":1,"x":2},"secrets":{},"finance_senders":{}}', b'NaN', b'Infinity', b'\xff', b'['*2000, b'private-marker']:
            self.path.write_bytes(raw)
            with self.assertRaises(RuntimeError) as caught: runtime.load_file(self.path)
            self.assertEqual(str(caught.exception), runtime.INVALID)
        self.path.write_bytes(b' '*(runtime.MAX_BYTES+1))
        link = Path(self.tmp.name)/'link'; link.symlink_to(self.path)
        fifo = Path(self.tmp.name)/'fifo'; os.mkfifo(fifo)
        for path in [self.path, link, fifo, Path(self.tmp.name), Path(self.tmp.name)/'missing', 'relative', '']:
            with self.subTest(path=str(path)):
                with self.assertRaises(RuntimeError) as caught: runtime.load_file(path)
                self.assertEqual(str(caught.exception), runtime.FILE_INVALID)

    def test_preflight_does_not_resolve_or_disclose(self):
        with patch('os.getenv', side_effect=AssertionError('environment resolution prohibited')):
            report = runtime.preflight(str(self.path))
        raw = json.dumps(report)
        for private in ['gateway.invalid', 'SYNTHETIC_TEST_KEY', str(self.path), CASE]: self.assertNotIn(private, raw)
        self.assertFalse(report['network_checked']); self.assertFalse(report['credentials_resolved']); self.assertFalse(report['operational_readiness'])
        stdout = io.StringIO()
        with redirect_stdout(stdout): self.assertEqual(runtime.main(['--profile', str(self.path)]), 0)
        self.assertEqual(json.loads(stdout.getvalue()), report)
        for args in [['--profile', 'private-marker'], ['--private-marker'], ['--profile', '']]:
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as caught: runtime.main(args)
            self.assertEqual(caught.exception.code, 2); self.assertNotIn('private-marker', stderr.getvalue())

class IntakeCredentialTests(unittest.TestCase):
    """Compile exact production function without importing ORM-dependent endpoint module."""
    def setUp(self):
        path = Path(__file__).resolve().parents[1]/'apps/finance/followup_intake.py'
        tree = ast.parse(path.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'credentials')
        class Denied(Exception): pass
        self.Denied = Denied
        self.settings = SimpleNamespace(FINANCE_INBOX_SENDERS=fixture()['finance_senders'], READINESS_SECRET_REFS=fixture()['secrets'], SECRET_KEY='synthetic-application-signing-key')
        scope = {'settings': self.settings, 'os': SimpleNamespace(environ={'SYNTHETIC_TEST_KEY': 's'*32}), 'PermissionDenied': Denied, 'hmac': hmac, 'hashlib': hashlib, 'digest': lambda v: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
        self.scope = scope; self.call = scope['credentials']; self.case = SimpleNamespace(pk=CASE, synthetic=True)

    def test_valid_current_binding(self):
        v, secret, binding = self.call(self.case, 'sender:test')
        self.assertEqual(v, fixture()['finance_senders']['sender:test']); self.assertEqual(secret, 's'*32); self.assertEqual(len(binding), 64)
        self.scope['os'].environ['SYNTHETIC_TEST_KEY'] = 't'*32
        self.assertNotEqual(self.call(self.case, 'sender:test')[2], binding)

    def test_scope_and_secret_guards(self):
        for field, bad in [('case_ids', []), ('case_ids', CASE), ('classification', 'operational'), ('credential_revision', 'v2'), ('destination_ref', None)]:
            original = copy.deepcopy(self.settings.FINANCE_INBOX_SENDERS)
            self.settings.FINANCE_INBOX_SENDERS['sender:test'][field] = bad
            with self.assertRaises(self.Denied): self.call(self.case, 'sender:test')
            self.settings.FINANCE_INBOX_SENDERS = original
        for secret in ['', 's'*31, 's'*4097, 's'*32+'\n', 's'*32+'\r', None]:
            self.scope['os'].environ['SYNTHETIC_TEST_KEY'] = secret
            with self.assertRaises(self.Denied) as caught: self.call(self.case, 'sender:test')
            self.assertEqual(str(caught.exception), 'Current source inbox sender/key/case binding unavailable')
        self.scope['os'].environ = {}
        with self.assertRaises(self.Denied): self.call(self.case, 'sender:test')
        self.scope['os'].environ = {'SYNTHETIC_TEST_KEY': 's'*32}
        for credential in [[], None, {'env': 'SYNTHETIC_TEST_KEY', 'revision': 'v2'}, {'env': None, 'revision': 'v1'}]:
            self.settings.READINESS_SECRET_REFS = {'secret:test': credential}
            with self.assertRaises(self.Denied): self.call(self.case, 'sender:test')
        with self.assertRaises(self.Denied): self.call(self.case, 'missing')
        self.settings.FINANCE_INBOX_SENDERS['sender:test'] = []
        with self.assertRaises(self.Denied): self.call(self.case, 'sender:test')

if __name__ == '__main__': unittest.main()
