"""Bounded ordering repair checks; no mutation of migration history or business rows."""
import hashlib
from importlib import import_module
from pathlib import Path
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase,TestCase

OLD=('workflows','0068_factory_ppe')
NEW=('workflows','0068_ppe_identity_dependency_replacement')

class PPEReplacementPlanTests(SimpleTestCase):
    def test_historical_migration_bytes_unchanged(self):
        path=Path(import_module('apps.workflows.migrations.0068_factory_ppe').__file__)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'513426d1ca9cf9db872cc7828fa00e05eabbfbc98460dee196839ae249e117ab')
    def test_exact_immutable_operations_and_minimal_dependencies(self):
        original=import_module('apps.workflows.migrations.0068_factory_ppe').Migration
        replacement=import_module('apps.workflows.migrations.0068_ppe_identity_dependency_replacement').Migration
        self.assertIs(replacement.operations,original.operations)
        self.assertEqual(replacement.replaces,[OLD])
        self.assertEqual(replacement.dependencies,[('workflows','0067_factory_forecast'),('identity','0001_initial')])
    def test_fresh_plan_applies_original_operations_exactly_once_after_identity(self):
        loader=MigrationLoader(None,ignore_no_migrations=True)
        executor=MigrationExecutor.__new__(MigrationExecutor);executor.loader=loader
        plan=executor.migration_plan(loader.graph.leaf_nodes(),clean_start=True)
        keys=[(m.app_label,m.name) for m,backwards in plan]
        self.assertNotIn(OLD,keys);self.assertEqual(keys.count(NEW),1)
        self.assertLess(keys.index(('identity','0001_initial')),keys.index(NEW))
        self.assertLess(keys.index(NEW),keys.index(('workflows','0069_factory_schedules')))
        self.assertTrue(all(not backwards for _,backwards in plan))
    def test_latest_actual_document_graph_has_no_duplicate_replacement_leaf(self):
        loader=MigrationLoader(None,ignore_no_migrations=True)
        self.assertNotIn(OLD,loader.graph.nodes)
        self.assertIn(NEW,loader.graph.forwards_plan(('workflows','0071_factory_group_forecast')))
        self.assertNotIn(NEW,loader.graph.leaf_nodes())

class PPEReplacementDatabaseTests(TestCase):
    def test_applied_original_and_replacement_have_consistent_history(self):
        loader=MigrationLoader(connection);loader.check_consistent_history(connection)
        applied=MigrationRecorder(connection).applied_migrations()
        self.assertIn(OLD,applied);self.assertIn(NEW,applied)
        self.assertIn(NEW,loader.applied_migrations)
    def test_expected_identity_table_and_unchanged_ppe_helpers_exist(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.identity_grant'),to_regprocedure('psl_ppe_policy_people_current(bigint)'),to_regprocedure('psl_ppe_policy_current(uuid,bigint)')")
            self.assertTrue(all(cursor.fetchone()))
