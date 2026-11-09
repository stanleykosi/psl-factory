"""Actual F01 migration extends the exact accepted BU boundary, never a harness."""
import ast,hashlib,re
from pathlib import Path
from importlib import import_module
from django.test import SimpleTestCase
from django.db.migrations.loader import MigrationLoader

class LedgerFactoryMigrationTests(SimpleTestCase):
    def test_frozen_actual_predecessor_and_no_document_migration(self):
        prior=import_module('apps.workflows.migrations.0076_factory_bu');current=import_module('apps.workflows.migrations.0077_factory_ledger')
        self.assertEqual(hashlib.sha256(Path(prior.__file__).read_bytes()).hexdigest(),'2471139a26327959d72da95ad60cd06b0b4109c999586828657d1d9ad7eaea68')
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertTrue(current.REVERSE.startswith(prior.SQL))
        self.assertEqual(current.Migration.dependencies,[('workflows','0076_factory_bu')])
        tree=ast.parse(Path(current.__file__).read_text());imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'django.db')
        for node in tree.body:
            if isinstance(node,ast.Assign):self.assertIsInstance(node.value,ast.Constant)
        loader=MigrationLoader(None);plan=loader.graph.forwards_plan(('workflows','0077_factory_ledger'))
        for node in [('workflows','0074_factory_minutes'),('workflows','0075_factory_engagement'),('workflows','0076_factory_bu'),('documents','0028_factory_minutes')]:self.assertIn(node,plan)
        self.assertNotIn(('documents','0029_factory_ledger'),loader.graph.nodes)
    def test_old_guards_are_exact_and_extension_matches_reviewed_source(self):
        prior=import_module('apps.workflows.migrations.0076_factory_bu').SQL;current=import_module('apps.workflows.migrations.0077_factory_ledger').SQL
        from apps.workflows.ledger_factory_guard import SQL
        expected=prior.replace('NEW.definition NOT IN (',"NEW.definition NOT IN ('finance-ledger/v1',",1).replace('CASE NEW.definition ',"CASE NEW.definition WHEN 'finance-ledger/v1' THEN 'OPS.factory_ledger_execution' ",1)+'\n'+SQL
        self.assertEqual(current,expected)
        blocks=re.findall(r'CREATE OR REPLACE FUNCTION .*?\$\$;',prior,re.S)
        self.assertGreater(len(blocks),20)
        for block in blocks:
            if not block.startswith('CREATE OR REPLACE FUNCTION psl_factory_identity()'):self.assertIn(block,current)
