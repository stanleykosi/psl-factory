from django.test import TestCase
from django.urls import reverse

from apps.identity.models import Grant
from tests.helpers import setup_case


class SetupOverviewTests(TestCase):
    def test_read_only_rules_and_deferred_payroll_fields(self):
        actor, case = setup_case()
        self.client.force_login(actor)
        url = reverse('workspace_settings',args=[case.pk])
        self.assertContains(self.client.get(url,{'area':'finance'}),'Stage billing terms')
        self.assertContains(self.client.get(url,{'area':'delivery'}),'Hypercare acceptance')
        self.assertContains(self.client.get(url,{'area':'payroll'}),'Payroll field visibility is awaiting an owner decision.')
        Grant.objects.filter(case=case,user=actor,action='policy.configure').update(active=False)
        page = self.client.get(url)
        self.assertContains(page,'View access only.')
        self.assertNotContains(page,'Review rule versions and configuration')
