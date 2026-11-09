"""Additive actual 0080 source contract, without mutable historical imports."""
from importlib import import_module
from pathlib import Path
import hashlib
from django.test import SimpleTestCase

class IssueFactoryMigrationTests(SimpleTestCase):
    def test_exact_parent_and_narrow_function_extension(self):
        m=import_module('apps.workflows.migrations.0080_factory_issue_reference')
        old=import_module('apps.workflows.migrations.0079_statement_ppe_verification')
        task=import_module('apps.workflows.migrations.0050_factory_accounting')
        self.assertEqual(m.PREVIOUS_IDENTITY,old.SQL)
        self.assertEqual(m.PREVIOUS_TASK,task.TASK)
        self.assertEqual(m.IDENTITY.replace("'pmo-issues/v1',",'',1).replace(" WHEN 'pmo-issues/v1' THEN 'OPS.factory_issue_execution'",'',1),old.SQL)
        self.assertEqual(m.TASK.replace("'issue_followup',",'',1),task.TASK)
        self.assertEqual(m.Migration.dependencies,[('workflows','0079_statement_ppe_verification'),('pmo','0044_issue_reference_observations')])
        self.assertEqual(hashlib.sha256(Path('apps/pmo/migrations/0044_issue_reference_observations.py').read_bytes()).hexdigest(),'7af1f84f33876f1549ceb245fb95bf14e9be11aa871c944ec917e50e16019d61')
        self.assertEqual(hashlib.sha256(Path('apps/workflows/migrations/0079_statement_ppe_verification.py').read_bytes()).hexdigest(),'ad8a72a540cb7466a995503e6a455a52c0540a5c59fa94e1d35d22c1fd2c6c1a')
