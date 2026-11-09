"""Actual P56 migration contracts; no provisional schema substitutes or runtime SQL helpers."""
import ast
import re
from importlib import import_module
from pathlib import Path
from django.db import connection, migrations, models
from django.test import SimpleTestCase, TestCase


MIGRATION = 'apps.workflows.migrations.0070_change_intake_confirmation'


class ChangeIntakeMigrationTests(SimpleTestCase):
    def test_exact_0069_dependency_and_additive_operations(self):
        migration = import_module(MIGRATION)
        self.assertEqual([item for item in migration.Migration.dependencies if item[0] == 'workflows'],
                         [('workflows', '0069_factory_schedules')])
        operations = migration.Migration.operations
        self.assertEqual([type(operation) for operation in operations], [migrations.CreateModel, migrations.RunSQL])
        self.assertEqual(operations[0].name, 'ChangeIntakeConfirmation')
        self.assertEqual(operations[1].sql, migration.SQL)
        self.assertEqual(operations[1].reverse_sql, migration.REVERSE_SQL)

    def test_frozen_literals_match_reviewed_guard_without_runtime_imports(self):
        migration = import_module(MIGRATION)
        source = Path(migration.__file__).read_text()
        tree = ast.parse(source)
        for name in ['SQL', 'REVERSE_SQL']:
            assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                              and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))
            self.assertIsInstance(assignment.value, ast.Constant)
            self.assertIsInstance(assignment.value.value, str)
        # The reviewed file retains its historical provisional header. The final
        # migration must embed the exact reviewed executable SQL, not load it.
        reviewed = (Path(__file__).resolve().parents[1] / 'docs/design/p56-change-intake-guard.sql').read_text()
        reviewed = reviewed[reviewed.index('CREATE FUNCTION psl_change_intake_confirmation()'):]
        self.assertEqual(migration.SQL.strip(), reviewed.strip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name.startswith('django.') for alias in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertTrue((node.module or '').startswith('django.'))
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
                self.assertNotIn(name, ['open', 'read_text', 'read_bytes', 'import_module', '__import__', 'exec', 'eval'])

    def test_sql_creates_only_own_guard_and_triggers_without_replacing_shared_factory_function(self):
        migration = import_module(MIGRATION)
        self.assertEqual(re.findall(r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)', migration.SQL, re.I),
                         ['psl_change_intake_confirmation'])
        self.assertNotRegex(migration.SQL, r'(?i)CREATE\s+OR\s+REPLACE|\b(?:ALTER|DROP)\s+(?:TABLE|FUNCTION|TRIGGER)')
        self.assertEqual(re.findall(r'CREATE\s+TRIGGER\s+(\w+).*?\sON\s+(\w+)', migration.SQL, re.I),
                         [('psl_change_intake_binding', 'workflows_changeintakeconfirmation'),
                          ('psl_immutable', 'workflows_changeintakeconfirmation')])
        self.assertEqual(re.findall(r'DROP\s+FUNCTION\s+(\w+)', migration.REVERSE_SQL, re.I),
                         ['psl_change_intake_confirmation'])
        self.assertEqual(re.findall(r'DROP\s+TRIGGER\s+(\w+)\s+ON\s+(\w+)', migration.REVERSE_SQL, re.I),
                         [('psl_change_intake_binding', 'workflows_changeintakeconfirmation'),
                          ('psl_immutable', 'workflows_changeintakeconfirmation')])
        self.assertNotRegex(migration.REVERSE_SQL, r'(?i)DROP\s+TABLE|CASCADE')

    def test_frozen_model_preserves_exact_unique_bindings_and_nullable_handoffs(self):
        operation = import_module(MIGRATION).Migration.operations[0]
        fields = dict(operation.fields)
        self.assertEqual(set(fields), {'id', 'payload', 'sha256', 'authority', 'created_at',
                                       'actor', 'extraction', 'receipt', 'version', 'work'})
        for name, target, nullable in [('receipt', 'core.audit', False), ('version', 'pmo.changeversion', False),
                                       ('work', 'workflows.factorywork', True), ('extraction', 'agents.agentrun', True)]:
            with self.subTest(field=name):
                field = fields[name]
                self.assertEqual(field.remote_field.model, target)
                self.assertEqual(field.null, nullable)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
                self.assertEqual(field.one_to_one, name != 'extraction')
        self.assertIs(fields['actor'].remote_field.on_delete, models.PROTECT)
        self.assertEqual(fields['sha256'].max_length, 64)
        self.assertTrue(fields['created_at'].auto_now_add)
        for name in ['payload', 'authority']: self.assertIsInstance(fields[name], models.JSONField)


class InstalledChangeIntakeMigrationTests(TestCase):
    def test_actual_graph_installs_enabled_provenance_and_immutability_triggers(self):
        self.assertEqual(connection.vendor, 'postgresql')
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM django_migrations WHERE app='workflows' AND name IN (%s,%s) ORDER BY name",
                           ['0069_factory_schedules', '0070_change_intake_confirmation'])
            self.assertEqual([row[0] for row in cursor.fetchall()],
                             ['0069_factory_schedules', '0070_change_intake_confirmation'])
            cursor.execute("""SELECT t.tgname, p.proname, t.tgenabled, pg_get_triggerdef(t.oid)
                              FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
                              WHERE t.tgrelid='workflows_changeintakeconfirmation'::regclass AND NOT t.tgisinternal
                              ORDER BY t.tgname""")
            triggers = {row[0]: row[1:] for row in cursor.fetchall()}
            self.assertEqual(set(triggers), {'psl_change_intake_binding', 'psl_immutable'})
            self.assertEqual(triggers['psl_change_intake_binding'][:2], ('psl_change_intake_confirmation', 'O'))
            self.assertIn('BEFORE INSERT', triggers['psl_change_intake_binding'][2])
            self.assertEqual(triggers['psl_immutable'][:2], ('psl_append_only', 'O'))
            self.assertIn('BEFORE DELETE OR UPDATE', triggers['psl_immutable'][2])
            cursor.execute("SELECT prosrc FROM pg_proc WHERE oid='psl_change_intake_confirmation()'::regprocedure")
            installed_body = cursor.fetchone()[0]
            reviewed_body = import_module(MIGRATION).SQL.split('AS $$', 1)[1].split('$$;', 1)[0]
            self.assertEqual(installed_body, reviewed_body)
