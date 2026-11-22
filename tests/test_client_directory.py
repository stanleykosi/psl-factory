from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.client_contacts import save as save_contact
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from tests.billing_helpers import coverage
from tests.helpers import rev, setup_case
from tests.test_fixed_contract_bridge import FixedContractFixture


class ClientDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.first = setup_case()
        cls.first.title = 'Sample local client record one'
        cls.first.save(update_fields=['title'])
        cls.second = cls.make_case('Sample local client record two')
        cls.hidden = cls.make_case('Sample local client record hidden')
        cls.unknown = cls.make_case('Sample local client record unknown')
        for row in (cls.first, cls.second, cls.hidden):
            proof = add_evidence(cls.owner, row.pk, 'engagement_source', 'Synthetic verified project contact',
                                 'synthetic:client-directory-test')
            save_contact(cls.owner, row, 'project', {'revision': rev(row), 'evidence': proof, 'customer': '',
                'client_name': 'Same Display Name', 'name': 'Sample contact', 'email': 'private@example.invalid', 'role': ''})
        cls.initial = coverage(cls.owner, cls.first, reference='local-record', customer='C1')
        coverage(cls.owner, cls.second, reference='local-record', customer='C1')
        coverage(cls.owner, cls.hidden, reference='local-record', customer='C1')
        save_contact(cls.owner, cls.first, 'billing', {'revision': rev(cls.first), 'evidence': cls.initial.evidence,
            'customer': 'C1', 'client_name': 'Same Display Name', 'name': 'Accounts office',
            'email': 'sample-billing@example.invalid', 'role': 'Billing'})

    @classmethod
    def make_case(cls, title):
        row = Case.objects.create(tenant=cls.first.tenant, kind='project', synthetic=True, title=title)
        Grant.objects.bulk_create([Grant(user=cls.owner, case=row, action=action) for action in
            ('case.read', 'engagement.read', 'engagement.capture', 'finance.read', 'finance.billing.register', 'evidence.add')])
        return row

    def test_current_case_contacts_and_permissions_control_filter_without_grouping_names(self):
        self.assertEqual(connection.vendor, 'postgresql')
        reader = get_user_model().objects.create_user('client-directory-sample-reader')
        Grant.objects.bulk_create([
            Grant(user=reader, case=row, action=action) for row in (self.first, self.second, self.unknown)
            for action in ('case.read', 'engagement.read', 'finance.read')
        ] + [Grant(user=reader, case=self.hidden, action='finance.read')])
        self.client.force_login(reader)
        url = reverse('design_clients')

        def get(**params):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 200)
            return response, {item.pk: item.billing_status for item in response.context['projects']}

        page, rows = get(q='Same Display Name')
        self.assertEqual(rows, {self.first.pk: 'recorded', self.second.pk: 'needed'})
        self.assertContains(page, 'Projects without a verified client link')
        for case in (self.first, self.second):
            self.assertContains(page, reverse('design_client_project', args=[case.pk]))
        self.assertNotContains(page, 'example.invalid')
        self.assertNotContains(page, str(self.hidden.pk))

        self.assertEqual(get(billing='needed')[1], {self.second.pk: 'needed'})
        self.assertEqual(get(billing='recorded')[1], {self.first.pk: 'recorded'})
        self.assertEqual(get(billing='unknown')[1], {self.unknown.pk: 'unknown'})
        scope = coverage(self.owner, self.first, reference='other-register', customer='C2')
        self.assertEqual(get(billing='needed')[1], {self.first.pk: 'needed', self.second.pk: 'needed'})
        successor = coverage(self.owner, self.first, reference=scope.reference, customer='C1')
        self.assertEqual(successor.version, scope.version + 1)
        self.assertEqual(get(billing='recorded')[1], {self.first.pk: 'recorded'})

        Grant.objects.filter(case=self.second, user=reader, action='finance.read').update(active=False)
        self.assertEqual(get(billing='needed')[1], {})
        self.assertEqual(get(billing='unknown')[1], {self.second.pk: 'unknown', self.unknown.pk: 'unknown'})
        Grant.objects.filter(case=self.first, user=reader, action='engagement.read').update(active=False)
        self.assertEqual(get(q='Same Display Name')[1], {self.second.pk: 'unknown'})
        self.assertEqual(get(q=self.first.title, billing='recorded')[1], {self.first.pk: 'recorded'})

    def test_api_directory_contact_proof_and_versioned_readback(self):
        self.client.force_login(self.owner)
        url = f'/api/v1/clients/{self.first.pk}/contacts'
        directory = self.client.get('/api/v1/clients', {'q': 'Same Display Name'})
        self.assertNotContains(directory, 'example.invalid')
        self.assertCountEqual([row['case_id'] for row in directory.json()['projects']],
                              [str(case.pk) for case in (self.first, self.second, self.hidden)])
        options = self.client.get(url + '/options', {'purpose': 'billing'}).json()
        self.assertEqual(options['customers'], ['C1'])
        replacement = self.client.post(url, {
            'purpose': 'billing', 'customer': 'C1', 'client_name': 'Same Display Name', 'name': 'Billing successor',
            'email': 'successor@example.invalid', 'role': 'Accounts', 'evidence_id': options['proofs'][0]['id'],
            'expected_revision': options['revision'],
        }, content_type='application/json')
        self.assertEqual(replacement.status_code, 200, replacement.content)
        params = {'purpose': 'billing', 'customer': 'C1'}
        history = self.client.get(url + '/history', params).json()['items']
        self.assertEqual([row['version'] for row in history], [2, 1])
        self.assertEqual(history[0], replacement.json())
        Grant.objects.filter(case=self.first, user=self.owner, action='finance.read').update(active=False)
        self.assertEqual(self.client.get(url + '/history', params).status_code, 403)

    def test_search_and_billing_filter_paginate_without_per_project_billing_queries(self):
        for index in range(26):
            self.make_case(f'Sample directory page {index:02}')
        self.client.force_login(self.owner)
        with CaptureQueriesContext(connection) as queries:
            result = self.client.get(reverse('design_clients'), {'q': 'directory page', 'billing': 'unknown'})
        self.assertContains(result, 'q=directory%20page&amp;billing=unknown&amp;page=2')
        self.assertEqual(len(result.context['projects']), 25)
        self.assertLessEqual(sum('finance_billingcoverage' in entry['sql'] for entry in queries), 2)
        next_page = self.client.get(reverse('design_clients'), {'q': 'directory page', 'billing': 'unknown', 'page': 2})
        self.assertEqual(len(next_page.context['projects']), 1)
        self.assertContains(next_page, 'Sample directory page 25')


class RestrictedClientDirectoryTests(FixedContractFixture, TestCase):
    def test_no_billing_filter_disclosure_of_a_private_fixed_contract(self):
        self.prepared()
        reader = get_user_model().objects.create_user('directory-fixed-contract-reader')
        Grant.objects.bulk_create([
            Grant(user=reader, case=self.c, action=action) for action in ('case.read', 'engagement.read', 'finance.read')
        ])
        self.client.force_login(reader)
        url = reverse('design_clients')
        self.assertEqual(len(self.client.get(url, {'billing': 'needed'}).context['projects']), 0)
        page = self.client.get(url, {'billing': 'unknown'})
        self.assertEqual([(item.pk, item.billing_status) for item in page.context['projects']], [(self.c.pk, 'unknown')])
        self.assertNotContains(page, self.cov.customer)
        detail = self.client.get(reverse('design_client_project', args=[self.c.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, self.cov.customer)
