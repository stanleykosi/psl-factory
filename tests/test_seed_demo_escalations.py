"""The demo's escalation line: the PMO Lead reads the register, and Lagoon has a placeholder profile and request (D-216)."""
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from apps.core.models import Case
from apps.pmo.models import EscalationProfile, EscalationRequest

LAGOON, DELTA = 'Lagoon Health · patient app', 'Delta Foods · ordering app'


def register(username, title):
    client = Client()
    client.force_login(get_user_model().objects.get(username=username + '@psl-demo.test'))
    case = Case.objects.get(tenant='psl-demo', title=title)
    return client.get(f'/api/v1/projects/{case.pk}/escalation-register')


class SeedDemoEscalationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with tempfile.TemporaryDirectory() as folder:
            call_command('seed_psl_demo', credentials_file=str(Path(folder) / 'people.txt'), stdout=StringIO())
        cls.lagoon = Case.objects.get(tenant='psl-demo', title=LAGOON)

    def test_the_pmo_lead_reads_the_register_and_roles_without_the_read_do_not(self):
        self.assertEqual(register('kemi.adebayo', LAGOON).status_code, 200)
        self.assertEqual(register('kemi.adebayo', DELTA).status_code, 200)
        self.assertNotEqual(register('ada.okafor', LAGOON).status_code, 200)
        self.assertNotEqual(register('ngozi.adeyemi', LAGOON).status_code, 200)

    def test_the_command_adds_a_profile_and_a_request_once(self):
        out = StringIO()
        call_command('seed_demo_escalations', stdout=out)
        profile = EscalationProfile.objects.get(state__issue__case=self.lagoon)
        self.assertEqual(profile.state.issue.reference, 'ISS-0233')
        self.assertIn('Placeholder', profile.note)
        request = EscalationRequest.objects.get(profile=profile)
        self.assertEqual((request.direction, request.target), ('escalate', 'PMO'))
        call_command('seed_demo_escalations', stdout=StringIO())
        self.assertEqual(EscalationProfile.objects.count(), 1)
        self.assertEqual(EscalationRequest.objects.count(), 1)
        for who in ('tunde.bello', 'kemi.adebayo'):
            body = register(who, LAGOON).json()
            self.assertEqual((len(body['issues']), len(body['profiles']), len(body['requests'])), (1, 1, 1))
        self.assertTrue(register('tunde.bello', LAGOON).json()['can_request'])
        self.assertFalse(register('kemi.adebayo', LAGOON).json()['can_request'])


class RefusesOutsideTheDemoTests(TestCase):
    def test_it_refuses_a_workspace_that_is_not_the_synthetic_demo(self):
        Case.objects.create(tenant='other', title=LAGOON, kind='project', synthetic=False)
        with self.assertRaises(CommandError):
            call_command('seed_demo_escalations', stdout=StringIO())
        self.assertFalse(EscalationProfile.objects.exists())
