"""The demo's change line: Lagoon and Delta each have one logged change version to choose (D-216)."""
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from apps.core.models import Case
from apps.pmo.models import ChangeRequest

LAGOON, DELTA = 'Lagoon Health · patient app', 'Delta Foods · ordering app'


def sources(username, title, **query):
    client = Client()
    client.force_login(get_user_model().objects.get(username=username + '@psl-demo.test'))
    case = Case.objects.get(tenant='psl-demo', title=title)
    return client.get(f'/api/v1/projects/{case.pk}/intake-sources', {'line': 'pmo-change/v1', **query})


class SeedDemoChangesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with tempfile.TemporaryDirectory() as folder:
            call_command('seed_psl_demo', credentials_file=str(Path(folder) / 'people.txt'), stdout=StringIO())

    def test_each_signed_project_offers_one_change_version_and_a_second_run_adds_nothing(self):
        call_command('seed_demo_changes', stdout=StringIO())
        call_command('seed_demo_changes', stdout=StringIO())
        self.assertEqual(ChangeRequest.objects.count(), 2)
        for who, title in (('tunde.bello', LAGOON), ('chinedu.okeke', DELTA)):
            response = sources(who, title, field='version_id')
            self.assertEqual(response.status_code, 200, response.content)
            items = response.json()['items']
            self.assertEqual(len(items), 1, items)
            follow = sources(who, title, field='inputs.authorization_id', parent_id=items[0]['id'])
            self.assertEqual(follow.status_code, 200, follow.content)
            self.assertEqual(follow.json()['items'], [])


class RefusesOutsideTheDemoTests(TestCase):
    def test_it_refuses_a_workspace_that_is_not_the_synthetic_demo(self):
        Case.objects.create(tenant='other', title=LAGOON, kind='project', synthetic=False)
        with self.assertRaises(CommandError):
            call_command('seed_demo_changes', stdout=StringIO())
        self.assertFalse(ChangeRequest.objects.exists())
