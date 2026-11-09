"""Actual predecessor-only additive P40/P42 migration source contract."""
import ast,hashlib,re
from importlib import import_module
from pathlib import Path
from django.test import SimpleTestCase

class LeadershipMigrationTests(SimpleTestCase):
    def test_frozen_predecessors_and_literal_only_migrations(self):
        prior=import_module('apps.workflows.migrations.0077_factory_ledger')
        current=import_module('apps.workflows.migrations.0078_factory_leadership')
        docprior=import_module('apps.documents.migrations.0028_factory_minutes')
        doc=import_module('apps.documents.migrations.0029_factory_leadership')
        self.assertEqual(hashlib.sha256(Path(prior.__file__).read_bytes()).hexdigest(),'52be3cf793c1ff78db96ed99b57bc99ebd880114e79d07dd0edda7fa19068f88')
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertEqual(doc.PREVIOUS,docprior.SQL);self.assertEqual(doc.REVERSE,docprior.SQL)
        for module in [current,doc]:
            tree=ast.parse(Path(module.__file__).read_text());imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
            self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'django.db')
            for node in tree.body:
                if isinstance(node,ast.Assign):self.assertIsInstance(node.value,ast.Constant)
        self.assertIn(('workflows','0077_factory_ledger'),current.Migration.dependencies)
        self.assertIn(('documents','0028_factory_minutes'),current.Migration.dependencies)
        self.assertEqual(doc.Migration.dependencies,[('documents','0028_factory_minutes'),('workflows','0078_factory_leadership')])
    def test_no_legacy_function_or_trigger_replacement_except_identity(self):
        current=import_module('apps.workflows.migrations.0078_factory_leadership')
        functions=re.findall(r'CREATE OR REPLACE FUNCTION (\w+)\(',current.SQL)
        self.assertTrue(functions)
        self.assertTrue(all(name=='psl_factory_identity' or name.startswith('psl_leadership_') or name=='psl_factory_leadership_guard' for name in functions))
        self.assertNotIn('CREATE TRIGGER factory_ledger_guard',current.SQL)
