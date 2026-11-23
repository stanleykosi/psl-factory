"""Check report and linked history permissions through the same routes users open."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.agents.schedules import investigate
from apps.identity.models import Grant
from tests.helpers import rev
from tests.schedule_helpers import detail, fixture, review, row


class ScheduleHistoryScopeTests(TestCase):
    def test_metadata_history_cannot_read_values_and_exact_report_checks_original_authority(self):
        f = fixture()
        case = f['case']
        marker = 'synthetic-private-licence-line'
        work = detail(f, [row(f, marker, '-873.19'), row(f, 'synthetic-maintenance', '-126.81')])
        history = reverse('finance_schedules', args=[case.pk])
        report = reverse('schedule_report', args=[case.pk, work.pk])

        self.client.force_login(f['reviewer'])
        self.assertContains(self.client.get(history), marker)
        self.assertEqual(self.client.get(report + '?format=json').status_code, 409)
        decision = review(f, work)
        self.assertContains(self.client.get(history), 'Current human approval')
        self.assertContains(self.client.get(report), marker)
        envelope = self.client.get(report + '?format=json')
        self.assertEqual(envelope['Cache-Control'], 'no-store')
        self.assertEqual(envelope.json()['review_id'], decision.pk)
        self.assertEqual(envelope.json()['result']['rows'][0]['amount'], '-873.19')

        agent_marker = 'synthetic-protected-finding-label'
        detail(f, [row(f, agent_marker, None)], reference='held-investigation-source')
        investigation = investigate(f['actor'], case.pk, rev(case))
        self.assertIn(agent_marker, str(investigation.result['findings']))

        reader = get_user_model().objects.create_user('schedule-metadata-only-reader')
        Grant.objects.bulk_create([Grant(case=case, user=reader, action=action)
                                   for action in ['case.read', 'finance.read', 'schedules.read']])
        self.client.force_login(reader)
        with CaptureQueriesContext(connection) as captured:
            metadata = self.client.get(history)
        self.assertContains(metadata, f'income #{work.pk} v1')
        self.assertContains(metadata, f'Review #{decision.pk}')
        self.assertContains(metadata, 'Schedule values require report access')
        self.assertNotContains(metadata, marker)
        self.assertNotContains(metadata, '-873.19')
        self.assertContains(metadata, f'Investigation #{investigation.pk} recorded')
        self.assertNotContains(metadata, agent_marker)
        self.assertNotContains(metadata, 'Current human approval')
        self.assertNotContains(metadata, report)
        queries = [entry['sql'] for entry in captured.captured_queries if 'finance_schedulework' in entry['sql']]
        self.assertTrue(queries)
        self.assertTrue(all('"finance_schedulework"."payload"' not in sql and
                            '"finance_schedulework"."snapshot"' not in sql for sql in queries))
        self.assertFalse(any('"agents_agentrun"."result"' in entry['sql']
                             for entry in captured.captured_queries))
        for path in [report, report + '?format=json']:
            self.assertNotContains(self.client.get(path), marker, status_code=403)

        self.client.force_login(f['reviewer'])
        Grant.objects.filter(case=case, user=f['actor'], action='schedules.prepare').update(active=False)
        stale = self.client.get(history)
        self.assertContains(stale, f'Review #{decision.pk}')
        self.assertNotContains(stale, marker)
        self.assertNotContains(stale, 'Current human approval')
        for path in [report, report + '?format=json']:
            self.assertNotContains(self.client.get(path), marker, status_code=403)
