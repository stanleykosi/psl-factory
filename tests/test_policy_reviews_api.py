from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.role_assignments import COMPONENT
from apps.policy.services import decision_authority, resolve
from tests.helpers import rev, setup_case


class PolicyReviewApiTests(TestCase):
    def test_scoped_appointment_draft_review_and_revocation(self):
        preparer, case = setup_case(username='sample-appointment-preparer')
        reviewer = get_user_model().objects.create_user('sample-appointment-reviewer')
        nominee = get_user_model().objects.create_user('sample-planning-nominee')
        outsider = get_user_model().objects.create_user('sample-appointment-outsider')
        for action in ('case.read', 'policy.read', 'policy.activate'):
            Grant.objects.create(user=reviewer, case=case, action=action)
        Grant.objects.create(user=nominee, case=case, action='case.read')
        decision = add_evidence(preparer, case.pk, 'policy_decision', 'Synthetic named Planning appointment', 'synthetic:policy-review-api')
        url = f'/api/v1/setup/{case.pk}'
        self.client.force_login(preparer)
        opened = self.client.get(url + '/decision-appointments')
        self.assertEqual(opened.status_code, 200, opened.content)
        self.assertIsNone(opened.json()['latest_id'])
        self.assertIn(nominee.pk, [row['id'] for row in opened.json()['people']])
        draft = {'case_revision': rev(case), 'latest_id': None, 'evidence_id': decision.pk,
                 'effective_from': (timezone.now() - timedelta(seconds=1)).isoformat(),
                 'assignments': [{'user_id': nominee.pk, 'role': 'PMO Lead'}]}
        rejected = self.client.post(url + '/decision-appointments', draft | {
            'assignments': [{'user_id': outsider.pk, 'role': 'PMO Lead'}]}, content_type='application/json')
        self.assertEqual(rejected.status_code, 422, rejected.content)
        response = self.client.post(url + '/decision-appointments', draft, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        version = response.json()
        self.assertEqual(version['state'], 'draft')
        self.assertEqual(resolve(COMPONENT, case).status, 'MISSING')
        self.assertEqual(self.client.post(url + '/decision-appointments', draft, content_type='application/json').status_code, 409)
        review_url = f"{url}/policy-configurations/{version['id']}/review"

        def review(record, action):
            return self.client.post(review_url, {'case_revision': rev(case), 'state_id': record['state_id'],
                'transition': action}, content_type='application/json')

        Grant.objects.filter(case=case, user=preparer, action='policy.activate').update(active=False)
        checked = review(version, 'validated')
        self.assertEqual(checked.status_code, 200, checked.content)
        self.assertEqual(review(checked.json(), 'active').status_code, 403)
        self.client.force_login(reviewer)
        options = self.client.get(url + '/policy-configurations', {'component': COMPONENT}).json()
        self.assertEqual(options['items'][0]['actions'], ['active'])
        self.assertEqual(review(version, 'active').status_code, 409)
        active = review(checked.json(), 'active')
        self.assertEqual(active.status_code, 200, active.content)
        self.assertEqual(decision_authority(nominee, case, 'PMO Lead')[COMPONENT], version['id'])
        self.assertFalse(Grant.objects.filter(case=case, user=nominee, action='delivery.planning_decide').exists())
        self.assertEqual(self.client.get(url + '/decision-appointments').json()['active_id'], version['id'])
        self.assertEqual(review(active.json(), 'revoked').status_code, 200)
        self.assertEqual(resolve(COMPONENT, case).status, 'REVOKED')
