"""Browser precision and current-timezone contract for native RFP outcomes."""
from datetime import timedelta
from html.parser import HTMLParser
import time

from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.pmo.models import RFPOutcome, RFPSubmission
from apps.workflows import factory
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class OutcomeInputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'observed_at':
            self.inputs.append(attrs)


class RFPOutcomeTimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = helpers.configured()
        cls.work = helpers.start(cls.data)
        response, _ = helpers.reviewed_document(cls.data, cls.work)
        factory.run_until_wait(cls.work.pk)
        cls.submission = RFPSubmission.objects.get(response=response)

    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.client.force_login(self.data['actor'])
        self.url = reverse('factory_detail', args=[self.work.pk])

    def post_outcome(self, observed):
        self.work.refresh_from_db()
        return self.client.post(self.url, {
            'action': 'outcome', 'revision': self.work.revision,
            'case_revision': rev(self.data['case']), 'target': self.submission.pk,
            'role': 'Client', 'verdict': 'won', 'observed_at': observed,
            'evidence': self.data['evidence']['rfp_outcome'].pk,
            'note': 'Actual evidenced synthetic customer award with seconds precision',
        })

    def test_input_allows_seconds_and_labels_active_timezone(self):
        for zone in ['Africa/Lagos', 'UTC', 'America/New_York']:
            with self.subTest(zone=zone), timezone.override(zone):
                page = self.client.get(self.url)
                self.assertContains(page, f'Observed at ({zone})')
                parser = OutcomeInputParser()
                parser.feed(page.content.decode())
                self.assertEqual(len(parser.inputs), 1)
                self.assertEqual(parser.inputs[0]['type'], 'datetime-local')
                self.assertEqual(parser.inputs[0]['step'], '1')
                self.assertIn('required', parser.inputs[0])

    def test_seconds_local_http_outcome_preserves_native_time_guards(self):
        # Wait only for the next real whole second after the native receipt.
        # Neither the clock nor the internal submission workflow is mocked.
        observed = self.submission.submitted_at.replace(microsecond=0) + timedelta(seconds=1)
        delay = (observed - timezone.now()).total_seconds()
        if delay > 0:
            time.sleep(delay)
        with timezone.override('America/New_York'):
            for invalid in [self.submission.submitted_at - timedelta(seconds=1),
                            timezone.now() + timedelta(days=1)]:
                result = self.post_outcome(timezone.localtime(invalid).strftime('%Y-%m-%dT%H:%M:%S'))
                self.assertEqual(result.status_code, 200)
                self.assertFalse(RFPOutcome.objects.filter(submission=self.submission).exists())
            result = self.post_outcome(timezone.localtime(observed).strftime('%Y-%m-%dT%H:%M:%S'))
        self.assertEqual(result.status_code, 302)
        outcome = RFPOutcome.objects.get(submission=self.submission)
        self.assertEqual(outcome.observed_at, observed)
        self.assertGreater(outcome.observed_at, self.submission.submitted_at)
        self.assertEqual(outcome.result, 'won')
