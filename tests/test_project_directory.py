from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core import workbench
from apps.core.models import Case
from apps.identity.models import Grant
from apps.policy.services import active_component, transition
from apps.workflows import factory, factory_reporting
from tests import settlement_helpers, test_engagement_intake, test_factory_reporting
from tests.billing_helpers import policy, stage_policy
from tests.helpers import setup_case, signed
from tests.test_factory_planning import setup as setup_planning


class ProjectDirectoryTests(TestCase):
    def test_native_manager_and_milestone_are_independently_scoped_and_current(self):
        self.assertEqual(connection.vendor, 'postgresql')
        maker, engagement, *_ = test_engagement_intake.EngagementIntakeTests().ready('directory-pm')
        maker.first_name = 'Recorded PM'
        maker.save(update_fields=['first_name'])
        owner, agreement, coverage, _, _ = settlement_helpers.fixture()
        proof = signed(owner, agreement)['signature']
        stage_policy(owner, agreement, coverage, proof)
        current_terms = policy(owner, agreement, 'D12.stage_terms', [
            {'coverage_id': coverage.pk, 'stage': 'uat', 'amount': '42.50', 'due_date': '2026-12-02'},
        ])
        policy(owner, agreement, 'D12.uat_billing_predicate_ref', {
            'coverage_id': coverage.pk, 'stage': 'uat', 'milestone_name': 'Recorded acceptance milestone',
        })
        viewer = get_user_model().objects.create_user('directory-source-reader')
        plain = Case.objects.create(tenant='directory-unknown', title='Visible project with unprovided facts',
                                    kind='project', synthetic=True)
        Grant.objects.bulk_create([Grant(case=case, user=viewer, action=action) for case, actions in (
            (engagement, ['case.read', 'engagement.read']), (agreement, ['case.read', 'finance.read']),
            (plain, ['case.read']),
        ) for action in actions])
        url = reverse('workspace_overview')
        self.client.force_login(viewer)
        response = self.client.get(url, {'kind': 'project'})
        rows = {item['case'].pk: item for item in response.context['project_rows']}
        self.assertContains(response, 'Next milestone')
        self.assertContains(response, 'Recorded PM')
        self.assertContains(response, 'Recorded acceptance milestone')
        self.assertContains(response, '02 Dec 2026')
        self.assertEqual(rows[engagement.pk]['manager'], 'Recorded PM')
        self.assertEqual(rows[agreement.pk]['milestone'], {'name': 'Recorded acceptance milestone', 'due': date(2026, 12, 2)})
        for key in ('manager', 'milestone', 'phase', 'lifecycle', 'reviews', 'exceptions'):
            self.assertIsNone(rows[plain.pk][key])

        viewer_grant = Grant.objects.get(case=agreement, user=viewer, action='finance.read')
        Grant.objects.filter(pk=viewer_grant.pk).update(active=False)
        restricted = self.client.get(url, {'kind': 'project'})
        self.assertIn(agreement, restricted.context['cases'])
        self.assertNotContains(restricted, 'Recorded acceptance milestone')
        Grant.objects.filter(pk=viewer_grant.pk).update(active=True)
        Grant.objects.filter(case=engagement, user=maker, action='engagement.assign').update(active=False)
        transition(owner, current_terms.pk, 'revoked')
        stale = self.client.get(url, {'kind': 'project'})
        self.assertNotContains(stale, 'Recorded PM')
        self.assertNotContains(stale, 'Recorded acceptance milestone')
        self.assertContains(stale, 'Unknown')
        Grant.objects.filter(case=engagement, user=viewer, action='case.read').update(active=False)
        remaining = self.client.get(url, {'kind': 'project'})
        self.assertNotIn(engagement, remaining.context['cases'])
        self.assertNotIn('project_rows', self.client.get(url).context)
        self.assertNotIn('project_rows', self.client.get(url, {'kind': 'project', 'area': 'finance'}).context)

    def test_counts_use_native_review_and_exception_conditions_and_respect_budget(self):
        weekly = test_factory_reporting.FactoryReportingTests()
        weekly.setUp()
        work = weekly.start_work()
        weekly.advance()
        self.assertEqual(work.status, 'waiting')
        planning = setup_planning(configured=False)
        factory.run_until_wait(planning['work'].pk)
        other = planning['c']
        Grant.objects.bulk_create([Grant(user=weekly.actor, case=other, action=action)
                                   for action in ('case.read', 'factory.read', 'planning.read')])

        with patch.object(factory_reporting, 'inventory', wraps=factory_reporting.inventory) as inventory:
            with CaptureQueriesContext(connection) as queries:
                records = workbench.discover(weekly.actor, kind='project')['project_rows']
        inventory.assert_called_once()
        rows = {item['case'].pk: item for item in records}
        self.assertLessEqual(len(queries), 546)
        self.assertEqual(rows[weekly.case.pk]['reviews'], 1)
        self.assertEqual(rows[other.pk]['phase'], 'Planning')
        self.assertEqual(rows[other.pk]['exceptions'], 1)
        Grant.objects.filter(case=weekly.case, user=weekly.actor, action='report.read').update(active=False)
        excluded = workbench.discover(weekly.actor, kind='project', q=str(weekly.case.pk))['project_rows']
        self.assertEqual((excluded[0]['reviews'], excluded[0]['exceptions']), (0, 0))
        with patch('apps.core.project_list.WORK_LIMIT', 0):
            limited = workbench.discover(weekly.actor, kind='project', q=str(other.pk))['project_rows']
        self.assertEqual((limited[0]['reviews'], limited[0]['exceptions']), (None, None))
        with patch('apps.core.project_list.PAGE_QUERIES', 0):
            budget = workbench.discover(weekly.actor, kind='project', q=str(other.pk))['project_rows']
        self.assertEqual((budget[0]['reviews'], budget[0]['exceptions']), (None, None))

    def test_quiet_project_page_paginates_without_one_query_per_case(self):
        viewer, _ = setup_case(username='directory-paginated-reader')
        projects = Case.objects.bulk_create([Case(tenant='directory-page', title=f'Sample project {index}',
            kind='project', synthetic=True) for index in range(27)])
        Grant.objects.bulk_create([Grant(case=case, user=viewer, action=action) for case in projects
                                   for action in ('case.read', 'factory.read', 'delivery.read')])
        with CaptureQueriesContext(connection) as queries:
            first = workbench.discover(viewer, tenant='directory-page', kind='project')
            next_page = workbench.discover(viewer, tenant='directory-page', kind='project', cursor=first['next_cursor'])
        self.assertLessEqual(len(queries), 14)
        self.assertEqual(len(first['project_rows']), 25)
        self.assertEqual(len(next_page['project_rows']), 2)
        seen = [item['case'].pk for page in (first, next_page) for item in page['project_rows']]
        self.assertCountEqual(seen, [case.pk for case in projects])
        self.assertTrue(all(item['reviews'] == 0 and item['exceptions'] == 0 for item in first['project_rows']))
