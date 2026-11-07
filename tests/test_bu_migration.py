"""Literal additive BU migration retains the exact accepted actual0075 graph."""
import ast,hashlib,re
from pathlib import Path
from importlib import import_module
from django.test import SimpleTestCase
from django.db.migrations.loader import MigrationLoader

class BUMigrationTests(SimpleTestCase):
    def test_exact_literal_predecessor_and_no_document_migration(self):
        prior=import_module('apps.workflows.migrations.0075_factory_engagement');current=import_module('apps.workflows.migrations.0076_factory_bu')
        self.assertEqual(hashlib.sha256(Path(prior.__file__).read_bytes()).hexdigest(),'b8ce004f77cc9e5893fbe6c4dc679a3a33d4325b1de38a07ce2a82425a1d4957')
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertTrue(current.REVERSE.startswith(prior.SQL))
        self.assertEqual(current.Migration.dependencies,[('workflows','0075_factory_engagement')])
        tree=ast.parse(Path(current.__file__).read_text());imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'django.db')
        for n in tree.body:
            if isinstance(n,ast.Assign):self.assertIsInstance(n.value,ast.Constant)
        loader=MigrationLoader(None);plan=loader.graph.forwards_plan(('workflows','0076_factory_bu'))
        for node in [('workflows','0073_factory_escalation'),('workflows','0074_factory_minutes'),('workflows','0075_factory_engagement'),('documents','0028_factory_minutes')]:self.assertIn(node,plan)
        self.assertNotIn(('documents','0029_factory_bu'),loader.graph.nodes)
    def test_every_existing_nonidentity_function_is_byte_identical(self):
        prior=import_module('apps.workflows.migrations.0075_factory_engagement').SQL;current=import_module('apps.workflows.migrations.0076_factory_bu').SQL
        blocks=re.findall(r'CREATE OR REPLACE FUNCTION .*?\$\$;',prior,re.S)
        self.assertGreater(len(blocks),20)
        for block in blocks:
            if not block.startswith('CREATE OR REPLACE FUNCTION psl_factory_identity()'):self.assertIn(block,current)
        for name in ['private','authority','current','review']:self.assertEqual(current.count('CREATE OR REPLACE FUNCTION psl_bu_'+name+'('),1)
