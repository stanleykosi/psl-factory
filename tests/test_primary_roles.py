from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.factory_api.urls import contract
from apps.core.models import Case
from apps.identity import intake, primary_roles as domain
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.identity.services import require
from apps.identity.staff_models import StaffPrimaryRoleChange, StaffRoleDefinition
from apps.policy.models import Configuration
from apps.workflows.models import HumanTask
from jsonschema import Draft202012Validator, FormatChecker


NAMES = ['PMO Lead', 'Finance Lead', 'CEO', 'CTO', 'HR', 'Admin']


def fixture():
    users = get_user_model().objects
    root = users.create_superuser('role-bootstrap')
    admin = users.create_user('role-admin')
    value = {'format': 'psl.tenant-access/v3', 'create_cases': True, 'manage_access': True,
             'kinds': ['project'], 'allowed_actions': ['case.read', 'agent.extract', *sorted(domain.actions(domain.FUNCTIONS))],
             'initial_actions': ['case.read'], 'classification': 'synthetic',
             'staff_lifecycle': {'invite_minutes': 30, 'allow_invite': True, 'allow_deactivation': True,
                                 'allow_roster': True, 'allow_profile_edit': True}}
    authority = intake.provision(root, admin, 'role-test', value, timezone.now() + timedelta(hours=2),
                                 True, 'Synthetic role test delegation')
    case = intake.create_case(admin, 'role-test', 'main-role-test', 'Sample role workspace', 'project')
    other = intake.create_case(admin, 'role-test', 'other-role-test', 'Second role workspace', 'project')
    people = {key: users.create_user('role-' + key) for key in domain.BUILT_INS if key != 'admin'}
    for user in people.values():
        for workspace in (case, other):
            intake.change_access(admin, workspace.pk, user.pk, 'case.read', True, 'Synthetic admitted workspace member')
    return root, admin, authority, case, other, people


class PrimaryRoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root, cls.admin, cls.authority, cls.case, cls.other, cls.people = fixture()

    def api(self, url, data=None, client=None, **headers):
        client = client or self.client
        return (client.post('/api/v1' + url, data, content_type='application/json', **headers)
                if data is not None else client.get('/api/v1' + url))

    def validate(self, response, path, method='get', status=200):
        self.assertEqual(response.status_code, status, response.content[:700])
        self.assertIn('no-store', response.headers['Cache-Control'])
        schema = contract()['paths']['/api/v1' + path][method]['responses'][str(status)]['content']['application/json']['schema']
        value = response.json()
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
        return value

    def preview(self, person, key):
        self.case.refresh_from_db()
        return domain.proposal(domain.review(self.admin, self.case, person.pk), key)

    def assign(self, person, key):
        preview = self.preview(person, key)
        return domain.apply(self.admin, self.case.pk, person.pk, key, preview['fingerprint'],
                            'Reviewed exact role access', uuid4())

    def test_six_primary_roles_and_existing_admin_scope(self):
        self.assertTrue(domain.actions(domain.FUNCTIONS) <= set(ACTIONS))
        self.assertTrue(all(action.endswith('.read') or action == 'project.view'
                            for action in domain.actions(domain.FUNCTIONS)))
        self.assertEqual(self.api('/setup/primary-roles').status_code, 401)
        self.client.force_login(self.admin)
        self.assertEqual([role['name'] for role in self.validate(self.api('/setup/primary-roles'),
            '/setup/primary-roles')['roles']], NAMES)
        page = self.client.get(reverse('design_setup'))
        for name in NAMES:
            self.assertContains(page, name)
        self.assertContains(page, reverse('staff_primary_roles', args=[self.case.pk]))
        current = self.validate(self.api(f'/me/workspaces/{self.case.pk}/primary-role'),
                                '/me/workspaces/{case_id}/primary-role')
        self.assertEqual(current['role']['key'], 'admin')
        self.assertFalse(self.admin.is_superuser)
        self.assertTrue(self.api(f'/setup/{self.case.pk}/primary-roles').json()['can_create'])
        target = self.people['ceo']
        with self.assertRaisesMessage(ValidationError, 'catalogue'):
            self.preview(target, 'admin')
        with self.assertRaises(PermissionDenied):
            domain.review(self.admin, self.case, self.admin.pk)

    def test_separate_role_accounts_use_only_their_workspace_reads(self):
        expected = {'pmo-lead': 'meeting.read', 'finance-lead': 'finance.read', 'ceo': 'project.view',
                    'cto': 'delivery.read', 'hr': 'hrfinance.read'}
        for key, person in self.people.items():
            with self.subTest(role=key):
                row = self.assign(person, key)
                require(person, self.case, expected[key])
                with self.assertRaises(PermissionDenied):
                    require(person, self.other, expected[key])
                for action in ('decision.record', 'finance.invoice.review', 'finance.invoice.issue',
                               'emergency.authorize', 'payroll.private.read', 'hrfinance.snapshot.read', 'policy.activate'):
                    with self.assertRaises(PermissionDenied):
                        require(person, self.case, action)
                self.client.force_login(person)
                self.assertEqual(self.api(f'/me/workspaces/{self.case.pk}/primary-role').json()['role']['key'], key)
                self.assertIsNone(self.api(f'/me/workspaces/{self.other.pk}/primary-role').json()['role'])
                self.assertEqual(self.api(f'/setup/{self.case.pk}/primary-roles',
                    {'name': 'Lookalike', 'functions': ['workspace'], 'reason': 'Synthetic denied request'}).status_code, 403)
                self.assertFalse(person.is_staff or person.is_superuser)
                self.assertEqual(set(row.managed_access), set(row.added))
        self.assertFalse(Configuration.objects.filter(case=self.case).exists())

    def test_admin_creates_and_assigns_an_extra_workspace_role(self):
        url = f'/setup/{self.case.pk}/primary-roles'
        page = reverse('staff_primary_roles', args=[self.case.pk])
        self.client.force_login(self.people['ceo'])
        self.assertNotContains(self.client.get(page), 'Add a role')
        self.assertEqual(self.client.post(page, {'name': 'Rejected', 'functions': ['workspace']}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(page), 'Add a role')
        request = {'name': 'Project observer', 'functions': ['reporting'], 'reason': 'Synthetic reviewed role'}
        result = self.validate(self.api(url, request), '/setup/{case_id}/primary-roles', 'post', 201)
        self.assertEqual(result['key'], 'project-observer')
        self.assertEqual(self.api(url, request).status_code, 409)
        self.assertEqual(self.api(url, {**request, 'name': 'Admin'}).status_code, 422)
        self.assertEqual(self.api(url, {**request, 'functions': ['finance.invoice.review']}).status_code, 422)
        self.assertEqual(len(self.api(f'/setup/{self.other.pk}/primary-roles').json()['roles']), len(NAMES))
        self.assertContains(self.client.get(page), 'Project observer')
        self.assign(self.people['ceo'], 'project-observer')
        require(self.people['ceo'], self.case, 'report.read')
        self.assertEqual(StaffRoleDefinition.objects.filter(case=self.case).count(), 1)
        self.assertEqual(connection.vendor, 'postgresql')
        with self.assertRaises(DatabaseError), transaction.atomic():
            StaffRoleDefinition.objects.filter(pk=result['definition_id']).update(name='Rewritten')

    def test_assignment_page_exact_preview_json_replay_and_preserved_access(self):
        person = self.people['pmo-lead']
        self.client.force_login(self.admin)
        path = reverse('staff_primary_role', args=[self.case.pk, person.pk])
        self.assertContains(self.client.get(reverse('staff_person', args=[person.pk])), path)
        review = self.client.get(path, {'role': 'pmo-lead'})
        self.assertContains(review, 'Assign PMO Lead')
        self.assertContains(review, 'View project plans')
        form = review.context['form']
        response = self.client.post(path, {**form.initial, 'reason': 'Reviewed exact project roles', 'confirmed': 'on'})
        self.assertRedirects(response, path, fetch_redirect_response=False)
        self.assertContains(self.client.get(path), 'PMO Lead')
        intake.change_access(self.admin, self.case.pk, person.pk, 'planning.read', True, 'Separate planning permission reviewed')
        url = f'/setup/{self.case.pk}/people/{person.pk}/primary-role'
        preview = self.validate(self.api(url + '?role='), '/setup/{case_id}/people/{person_id}/primary-role')['preview']
        self.assertNotIn('planning.read', preview['removed'])
        body = {'role_key': None, 'fingerprint': preview['fingerprint'], 'reason': 'Reviewed primary role removal',
                'operation': str(uuid4()), 'confirmed': True}
        changed = self.validate(self.api(url, body), '/setup/{case_id}/people/{person_id}/primary-role', 'post')
        self.assertEqual(self.api(url, body).json(), changed)
        self.assertEqual(self.api(url, {**body, 'reason': 'Different request'}).status_code, 409)
        self.assertEqual(set(Grant.objects.filter(case=self.case, user=person, active=True).values_list('action', flat=True)),
                         {'case.read', 'planning.read'})
        with self.assertRaises(DatabaseError), transaction.atomic():
            StaffPrimaryRoleChange.objects.filter(pk=changed['change_id']).update(role_name='Rewritten')

    def test_stale_preview_csrf_and_open_claim_block_role_effects(self):
        person = self.people['finance-lead']
        self.assign(person, 'finance-lead')
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        token = self.api('/me', client=protected).json()['csrf_token']
        url = f'/setup/{self.case.pk}/people/{person.pk}/primary-role'
        data = {'role_key': None, 'fingerprint': self.preview(person, None)['fingerprint'], 'reason': 'Reviewed removal',
                'operation': str(uuid4()), 'confirmed': True}
        self.assertEqual(self.api(url, data, protected).json()['code'], 'csrf_failed')
        intake.change_access(self.admin, self.case.pk, person.pk, 'report.read', True, 'Separate report access')
        self.assertEqual(self.api(url, data, protected, HTTP_X_CSRFTOKEN=token).status_code, 409)
        pending = HumanTask.objects.create(case=self.case, claimed_by=person, created_by=self.admin,
            kind='factory_information', factory_key='synthetic-primary-role-handover')
        data['fingerprint'] = self.preview(person, None)['fingerprint']
        rejected = self.api(url, data, protected, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(rejected.status_code, 422)
        self.assertIn('Release this person', rejected.json()['message'])
        self.assertEqual(StaffPrimaryRoleChange.objects.filter(user=person).count(), 1)
        pending.status = 'returned'
        pending.save(update_fields=['status'])
        self.assertEqual(self.api(url, data, protected, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_admin_delegation_ceiling_revocation_and_cross_workspace_denial(self):
        person = self.people['cto']
        self.client.force_login(self.admin)
        private = Case.objects.create(tenant='unrelated', title='Another company workspace', kind='project', synthetic=True)
        self.assertEqual(self.api(f'/setup/{private.pk}/primary-roles').status_code, 404)
        self.assertEqual(self.api(f'/setup/{self.case.pk}/people/999999/primary-role').status_code, 404)
        value = deepcopy(self.authority.value)
        value['allowed_actions'].remove('emergency.read')
        intake.provision(self.root, self.admin, self.case.tenant, value, self.authority.expires_at, True, 'Reduced test delegation')
        self.assertEqual(self.api(f'/setup/{self.case.pk}/people/{person.pk}/primary-role?role=cto').status_code, 403)
        self.assertEqual(self.api(f'/setup/{self.case.pk}/primary-roles',
            {'name': 'Broader role', 'functions': ['changes'], 'reason': 'Review scope cap'}).status_code, 403)
        intake.provision(self.root, self.admin, self.case.tenant, value, self.authority.expires_at, False, 'Revoked test delegation')
        self.assertIsNone(self.api(f'/me/workspaces/{self.case.pk}/primary-role').json()['role'])
        self.assertEqual(self.api(f'/setup/{self.case.pk}/primary-roles',
            {'name': 'Expired role', 'functions': ['workspace'], 'reason': 'Attempt after revocation'}).status_code, 403)

    def test_hr_assignment_enables_only_its_scoped_project_destinations(self):
        person = self.people['hr']
        self.client.force_login(self.admin)
        setup = f'/setup/{self.case.pk}/people/{person.pk}/primary-role'
        reviewed = self.api(setup + '?role=hr').json()['preview']
        body = {'role_key': 'hr', 'fingerprint': reviewed['fingerprint'], 'reason': 'Synthetic HR role review',
                'operation': str(uuid4()), 'confirmed': True}
        row = self.validate(self.api(setup, body), '/setup/{case_id}/people/{person_id}/primary-role', 'post')
        self.assertEqual(row['added'], ['hrfinance.read'])

        self.client.force_login(person)
        url = f'/projects/{self.case.pk}/hr'
        tab = reverse('design_project_tab', args=[self.case.pk, 'hr'])
        summary = self.client.get(reverse('design_project', args=[self.case.pk]))
        self.assertContains(summary, tab)
        page = self.client.get(tab)
        self.assertContains(page, 'Human resources')
        self.assertIn('no-store', page['Cache-Control'])
        links = self.validate(self.api(url), '/projects/{case_id}/hr')['destinations']
        self.assertEqual([link['key'] for link in links], ['handoffs', 'questions'])
        for link in links:
            self.assertContains(page, link['django_url'])
            self.assertEqual(self.client.get(link['django_url']).status_code, 200)
        self.assertNotContains(page, 'Staff matching corrections')
        self.assertEqual(self.client.get(reverse('design_hr_payroll_corrections', args=[self.case.pk])).status_code, 403)
        self.assertEqual(self.api(f'/projects/{self.other.pk}/hr').status_code, 403)
        for action in ('hrfinance.authorize', 'hrfinance.capture', 'hrfinance.respond', 'payroll.read', 'staff.authority'):
            with self.assertRaises(PermissionDenied):
                require(person, self.case, action)

        intake.change_access(self.admin, self.case.pk, person.pk, 'agent.extract', True, 'Independent assistant access')
        links = self.api(url).json()['destinations']
        self.assertEqual(links[-1]['key'], 'assistant')
        self.assertContains(self.client.get(links[-1]['django_url']), 'Zainab')
        self.assign(person, None)
        self.assertEqual(self.api(url).status_code, 403)
        self.assertEqual(self.client.get(tab).status_code, 403)
        require(person, self.case, 'agent.extract')

    def test_preexisting_custom_hr_role_keeps_its_exact_definition(self):
        person = self.people['ceo']
        before_hr = {key: role for key, role in domain.BUILT_INS.items() if key != 'hr'}
        with patch.dict(domain.BUILT_INS, before_hr, clear=True):
            definition = domain.create_definition(self.admin, self.case.pk, 'HR', ['reporting'], 'Prior custom role')
            old = self.assign(person, 'hr')
        reviewed = domain.review(self.admin, self.case, person.pk)
        alias = f'custom-role-{definition.pk}'
        self.assertEqual(reviewed['current'], {'key': alias, 'name': 'HR', 'state': 'active'})
        self.assertEqual(domain.own_role(person, self.case), reviewed['current'])
        self.assertFalse(domain.proposal(reviewed, alias)['changed'])
        self.assertEqual(old.definition_id, definition.pk)
        self.assertEqual(StaffPrimaryRoleChange.objects.get(pk=old.pk).role_key, 'hr')

        new = self.assign(person, 'hr')
        self.assertIsNone(new.definition_id)
        self.assertEqual(new.added, ['hrfinance.read'])
        self.assertEqual(new.removed, ['report.read'])
        self.assertEqual(domain.own_role(person, self.case)['key'], 'hr')
        with self.assertRaises(ValidationError):
            domain.create_definition(self.admin, self.case.pk, 'HR', ['reporting'], 'Conflicting role')


class ConcurrentRoleTests(TransactionTestCase):
    def test_same_review_cannot_apply_two_conflicting_commands(self):
        _, admin, _, case, _, people = fixture()
        person = people['pmo-lead']
        case.refresh_from_db()
        reviewed = domain.review(admin, case, person.pk)
        plans = {key: domain.proposal(reviewed, key)['fingerprint'] for key in ('pmo-lead', 'cto')}
        barrier = Barrier(2)

        def apply_choice(key):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                domain.apply(admin, case.pk, person.pk, key, plans[key], 'Reviewed concurrent assignment', uuid4())
                return 'applied'
            except ValidationError as error:
                return error.messages[0].split(':', 1)[0]
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(apply_choice, plans))
        self.assertCountEqual(outcomes, ['applied', 'STALE_VERSION'])
        self.assertEqual(StaffPrimaryRoleChange.objects.filter(user=person).count(), 1)
