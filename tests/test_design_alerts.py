from django.test import TestCase
from django.urls import reverse

from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.core.alert_models import AlertPreference, AlertRead
from apps.identity.models import Grant
from tests.helpers import setup_case


class DesignAlertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case(username='alert-recipient')
        cls.other, _ = setup_case(username='alert-other')
        conversation = AssistantConversation.objects.create(actor=cls.actor, case=cls.case, persona='chidi')
        AssistantTurn.objects.create(conversation=conversation, status='answered', question='Synthetic question', answer='Private reply')

    def test_read_state_belongs_to_current_recipient(self):
        url = reverse('design_alerts')
        mark = reverse('design_alert_read')
        self.client.force_login(self.actor)
        response = self.client.get(url, {'group': 'update', 'q': 'Chidi', 'unread': 1})
        self.assertContains(response, 'Assistant reply')
        self.assertNotContains(response, 'Private reply')
        key = response.context['rows'][0]['key']
        preview = reverse('design_alert_preview')
        self.assertContains(self.client.get(preview), 'Assistant reply')
        self.assertNotContains(self.client.get(preview), 'Private reply')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), 'Chidi')
        self.assertNotContains(self.client.get(preview), 'Assistant reply')
        self.assertEqual(self.client.post(mark, {'key': key}).status_code, 404)
        self.client.force_login(self.actor)
        for _ in range(2):
            self.assertRedirects(self.client.post(mark, {'key': key}), url, fetch_redirect_response=False)
        self.assertEqual(AlertRead.objects.filter(actor=self.actor).count(), 1)
        self.assertNotContains(self.client.get(url, {'unread': 1}), 'Assistant reply')
        self.assertNotContains(self.client.get(preview), 'Assistant reply')
        Grant.objects.filter(user=self.actor, case=self.case, action='finance.read').update(active=False)
        self.assertNotContains(self.client.get(url), 'Assistant reply')

    def test_preferences_save_and_protect_later_edit(self):
        self.client.force_login(self.actor)
        url = reverse('design_alert_preferences')
        self.assertContains(self.client.get(url), 'delivery setup is pending')
        self.assertRedirects(self.client.post(url, {'revision': 1, 'email_requested': 'on'}), url,
                             fetch_redirect_response=False)
        self.assertContains(self.client.post(url, {'revision': 1, 'whatsapp_requested': 'on'}), 'Preferences changed')
        preference = AlertPreference.objects.get(actor=self.actor)
        self.assertTrue(preference.email_requested)
        self.assertFalse(preference.whatsapp_requested)
