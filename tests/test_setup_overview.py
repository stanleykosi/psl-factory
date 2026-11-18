from django.test import TestCase
from django.urls import reverse

from apps.identity.models import Grant
from tests.helpers import setup_case


class SetupOverviewTests(TestCase):
    def test_setup_filters_current_workspace_permissions_before_pagination(self):
        from apps.core.models import Case

        actor, case = setup_case()
        self.client.force_login(actor)
        others = Case.objects.bulk_create([
            Case(title=f'Setup sample {number:02}', tenant=case.tenant, kind='project', synthetic=True)
            for number in range(26)
        ])
        Grant.objects.bulk_create([Grant(case=row, user=actor, action='case.read') for row in others])
        url = reverse('design_setup')
        page = self.client.get(url)
        self.assertEqual(page.context['workspaces'].paginator.count, 1)
        self.assertContains(page, reverse('workspace_settings', args=[case.pk]))
        self.assertNotContains(page, 'Staff accounts')
        Grant.objects.bulk_create([Grant(case=row, user=actor, action='policy.read') for row in others[:25]])
        page = self.client.get(url)
        self.assertEqual(page.context['workspaces'].paginator.count, 26)
        self.assertTrue(page.context['workspaces'].has_next())
        second = self.client.get(url, {'page': 2})
        self.assertEqual(len(second.context['workspaces']), 1)
        self.assertNotContains(self.client.get(url, {'q': 'missing sample'}), str(case.pk))
        Grant.objects.filter(case=case, user=actor, action='policy.read').update(active=False)
        self.assertNotContains(self.client.get(url), reverse('workspace_settings', args=[case.pk]))

    def test_manage_only_authority_is_independent_of_case_creation_and_is_current(self):
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from apps.identity import intake

        actor, case = setup_case()
        Grant.objects.filter(case=case, user=actor, action='policy.read').update(active=False)
        root = get_user_model().objects.create_superuser('setup-test-root', password='test-only-password')
        value = {'format': 'psl.tenant-access/v1', 'create_cases': False, 'manage_access': True,
                 'kinds': ['project'], 'allowed_actions': ['case.read'], 'initial_actions': [],
                 'classification': 'synthetic'}
        expiry = timezone.now() + timedelta(hours=1)
        intake.provision(root, actor, case.tenant, value, expiry, True, 'Sample account manager')
        self.assertEqual(intake.options(actor), [])
        self.assertEqual(len(intake.options(actor, 'manage_access')), 1)
        self.client.force_login(actor)
        page = self.client.get(reverse('design_setup'))
        self.assertContains(page, reverse('case_access', args=[case.pk]))
        self.assertNotContains(page, reverse('workspace_settings', args=[case.pk]))
        intake.provision(root, actor, case.tenant, value, expiry, False, 'Withdraw sample account manager')
        self.assertEqual(self.client.get(reverse('design_setup')).context['workspaces'].paginator.count, 0)

    def test_setup_is_safe_read_only_and_normal_navigation_exposes_it(self):
        from apps.core.models import Audit, Case

        actor, case = setup_case()
        self.client.force_login(actor)
        before = (Audit.objects.count(), Case.objects.count(), Grant.objects.count())
        self.assertContains(self.client.get(reverse('case', args=[case.pk])), reverse('design_setup'))
        self.assertEqual(self.client.post(reverse('design_setup'), {}).status_code, 405)
        self.assertEqual(self.client.get(reverse('design_setup')).status_code, 200)
        self.assertEqual(before, (Audit.objects.count(), Case.objects.count(), Grant.objects.count()))

    def test_read_only_rules_and_deferred_payroll_fields(self):
        actor, case = setup_case()
        self.client.force_login(actor)
        url = reverse('workspace_settings',args=[case.pk])
        self.assertContains(self.client.get(url,{'area':'finance'}),'Stage billing terms')
        self.assertContains(self.client.get(url,{'area':'delivery'}),'Hypercare acceptance')
        self.assertContains(self.client.get(url,{'area':'payroll'}),'Choose the HR source, recipients, purpose and retention terms')
        Grant.objects.filter(case=case,user=actor,action='policy.configure').update(active=False)
        page = self.client.get(url)
        self.assertContains(page,'View access only.')
        self.assertNotContains(page,'Review rule versions and configuration')
