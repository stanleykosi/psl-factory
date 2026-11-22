import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import issue_teams
from apps.pmo.issue_access import public_current_issues, state_public
from apps.pmo.issues import log_issue, update_issue
from apps.pmo.models import Issue, IssueState
from apps.policy.issue_team_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests.helpers import rev, roles, setup_case


class ProjectIssueRegisterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case()
        cls.proof = add_evidence(cls.actor, cls.case.pk, 'completion', 'Public sample issue source', 'synthetic:register')
        cls.policy = add_evidence(cls.actor, cls.case.pk, 'policy_decision', 'Sample issue owner', 'synthetic:register')
        roles(cls.actor, cls.case, cls.policy)
        cls.reader = get_user_model().objects.create_user('sample-register-reader')
        Grant.objects.bulk_create([Grant(case=cls.case, user=cls.reader, action=action)
                                    for action in ('case.read', 'issue.read')])

    def setUp(self):
        self.url = reverse('design_project_tab', args=[self.case.pk, 'registers'])
        self.client.force_login(self.reader)

    def log(self, reference, title, severity=None):
        return log_issue(self.actor, self.case.pk, reference, title, 'Delivery', self.actor.pk,
            'Check the source', self.proof.pk, 'Recorded sample issue', rev(self.case), severity)

    def legacy(self, reference, **changes):
        issue = Issue.objects.create(case=self.case, tenant=self.case.tenant, reference=reference)
        values = {'title': reference, 'kind': 'Delivery', 'severity': 'Critical', 'status': 'Resolved',
                  'owner': self.actor, 'actor': self.actor, 'evidence': self.proof,
                  'external_links': [], 'next_action': 'Review old source', 'note': 'Private note should not be loaded'}
        state = IssueState.objects.create(issue=issue, number=1, **(values | changes))
        issue.current = state
        issue.save(update_fields=['current'])
        return issue

    def test_current_owner_and_native_recorded_team_with_date_from_original_state(self):
        self.assertEqual(connection.vendor, 'postgresql')
        known = self.log('REGISTER-OPEN', 'Sample open issue', 'High')
        external = self.log('REGISTER-TEAM', 'Sample team issue')
        self.legacy('REGISTER-CLOSED', severity='Low', status='Closed')
        settings = json.loads(Path('fixtures/issue-team-controls.json').read_text())['value']
        configuration = draft_operator_policy(self.actor, self.case.pk, COMPONENT, settings, self.policy.pk, timezone.now())
        transition(self.actor, configuration.pk, 'validated')
        transition(self.actor, configuration.pk, 'active')
        team = next(row for row in settings['teams'] if row['key'] == 'sample-engineering')
        issue_teams.assign(self.actor, self.case.pk, external.issue_id, external.pk, 'team', team['key'],
            self.actor.pk, 'PM', self.proof.pk, 'Synthetic recorded team', rev(self.case))
        update_issue(self.actor, self.case.pk, known.issue_id, known.pk, 'acknowledge', self.proof.pk,
            'New state is separate from the original opening date', rev(self.case))

        with patch.object(timezone, 'now', return_value=known.created_at + timedelta(days=2)):
            page = self.client.get(self.url)
        self.assertContains(page, '<td data-label="Severity">High</td>', html=True)
        self.assertContains(page, '<td data-label="Age">2 days</td>', html=True)
        self.assertContains(page, '<td data-label="Age">—</td>', html=True)
        self.assertContains(page, '<td data-label="Severity">Unknown</td>', html=True)
        self.assertContains(page, team['label'])
        self.assertContains(page, f'Coordinator {self.actor.username}')
        self.assertContains(page, reverse('issues', args=[self.case.pk]) + f'#issue-{known.issue_id}')
        filtered = self.client.get(self.url, {'q': 'REGISTER', 'severity': 'High', 'owner': self.actor.pk, 'state': 'Open'})
        self.assertContains(filtered, 'Sample open issue')
        self.assertNotContains(filtered, 'Sample team issue')

    def test_private_and_foreign_proofs_are_excluded_before_filters_search_and_pagination(self):
        hidden_owner = get_user_model().objects.create_user('unknown-register-private-owner')
        private = add_evidence(self.actor, self.case.pk, 'approval_source', 'Restricted sample source', 'synthetic:register-private')
        foreign_actor, foreign_case = setup_case(username='foreign-register-writer')
        foreign = add_evidence(foreign_actor, foreign_case.pk, 'completion', 'Foreign sample source', 'synthetic:register-foreign')
        visible = self.log('REGISTER-VISIBLE', 'Visible issue', 'High')
        hidden = [self.legacy(f'HIDDEN-{index}', owner=hidden_owner, **values) for index, values in enumerate((
            {'evidence': private}, {'fix': private}, {'root_cause': private},
            {'external_links': [{'evidence_id': private.pk}]}, {'external_links': [{'evidence_id': foreign.pk}]},
            {'evidence': foreign}, {'external_links': [{'evidence_id': 2**80}]},
            {'external_links': [{'evidence_id': str(self.proof.pk)}]}, {'external_links': [False]},
        ), start=1)]
        for record in hidden[:6]:
            self.assertFalse(state_public(record.current))
        nullable = self.legacy('REGISTER-LEGACY-NULL', severity=None, status='Open',
            external_links=[{'evidence_id': None}, {}, {'evidence_id': self.proof.pk}])
        self.assertTrue(state_public(nullable.current))
        self.assertEqual(set(public_current_issues(self.case).values_list('pk', flat=True)), {visible.issue_id, nullable.pk})

        page = self.client.get(self.url)
        self.assertContains(page, 'Visible issue')
        self.assertNotContains(page, 'HIDDEN-')
        self.assertNotContains(page, hidden_owner.username)
        self.assertContains(page, '<caption>2 issues</caption>', html=True)
        form = page.context['filter_form']
        self.assertNotIn('Critical', dict(form.fields['severity'].choices))
        self.assertNotIn('Resolved', dict(form.fields['state'].choices))
        self.assertNotIn(str(hidden_owner.pk), dict(form.fields['owner'].choices))
        self.assertContains(self.client.get(self.url, {'q': 'HIDDEN-'}), 'No records match this search.')
        self.assertContains(self.client.get(self.url, {'owner': hidden_owner.pk}), 'Select a valid choice')

    def test_issue_page_has_bounded_metadata_queries_and_stays_scoped(self):
        original = self.log('REGISTER-LOAD-1', 'Small public issue', 'Medium')
        with CaptureQueriesContext(connection) as small:
            self.assertContains(self.client.get(self.url), 'Small public issue')

        for index in range(2, 32):
            self.legacy(f'REGISTER-LOAD-{index}', severity='Medium', status='Open')
        with CaptureQueriesContext(connection) as full:
            first = self.client.get(self.url)
            self.assertContains(first, 'Showing 1–25 of 31')
            self.assertNotContains(first, 'Small public issue')
        self.assertLessEqual(len(full), len(small))
        for row in full:
            self.assertNotIn('"pmo_issuestate"."note"', row['sql'])
            self.assertNotIn('"core_evidence"."body"', row['sql'])
        second = self.client.get(self.url, {'issues-page': '2'})
        self.assertContains(second, reverse('issues', args=[self.case.pk]) + f'#issue-{original.issue_id}')
        Grant.objects.filter(case=self.case, user=self.reader, action='issue.read').update(active=False)
        self.assertEqual(self.client.get(self.url).status_code, 404)
