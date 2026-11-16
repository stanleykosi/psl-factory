import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.agents.models import AgentJob, CaseUpload
from apps.agents.upload_jobs import ROLES, run_once
from apps.core.models import Case
from apps.documents.controlled import register_template
from apps.identity.models import Grant
from tests.document_helpers import DEFINITION
from tests.factory_helpers import fixture
from tests.helpers import rev


class DesignConsolidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sample = fixture(username='screen-operator')
        private = fixture(username='private-screen-operator')
        cls.actor, cls.case, cls.work = sample['actor'], sample['case'], sample['work']
        cls.template_owner = sample['evidence']['policy_decision']
        cls.other = private['case']
        cls.upload = CaseUpload.objects.create(
            case=cls.case, actor=cls.actor, name='permitted.txt', key='permitted', sha256='test', size=5,
        )
        cls.job = AgentJob.objects.create(upload=cls.upload, actor=cls.actor, role='A01', status='draft',
                                          result={'summary': 'Private draft body'})

    def test_sign_in_and_factory_navigation_use_native_session(self):
        url = reverse('design_overview')
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}", fetch_redirect_response=False)
        self.client.post(reverse('login'), {'username': self.actor.username, 'password': 'test-only-password'})
        response = self.client.get(url)
        self.assertContains(response, 'factory-design.css')
        self.assertContains(response, 'Invoice preparation and delivery')
        self.assertContains(response, '1 open')
        self.assertNotContains(response, '2 open')
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_project_links_are_limited_by_case_and_action(self):
        self.client.force_login(self.actor)
        url = reverse('design_project', args=[self.case.pk])
        response = self.client.get(url)
        self.assertContains(response, reverse('issues', args=[self.case.pk]))
        self.assertContains(response, reverse('factory_detail', args=[self.work.pk]))
        self.assertEqual(self.client.get(reverse('design_project', args=[self.other.pk])).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action__in=['issue.read', 'finance.read']).update(active=False)
        response = self.client.get(url)
        self.assertNotContains(response, reverse('issues', args=[self.case.pk]))
        self.assertNotContains(response, reverse('factory_detail', args=[self.work.pk]))

    def test_onboarding_and_password_use_same_shell_and_do_not_grant_access(self):
        user = get_user_model().objects.create_user('new-operator', password='synthetic-new-account')
        response = self.client.post(reverse('login'), {'username': user.username, 'password': 'synthetic-new-account'},
                                    follow=True)
        self.assertContains(response, 'Ask for workspace access')
        self.assertContains(response, 'factory-design.css')
        self.assertFalse(Grant.objects.filter(user=user).exists())
        self.assertContains(self.client.get(reverse('password_change')), 'Save password')
        self.assertContains(self.client.get(reverse('case_create')), 'Workspace access needed')
        Grant.objects.create(case=self.case, user=user, action='case.read')
        self.assertRedirects(self.client.get(reverse('getting_started')), reverse('home'),
                             fetch_redirect_response=False)

    def test_project_tabs_use_current_grants_and_native_milestone(self):
        self.client.force_login(self.actor)
        Grant.objects.get_or_create(case=self.case, user=self.actor, action='milestone.complete')
        milestones = reverse('design_project_tab', args=[self.case.pk, 'milestones'])
        self.assertContains(self.client.get(milestones), 'Contract completion criterion')
        self.assertContains(self.client.get(reverse('design_project_tab', args=[self.case.pk, 'money'])), 'Open invoices and receipts')
        self.assertEqual(self.client.get(reverse('design_project_tab', args=[self.other.pk, 'milestones'])).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action='finance.read').update(active=False)
        self.assertEqual(self.client.get(reverse('design_project_tab', args=[self.case.pk, 'money'])).status_code, 404)

    def test_agent_entry_lists_eight_roles_and_checks_current_grants(self):
        self.client.force_login(self.actor)
        assistant = reverse('design_agents')
        files = reverse('case_uploads', args=[self.case.pk])
        response = self.client.get(assistant)
        for title, _ in ROLES.values():
            self.assertContains(response, title)
        self.assertContains(response, f'{files}#agent-job-{self.job.pk}')
        self.assertNotContains(response, 'Private draft body')
        self.assertContains(self.client.get(files), 'Private draft body')
        Grant.objects.filter(case=self.case, user=self.actor, action='agent.extract').update(active=False)
        self.assertNotContains(self.client.get(assistant), 'permitted.txt')
        self.assertNotContains(self.client.get(files), 'Private draft body')

    def test_template_catalog_reads_controlled_versions_and_revokes_access(self):
        self.client.force_login(self.actor)
        Grant.objects.get_or_create(case=self.case, user=self.actor, action='document.template')
        Grant.objects.get_or_create(case=self.case, user=self.actor, action='document.read')
        for _ in range(2):
            register_template(self.actor, self.case.pk, 'Controlled weekly layout', DEFINITION,
                              self.template_owner.pk, rev(self.case))
        url = reverse('design_project_tab', args=[self.case.pk, 'templates'])
        response = self.client.get(url)
        self.assertContains(response, 'Controlled weekly layout · Version 2')
        self.assertContains(response, 'Controlled weekly layout · Version 1')
        self.assertContains(response, reverse('template_current', args=[self.case.pk]))
        self.assertEqual(self.client.get(url, {'templates': 'invalid'}).status_code, 400)
        Grant.objects.filter(case=self.case, user=self.actor, action='document.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    @patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
    def test_assistant_queues_each_role_through_the_real_worker(self):
        self.client.force_login(self.actor)
        assistant = reverse('design_agents')
        store = {}
        source = b'Synthetic acceptance evidence.\n'

        def save(key, data):
            store[key] = data

        def draft(model, instructions, text):
            self.assertEqual(model, 'synthetic')
            self.assertIn(instructions, [instruction for _, instruction in ROLES.values()])
            self.assertEqual(text, source.decode())
            return {'summary': 'A scoped draft', 'quotes': ['1'], 'gaps': []}

        with (patch('adapters.case_uploads.put', side_effect=save),
              patch('adapters.case_uploads.read', side_effect=lambda upload: store[upload.key]),
              patch('adapters.openrouter.review', side_effect=draft)):
            forbidden = self.client.post(assistant, {'workspace': self.other.pk, 'role': 'A01',
                                                     'file': SimpleUploadedFile('source.txt', source)})
            self.assertEqual(forbidden.status_code, 200)
            self.assertEqual(store, {})
            for role in ROLES:
                response = self.client.post(assistant, {'workspace': self.case.pk, 'role': role,
                                                       'file': SimpleUploadedFile('source.txt', source)})
                self.assertEqual(response.status_code, 302)
                self.assertTrue(run_once())
                job = AgentJob.objects.get(upload__name='source.txt', role=role)
                self.assertEqual(job.status, 'draft')
                self.assertEqual(job.result['quotes'], [source.decode().strip()])
            self.assertEqual(len(store), 1)
