"""Exact accepted-parent function delta, without replaying unrelated triggers."""
import ast,hashlib,re
from pathlib import Path
from importlib import import_module
from django.test import SimpleTestCase
from scripts.statement_ppe_guard import extend

class StatementPPEMigrationTests(SimpleTestCase):
    def test_literal_functions_preserve_exact_parent_clauses(self):
        for app,parent,current,function,digest,publication in [
            ('workflows','0078_factory_leadership','0079_statement_ppe_verification','psl_factory_identity','24e2d4f633807c4c94415646a5a5fcaabd38068bf4676497732b7598070df295',False),
            ('documents','0029_factory_leadership','0030_statement_ppe_scope','psl_publication_factory_scope','20d2ce21b7ec0f9334539904f5e202161780a7a80c559940e0d179703d60a682',True)]:
            prior=import_module(f'apps.{app}.migrations.{parent}');new=import_module(f'apps.{app}.migrations.{current}')
            self.assertEqual(hashlib.sha256(Path(prior.__file__).read_bytes()).hexdigest(),digest)
            bodies=re.findall(r'CREATE OR REPLACE FUNCTION '+function+r'\(\).*?\$\$;',prior.SQL,re.S)
            self.assertEqual(bodies,[new.PREVIOUS]);self.assertEqual(new.SQL,extend(new.PREVIOUS,publication))
            self.assertNotIn('CREATE TRIGGER',new.SQL)
            tree=ast.parse(Path(new.__file__).read_text())
            imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
            self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'django.db')
            for node in tree.body:
                if isinstance(node,ast.Assign):self.assertIsInstance(node.value,ast.Constant)

class StatementPPEKindValidationTests(SimpleTestCase):
    def test_kind_only_objects_are_classification_not_persisted_authority(self):
        from types import SimpleNamespace
        from apps.core.evidence_access import restricted,ppe_statement_private
        for kind in ['ppe_register','finance_report_snapshot','policy_decision']:
            obj=SimpleNamespace(kind=kind)
            self.assertFalse(ppe_statement_private(obj));self.assertFalse(restricted(obj))
        for kind in ['ledger_source','agent_private_ledger_intake','forecast_source']:
            self.assertTrue(restricted(SimpleNamespace(kind=kind)))
        claim=SimpleNamespace(kind='finance_report_snapshot',source='derived:ppe-statement:1')
        self.assertTrue(restricted(claim))
        # This class is database-forbidden: kind-only classification performs no model lookup.
        # Native persisted-proof and unsaved-forgery rejection are exercised in StatementPPETests.
