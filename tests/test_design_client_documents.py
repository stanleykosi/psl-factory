from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ClientContactRevision
from apps.core.services import add_evidence
from apps.documents.controlled import register_template
from apps.documents.models import Template, TemplateFile
from apps.identity.models import Grant
from tests.billing_helpers import coverage
from tests.document_helpers import DEFINITION
from tests.helpers import rev, setup_case


class ClientAndTemplateDesignTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case(username='template-contact')
        cls.other, cls.other_case = setup_case(username='outside-template-contact')
        cls.proof = add_evidence(cls.actor, cls.case.pk, 'policy_decision', 'Synthetic owner evidence', 'synthetic:exact-proof')
        cls.coverage = coverage(cls.actor, cls.case)
        cls.base = register_template(cls.actor, cls.case.pk, 'Client update', DEFINITION, cls.proof.pk, rev(cls.case))

    def test_contact_edits_keep_proof_history_and_scope(self):
        self.client.force_login(self.actor)
        url = reverse('design_client_project', args=[self.case.pk])
        data = {'purpose': 'billing', 'customer': self.coverage.customer, 'client_name': 'Synthetic Customer',
                'name': 'Test Billing Contact', 'email': 'billing@example.test', 'evidence': self.proof.pk,
                'revision': rev(self.case)}
        self.assertRedirects(self.client.post(url, data), url, fetch_redirect_response=False)
        self.assertContains(self.client.get(url), 'billing@example.test')
        self.assertContains(self.client.post(url, dict(data, email='stale@example.test')), 'Stale revision')
        self.assertRedirects(self.client.post(url, dict(data, email='current@example.test', revision=rev(self.case))),
                             url, fetch_redirect_response=False)
        self.assertEqual(list(ClientContactRevision.objects.order_by('number').values_list('email', flat=True)),
                         ['billing@example.test', 'current@example.test'])
        Grant.objects.filter(case=self.case, user=self.actor, action='finance.read').update(active=False)
        self.assertNotContains(self.client.get(url), 'current@example.test')
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_client_directory_search_uses_only_accessible_client_names(self):
        self.client.force_login(self.actor)
        url = reverse('design_client_project', args=[self.case.pk])
        self.assertRedirects(self.client.post(url, {'purpose': 'project', 'client_name': 'Synthetic Account',
                            'name': 'Test Contact', 'evidence': self.proof.pk, 'revision': rev(self.case)}), url,
                             fetch_redirect_response=False)
        directory = reverse('design_clients')
        self.assertContains(self.client.get(directory, {'q': 'Synthetic Account'}), url)
        Grant.objects.filter(case=self.case, user=self.actor, action='engagement.read').update(active=False)
        self.assertNotContains(self.client.get(directory, {'q': 'Synthetic Account'}), url)

    def test_private_template_upload_replays_and_retains_exact_native_definition(self):
        self.client.force_login(self.actor)
        catalogue = reverse('design_project_tab', args=[self.case.pk, 'templates'])
        url = reverse('design_template_upload', args=[self.case.pk])
        self.assertContains(self.client.get(catalogue), 'Upload a revised template')
        data = {'previous': self.base.pk, 'proof': self.proof.pk, 'request_key': uuid4(), 'revision': rev(self.case)}
        body = b'%PDF-1.4\nSynthetic template\n%%EOF\n'
        with patch('adapters.case_uploads.put') as put:
            self.assertContains(self.client.post(url, dict(data, file=SimpleUploadedFile('spoof.pdf', b'not a pdf'))), 'Choose a Word, Excel or PDF')
            put.assert_not_called()
            for _ in range(2):
                submitted = self.client.post(url, dict(data, file=SimpleUploadedFile('update.pdf', body)))
                self.assertRedirects(submitted, catalogue, fetch_redirect_response=False)
            replay = self.client.post(f'/api/v1/projects/{self.case.pk}/templates/replacements',
                                      dict(data, file=SimpleUploadedFile('update.pdf', body)))
            self.assertEqual(replay.json()['version'], self.base.version + 1)
            self.assertContains(self.client.post(url, dict(data, file=SimpleUploadedFile('different.pdf', body))), 'upload request is already in use')
            put.assert_called_once()
        attachment = TemplateFile.objects.select_related('template').get()
        self.assertEqual(attachment.template.definition, self.base.definition)
        self.assertEqual(attachment.template.version, 2)
        self.assertEqual(Template.objects.filter(case=self.case).count(), 2)
        file_url = reverse('design_template_download', args=[self.case.pk, attachment.template_id])
        with patch('apps.documents.template_catalog.read', return_value=body) as read:
            response = self.client.get(file_url)
            self.assertEqual(b''.join(response.streaming_content), body)
            self.assertIn('attachment', response.headers['Content-Disposition'])
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(file_url).status_code, 404)
            read.assert_called_once()

    def test_word_and_excel_use_native_version_registration(self):
        self.client.force_login(self.actor)
        url = reverse('design_template_upload', args=[self.case.pk])
        previous = self.base
        with patch('adapters.case_uploads.put'):
            for extension, member in [('docx', 'word/document.xml'), ('xlsx', 'xl/workbook.xml')]:
                package = BytesIO()
                with ZipFile(package, 'w') as archive:
                    archive.writestr('[Content_Types].xml', '<Types/>')
                    archive.writestr(member, '<fixture/>')
                response = self.client.post(url, {'previous': previous.pk, 'proof': self.proof.pk,
                    'request_key': uuid4(), 'revision': rev(self.case),
                    'file': SimpleUploadedFile('fixture.' + extension, package.getvalue())})
                self.assertEqual(response.status_code, 302)
                previous = Template.objects.filter(case=self.case).latest('version')
        self.assertEqual(previous.version, 3)

    def test_first_template_validates_audience_and_reuses_original_file(self):
        self.client.force_login(self.actor)
        url = reverse('design_template_upload', args=[self.case.pk])
        catalogue = reverse('design_project_tab', args=[self.case.pk, 'templates'])
        self.assertContains(self.client.get(catalogue), 'Add a template')
        body = b'%PDF-1.4\nSynthetic first version\n%%EOF\n'
        data = {'operation': 'first', 'name': 'Project checkpoint', 'document_type': 'status_report',
                'required': ['executive_summary'], 'proof': self.proof.pk, 'request_key': uuid4(), 'revision': rev(self.case)}

        def submit(**choices):
            return self.client.post(url, {**data, **choices, 'file': SimpleUploadedFile('template.pdf', body)})

        with patch('adapters.case_uploads.put') as put:
            self.assertContains(submit(client=['executive_summary', 'internal_notes']), 'cannot expose internal notes')
            put.assert_not_called()
            for _ in range(2):
                self.assertRedirects(submit(internal=['executive_summary', 'status']), catalogue, fetch_redirect_response=False)
            self.assertContains(submit(internal=['executive_summary']), 'upload request is already in use')
            put.assert_called_once()
        first = TemplateFile.objects.select_related('template').get()
        self.assertIsNone(first.previous_id)
        self.assertEqual(first.template.version, 1)
        self.assertEqual(first.template.definition, {'document_type': 'status_report', 'required_fields': ['executive_summary'],
                         'audience_fields': {'internal': ['executive_summary', 'status']}})

    def test_api_first_template_catalogue_and_download(self):
        self.client.force_login(self.actor)
        url = f'/api/v1/projects/{self.case.pk}/templates'
        catalogue = self.client.get(url).json()
        self.assertTrue(catalogue['can_upload'])
        file = b'%PDF-1.4\nSynthetic API template\n%%EOF\n'
        fields = {'name': 'Synthetic API layout', 'document_type': 'status_report',
                  'required': ['executive_summary'], 'internal': ['executive_summary', 'status'],
                  'proof': self.proof.pk, 'request_key': uuid4(), 'revision': catalogue['revision']}
        with patch('adapters.case_uploads.put') as put, patch('apps.documents.template_catalog.read', return_value=file):
            result = self.client.post(url, {**fields, 'file': SimpleUploadedFile('sample.pdf', file)})
            self.assertEqual(result.status_code, 201, result.content)
            put.assert_called_once()
            item = next(row for row in self.client.get(url).json()['items'] if row['id'] == result.json()['template_id'])
            response = self.client.get(item['download_url'])
            self.assertEqual(response.status_code, 200, response.content if not response.streaming else '')
            self.assertEqual(b''.join(response.streaming_content), file)
