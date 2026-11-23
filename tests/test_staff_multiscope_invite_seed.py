from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.alert_models import AccountDelivery
from apps.core.models import Case
from apps.identity import intake, staff
from apps.identity.models import Grant
from apps.identity.staff_models import StaffAdmission, StaffInvitation
from tests.railway_staff_multiscope_invite_seed import BOOTSTRAP, PROFILES, RECIPIENT, TENANT, authority_value, prepare


class MultiWorkspaceInvitationSeedTests(TestCase):
    def test_isolated_preview_exposes_a_base_role_and_preserves_previous_invitation_history(self):
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
        self.assertNotContains(page, Case.objects.get(pk=seeded['second']).title)
        self.assertNotContains(page, prior.title)
        form = page.context['form']
        self.assertEqual({key for key,_ in form.fields['base_role'].choices if key},
                         {'pmo-lead','finance-lead','ceo','cto','hr','admin'})
        self.assertNotIn('profile',form.fields)
        self.assertContains(page, 'No staff invitation recorded.')

        invite = self.client.post(seeded['form'], {
            **RECIPIENT,
            'base_role':'ceo','role_mode':'standalone',
            'revision': form.initial['revision'],
            'project_review': form.initial['project_review'],
        })
        self.assertContains(invite, 'Preview invitation')
        self.assertContains(invite, 'rel="noopener noreferrer"')
        self.assertTrue(invite.context['invitation_link'].startswith('http://testserver/staff/join/#'))
        self.assertFalse(users.filter(username=RECIPIENT['username']).exists())

    def test_role_preview_and_optional_alert_handoff_require_sign_in(self):
        trial = get_user_model().objects.create_user('psl-agent-trial')
        seeded = prepare(trial)
        first = Case.objects.get(pk=seeded['first'])
        invitation, token = staff.invite_person(trial,first.pk,RECIPIENT['username'],RECIPIENT['name'],
            RECIPIENT['email'],first.revision,role='ceo',mode='standalone',team_id=None)
        join = reverse('staff_accept_invite')
        preview = self.client.post(join, {'action': 'preview', 'token': token})
        self.assertContains(preview, first.title)
        self.assertContains(preview, 'CEO')
        self.assertContains(preview, 'Review optional WhatsApp alerts after signing in')
        self.assertFalse(StaffAdmission.objects.filter(invitation=invitation).exists())
        password = 'Synthetic-Workbench-Setup-763'
        settings_path = reverse('design_alert_preferences')
        login = reverse('login', query={'next': settings_path})
        response = self.client.post(join, {'action': 'accept', 'token': token, 'password': password,
                                         'confirm': password, 'review_alerts': 'on'})
        self.assertRedirects(response, login, fetch_redirect_response=False)
        self.assertFalse(self.client.session.get('_auth_user_id'))
        admission = StaffAdmission.objects.get(invitation=invitation)
        self.assertFalse(Grant.objects.filter(user=admission.user).exists())
        self.assertEqual(admission.invitation.staffmembership.role,'ceo')
        signed_in = self.client.post(login, {'username': RECIPIENT['username'], 'password': password, 'next': settings_path})
        self.assertRedirects(signed_in, settings_path, fetch_redirect_response=False)
        self.assertContains(self.client.get(settings_path), 'Waiting for a verified WhatsApp number')
        self.assertFalse(AccountDelivery.objects.filter(actor=admission.user).exists())
