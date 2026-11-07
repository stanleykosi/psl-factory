"""Pure synthetic components: no Django, database, credentials or network."""
import copy
from dataclasses import FrozenInstanceError, replace
import json
from http.client import BadStatusLine, IncompleteRead, LineTooLong
import unittest
from unittest.mock import patch
from adapters import quickbooks_online as q
from config.integration_runtime import validate_registry


class QuickBooksReadTests(unittest.TestCase):
    def setUp(self):
        self.secrets = {'secret:qbo': {'env': 'SYNTHETIC_QBO_TOKEN', 'revision': 'v1'}}
        self.binding = dict(enabled=True, environment='sandbox', realm='123', entity='Invoice',
                            minor_version='75', credential_ref='secret:qbo', credential_revision='v1',
                            principal_ref='principal:synthetic')
        self.intent = q.ReadIntent.create('case:synthetic', 'r1', self.binding, '42', self.secrets)
        self.body = {'Invoice': {'Id': '42', 'SyncToken': '0', 'TxnDate': '2026-11-07',
                                'CustomerRef': {'value': 'private'}, 'Line': ['private']}}

    def read(self, status=200, body=None, content_type='application/json'):
        raw = json.dumps(self.body if body is None else body).encode() if not isinstance(body, bytes) else body
        return q.read(self.intent, self.binding, self.secrets, lambda _: 'synthetic-token',
                      send=lambda url, token: (status, content_type, raw))

    def test_exact_get_projection_and_immutable_observation(self):
        calls = []
        def send(url, token):
            calls.append((url, token))
            return 200, 'application/json', json.dumps(self.body).encode()
        result = q.read(self.intent, self.binding, self.secrets, lambda _: 'synthetic-token', send=send)
        self.assertEqual(calls, [('https://sandbox-quickbooks.api.intuit.com/v3/company/123/invoice/42?minorversion=75', 'synthetic-token')])
        self.assertEqual((result.status, result.sync_token, result.transaction_date), ('observed_object', '0', '2026-11-07'))
        self.assertNotIn('private', repr(result))
        self.assertNotIn('synthetic-token', repr(result))
        with self.assertRaises(FrozenInstanceError): result.status = 'changed'
        self.body['Invoice']['SyncToken'] = '1'
        later = self.read()
        self.assertEqual(result.sync_token, '0')
        self.assertEqual(later.sync_token, '1')

    def test_statuses(self):
        for code, expected in [(401,'authentication_required'),(403,'authentication_required'),
                               (404,'not_observed'),(429,'throttled'),(500,'unavailable'),
                               (503,'unavailable'),(302,'request_rejected'),(400,'request_rejected')]:
            with self.subTest(code=code): self.assertEqual(self.read(code).status, expected)
        self.assertEqual(self.read(429).retry_after_seconds, 60)

    def test_protocol_rejection(self):
        cases = [b'{"Invoice":{},"Invoice":{}}', b'{"number":NaN}', b'{"number":1e999}', b'\xff', b'['*2000,
                 b'x'*(q.MAX_BODY+1), {}, {'Fault': {}}, {'Invoice':{}, 'Fault':{}},
                 {'Invoice': {'Id':'43','SyncToken':'0','TxnDate':'2026-11-07'}},
                 {'Invoice': {'Id':'42','SyncToken':0,'TxnDate':'2026-11-07'}},
                 {'Invoice': {'Id':'42','SyncToken':'0','TxnDate':'2026-02-30'}}]
        for body in cases:
            with self.subTest(body=str(body)[:80]): self.assertEqual(self.read(body=body).status, 'protocol_mismatch')
        self.assertEqual(self.read(content_type='text/html').status, 'protocol_mismatch')

    def test_binding_fail_closed(self):
        for key, bad in [('enabled',False),('realm','123/other'),('environment','https://evil'),
                         ('entity','query'),('minor_version','75&query=x'),('credential_revision','v2')]:
            value = dict(self.binding, **{key:bad})
            with self.subTest(key=key), self.assertRaises(ValueError):
                q.read(self.intent, value, self.secrets, lambda _: 'synthetic-token', send=lambda *_: self.fail('network'))
        with self.assertRaises(ValueError):
            q.read(replace(self.intent, object_id='../42'), self.binding, self.secrets, lambda _: 'token')

    def test_direct_transport_rejects_other_targets_and_bad_secrets(self):
        for url in ('https://example.org',
                    'https://quickbooks.api.intuit.com/v3/company/123/query?query=x',
                    'https://quickbooks.api.intuit.com/v3/company/123/invoice/42?minorversion=75&x=y'):
            with self.assertRaises(ValueError): q.transport(url, 'synthetic')
        for token in ('', 'bad\nheader', 'x'*4097, 'nonascii-é'):
            with self.assertRaises(ValueError):
                q.read(self.intent, self.binding, self.secrets, lambda _: token,
                       send=lambda *_: self.fail('network called'))

    def test_timeout_no_retry(self):
        calls = []
        def send(*args):
            calls.append(1)
            raise TimeoutError('secret provider response')
        result = q.read(self.intent, self.binding, self.secrets, lambda _: 'token', send=send)
        self.assertEqual(result.status, 'unavailable')
        self.assertEqual(len(calls), 1)
        self.assertNotIn('secret provider', repr(result))

    def test_http_protocol_errors_are_sanitized(self):
        for error in (BadStatusLine('private response'), IncompleteRead(b'private response'), LineTooLong('private response')):
            def send(*_, error=error): raise error
            result = q.read(self.intent, self.binding, self.secrets, lambda _: 'synthetic', send=send)
            self.assertEqual(result.status, 'unavailable')
            self.assertNotIn('private response', repr(result))

    def test_http_error_closed_without_reading(self):
        from unittest.mock import Mock
        stream = Mock()
        error = q.urllib.error.HTTPError('https://example.invalid', 401, 'private', {}, stream)
        with patch.object(q.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = error
            result = q.transport('https://sandbox-quickbooks.api.intuit.com/v3/company/123/invoice/42?minorversion=75', 'synthetic')
        self.assertEqual(result, (401, '', b''))
        stream.close.assert_called_once()
        stream.read.assert_not_called()

    def test_optional_registry_and_disabled_config(self):
        old = dict(endpoints={}, secrets=self.secrets, finance_senders={})
        self.assertIs(validate_registry(old), old)
        new = dict(old, quickbooks_reads={'qbo:optional': dict(self.binding, enabled=False)})
        self.assertIs(validate_registry(new), new)
        for key, value in [('enabled',1),('realm',''),('extra','x')]:
            bad = copy.deepcopy(new)
            bad['quickbooks_reads']['qbo:optional'][key] = value
            with self.assertRaises(RuntimeError): validate_registry(bad)

    def test_transport_get_timeout_no_proxy_redirects(self):
        class Response:
            status = 200
            class headers:
                @staticmethod
                def get_content_type(): return 'application/json'
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def read(self, size):
                self.size = size
                return b'{}'
        response = Response()
        with patch.object(q.urllib.request, 'build_opener') as build:
            build.return_value.open.return_value = response
            q.transport('https://sandbox-quickbooks.api.intuit.com/v3/company/123/invoice/42?minorversion=75', 'synthetic')
            handlers = build.call_args.args
            self.assertEqual(handlers[0].proxies, {})
            self.assertIsNone(handlers[1].redirect_request())
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertIsNone(request.data)
            self.assertEqual(build.return_value.open.call_args.kwargs, {'timeout':5})
            self.assertEqual(response.size, q.MAX_BODY+1)
