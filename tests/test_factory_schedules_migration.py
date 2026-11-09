"""Actual immutable schedule migration and retained predecessor registrations."""
import ast
from importlib import import_module
from pathlib import Path
from django.test import SimpleTestCase,TestCase
from django.db import connection

class SchedulesMigrationTests(SimpleTestCase):
    def test_immutable_literal_sql_matches_reviewed_additive_extension(self):
        from apps.workflows.schedules_factory_guard import extend
        migration=import_module('apps.workflows.migrations.0069_factory_schedules')
        previous=import_module('apps.workflows.migrations.0068_factory_ppe').SQL
        self.assertEqual(migration.SQL,extend(previous))
        tree=ast.parse(Path(migration.__file__).read_text())
        sql=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SQL' for t in n.targets))
        self.assertIsInstance(sql.value,ast.Constant)
        self.assertNotIn('schedules_factory_guard',Path(migration.__file__).read_text())
        self.assertEqual(migration.Migration.dependencies,[('workflows','0068_factory_ppe')])
        self.assertEqual(migration.Migration.operations[0].reverse_sql,previous)
    def test_shared_registrations_preserve_predecessors(self):
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.policy.operator_validators import SCHEMAS
        for name in ['schedules','ppe','forecast','payroll']:
            key='OPS.factory_'+name+'_execution'
            self.assertEqual(DEFINITIONS['finance-'+name+'/v1']['component'],key)
            self.assertIn(key,SCHEMAS)

class InstalledSchedulesMigrationTests(TestCase):
    def test_actual_0069_is_installed_without_provisional_override(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM django_migrations WHERE app='workflows' AND name IN ('0067_factory_forecast','0068_factory_ppe','0069_factory_schedules') ORDER BY name")
            self.assertEqual([r[0] for r in cursor.fetchall()],['0067_factory_forecast','0068_factory_ppe','0069_factory_schedules'])
            cursor.execute("SELECT pg_get_functiondef('psl_schedules_policy_pin_current(uuid,text,jsonb)'::regprocedure)")
            self.assertIn('psl_schedules_policy_status',cursor.fetchone()[0])
