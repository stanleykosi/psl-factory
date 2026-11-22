from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case, ClientWorkspaceLink
from apps.finance.models import Invoice
from apps.identity import staff
from apps.identity.models import Grant
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_client_workspace_link_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class ClientWorkspaceLinkFixtureTests(TestCase):
    def test_trial_reviews_second_link_without_replaying_the_first(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = configured()
        origin = data['scopes'][0]['case']
        trial = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(data['actor'], origin.pk, 'sample-admitted-client-link-maker',
            'Sample client link preparer', 'sample-client-link-maker@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!client-link-sample.062')
        original_grants = set(Grant.objects.filter(user=maker).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1000, maker.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        first = sample['projects']['installation']
        second = sample['projects']['follow-up']
        project = Case.objects.get(pk=second['case'])
        self.assertEqual((sample['maker'], sample['reviewer']), (maker.pk, trial.pk))
        self.assertEqual(first['original_link'], first['current_link'])
        self.assertTrue(first['contact'])
        self.assertIsNone(second['current_link'])
        self.assertFalse(second['contact'])
        self.client.force_login(maker)
        self.assertNotContains(self.client.get(second['detail']), 'Confirm client link')
        self.client.force_login(trial)
        group = self.client.get(sample['group'])
        self.assertContains(group, first['title'])
        self.assertNotContains(group, second['title'])
        self.assertContains(self.client.get(second['detail']), 'Confirm client link')
        post = self.client.post(second['detail'], {'operation': 'confirm', 'revision': rev(project),
                                                  'evidence': second['proof']})
        self.assertEqual(post.status_code, 302)

        linked = self.client.get(sample['group'])
        self.assertContains(linked, first['title'])
        self.assertContains(linked, second['title'])
        self.assertContains(linked, 'Billing contact missing')
        self.assertContains(self.client.get(sample['missing_filter']), '2 projects in view')
        self.assertEqual(ClientWorkspaceLink.objects.filter(case__tenant=seed.TENANT).count(), 2)
        original = ClientWorkspaceLink.objects.get(pk=first['original_link'])
        successor = ClientWorkspaceLink.objects.get(case=project)
        self.assertEqual(successor.group_key, original.group_key)
        self.assertEqual((successor.evidence.created_by_id, successor.reviewer_id), (maker.pk, trial.pk))
        self.assertIsNone(successor.previous_id)
        self.assertEqual(original.evidence_id, first['proof'])
        self.assertFalse(Invoice.objects.filter(case__tenant=seed.TENANT).exists())
        replay = seed.prepare(invitation.pk, maker.pk)
        self.assertTrue(replay['preserved'])
        self.assertEqual(replay['projects']['follow-up']['current_link'], successor.pk)
        self.assertEqual(set(Grant.objects.filter(user=maker).exclude(case__tenant=seed.TENANT)
                             .values_list('case_id', 'action', 'active')), original_grants)
