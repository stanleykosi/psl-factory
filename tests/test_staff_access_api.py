from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.identity.models import Grant
from tests.test_staff_profiles import PROFILES, configured
from tests.test_staff_reactivation import remove_old_nominations


class StaffAccessAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = configured()

    def post(self, path, payload, expected=200):
        response = self.client.post(path, payload, content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content)
        return response.json()

    def test_technical_review_account_departure_and_new_access_remain_independent(self):
        d = self.data
        operator, person = d['actor'], d['target']
        self.client.force_login(d['root'])
        delegation = '/api/v1/staff/delegations/'
        current = self.client.get(delegation + str(d['authority'].pk)).json()
        reviewed = self.post(delegation + str(current['id']), {'action': 'controls',
            'controls': {**current['controls'], 'allow_reactivation': True}, 'reason': 'Synthetic reviewed restoration authority.'}, 201)
        self.post(delegation + str(reviewed['id']), {'action': 'profiles', 'profiles': PROFILES,
            'reason': 'Synthetic reviewed access profiles.'}, 201)

        self.client.force_login(operator)
        base = f'/api/v1/staff/{person.pk}'
        roster = self.client.get('/api/v1/staff', {'q': person.username})
        self.assertEqual(roster.status_code, 200, roster.content)
        self.assertEqual([row['id'] for row in roster.json()['people']], [person.pk])
        detail = self.client.get(base)
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(len(detail.json()['workspaces']), 2)
        self.assertEqual(self.client.get(delegation + str(current['id'])).status_code, 403)

        person_scope = f"/api/v1/setup/{d['scopes'][0]['case'].pk}/people/{person.pk}"
        profile = self.client.get(person_scope + '/profile')
        self.assertEqual(profile.status_code, 200, profile.content)
        self.post(person_scope + '/profile', {'fingerprint': profile.json()['fingerprint'], 'confirmed': True,
            'operation': str(uuid4()), 'reason': 'Synthetic workplace contributor.', 'profile': PROFILES[0]['key']})
        self.assertTrue(Grant.objects.filter(user=person, action='meeting.read', active=True).exists())

        farewell = self.client.get(base + '/deactivation')
        self.assertEqual(farewell.status_code, 200, farewell.content)
        input_data = {'fingerprint': farewell.json()['fingerprint'], 'confirmed': True, 'operation': str(uuid4()),
            'reason': 'Synthetic complete staff handover.',
            'actions': [{'action_id': s['item'].pk, 'successor_id': d['successor'].pk} for s in d['scopes']],
            'evidence': [{'case_id': str(s['case'].pk), 'evidence_id': s['proof'].pk} for s in d['scopes']]}
        removed = self.post(base + '/deactivation', input_data)
        self.assertFalse(removed['active'])
        self.assertFalse(Grant.objects.filter(user=person, active=True).exists())
        held = self.client.get(base + '/restoration').json()
        self.assertTrue(held['blocked'])
        remove_old_nominations(d)
        opened = self.client.get(base + '/restoration')
        self.assertEqual(opened.status_code, 200, opened.content)
        self.assertEqual(opened.json()['blocked'], [])
        restored = self.post(base + '/restoration', {'fingerprint': opened.json()['fingerprint'], 'confirmed': True,
            'operation': str(uuid4()), 'reason': 'Synthetic fresh sign-in review.'})
        self.assertTrue(restored['active'])
        self.assertFalse(Grant.objects.filter(user=person, active=True).exists())
        self.assertContains(self.client.get(reverse('staff_person', args=[person.pk])), 'No current access')

    def test_workspace_departure_preserves_separate_scope_and_action_deadline(self):
        d = self.data
        scope, other = d['scopes']
        person = d['target']
        self.client.force_login(d['actor'])
        path = f"/api/v1/setup/{scope['case'].pk}/people/{person.pk}/departure"
        options = self.client.get(path)
        self.assertEqual(options.status_code, 200, options.content)
        row = options.json()['workspace']['actions'][0]
        self.assertIn(d['successor'].pk, {item['id'] for item in row['successors']})
        self.post(path, {'revision': options.json()['revision'], 'reason': 'Explicit synthetic workspace handover.',
            'evidence_id': scope['proof'].pk, 'actions': [{'action_id': row['id'], 'successor_id': d['successor'].pk}]})
        self.assertFalse(Grant.objects.filter(case=scope['case'], user=person, active=True).exists())
        self.assertTrue(Grant.objects.filter(case=other['case'], user=person, active=True).exists())
        scope['item'].refresh_from_db()
        self.assertEqual(scope['item'].current.due_at, scope['due'])
        self.assertEqual(scope['item'].current.owner_id, d['successor'].pk)
