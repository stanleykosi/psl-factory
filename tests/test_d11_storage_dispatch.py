from builtins import __import__ as real_import
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.services import add_evidence
from apps.documents.controlled import register_template
from apps.policy.services import resolve
from tests.document_helpers import DEFINITION, artifact
from tests.helpers import rev, setup_case


class StorageDispatchTests(TestCase):
    def test_storage_lifecycle_uses_its_validator_without_unrelated_imports(self):
        actor, case = setup_case()
        evidence = add_evidence(actor, case.pk, 'policy_decision',
                                'Synthetic storage configuration', 'synthetic:storage')
        template = register_template(actor, case.pk, 'Storage fixture', DEFINITION,
                                     evidence.pk, rev(case))
        component = 'D11.template_storage_retention_rules'
        schema = 'schema:psl/document-storage/v1'
        content = {'template_ids': [template.pk], 'repository': 'internal-versioned',
                   'retention_days': 30}

        def import_with_unavailable_domains(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 1 and (globals or {}).get('__name__') == 'apps.policy.services':
                if name in {'clock_validators', 'd03_validators'}:
                    raise ImportError('Unrelated validator unavailable in the fixture')
            return real_import(name, globals, locals, fromlist, level)

        with patch('builtins.__import__', side_effect=import_with_unavailable_domains):
            config = artifact(actor, case, component, schema, content, evidence)
            resolution = resolve(component, case)
            self.assertEqual(resolution.status, 'ACTIVE')
            self.assertEqual(resolution.configuration.pk, config.pk)
            with self.assertRaisesMessage(ValidationError, 'minimum'):
                artifact(actor, case, component, schema, dict(content, retention_days=0), evidence)
