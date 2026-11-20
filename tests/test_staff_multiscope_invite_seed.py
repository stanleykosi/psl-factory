from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.alert_models import AccountDelivery
from apps.core.models import Case
from apps.identity import intake, staff
from apps.identity.models import Grant
from apps.identity.staff_models import StaffAdmission, StaffInvitation
from tests.railway_staff_multiscope_invite_seed import BOOTSTRAP, PROFILES, RECIPIENT, TENANT, authority_value, prepare


class MultiWorkspaceInvitationSeedTests(TestCase):
    def test_isolated_preview_prepares_two_exact_profile_choices_and_no_invitation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        trial = users.create_user('psl-agent-trial')
        prior_operator = users.create_user('sample-prior-workspace-operator')
        prior_root = users.create_superuser('sample-prior-workspace-bootstrap')
        prior_authority = intake.provision(prior_root, prior_operator, 'sample-prior-invitation', authority_value(True),
            timezone.now() + timedelta(hours=1), True, 'Existing synthetic invitation authority')
        prior = intake.create_case(prior_operator, prior_authority.tenant, 'before-fixture', 'Separate invitation workspace', 'project')
        previous, _ = staff.invite(prior_operator, prior.pk, 'sample-previous-recipient', 'Sample prior recipient',
            'sample-prior@example.invalid', ['case.read'], prior.revision, profile_key=PROFILES[1]['key'])
        previous_pin = (previous.case_id, previous.authority_id, previous.profile_key, previous.workspace_profiles, previous.expires_at)
        before = (StaffInvitation.objects.count(), StaffAdmission.objects.count(), AccountDelivery.objects.count())

        seeded = prepare(trial)
        self.assertEqual(prepare(trial), seeded)
        self.assertEqual(seeded['existing_invitations'], 0)
        self.assertFalse(users.filter(username=RECIPIENT['username']).exists())
        self.assertEqual((StaffInvitation.objects.count(), StaffAdmission.objects.count(), AccountDelivery.objects.count()), before)
        previous.refresh_from_db()
        self.assertEqual((previous.case_id, previous.authority_id, previous.profile_key, previous.workspace_profiles,
                          previous.expires_at), previous_pin)
        technical = users.get(username=BOOTSTRAP)
        self.assertFalse(technical.has_usable_password())
        self.assertFalse(technical.is_active or technical.is_staff or technical.is_superuser)
        self.assertEqual(set(Grant.objects.filter(user=trial).values_list('case__tenant', 'action')), {(TENANT, 'case.read')})

        self.client.force_login(trial)
        page = self.client.get(seeded['form'])
        self.assertContains(page, 'Invite a person')
        self.assertContains(page, Case.objects.get(pk=seeded['first']).title)
        self.assertContains(page, Case.objects.get(pk=seeded['second']).title)
        self.assertNotContains(page, prior.title)
        form = page.context['form']
        keys = {profile['key'] for profile in PROFILES}
        self.assertEqual({key for key, _ in form.fields['profile'].choices if key}, keys)
        self.assertEqual({key for key, _ in form.fields[seeded['additional_field']].choices if key}, keys)
        self.assertTrue(page.context['show_all_projects'])
        self.assertContains(page, 'No staff invitation recorded.')
