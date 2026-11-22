from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse

from apps.core import client_workspace_links as links
from apps.core.client_contacts import save as save_contact
from apps.core.evidence_access import CLIENT_WORKSPACE_LINK_PROOF, public_evidence, public_timeline
from apps.core.models import Case, ClientWorkspaceLink
from apps.identity.models import Grant
from tests.billing_helpers import coverage
from tests.helpers import rev


class ClientWorkspaceLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.maker = users.create_user('sample-client-link-preparer')
        cls.reviewer = users.create_user('sample-client-link-reviewer')
        cls.reader = users.create_user('sample-client-link-reader')
        cls.project_only = users.create_user('sample-client-link-project-reader')
        cls.first, cls.first_scope = cls.projects('scope-one', 'Sample installation work')
        cls.second, cls.second_scope = cls.projects('scope-one', 'Sample follow-up work')
        cls.hidden, cls.hidden_scope = cls.projects('scope-one', 'Sample other restricted project')
        cls.foreign, cls.foreign_scope = cls.projects('scope-two', 'Sample independent tenant project')
        cls.unlinked, _ = cls.projects('scope-one', 'Sample unrelated unlinked project')
        for project in (cls.first, cls.second, cls.foreign, cls.unlinked):
            Grant.objects.bulk_create([Grant(user=cls.reader, case=project, action=action)
                                       for action in ('case.read', 'finance.read')])
        Grant.objects.bulk_create([Grant(user=cls.project_only, case=cls.first, action=action)
                                   for action in ('case.read', 'engagement.read')])
        save_contact(cls.maker, cls.first, 'billing', {'revision': rev(cls.first), 'evidence': cls.first_scope.evidence,
            'customer': cls.first_scope.customer, 'client_name': 'Sample shared display name', 'name': 'Sample office',
            'email': 'sample-office@example.invalid', 'role': 'Billing'})
        coverage(cls.maker, cls.first, customer='OTHER-LOCAL', reference='independent-bill')

    @classmethod
    def projects(cls, tenant, title):
        project = Case.objects.create(tenant=tenant, kind='project', synthetic=True, title=title)
        Grant.objects.bulk_create([
            *[Grant(user=cls.maker, case=project, action=action) for action in
              ('case.read', 'finance.read', 'finance.billing.register', 'evidence.add', 'policy.activate')],
            *[Grant(user=cls.reviewer, case=project, action=action) for action in
              ('case.read', 'finance.read', 'policy.activate')],
        ])
        return project, coverage(cls.maker, project, customer='C1', reference='billing')

    def proposal(self, project, scope, reference='SAMPLE-MASTER-001'):
        return links.propose(self.maker, project, rev(project), action='link', coverage_id=scope.pk,
                             issuer='sample.customer.register', reference=reference, name='Sample shared display name',
                             source='Synthetic original customer register entry')

    def test_current_groups_use_only_reviewed_same_tenant_visible_projects(self):
        self.assertEqual(connection.vendor, 'postgresql')
        detail = reverse('design_client_workspace_link', args=[self.first.pk])
        index = reverse('design_clients')
        self.client.force_login(self.maker)
        self.assertEqual(self.client.post(detail, {'operation': 'propose', 'revision': rev(self.first), 'action': 'link',
            'coverage': self.first_scope.pk, 'issuer': 'sample.customer.register', 'reference': 'SAMPLE-MASTER-001',
            'name': 'Sample shared display name', 'source': 'Synthetic first coverage proof'}).status_code, 302)
        proof = self.first.evidence.get(kind=CLIENT_WORKSPACE_LINK_PROOF)
        self.assertFalse(public_evidence(self.first.evidence.filter(pk=proof.pk)).exists())
        self.assertNotContains(self.client.get(detail), 'Confirm client link')
        self.assertFalse(ClientWorkspaceLink.objects.exists())
        self.assertEqual(self.client.post(detail, {'operation': 'confirm', 'revision': rev(self.first),
                                                  'evidence': proof.pk}).status_code, 403)

        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(detail), 'SAMPLE-MASTER-001')
        self.assertEqual(self.client.post(detail, {'operation': 'confirm', 'revision': rev(self.first),
                                                  'evidence': proof.pk}).status_code, 302)
        first = ClientWorkspaceLink.objects.get(case=self.first)
        self.assertFalse(public_timeline(self.first).filter(action='client.workspace_link_reviewed').exists())
        for project, scope in ((self.second, self.second_scope), (self.hidden, self.hidden_scope),
                               (self.foreign, self.foreign_scope)):
            proposed = self.proposal(project, scope)
            links.confirm(self.reviewer, project, rev(project), proposed.pk)
        other_tenant = ClientWorkspaceLink.objects.get(case=self.foreign)
        self.assertNotEqual(first.group_key, other_tenant.group_key)
        self.client.force_login(self.reader)
        page = self.client.get(index, {'q': self.first.title, 'billing': 'needed'})
        groups = list(page.context['groups'])
        self.assertEqual([(row['group_key'], row['project_count'], row['contacts_needed']) for row in groups],
                         [(first.group_key, 2, 1)])
        self.assertNotContains(page, self.hidden.title)
        self.assertNotContains(page, 'SAMPLE-MASTER-001')
        grouped = self.client.get(index, {'client': first.group_key})
        self.assertEqual({member.case_id for member in grouped.context['members']}, {self.first.pk, self.second.pk})
        api = self.client.get(f'/api/v1/clients/groups/{first.group_key}')
        self.assertEqual({row['case_id'] for row in api.json()['projects']}, {str(self.first.pk), str(self.second.pk)})
        self.assertContains(grouped, self.first.title)
        self.assertNotContains(grouped, self.hidden.title)
        self.assertNotContains(grouped, self.foreign.title)
        self.assertContains(self.client.get(index), self.unlinked.title)
        self.client.force_login(self.project_only)
        self.assertEqual(self.client.get(index, {'client': first.group_key}).status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/clients/groups/{first.group_key}').status_code, 404)
        self.assertContains(self.client.get(index), self.first.title)
        self.assertNotContains(self.client.get(index), 'Sample shared display name')

    def test_exact_source_successor_and_independent_removal_preserve_link_history(self):
        pending = self.proposal(self.first, self.first_scope)
        competing = self.proposal(self.first, self.first_scope, reference='OTHER-MASTER-REF')
        with self.assertRaises(ValidationError):
            links.confirm(self.reviewer, self.second, rev(self.second), pending.pk)
        first = links.confirm(self.reviewer, self.first, rev(self.first), pending.pk)
        self.assertEqual(links.confirm(self.reviewer, self.first, rev(self.first), pending.pk), first)
        with self.assertRaisesMessage(ValidationError, 'client link changed'):
            links.confirm(self.reviewer, self.first, rev(self.first), competing.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ClientWorkspaceLink.objects.filter(pk=first.pk).update(group_key='f' * 64)
        amended_scope = coverage(self.maker, self.first, customer=self.first_scope.customer,
                                  reference=self.first_scope.reference)
        self.assertEqual(amended_scope.version, self.first_scope.version + 1)
        self.client.force_login(self.reader)
        index = reverse('design_clients')
        self.assertEqual(self.client.get(index, {'client': first.group_key}).status_code, 404)
        unlinked = self.client.get(index)
        self.assertIn(self.first.pk, [item.pk for item in unlinked.context['projects']])

        revised = self.proposal(self.first, amended_scope)
        current = links.confirm(self.reviewer, self.first, rev(self.first), revised.pk)
        self.assertEqual((current.group_key, current.previous_id, current.number), (first.group_key, first.pk, 2))
        removal = links.propose(self.maker, self.first, rev(self.first), action='unlink',
                                source='Sample instruction to remove this exact project link')
        removed = links.confirm(self.reviewer, self.first, rev(self.first), removal.pk)
        self.assertEqual((removed.previous_id, removed.number, removed.coverage_id), (current.pk, 3, None))
        self.assertEqual(self.client.get(index, {'client': first.group_key}).status_code, 404)
        self.assertEqual(ClientWorkspaceLink.objects.get(pk=first.pk).coverage_id, self.first_scope.pk)
