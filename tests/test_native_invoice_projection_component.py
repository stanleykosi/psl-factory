"""Actual source adapter/projection functions with a synthetic read-only connection."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


class SourceProjectionTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).parents[1]
        def function(path,name):
            tree=ast.parse((root/path).read_text())
            return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        self.digest=digest
        self.ns={'SimpleNamespace':SimpleNamespace,'ValidationError':ValueError,'n':SimpleNamespace(digest=digest),'VARIANTS':('issue','deliver','adjust','adjust_deliver')}
        for path,name in [('apps/finance/invoices.py','delivery_payload'),('adapters/native_invoice_receipts.py','document')]:
            exec(compile(ast.Module(body=[function(path,name)],type_ignores=[]),path,'exec'),self.ns)
        self.payload=dict(reference='INV',version=1,customer='customer',contract='contract',currency='GBP',amount='10',amount_basis='net',due_date='2026-11-20',contract_period='2026-11',lines=[{'total':'10','private':'hidden'}])
        self.invoice=dict(id=1,case_id='synthetic-case',preparation_id=9,payload=self.payload,sha256=digest(self.payload))
        self.job=dict(kind='deliver',operation_key='invoice:1:deliver:g1',generation=1,intent={})

    def call(self, preparation=(9,'synthetic-case','usage'), corrupt_hash=False):
        expected=self.ns['delivery_payload'](SimpleNamespace(payload=self.payload,preparation=SimpleNamespace(kind='fixed_contract' if preparation and preparation[2]=='fixed_contract' else 'usage')))
        self.job['intent']['delivery_hash']='wrong' if corrupt_hash else self.digest(expected)
        calls=[]
        rows=[(self.job,self.invoice,'row-hash'),preparation]
        def execute(sql,args):
            calls.append((sql,args))
            return SimpleNamespace(fetchone=lambda:rows.pop(0))
        result=self.ns['document'](SimpleNamespace(execute=execute),12,'synthetic-case',10000)
        return result,calls

    def test_exact_source_join_and_nonfixed_projection(self):
        result,calls=self.call()
        self.assertEqual(len(calls),2)
        sql,args=calls[1]
        self.assertIn('p.id=source_invoice.preparation_id AND p.case_id=source_invoice.case_id',sql)
        self.assertIn('octet_length(p.kind)<=30',sql)
        self.assertEqual(args,[1,'synthetic-case',9,10000])
        self.assertNotIn('contract_period',result[3])
        self.assertEqual(result[3]['lines'],[{'total':'10'}])

    def test_fixed_contract_retains_exact_period(self):
        result,_=self.call((9,'synthetic-case','fixed_contract'))
        self.assertEqual(result[3]['contract_period'],'2026-11')

    def test_missing_wrong_case_wrong_id_unknown_kind_rejected(self):
        for prep in (None,(8,'synthetic-case','usage'),(9,'another-case','usage'),(9,'synthetic-case','guess'),(True,'synthetic-case','usage')):
            with self.subTest(prep=prep),self.assertRaises(ValueError):self.call(prep)

    def test_original_invoice_and_delivery_hash_guards_unchanged(self):
        with self.assertRaises(ValueError):self.call(corrupt_hash=True)
        self.invoice['sha256']='wrong'
        with self.assertRaises(ValueError):self.call()
