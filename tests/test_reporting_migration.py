"""Actual immutable P41 composition; does not stand in for PostgreSQL migration proof."""
import ast
import hashlib
from importlib import import_module
from pathlib import Path
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase
from tests import reporting_guard_sql as proposed

class ReportingMigrationTests(SimpleTestCase):
    def test_exact_frozen_composition_and_predecessor_function_are_retained(self):
        workflow=import_module('apps.workflows.migrations.0072_factory_weekly_report')
        document=import_module('apps.documents.migrations.0025_factory_weekly_report')
        self.assertEqual(workflow.SQL,proposed.SQL)
        self.assertEqual(workflow.PREVIOUS,proposed.PREVIOUS)
        self.assertEqual(document.SQL,proposed.DOCUMENT_SQL)
        self.assertEqual(document.PREVIOUS,proposed.PREVIOUS_DOCUMENT)
        self.assertEqual(document.SQL.replace(proposed.BRANCH,'',1),document.PREVIOUS)
        self.assertTrue(workflow.REVERSE.startswith(workflow.PREVIOUS))

    def test_no_mutable_application_sql_is_imported(self):
        for path in ['apps/workflows/migrations/0072_factory_weekly_report.py','apps/documents/migrations/0025_factory_weekly_report.py']:
            tree=ast.parse(Path(path).read_text())
            imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
            self.assertEqual(len(imports),1)
            self.assertIsInstance(imports[0],ast.ImportFrom)
            self.assertEqual(imports[0].module,'django.db')

    def test_every_accepted_predecessor_migration_keeps_exact_bytes(self):
        expected={
            'apps/workflows/migrations/0068_factory_ppe.py':'513426d1ca9cf9db872cc7828fa00e05eabbfbc98460dee196839ae249e117ab',
            'apps/workflows/migrations/0068_ppe_identity_dependency_replacement.py':'3dc0227f8b1fc26eeeaea916f06a1c29042fbae86e8a086a86318f492250af24',
            'apps/workflows/migrations/0071_factory_group_forecast.py':'1b44a99fddba6861744fc792bab61c2ca03dcd95258d5f624eeb630dc9454b9e',
            'apps/documents/migrations/0024_group_forecast_guard.py':'d04fb17544411a5041a89c84a254981ff8c57823d965ceab4d22c5c1d1796728'}
        for path,sha in expected.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),sha)

    def test_full_document_graph_requires_identity_before_ppe_replacement(self):
        loader=MigrationLoader(None)
        plan=loader.graph.forwards_plan(('documents','0025_factory_weekly_report'))
        identity=('identity','0001_initial')
        replacement=('workflows','0068_ppe_identity_dependency_replacement')
        self.assertLess(plan.index(identity),plan.index(replacement))
        self.assertLess(plan.index(replacement),plan.index(('workflows','0072_factory_weekly_report')))
        self.assertNotIn(('workflows','0068_factory_ppe'),plan)
