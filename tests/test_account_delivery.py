from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.core import account_delivery, alerts
from apps.core.alert_models import AccountDelivery, SampleAccountInbox
from config.contact_runtime import ContactRuntime, Route, parse
from tests.helpers import setup_case

WORK_EMAIL = 'delivery-trial@accounts.invalid'
SAMPLE = ContactRuntime('https://factory.example.test', '', (
    Route('delivery-trial', WORK_EMAIL, '+12025550123', True),
), True)


@override_settings(CONTACT_DELIVERY=SAMPLE)
class AccountDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case(username='delivery-trial')
        cls.actor.set_password('Previous-sample-password?25')
        cls.actor.email = WORK_EMAIL
        cls.actor.save(update_fields=['password', 'email'])
        conversation = AssistantConversation.objects.create(actor=cls.actor, case=cls.case, persona='chidi')
        AssistantTurn.objects.create(conversation=conversation, status='answered', question='Synthetic question',
                                     answer='Sensitive Assistant content that stays inside the app')

    def test_recovery_http_through_original_email_new_sign_in_and_replay(self):
        reset = reverse('password_reset')
        accepted = reverse('factory_recovery_sent')
        for address in ('missing@accounts.invalid', WORK_EMAIL, WORK_EMAIL.upper()):
            self.assertRedirects(self.client.post(reset, {'email': address}), accepted)
        self.assertEqual(AccountDelivery.objects.count(), 1)
        call_command('work_account_delivery')
        row = AccountDelivery.objects.get()
        self.assertEqual(row.state, AccountDelivery.State.DELIVERED)
        self.assertTrue(SampleAccountInbox.objects.filter(delivery=row, fingerprint=row.fingerprint).exists())
        token = account_delivery.recovery_token(row)
        exchange = reverse('factory_recovery_token')
        choose = reverse('factory_recovery_confirm')
        self.assertEqual(self.client.get(exchange)['Referrer-Policy'], 'same-origin')
        second_client = Client()
        for client in (self.client, second_client):
            self.assertRedirects(client.post(exchange, {'token': token}), choose)
            self.assertContains(client.get(choose), 'Choose a new password')
        weak = self.client.post(choose, {'new_password1': 'short', 'new_password2': 'short'})
        self.assertContains(weak, 'at least 12 characters')
        new = 'Synthetic!greenhouse.44.ORBIT'
        self.assertRedirects(self.client.post(choose, {'new_password1': new, 'new_password2': new}),
                             reverse('factory_recovery_complete'))
        self.assertContains(second_client.post(choose, {'new_password1': new, 'new_password2': new}), 'This link has expired')
        self.assertRedirects(self.client.post(exchange, {'token': token}), choose)
        self.assertContains(self.client.get(choose), 'This link has expired')
        self.assertTrue(self.client.login(username=self.actor.username, password=new))

    def test_expired_wrong_session_and_other_viewer_cannot_use_recovery(self):
        self.client.post(reverse('password_reset'), {'email': WORK_EMAIL})
        call_command('work_account_delivery')
        row = AccountDelivery.objects.get()
        other = get_user_model().objects.create_user('other-contact')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('design_sample_mailbox')).status_code, 404)
        AccountDelivery.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        self.client.post(reverse('factory_recovery_token'), {'token': account_delivery.recovery_token(row)})
        self.assertContains(self.client.get(reverse('factory_recovery_confirm')), 'This link has expired')

    def test_secure_recovery_post_uses_same_origin_and_csrf(self):
        secure = Client(enforce_csrf_checks=True)
        url = reverse('password_reset')
        form = secure.get(url, secure=True)
        self.assertEqual(form['Referrer-Policy'], 'same-origin')
        values = {'email': WORK_EMAIL}
        self.assertEqual(secure.post(url, values, secure=True).status_code, 403)
        values['csrfmiddlewaretoken'] = form.cookies['csrftoken'].value
        response = secure.post(url, values, secure=True, HTTP_REFERER=f'https://testserver{url}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AccountDelivery.objects.count(), 1)

    def test_native_alert_delivers_once_per_channel_and_has_private_receipts(self):
        self.client.force_login(self.actor)
        preferences = reverse('design_alert_preferences')
        self.assertRedirects(self.client.post(preferences, {'revision': 1, 'email_requested': 'on', 'whatsapp_requested': 'on'}),
                             preferences)
        for _ in range(2):
            call_command('work_account_delivery')
        rows = AccountDelivery.objects.filter(actor=self.actor, purpose='alert', state='delivered')
        self.assertEqual(set(rows.values_list('channel', flat=True)), {'email', 'whatsapp'})
        self.assertEqual(rows.count(), 2)
        self.assertEqual(SampleAccountInbox.objects.count(), 2)
        page = self.client.get(preferences)
        for row in rows:
            self.assertContains(page, row.receipt)
        self.assertNotContains(page, 'Sensitive Assistant content')
        self.assertNotContains(page, WORK_EMAIL)
        other = get_user_model().objects.create_user('other-alert-viewer')
        self.client.force_login(other)
        self.assertNotContains(self.client.get(preferences), 'Delivery verified')

    def test_opt_out_and_revoked_source_hold_queued_delivery(self):
        alerts.save_preferences(self.actor, 1, True, True)
        account_delivery.queue_alerts(self.actor)
        alerts.save_preferences(self.actor, 2, False, True)
        alert = AccountDelivery.objects.get(channel='whatsapp')
        self.client.force_login(self.actor)
        self.client.post(reverse('design_alert_read'), {'key': alert.source})
        call_command('work_account_delivery')
        self.assertEqual(AccountDelivery.objects.filter(state='held').count(), 2)
        self.assertFalse(SampleAccountInbox.objects.exists())

    def test_uncertain_provider_effect_checks_original_without_another_send(self):
        runtime = ContactRuntime(SAMPLE.origin, 'https://relay.example.test/v1/deliveries', (
            Route(self.actor.username, self.actor.email, '', True, self.actor.pk),
        ), False)
        with self.settings(CONTACT_DELIVERY=runtime), patch('apps.core.account_delivery.receipt_for') as relay:
            relay.side_effect = [None, 'verified-original']
            self.client.post(reverse('password_reset'), {'email': WORK_EMAIL})
            call_command('work_account_delivery')
            row = AccountDelivery.objects.get()
            self.assertEqual(row.state, AccountDelivery.State.UNCERTAIN)
            AccountDelivery.objects.filter(pk=row.pk).update(next_check=timezone.now())
            call_command('work_account_delivery')
        row.refresh_from_db()
        self.assertEqual(row.receipt, 'verified-original')
        self.assertEqual(relay.call_count, 2)
        self.assertEqual(relay.call_args_list[0].args[1:], relay.call_args_list[1].args[1:])
        self.assertIn('#', relay.call_args_list[0].kwargs['payload']['body'])
        self.assertIsNone(relay.call_args_list[1].kwargs['payload'])

    def test_route_contract_rejects_wrong_version_and_ambiguous_destinations(self):
        config = {'version': 1, 'origin': SAMPLE.origin, 'relay': 'https://relay.example.test/v1/deliveries',
                  'routes': [{'account_id': self.actor.pk, 'username': self.actor.username, 'email': WORK_EMAIL,
                              'whatsapp': '+12025550123', 'recovery': True}]}
        self.assertEqual(parse(config).routes[0].account_id, self.actor.pk)
        with self.assertRaises(ValueError):
            parse(dict(config, version=True))
        with self.assertRaises(ValueError):
            parse(dict(config, origin='https://factory.example.test/unreviewed'))
        with self.assertRaises(ValueError):
            parse(dict(config, routes=config['routes'] + [dict(config['routes'][0], account_id=999, username='different')]))
