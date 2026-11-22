from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.core.workbench import work
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_assignment_queue as queue
from apps.pmo.models import RFPAssignment
from apps.policy.role_assignments import draft
from apps.policy.services import transition
from tests.document_helpers import artifact
from tests.helpers import rev, setup_case


class RFPAssignmentQueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.assigner, cls.case = setup_case()
        users = get_user_model().objects
        cls.manager = users.create_user(username='sample-eligible-manager', first_name='Eligible', last_name='Manager')
        cls.successor = users.create_user(username='sample-eligible-successor', first_name='Eligible', last_name='Successor')
        cls.grant_only = users.create_user(username='sample-grant-without-nomination', first_name='Unnominated', last_name='Person')
        for person in (cls.manager, cls.successor, cls.grant_only):
            Grant.objects.bulk_create([Grant(user=person, case=cls.case, action=action)
                                       for action in ('case.read', 'rfp.read', 'rfp.prepare')])
        Grant.objects.create(user=cls.grant_only, case=cls.case, action='rfp.assign')
        proof = add_evidence(cls.assigner, cls.case.pk, 'policy_decision', 'Exact fictional nominations.', 'synthetic:assignment')
        artifact(cls.assigner, cls.case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v2', {
            'rfp': {'assignment_roles': ['CEO'], 'outcome_roles': ['Client']},
            'rules': [{'role': 'Engineering Lead', 'actions': ['return', 'reject']}],
        }, proof)
        profile = draft(cls.assigner, cls.case.pk, [
            {'role': 'CEO', 'user_id': cls.assigner.pk},
            {'role': 'PM', 'user_id': cls.manager.pk},
            {'role': 'PM', 'user_id': cls.successor.pk},
        ], proof.pk, timezone.now())
        transition(cls.assigner, profile.pk, 'validated')
        transition(cls.assigner, profile.pk, 'active')
        cls.intake = cls.log_bid(cls.case, 'SAMPLE-BID-ASSIGNMENT')

    @classmethod
    def log_bid(cls, case, reference):
        source = add_evidence(cls.assigner, case.pk, 'rfp_intake', 'Private sample tender source text.', 'synthetic:bid')
        return rfp.intake(cls.assigner, case.pk, reference, source.pk, timezone.now() - timedelta(minutes=1),
                          'unknown', None, None, 'Private sample intake note.', rev(case))

    def post_data(self, candidate, **fields):
        return {'intake': self.intake.pk, 'revision': rev(self.case), 'candidate': candidate.pk, 'role': 'CEO',
                'evidence': self.intake.evidence_id, 'reason': 'Reviewed the fictional appointment.', **fields}

    def test_api_assigns_current_bid_to_named_manager_and_prevents_repeat(self):
        url = f'/api/v1/received-bids/{self.case.pk}/assignment'
        self.client.force_login(self.grant_only)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.assigner)
        pending = self.client.get('/api/v1/received-bids/assignments')
        self.assertEqual(pending.json()['items'][0]['intake_id'], self.intake.pk)
        options = self.client.get(url)
        self.assertNotContains(options, 'Private sample intake note.')
        self.assertEqual({person['id'] for person in options.json()['nominees']}, {self.manager.pk, self.successor.pk})
        body = self.post_data(self.manager)
        result = self.client.post(url, body, content_type='application/json')
        self.assertEqual(result.status_code, 201, result.content)
        assignment = result.json()
        self.assertEqual(self.client.get(url).json()['assignment'], assignment)
        self.assertTrue(any(row['kind'] == 'assigned_rfp' and row['record_id'] == assignment['id']
                            for row in work(self.manager)['rows']))
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 409)
        self.assertFalse(self.client.get('/api/v1/received-bids/assignments').json()['items'])

    def test_scoped_chooser_and_native_assigned_work_handoff(self):
        self.assertEqual(connection.vendor, 'postgresql')
        url = reverse('rfp_assignment', args=[self.case.pk])
        unassigned = reverse('rfp_assignment_queue')
        self.client.force_login(self.grant_only)
        self.assertNotContains(self.client.get(unassigned), 'SAMPLE-BID-ASSIGNMENT')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, self.post_data(self.manager)).status_code, 403)
        self.assertNotContains(self.client.get(reverse('rfp', args=[self.case.pk])), 'Assign accountable PM')

        self.client.force_login(self.assigner)
        self.assertContains(self.client.get(unassigned), 'SAMPLE-BID-ASSIGNMENT')
        choices = self.client.get(url)
        self.assertContains(choices, 'Eligible Manager')
        self.assertNotContains(choices, 'Unnominated Person')
        self.assertNotContains(choices, 'Private sample tender source text.')
        self.assertNotContains(choices, 'Private sample intake note.')
        self.assertContains(self.client.post(url, self.post_data(self.grant_only)), 'Select a valid choice', status_code=422)
        command = self.post_data(self.manager)
        self.assertEqual(self.client.post(url, command).status_code, 302)
        self.assertContains(self.client.get(url), 'Project manager assigned')
        self.assertNotContains(self.client.get(unassigned), 'SAMPLE-BID-ASSIGNMENT')
        assigned = RFPAssignment.objects.get(intake=self.intake)
        self.assertEqual((assigned.pm_id, assigned.actor_id, assigned.evidence_id),
                         (self.manager.pk, self.assigner.pk, self.intake.evidence_id))
        self.assertTrue(any(item['record_id'] == assigned.pk and item['kind'] == 'assigned_rfp'
                            for item in work(self.manager)['rows']))
        self.assertEqual(self.client.post(url, command).status_code, 409)
        self.assertEqual(RFPAssignment.objects.filter(intake=self.intake).count(), 1)

    def test_stale_revision_and_predecessor_reopen_only_after_current_owner_loses_access(self):
        url = reverse('rfp_assignment', args=[self.case.pk])
        self.client.force_login(self.assigner)
        stale = self.post_data(self.manager)
        add_evidence(self.assigner, self.case.pk, 'rfp_intake', 'Fictional update.', 'synthetic:update')
        self.assertContains(self.client.post(url, stale), 'current assignment changed', status_code=409)
        self.assertFalse(RFPAssignment.objects.filter(intake=self.intake).exists())
        self.assertEqual(self.client.post(url, self.post_data(self.manager)).status_code, 302)
        Grant.objects.filter(case=self.case, user=self.manager, action='rfp.prepare').update(active=False)
        self.assertContains(self.client.get(reverse('rfp_assignment_queue')), 'SAMPLE-BID-ASSIGNMENT')
        self.assertNotContains(self.client.get(url), 'Eligible Manager')
        self.assertEqual(self.client.post(url, self.post_data(self.manager)).status_code, 422)
        self.assertEqual(self.client.post(url, self.post_data(self.successor)).status_code, 302)
        self.assertEqual(list(RFPAssignment.objects.filter(intake=self.intake).order_by('pk').values_list('pm_id', flat=True)),
                         [self.manager.pk, self.successor.pk])

    def test_each_missing_owner_read_grant_holds_the_existing_assignment_until_explicit_replacement(self):
        url = reverse('rfp_assignment', args=[self.case.pk])
        queue_url = reverse('rfp_assignment_queue')
        self.client.force_login(self.assigner)
        self.assertEqual(self.client.post(url, self.post_data(self.manager)).status_code, 302)
        original = RFPAssignment.objects.get(intake=self.intake)
        for action in ('case.read', 'rfp.read'):
            with self.subTest(action=action):
                grant = Grant.objects.filter(case=self.case, user=self.manager, action=action)
                grant.update(active=False)
                self.assertContains(self.client.get(queue_url), 'Project manager access needs review')
                page = self.client.get(url)
                self.assertContains(page, 'The assigned project manager can no longer open this bid.')
                self.assertNotContains(page, 'Eligible Manager')
                self.assertFalse(any(item['record_id'] == original.pk and item['kind'] == 'assigned_rfp'
                                    for item in work(self.manager)['rows']))
                self.assertEqual(rfp.current_assignment(rfp.root(self.case)).pk, original.pk)
                self.assertEqual(RFPAssignment.objects.filter(intake=self.intake).count(), 1)
                grant.update(active=True)
                self.assertNotContains(self.client.get(queue_url), 'SAMPLE-BID-ASSIGNMENT')
        Grant.objects.filter(case=self.case, user=self.manager, action='rfp.read').update(active=False)
        self.assertEqual(self.client.post(url, self.post_data(self.successor)).status_code, 302)
        self.assertEqual(list(RFPAssignment.objects.filter(intake=self.intake).order_by('pk').values_list('pm_id', flat=True)),
                         [self.manager.pk, self.successor.pk])
        self.assertFalse(Grant.objects.filter(case=self.case, user=self.manager, action='rfp.read', active=True).exists())

    def test_keyset_scan_is_bounded_without_private_intake_context_or_bodies(self):
        for index in range(3):
            case = Case.objects.create(tenant='synthetic-unconfigured-bids', title='Restricted sample bid', kind='project', synthetic=True)
            Grant.objects.bulk_create([Grant(user=self.assigner, case=case, action=action)
                for action in ('case.read', 'evidence.add', 'rfp.read', 'rfp.intake', 'rfp.assign')])
            self.log_bid(case, f'UNCONFIGURED-BID-{index}')
        with CaptureQueriesContext(connection) as checked:
            first = queue.page(self.assigner, page_size=2)
            second = queue.page(self.assigner, first['next_cursor'], page_size=2)
        self.assertEqual((first['checked'], len(first['rows']), second['checked']), (2, 0, 2))
        self.assertEqual([item.reference for item in second['rows']], ['SAMPLE-BID-ASSIGNMENT'])
        self.assertIsNone(second['next_cursor'])
        statements = [row['sql'] for row in checked]
        self.assertTrue(any('FROM "pmo_rfpcase"' in sql and 'LIMIT 3' in sql for sql in statements))
        self.assertFalse(any('"core_evidence"."body"' in sql or '"pmo_rfpintake"."note"' in sql
                             or 'pmo_rfpintakesourcecontext' in sql for sql in statements))
        with self.assertRaises(ValidationError):
            queue.page(self.grant_only, first['next_cursor'], page_size=2)
