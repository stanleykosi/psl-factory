"""The demo's synthetic test templates: every project has one for each document type its lines use."""
import tempfile
from io import StringIO
from pathlib import Path

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from apps.core.management.commands import seed_demo_templates as seed
from apps.core.management.commands.seed_demo_templates import definition
from apps.core.models import Case
from apps.documents.models import Template
from apps.policy.services import reference_values, resolve

TYPES = {'minutes', 'status_report', 'sow', 'rfp_response', 'project_artifact', 'finance_report',
         'finance_group_report'}
COMPONENT = 'D11.template_storage_retention_rules'


class SeedDemoTemplatesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.folder = tempfile.TemporaryDirectory()
        call_command('seed_psl_demo', credentials_file=str(Path(cls.folder.name) / 'people.txt'), stdout=StringIO())

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()
        super().tearDownClass()

    def cases(self):
        return Case.objects.filter(tenant='psl-demo')

    def run_command(self):
        out = StringIO()
        call_command('seed_demo_templates', stdout=out)
        return out.getvalue()

    def test_every_project_has_a_template_for_each_document_type(self):
        self.assertEqual(self.cases().count(), 4)
        for case in self.cases():
            templates = Template.objects.filter(case=case)
            self.assertEqual({t.definition['document_type'] for t in templates}, TYPES, case.title)
            self.assertEqual(templates.filter(definition__document_type='project_artifact').count(), 4)
            names = list(templates.values_list('name', flat=True))
            self.assertEqual(len(names), len(set(names)), case.title)

    def test_a_second_run_adds_nothing(self):
        before = {case.pk: Template.objects.filter(case=case).count() for case in self.cases()}
        out = self.run_command()
        self.assertEqual(out.count('0 added'), 4)
        self.assertEqual(before, {case.pk: Template.objects.filter(case=case).count() for case in self.cases()})

    def test_a_new_template_is_added_everywhere_and_storage_rule_lists_it(self):
        extra = ('Extra note (test template)', None, definition('project_artifact', ['executive_summary'],
                                                                {'internal': ['executive_summary']}))
        with patch.object(seed, 'TEMPLATES', [*seed.TEMPLATES, extra]):
            out = self.run_command()
        self.assertEqual(out.count('1 added: Extra note (test template)'), 4)
        for case in self.cases():
            rule = resolve(COMPONENT, case)
            self.assertEqual(rule.status, 'ACTIVE')
            self.assertEqual(sorted(reference_values(rule.configuration)[0]['template_ids']),
                             sorted(Template.objects.filter(case=case).values_list('pk', flat=True)))

    def test_start_work_minutes_form_lists_a_template_for_kora(self):
        client = Client()
        client.force_login(get_user_model().objects.get(username='tunde.bello@psl-demo.test'))
        case = self.cases().get(title__startswith='Kora')
        answer = client.get(f'/api/v1/projects/{case.pk}/intake-sources',
                            {'line': 'pmo-minutes/v1', 'field': 'data.template_id'})
        self.assertEqual(answer.status_code, 200, answer.content)
        self.assertEqual([row['label'] for row in answer.json()['items']], [f'Meeting minutes (test template) · 1 · #{Template.objects.get(case=case, name="Meeting minutes (test template)").pk}'])

    def test_it_refuses_without_the_demo_tenant(self):
        with patch.object(seed, 'TENANT', 'no-such-tenant'), self.assertRaises(CommandError):
            self.run_command()
