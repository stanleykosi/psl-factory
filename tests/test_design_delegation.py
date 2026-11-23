from datetime import timedelta
from uuid import uuid4

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
    def test_api_readback_and_idempotent_delegation_draft(self):
        actor, case = setup_case()
        delegate, _ = setup_case(username='api-delegation-recipient')
        Grant.objects.create(case=case, user=delegate, action='case.read')
        now = timezone.now()
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic draft decision', 'synthetic:test')
        roles = draft_roles(actor, case.pk, [{'role': 'PM', 'user_id': user.pk} for user in (actor, delegate)], proof.pk, now)
        transition(actor, roles.pk, 'validated')
        transition(actor, roles.pk, 'active')
        self.client.force_login(actor)
        url = f'/api/v1/setup/{case.pk}'
        rules = self.client.get(url + '/rules')
        self.assertEqual(rules.status_code, 200, rules.content)
        self.assertTrue(rules.json()['items'])
        options = self.client.get(url + '/delegations/options', {'role': 'PM'}).json()
        self.assertEqual({row['id'] for row in options['people']}, {actor.pk, delegate.pk})
        data = {'principal': actor.pk, 'delegate': delegate.pk, 'role': 'PM', 'revision': options['revision'],
                'starts': now.isoformat(), 'ends': (now + timedelta(days=1)).isoformat(), 'effective': now.isoformat(),
                'evidence': proof.pk, 'source_configuration': options['source_configuration'], 'submission_key': str(uuid4())}
        invalid = self.client.post(url + '/delegations/drafts', {**data, 'ends': now.isoformat(),
            'delegate': actor.pk}, content_type='application/json')
        self.assertEqual(invalid.status_code, 422, invalid.content)
        self.assertEqual({row['name'] for row in invalid.json()['fields']}, {'delegate', 'ends'})
        self.assertFalse(Configuration.objects.filter(case=case, component='D05.delegation_rules').exists())
        response = self.client.post(url + '/delegations/drafts', data, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        stored = Configuration.objects.get(pk=response.json()['configuration_id'])
        self.assertEqual(list(stored.states.values_list('state', flat=True)), ['draft'])
        self.assertEqual(self.client.post(url + '/delegations/drafts', data, content_type='application/json').json(), response.json())
        self.assertNotEqual(resolve('D05.delegation_rules', case).status, 'ACTIVE')
        active = self.client.get(url + '/delegations')
        self.assertEqual(active.status_code, 200, active.content)
        self.assertEqual(active.json()['items'], [])
        transition(actor, stored.pk, 'validated')
        transition(actor, stored.pk, 'active')
        [assignment] = self.client.get(url + '/delegations').json()['items']
        self.assertEqual((assignment['role'], assignment['principal_id'], assignment['delegate_id']),
                         ('PM', actor.pk, delegate.pk))
        Grant.objects.filter(case=case, user=actor, action='policy.configure').update(active=False)
        self.assertEqual(self.client.get(url + '/rules').status_code, 200)
        self.assertEqual(self.client.post(url + '/delegations/drafts', data, content_type='application/json').status_code, 403)

    def test_api_setup_retains_domain_scope_and_independent_rule_versions(self):
        from apps.documents.controlled import register_template
        from tests.document_helpers import DEFINITION, artifact

        actor, case = setup_case(username='api-setup-rules-review')
        self.client.force_login(actor)
        url = f'/api/v1/setup/{case.pk}/rules'
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic Setup authority.', 'synthetic:setup')
        template = register_template(actor, case.pk, 'Synthetic report', DEFINITION, proof.pk, rev(case))

        def rows():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.content)
            return {row['label']: row for row in response.json()['items']}

        archive = {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30}
        self.assertEqual(rows()['Archive storage and retention']['status'], 'MISSING')
        artifact(actor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v2', archive, proof)
        first = rows()['Archive storage and retention']
        self.assertEqual((first['status'], first['value']), ('ACTIVE', 'Internal versioned archive for 30 days'))
        artifact(actor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v2',
                 {**archive, 'retention_days': 90}, proof)
        revised = rows()['Archive storage and retention']
        self.assertGreater(revised['version'], first['version'])
        self.assertEqual(revised['value'], 'Internal versioned archive for 90 days')
        artifact(actor, case, 'OPS.invoice_short_payment_review', 'schema:psl/invoice-short-payment-review/v1',
                 {'reviewer_id': actor.pk, 'treatments': ['request_proof']}, proof)
        self.assertEqual(rows()['Short payments (e.g. tax deducted)']['status'], 'ACTIVE')
        Grant.objects.filter(case=case, user=actor, action='finance.read').update(active=False)
        restricted = rows()['Short payments (e.g. tax deducted)']
        self.assertEqual((restricted['status'], restricted['value'], restricted['details']), ('UNAVAILABLE', None, []))
        self.assertEqual(rows()['Archive storage and retention']['version'], revised['version'])

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
        self.assertContains(self.client.get(url, {'role': 'PM'}), f'{other.username} (Chief executive)')
        invalid = self.client.post(url, {**data, 'delegate': other.pk, 'ends': now.isoformat()})
        self.assertContains(invalid, 'Choose someone with a current project manager assignment.')
        self.assertContains(invalid, 'Enter a time after the start.')
        self.assertEqual(invalid.context['form']['delegate'].value(), str(other.pk))
        self.assertFalse(Configuration.objects.filter(case=case, component='D05.delegation_rules').exists())
        self.assertContains(self.client.post(url, {**data, 'delegate': actor.pk}), 'Choose a different person')
        self.assertContains(self.client.post(url, {**data, 'ends': now.isoformat()}), 'Enter a time after the start')
        self.assertRedirects(self.client.post(url, data), url)
        draft = Configuration.objects.get(case=case, component='D05.delegation_rules')
        self.assertEqual(list(draft.states.values_list('state', flat=True)), ['draft'])
        self.assertEqual(reference_values(draft)[0]['delegate_id'], delegate.pk)
        self.assertNotEqual(resolve('D05.delegation_rules', case).status, 'ACTIVE')
        self.client.post(url, data)
        self.assertEqual(Configuration.objects.filter(case=case, component='D05.delegation_rules').count(), 1)

        keyed = {**data, 'revision': rev(case), 'submission_key': uuid4(), 'principal': delegate.pk, 'delegate': actor.pk}
        saved = self.client.post(url, keyed)
        readback = self.client.get(saved.url)
        self.assertContains(readback, 'Your submission was recorded as delegation draft version')
        self.assertRedirects(self.client.post(url, keyed), saved.url)
        self.assertContains(self.client.post(url, {**keyed, 'ends': (now + timedelta(days=2)).isoformat()}),
                            'This submission already saved a different draft')
        self.assertEqual(Configuration.objects.filter(case=case, component='D05.delegation_rules').count(), 2)
        Grant.objects.create(case=case, user=delegate, action='policy.read')
        self.client.force_login(delegate)
        self.assertNotContains(self.client.get(url), 'Add a delegation draft')
        self.assertNotContains(self.client.get(saved.url), 'Your submission was recorded')
        self.assertEqual(self.client.post(url, data).status_code, 403)
