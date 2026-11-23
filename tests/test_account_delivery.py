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

    def test_same_origin_api_recovers_signs_in_and_updates_account_preferences(self):
        url = '/api/v1'
        browser = Client(enforce_csrf_checks=True)
        session = browser.get(url + '/session', secure=True)
        csrf = session.json()['csrf_token']
        self.assertFalse(session.json()['signed_in'])

        def post(path, payload, *, client=browser, with_token=True):
            headers = {'HTTP_ORIGIN': 'https://testserver'}
            if with_token:
                headers['HTTP_X_CSRFTOKEN'] = csrf
            return client.post(url + path, payload, content_type='application/json', secure=True, **headers)

        invalid = post('/session', {'username': WORK_EMAIL, 'password': 'incorrect-synthetic-password'})
        self.assertEqual((invalid.status_code, invalid.json()['code']), (422, 'sign_in_failed'))
        self.assertFalse(browser.get(url + '/session', secure=True).json()['signed_in'])
        self.assertEqual(post('/accounts/recovery/request', {'email': WORK_EMAIL}, with_token=False).status_code, 403)
        real = post('/accounts/recovery/request', {'email': WORK_EMAIL})
        missing = post('/accounts/recovery/request', {'email': 'missing@accounts.invalid'})
        self.assertEqual((real.status_code, missing.status_code), (202, 202))
        self.assertEqual(real.json(), missing.json())
        call_command('work_account_delivery')
        original = AccountDelivery.objects.get()
        self.assertTrue(SampleAccountInbox.objects.filter(delivery=original).exists())
        code = account_delivery.recovery_token(original)
        self.assertTrue(post('/accounts/recovery/link', {'token': code}).json()['ready'])
        recovery = url + '/accounts/recovery/password'
        self.assertTrue(browser.get(recovery, secure=True).json()['ready'])
        self.assertFalse(self.client.get(recovery).json()['ready'])
        self.assertEqual(post('/accounts/recovery/password', {'new_password1': 'weak', 'new_password2': 'weak'}).status_code, 422)
        password = 'Synthetic!Rainfield.54.account'
        confirmed = post('/accounts/recovery/password', {'new_password1': password, 'new_password2': password})
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        self.assertFalse(post('/accounts/recovery/link', {'token': code}).json()['ready'])

        signed_in = post('/session', {'username': WORK_EMAIL, 'password': password, 'next_url': 'https://external.invalid'})
        self.assertEqual(signed_in.status_code, 200, signed_in.content)
        self.assertTrue(signed_in.json()['signed_in'])
        self.assertNotIn('external.invalid', signed_in.json()['next_url'])
        csrf = signed_in.json()['csrf_token']
        self.assertTrue(browser.get(url + '/me/onboarding', secure=True).json()['admitted'])
        account = browser.get(url + '/me/account', secure=True).json()
        self.assertEqual(account['email'], WORK_EMAIL)
        self.assertTrue(account['alerts']['whatsapp_ready'])
        updated = post('/me/alert-preferences', {'revision': account['alerts']['revision'],
                                               'email_requested': False, 'whatsapp_requested': True})
        self.assertEqual(updated.status_code, 200, updated.content)
        after = 'Sample!Current87.Forest.Test'
        changed = post('/me/account/password', {'old_password': password, 'new_password1': after, 'new_password2': after})
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertTrue(changed.json()['signed_in'])
        csrf = changed.json()['csrf_token']
        self.assertFalse(post('/session/logout', {}).json()['signed_in'])
        self.assertEqual(browser.get(url + '/me', secure=True).status_code, 401)

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

    @override_settings(CONTACT_DELIVERY=None)
    def test_staff_alert_stays_in_app_when_channels_are_disconnected(self):
        self.client.force_login(self.actor)
        alerts.save_preferences(self.actor, 1, True, True)
        with patch('apps.core.account_delivery.receipt_for') as relay:
            call_command('work_account_delivery')
            relay.assert_not_called()
        self.assertContains(self.client.get(reverse('design_alerts')), 'Assistant reply')
        self.assertFalse(AccountDelivery.objects.filter(actor=self.actor, purpose='alert').exists())

    def test_native_alert_delivers_once_per_channel_and_has_private_receipts(self):
        self.client.force_login(self.actor)
        preferences = reverse('design_alert_preferences')
        self.assertRedirects(self.client.post(preferences, {'revision': 1, 'email_requested': 'on', 'whatsapp_requested': 'on'}),
                             preferences)
        api = '/api/v1/me/alert-preferences'
        updated = self.client.post(api, {'revision': 2, 'email_requested': True, 'whatsapp_requested': True},
                                   content_type='application/json')
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertTrue(updated.json()['email_ready'])
        self.assertTrue(updated.json()['whatsapp_ready'])
        for _ in range(2):
            call_command('work_account_delivery')
        rows = AccountDelivery.objects.filter(actor=self.actor, purpose='alert', state='delivered')
        self.assertEqual(set(rows.values_list('channel', flat=True)), {'email', 'whatsapp'})
        self.assertEqual(rows.count(), 2)
        self.assertEqual(SampleAccountInbox.objects.count(), 2)
        delivery = self.client.get(api)
        self.assertEqual(delivery.status_code, 200, delivery.content)
        self.assertEqual({row['channel']: (row['state'], row['receipt']) for row in delivery.json()['recent_deliveries']},
                         {row.channel: ('delivered', row.receipt) for row in rows})
        self.assertNotIn(WORK_EMAIL, delivery.content.decode())
        page = self.client.get(preferences)
        for row in rows:
            self.assertContains(page, row.receipt)
        self.assertNotContains(page, 'Sensitive Assistant content')
        self.assertNotContains(page, WORK_EMAIL)
        other = get_user_model().objects.create_user('other-alert-viewer')
        self.client.force_login(other)
        self.assertEqual(self.client.get(api).json()['recent_deliveries'], [])
        self.assertNotContains(self.client.get(preferences), 'Delivery verified')

    def test_api_personal_alert_retains_read_state_without_cross_account_access(self):
        self.client.force_login(self.actor)
        url = '/api/v1/notifications'
        alert, = self.client.get(url).json()['items']
        self.assertEqual(alert['title'], 'Assistant reply')
        self.assertFalse(alert['read'])
        marked = self.client.post(f"{url}/{alert['id']}/read", {}, content_type='application/json')
        self.assertEqual(marked.status_code, 200, marked.content)
        self.assertTrue(self.client.get(url).json()['items'][0]['read'])
        self.client.force_login(get_user_model().objects.create_user('outside-alert-replay'))
        self.assertEqual(self.client.get(url).json()['items'], [])
        self.assertEqual(self.client.post(f"{url}/{alert['id']}/read", {}, content_type='application/json').status_code, 404)

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
