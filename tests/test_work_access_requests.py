from datetime import timedelta
import re

from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.identity import intake
from apps.identity.models import Grant, WorkAccessRequest
from apps.workflows.models import FactoryWork


@override_settings(DEBUG=False)
class WorkAccessRequestTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.admin = users.create_user('sample-work-access-admin')
        self.reader = users.create_user('sample-work-access-requester')
        root = users.create_superuser('sample-work-access-bootstrap')
        self.scope = {'format': 'psl.tenant-access/v1', 'create_cases': False, 'manage_access': True,
                      'kinds': ['project'], 'allowed_actions': ['case.read'], 'initial_actions': [],
                      'classification': 'synthetic'}
        self.expiry = timezone.now() + timedelta(hours=1)
        intake.provision(root, self.admin, 'sample-access', self.scope, self.expiry, True, 'Synthetic review scope')
        self.case = Case.objects.create(tenant='sample-access', title='Restricted source workspace', kind='project', synthetic=True)
        self.other = Case.objects.create(tenant='sample-access', title='Other sample workspace', kind='project', synthetic=True)
        Grant.objects.bulk_create([Grant(case=case, user=self.admin, action='case.read') for case in (self.case, self.other)])
        self.work = FactoryWork.objects.create(
            case=self.case, actor=self.admin, key='sample-private-work', request={'reference': 'PRIVATE-REFERENCE'},
            request_hash='1' * 64, business_key='1' * 64)
        self.client.force_login(self.reader)

    def test_opaque_request_is_recorded_once_and_visible_to_scoped_admin_only(self):
        refs = [self.work.pk, self.work.pk + 1000000]
        bodies = []
        for reference in refs:
            work_url = reverse('factory_detail', args=[reference])
            request_url = reverse('work_access_request', args=[reference])
            blocked = self.client.get(work_url)
            self.assertContains(blocked, 'Ask for access', status_code=404)
            self.assertNotContains(blocked, self.case.title, status_code=404)
            self.assertNotContains(blocked, 'PRIVATE-REFERENCE', status_code=404)
            self.assertEqual(blocked['Cache-Control'], 'no-store')
            before = self.client.get(request_url)
            self.assertContains(before, 'Record access request')
            self.assertFalse(WorkAccessRequest.objects.filter(work_reference=reference).exists())
            for _ in range(2):
                submitted = self.client.post(request_url, follow=True)
                self.assertContains(submitted, 'Your request was recorded.')
            self.assertEqual(self.client.get(work_url).status_code, 404)
            # Django masks the logout form's CSRF token on each response.
            bodies.append(re.sub(rb'(name="csrfmiddlewaretoken" value=")[^"]+', rb'\g<1>csrf', submitted.content))
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(WorkAccessRequest.objects.count(), 2)
        self.assertFalse(Grant.objects.filter(user=self.reader).exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reader)
        self.assertEqual(csrf.post(reverse('work_access_request', args=[self.work.pk])).status_code, 403)

        self.client.force_login(self.admin)
        page = self.client.get(reverse('case_access', args=[self.case.pk]), {'request_page': 1})
        self.assertEqual([row['work_reference'] for row in page.context['work_requests']], [self.work.pk])
        self.assertContains(page, self.reader.username)
        self.assertNotContains(page, 'PRIVATE-REFERENCE')
        other = self.client.get(reverse('case_access', args=[self.other.pk]))
        self.assertEqual(list(other.context['work_requests']), [])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse('case_access', args=[self.case.pk])).status_code, 404)

        with self.assertRaises(DatabaseError), transaction.atomic():
            WorkAccessRequest.objects.update(work_reference=self.work.pk)

    def test_request_limit_and_earlier_unmatched_reference_remain_safe(self):
        next_id = self.work.pk + 1
        pending_url = reverse('work_access_request', args=[next_id])
        self.assertEqual(self.client.post(pending_url).status_code, 302)
        new_work = FactoryWork.objects.create(pk=next_id, case=self.case, actor=self.admin, key='later', request={},
                                              request_hash='2' * 64, business_key='2' * 64)
        for ref in range(next_id + 1, next_id + 10):
            self.assertEqual(self.client.post(reverse('work_access_request', args=[ref])).status_code, 302)
        bound = self.client.post(reverse('work_access_request', args=[next_id + 10]))
        self.assertContains(bound, 'Try again later', status_code=429)
        limited = self.client.post(f'/api/v1/work/{next_id + 10}/access-request', {}, content_type='application/json')
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(self.client.post(pending_url).status_code, 302)
        self.assertEqual(WorkAccessRequest.objects.count(), 10)
        self.client.force_login(self.admin)
        page = self.client.get(reverse('case_access', args=[new_work.case_id]))
        self.assertEqual(list(page.context['work_requests']), [])

    def test_api_uses_the_same_opaque_acknowledgement_for_hidden_and_missing_work(self):
        for reference in (self.work.pk, self.work.pk + 1000000):
            url = f'/api/v1/work/{reference}/access-request'
            self.assertEqual(self.client.get(url).json(), {'requested': False})
            for _ in range(2):
                self.assertEqual(self.client.post(url, {}, content_type='application/json').json(), {'requested': True})
            self.assertEqual(self.client.get(url).json(), {'requested': True})
            self.assertEqual(self.client.get(f'/api/v1/work/{reference}').status_code, 404)
        self.assertEqual(WorkAccessRequest.objects.filter(requester=self.reader).count(), 2)
        self.assertFalse(Grant.objects.filter(user=self.reader).exists())
