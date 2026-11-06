"""The accepted forecast graph is extended without mutable runtime imports."""
from importlib import import_module
from pathlib import Path
from django.test import SimpleTestCase


class PPEMigrationCompositionTests(SimpleTestCase):
    def test_exact_additive_guard_preserves_accepted_forecast_sql(self):
        migration=import_module('apps.workflows.migrations.0068_factory_ppe')
        previous=import_module('apps.workflows.migrations.0067_factory_forecast').SQL
        self.assertEqual(migration.PREVIOUS,previous)
        restored=migration.SQL.removeprefix(migration.FUNCTIONS).replace(migration.SOURCE,'',1).replace(migration.VERIFIED,'',1)
        restored=restored.replace(",'finance-ppe/v1'",'',1).replace(" WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution'",'',1)
        self.assertEqual(restored,previous)
        self.assertEqual(migration.Migration.operations[0].reverse_sql,previous)
        self.assertEqual(migration.Migration.dependencies,[('workflows','0067_factory_forecast')])
        self.assertNotIn('ppe_factory_guard',Path(migration.__file__).read_text())

    def test_shared_definitions_retain_all_predecessor_envelopes(self):
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.policy.operator_validators import SCHEMAS
        expected={'finance-ppe/v1':'OPS.factory_ppe_execution',
                  'finance-payroll/v1':'OPS.factory_payroll_execution',
                  'finance-forecast/v1':'OPS.factory_forecast_execution',
                  'pmo-emergency/v1':'OPS.factory_emergency_execution',
                  'pmo-change/v1':'OPS.factory_change_execution'}
        for envelope,component in expected.items():
            with self.subTest(envelope=envelope):
                self.assertEqual(DEFINITIONS[envelope]['component'],component)
                self.assertIn(component,SCHEMAS)
