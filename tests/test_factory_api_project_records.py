from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.models import ClientProjectPersonRevision
from apps.core.factory_api.intake import STARTS
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.workflows.factory_invoice_information import INVOICE_MILESTONE_PROOF
from tests.billing_helpers import coverage
from tests.helpers import rev, setup_case


class ProjectRecordApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case(username='api-project-recorder')
        cls.other, cls.other_case = setup_case(username='api-unrelated-project-recorder')
        cls.reviewer = get_user_model().objects.create_user('api-independent-client-identity-reviewer')
        Grant.objects.bulk_create([Grant(case=cls.case, user=cls.reviewer, action=action)
                                   for action in ('case.read', 'finance.read', 'policy.activate')])
        cls.source = add_evidence(cls.actor, cls.case.pk, 'policy_decision', 'Observed synthetic work and customer facts.',
                                  'synthetic:project-records')
        cls.bill = coverage(cls.actor, cls.case)

    def setUp(self):
        self.client.force_login(self.actor)

    def post(self, url, body, status=201):
        response = self.client.post(url, body, content_type='application/json')
        self.assertEqual(response.status_code, status, response.content)
        return response.json()

    def test_start_source_pages_use_only_current_authorised_metadata(self):
        root = f'/api/v1/projects/{self.case.pk}/intake-sources'
        for line in STARTS:
            listing = self.client.get(root, {'line': line})
            self.assertEqual(listing.status_code, 200, (line, listing.content))
            for field in listing.json()['fields']:
                with self.subTest(line=line, field=field):
                    response = self.client.get(root, {'line': line, 'field': field})
                    self.assertEqual(response.status_code, 200, response.content)
        old = add_evidence(self.actor, self.case.pk, 'planning_packet', 'Previous private contents', 'synthetic:test')
        current = add_evidence(self.actor, self.case.pk, 'planning_packet', 'Current private contents', 'synthetic:test')
        planning = self.client.get(root, {'line': 'planning/v1', 'field': 'packet_id'}).json()
        self.assertEqual([item['id'] for item in planning['items']], [current.pk])
        self.assertNotIn(old.pk, [item['id'] for item in planning['items']])
        self.assertNotIn('private contents', str(planning))
        rows = [add_evidence(self.actor, self.case.pk, 'meeting_notes', f'Private text {i}', 'synthetic:test')
                for i in range(30)]
        add_evidence(self.actor, self.case.pk, 'meeting_notes', 'Restricted notes', 'role-work:hidden-test')
        query = {'line': 'pmo-minutes/v1', 'field': 'data.evidence_id'}
        with CaptureQueriesContext(connection) as captured:
            first = self.client.get(root, query)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertLess(len(captured), 25)
        first = first.json()
        second = self.client.get(root, {**query, 'before': first['next_before']}).json()
        self.assertEqual([item['id'] for item in first['items'] + second['items']], [row.pk for row in reversed(rows)])
        self.assertIsNone(second['next_before'])
        self.assertNotIn('Private text', str(first))
        self.assertEqual(self.client.get(root, {**query, 'before': '9999999999999999999'}).status_code, 422)
        Grant.objects.filter(case=self.case, user=self.actor, action='ledger.private.read').update(active=False)
        self.assertEqual(self.client.get(root, {'line': 'finance-ledger/v1', 'field': 'evidence_id'}).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(root, query).status_code, 404)

    def test_retrospective_and_independent_actions_keep_original_evidence(self):
        self.assertEqual(connection.vendor, 'postgresql')
        case = self.case
        root = f'/api/v1/projects/{case.pk}'
        offered = self.client.get(root + '/meetings/options').json()
        self.assertIn(self.actor.pk, [row['id'] for row in offered['participants']])
        self.assertIn(self.actor.pk, [row['id'] for row in offered['owners']])
        self.assertIn(self.source.pk, [row['id'] for row in offered['proofs']])
        data = {'revision': offered['revision'], 'reference': 'SAMPLE-RETRO-001', 'kind': 'retrospective',
                'occurred_at': (timezone.now() - timedelta(hours=1)).isoformat(), 'purpose': 'Review the sample release',
                'summary': 'A retrospective with an exact original decision.', 'decisions': [
                    {'text': 'Review the support worksheet', 'evidence_id': self.source.pk},
                ], 'participant_ids': [self.actor.pk], 'evidence_id': self.source.pk}
        meeting = self.post(root + '/meetings', data)
        self.post(root + '/meetings', data, status=409)
        listing = self.client.get(root + '/meetings', {'kind': 'retrospective'}).json()
        self.assertEqual([item['id'] for item in listing['items']], [meeting['id']])
        action_body = {'revision': meeting['revision'], 'reference': 'SAMPLE-RETRO-FOLLOW-UP',
            'description': 'Check the recorded worksheet', 'owner_id': self.actor.pk, 'reason': 'Reviewed lesson',
            'evidence_id': self.source.pk, 'due_at': (timezone.now() + timedelta(days=2)).isoformat()}
        action = self.post(root + '/actions/create', action_body)
        path = f"{root}/meetings/{meeting['id']}"
        self.assertEqual(self.client.get(path).json()['actions'], [])
        self.post(path + '/actions', {'revision': action['revision'], 'action_id': action['id'],
                                     'evidence_id': self.source.pk})
        linked = self.client.get(path).json()
        self.assertEqual(linked['actions'][0]['id'], action['id'])
        self.assertEqual(linked['decisions'], data['decisions'])
        hidden = add_evidence(self.actor, case.pk, INVOICE_MILESTONE_PROOF, 'Private test source', 'synthetic:private')
        self.post(root + '/actions/create', {**action_body, 'revision': rev(case),
                  'reference': 'SAMPLE-PRIVATE-ACTION', 'evidence_id': hidden.pk}, status=422)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_client_people_billing_identity_and_independent_link_readback(self):
        root = f'/api/v1/clients/{self.case.pk}'
        named = root + '/project-people'
        identity = root + '/billing-identities'
        linked = root + '/workspace-link'
        options = self.client.get(named).json()
        body = {'revision': options['revision'], 'name': 'Example contact', 'role': 'Project liaison',
                'email': 'liaison@example.test', 'evidence_id': self.source.pk}
        first = self.post(named, body)
        second = self.post(named, {**body, 'revision': first['revision'], 'previous_id': first['person']['id'],
                                   'email': 'successor@example.test'})
        self.assertEqual(first['person']['key'], second['person']['key'])
        self.assertEqual(self.client.get(named).json()['items'], [second['person']])
        self.assertEqual(ClientProjectPersonRevision.objects.get(pk=first['person']['id']).email, body['email'])
        options = self.client.get(identity).json()
        saved = self.post(identity, {'revision': options['revision'], 'coverage_id': self.bill.pk,
            'evidence_id': self.bill.evidence_id, 'legal_name': 'Sample Legal Customer',
            'billing_address': 'Sample office', 'tax_reference': 'SYNTHETIC-TAX-ID'})
        self.assertEqual(self.client.get(identity).json()['items'][0]['identity'], saved['identity'])
        proposal = self.post(linked, {'revision': saved['revision'], 'action': 'link', 'coverage_id': self.bill.pk,
            'issuer': 'synthetic.register', 'reference': 'SYNTHETIC-001', 'name': 'Sample Legal Customer',
            'source': 'Synthetic customer listing'})
        confirmation = f"{linked}/{proposal['proposal_id']}/confirmation"
        self.assertFalse(self.client.get(linked).json()['proposals'][0]['can_confirm'])
        self.post(confirmation, {'revision': proposal['revision']}, status=403)
        self.client.force_login(self.reviewer)
        self.assertTrue(self.client.get(linked).json()['proposals'][0]['can_confirm'])
        accepted = self.post(confirmation, {'revision': proposal['revision']})
        self.assertEqual(self.client.get(linked).json()['current'], accepted['link'])
        group = self.client.get(f"/api/v1/clients/groups/{accepted['link']['group_key']}").json()
        self.assertEqual([project['case_id'] for project in group['projects']], [str(self.case.pk)])
        self.client.force_login(self.other)
        for path in (named, identity, linked):
            self.assertEqual(self.client.get(path).status_code, 404)
