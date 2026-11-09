"""Actual P44 composition, no provisional migration modules."""
import hashlib
from importlib import import_module
from pathlib import Path
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase

class EscalationMigrationTests(SimpleTestCase):
    def test_exact_frozen_workflow_predecessor_and_closed_extension(self):
        prior=import_module('apps.workflows.migrations.0072_factory_weekly_report')
        current=import_module('apps.workflows.migrations.0073_factory_escalation')
        from apps.workflows.escalation_factory_guard import FUNCTIONS,work_sql
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertEqual(current.SQL,FUNCTIONS+work_sql(prior.SQL))
        self.assertEqual(hashlib.sha256(Path(prior.__file__).read_bytes()).hexdigest(),'2f27f39702331f5e6d8e874e998cd573b4c070d576476ced7359afea0d128ec8')
        self.assertEqual(current.Migration.dependencies,[('workflows','0072_factory_weekly_report'),('identity','0001_initial'),('documents','0026_group_forecast_business_date')])
    def test_exact_frozen_document_predecessor_and_closed_extension(self):
        prior=import_module('apps.documents.migrations.0025_factory_weekly_report')
        current=import_module('apps.documents.migrations.0027_factory_escalation')
        from apps.workflows.escalation_factory_guard import document_sql
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertEqual(current.SQL,document_sql(prior.SQL));self.assertEqual(current.REVERSE,prior.SQL)
        self.assertEqual(hashlib.sha256(Path(prior.__file__).read_bytes()).hexdigest(),'89b3ce61813ad88b52768a1d8c1febea787e39a04ad8f466471047f3026cd863')
        datefix=import_module('apps.documents.migrations.0026_group_forecast_business_date')
        self.assertEqual(hashlib.sha256(Path(datefix.__file__).read_bytes()).hexdigest(),'a2a54824f25db90f8d729fd5c04cdf7c4b150e0b0541bf2ed534a7227aae3c21')
        self.assertEqual(datefix.Migration.dependencies,[('documents','0025_factory_weekly_report')])
        self.assertEqual(current.Migration.dependencies,[('documents','0026_group_forecast_business_date'),('workflows','0073_factory_escalation')])
        self.assertNotIn('psl_group_forecast_publication',current.SQL)
        self.assertNotIn('psl_group_forecast_business_date',current.SQL)
    def test_migrations_import_no_mutable_helpers(self):
        for name in ['apps.workflows.migrations.0073_factory_escalation','apps.documents.migrations.0027_factory_escalation']:
            module=import_module(name);text=Path(module.__file__).read_text()
            self.assertNotIn('import_module',text);self.assertNotIn('escalation_factory_guard',text)
            self.assertEqual(len(module.Migration.operations),1)
            self.assertEqual(module.Migration.operations[0].sql,module.SQL)
    def test_actual_graph_preserves_identity_replacement_and_precursor_order(self):
        loader=MigrationLoader(None,ignore_no_migrations=True)
        plan=loader.graph.forwards_plan(('documents','0027_factory_escalation'))
        ordered=[('identity','0001_initial'),('workflows','0068_ppe_identity_dependency_replacement'),('workflows','0071_factory_group_forecast'),('workflows','0072_factory_weekly_report'),('documents','0026_group_forecast_business_date'),('workflows','0073_factory_escalation'),('documents','0027_factory_escalation')]
        indexes=[plan.index(node) for node in ordered];self.assertEqual(indexes,sorted(indexes))
        self.assertNotIn(('workflows','0068_factory_ppe'),plan)
    def test_precursor_and_escalation_have_distinct_complete_intakes(self):
        from apps.workflows.factory_views import INTAKES
        self.assertTrue(all(len(row)==4 for row in INTAKES));self.assertEqual(len(INTAKES),len({row[0] for row in INTAKES}))
        entries={row[0]:row for row in INTAKES}
        self.assertIn('issue.read',entries['pmo-escalation/v1'][3]);self.assertIn('report.read',entries['pmo-weekly-report/v1'][3])
