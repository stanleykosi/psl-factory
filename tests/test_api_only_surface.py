from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.core.factory_api.urls import contract
from apps.workflows.models import FactoryProgress
from tests.factory_helpers import fixture
from tests.helpers import setup_case


@override_settings(ROOT_URLCONF='config.urls', PSL_DJANGO_UI=False, DEBUG=False)
class ApiOnlySurfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        data = fixture(username='api-only-finance')
        cls.actor, cls.case, cls.work = (data[key] for key in ('actor', 'case', 'work'))
        cls.outsider, _ = setup_case(username='api-only-outsider')

    def test_openapi_health_and_signed_inbox_are_available(self):
        self.assertEqual(self.client.get('/health/').status_code, 200)
        published = self.client.get('/api/v1/openapi.json')
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.json(), contract())
        self.assertEqual(self.client.get('/api/v1/me').status_code, 401)
        inbox = reverse('finance_followup_inbox', args=[uuid4(), 'a' * 64])
        rejected = self.client.post(inbox, {}, content_type='application/json')
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json(), {'held': 'source_intake_authentication_scope_or_policy'})

    def test_pages_and_static_assets_are_unavailable_with_a_valid_session(self):
        self.client.force_login(self.actor)
        pages = ['/', reverse('login'), reverse('staff_accept_invite'),
                 reverse('factory_recovery_token'), reverse('factory_detail', args=[self.work.pk])]
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual((response.status_code, response.json()['code']), (404, 'page_retired'))
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
        response = self.client.get('/static/factory-work-client.js')
        self.assertEqual((response.status_code, response.json()['code']), (404, 'not_found'))
        payload = {'expected_revision': self.work.revision, 'enabled': True}
        form = self.client.post(reverse('factory_background', args=[self.work.pk]), payload)
        self.assertEqual((form.status_code, form.json()['code']), (404, 'page_retired'))
        self.assertFalse(FactoryProgress.objects.filter(work=self.work).exists())

    def test_json_session_csrf_and_work_access_keep_their_authority(self):
        password = 'Synthetic-only-test-password'
        self.actor.set_password(password)
        self.actor.save(update_fields=['password'])
        browser = Client(enforce_csrf_checks=True)
        session = '/api/v1/session'
        token = browser.get(session).json()['csrf_token']
        body = {'username': self.actor.username, 'password': password}
        self.assertEqual(browser.post(session, body, content_type='application/json').status_code, 403)
        accepted = browser.post(session, body, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertTrue(accepted.json()['signed_in'])
        self.assertNotEqual(accepted.json()['csrf_token'], token)
        detail = browser.get(f'/api/v1/work/{self.work.pk}')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()['id'], self.work.pk)

    def test_private_uploads_keep_their_exact_download_and_reader_scope(self):
        self.client.force_login(self.actor)
        content = b'Synthetic bank and project evidence.'
        with patch('adapters.case_uploads.put') as store:
            created = self.client.post(f'/api/v1/cases/{self.case.pk}/files', {
                'file': SimpleUploadedFile('evidence.txt', content),
            })
            self.assertEqual(created.status_code, 200, created.content)
            self.assertEqual(store.call_args.args[1], content)
        download_url = created.json()['download_url']
        with patch('adapters.case_uploads.read', return_value=content) as read:
            download = self.client.get(download_url)
            self.assertEqual(download.status_code, 200)
            self.assertEqual(b''.join(download.streaming_content), content)
            self.assertEqual(download.headers['Cache-Control'], 'no-store')
            self.client.force_login(self.outsider)
            denied = self.client.get(download_url)
            self.assertEqual((denied.status_code, denied.json()['code']), (404, 'not_found'))
            read.assert_called_once()
