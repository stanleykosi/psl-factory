from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import reference_values, resolve, transition
from tests.helpers import rev, setup_case


class DesignDelegationTests(TestCase):
    def test_typed_draft_records_exact_people_without_activating_authority(self):
        actor, case = setup_case()
        delegate, _ = setup_case(username='synthetic-delegation-recipient')
        other, _ = setup_case(username='synthetic-delegation-other-role')
        Grant.objects.create(case=case, user=delegate, action='case.read')
        Grant.objects.create(case=case, user=other, action='case.read')
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic draft authorisation', 'synthetic:delegation')
        self.client.force_login(actor)
        url = reverse('design_delegation', args=[case.pk])
        self.assertContains(self.client.get(url), 'Add a delegation draft')
        now = timezone.now()
        self.assertContains(self.client.get(url), 'Record the workspace’s role assignments')
        assignments = draft_roles(actor, case.pk, [{'role': 'PM', 'user_id': actor.pk},
            {'role': 'PM', 'user_id': delegate.pk}, {'role': 'CEO', 'user_id': other.pk}], proof.pk, now)
        transition(actor, assignments.pk, 'validated')
        transition(actor, assignments.pk, 'active')
        data = {'principal': actor.pk, 'delegate': delegate.pk, 'role': 'PM', 'revision': rev(case),
                'starts': now.isoformat(), 'ends': (now + timedelta(days=1)).isoformat(), 'effective': now.isoformat(),
                'evidence': proof.pk}
        self.assertNotContains(self.client.get(url, {'role': 'PM'}), other.username)
        self.assertContains(self.client.post(url, {**data, 'delegate': other.pk}), 'Select a valid choice')
        self.assertRedirects(self.client.post(url, data), url)
        draft = Configuration.objects.get(case=case, component='D05.delegation_rules')
        self.assertEqual(list(draft.states.values_list('state', flat=True)), ['draft'])
        self.assertEqual(reference_values(draft)[0]['delegate_id'], delegate.pk)
        self.assertNotEqual(resolve('D05.delegation_rules', case).status, 'ACTIVE')
        self.client.post(url, data)
        self.assertEqual(Configuration.objects.filter(case=case, component='D05.delegation_rules').count(), 1)
        Grant.objects.create(case=case, user=delegate, action='policy.read')
        self.client.force_login(delegate)
        self.assertNotContains(self.client.get(url), 'Add a delegation draft')
        self.assertEqual(self.client.post(url, data).status_code, 403)
