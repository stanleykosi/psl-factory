"""Isolated production provenance/secret helpers; not ORM integration acceptance."""
import ast
import hashlib
import hmac
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class NativeReadHelperTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parents[1] / 'apps/finance/quickbooks_read.py'
        tree = ast.parse(path.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('authentic','credential_pin')]
        self.evidence = SimpleNamespace(pk=3, body='{"x":1}', created_by='actor', sha256=hashlib.sha256(b'{"x":1}').hexdigest())
        self.Evidence, self.Audit = Mock(), Mock()
        self.Evidence.objects.filter.return_value.first.return_value = self.evidence
        self.Audit.objects.filter.return_value.exists.return_value = True
        self.settings = SimpleNamespace(SECRET_KEY='synthetic-key', READINESS_SECRET_REFS={'secret:qbo':{'env':'SYNTHETIC_TEST_ONLY'}})
        self.ns = dict(Evidence=self.Evidence, Audit=self.Audit, ValidationError=ValueError,
                       hashlib=hashlib,hmac=hmac,json=json,os=os,settings=self.settings,PREFIX='ledger.qbo.')
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'), self.ns)

    def test_exact_service_anchor_required(self):
        evidence, payload = self.ns['authentic']('case',3,'qbo_native_intent')
        self.assertEqual(payload, {'x':1})
        self.Evidence.objects.filter.assert_called_with(case='case',pk=3,kind='qbo_native_intent',source='native:qbo-read/v1')
        self.Audit.objects.filter.assert_called_with(case='case',actor='actor',action='ledger.qbo.qbo_native_intent',data__evidence=3,data__sha256=evidence.sha256)
        self.Audit.objects.filter.return_value.exists.return_value = False
        with self.assertRaises(ValueError): self.ns['authentic']('case',3,'qbo_native_intent')

    def test_body_tampering_and_missing_record_rejected(self):
        self.evidence.body = '{"forged":true}'
        with self.assertRaises(ValueError): self.ns['authentic']('case',3,'qbo_native_intent')
        self.Evidence.objects.filter.return_value.first.return_value = None
        with self.assertRaises(ValueError): self.ns['authentic']('case',3,'qbo_native_intent')

    def test_keyed_rotation_and_missing_secret(self):
        value = {'credential_ref':'secret:qbo'}
        with patch.dict(os.environ, {'SYNTHETIC_TEST_ONLY':'synthetic-one'}):
            first = self.ns['credential_pin'](value)
        with patch.dict(os.environ, {'SYNTHETIC_TEST_ONLY':'synthetic-two'}):
            second = self.ns['credential_pin'](value)
        self.assertNotEqual(first, second)
        self.assertNotIn('synthetic', first)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): self.ns['credential_pin'](value)
