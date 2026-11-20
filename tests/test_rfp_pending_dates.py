from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_followup
from apps.pmo.models import RFPFollowupDispatch, RFPOutcome
from tests import factory_rfp_helpers, test_rfp
from tests.helpers import rev


class RFPPendingDateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        data = factory_rfp_helpers.configured()
        cls.actor, cls.case, cls.evidence = data['actor'], data['case'], data['evidence']
        response = test_rfp.response(cls.actor, cls.case, cls.evidence)
        test_rfp.approve(cls.actor, cls.case, cls.evidence, response)
        cls.submission = test_rfp.submit(cls.actor, cls.case, cls.evidence, data['template'], response)
        cls.work = factory_rfp_helpers.start(data)

    def setUp(self):
        self.observed_at = timezone.now()
        self.today = timezone.localdate(self.observed_at)
        self.customer_date = self.today + timedelta(days=7)
        self.proof = add_evidence(self.actor, self.case.pk, 'rfp_outcome',
            f'Sample customer message for submission {self.submission.pk} expects a decision on {self.customer_date}.',
            'synthetic:client-pending-message')

    def record(self, result='pending', role='Client', evidence_id=None, **dates):
        return rfp.outcome(self.actor, self.case.pk, self.submission.pk, result,
            self.observed_at, role, self.proof.pk if evidence_id is None else evidence_id,
            'Observed the sample customer message.', rev(self.case), **dates)

    def test_expected_date_is_separate_from_assigned_manager_reminder(self):
        earlier = self.record(customer_expected_on=self.customer_date)
        self.assertEqual(earlier.customer_expected_on, self.customer_date)
        self.assertIsNone(earlier.followup_on)
        self.assertEqual(list(rfp_followup.reminders(self.actor)), [])

        current = self.record(customer_expected_on=self.customer_date, followup_on=self.today)
        self.assertEqual(current.evidence_id, self.proof.pk)
        self.assertEqual(current.submission_id, self.submission.pk)
        self.assertEqual([reminder['detail'] for reminder in rfp_followup.reminders(self.actor)],
                         [self.today.isoformat()])
        earlier.refresh_from_db()
        self.assertIsNone(earlier.followup_on)

        latest = self.record(followup_on=self.today + timedelta(days=1))
        self.assertIsNone(latest.customer_expected_on)
        self.assertEqual(list(rfp_followup.reminders(self.actor)), [])
        current.refresh_from_db()
        self.assertEqual(current.customer_expected_on, self.customer_date)
        self.assertEqual(current.followup_on, self.today)

    def test_known_date_requires_pending_customer_evidence_and_authority(self):
        with self.assertRaisesMessage(ValidationError, 'only for an evidenced pending outcome'):
            self.record(result='unknown', customer_expected_on=self.customer_date)
        with self.assertRaisesMessage(ValidationError, 'only for an evidenced pending outcome'):
            self.record(customer_expected_on=self.customer_date.isoformat())
        with self.assertRaisesMessage(ValidationError, 'Choose the evidence for the customer response'):
            self.record(evidence_id=0, customer_expected_on=self.customer_date)
        with self.assertRaises(PermissionDenied):
            self.record(role='CEO', customer_expected_on=self.customer_date)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RFPOutcome.objects.create(submission=self.submission, observed_at=self.observed_at,
                result='unknown', role='Client', authority={}, actor=self.actor,
                customer_expected_on=self.customer_date)
        self.assertFalse(self.submission.outcomes.exists())

    def test_work_form_records_and_reads_each_date(self):
        self.client.force_login(self.actor)
        url = reverse('factory_work_response', args=[self.work.pk])
        self.assertContains(self.client.get(url, {'outcome': 'pending'}), 'name="customer_expected_on"')
        self.assertNotContains(self.client.get(url, {'outcome': 'unknown'}), 'name="customer_expected_on"')
        command = {'action': 'outcome', 'target': self.submission.pk, 'revision': self.work.revision,
            'case_revision': rev(self.case), 'verdict': 'pending', 'role': 'Client', 'evidence': self.proof.pk,
            'observed_at': self.observed_at.isoformat(), 'note': 'Sample client message with distinct dates.',
            'followup_on': self.today.isoformat(), 'customer_expected_on': self.customer_date.isoformat()}
        self.assertContains(self.client.post(url, {**command, 'customer_expected_on': '2026-13-40'}),
                            'Enter a valid date.')
        self.assertFalse(self.submission.outcomes.exists())
        response = self.client.post(url, command, follow=True)
        self.assertContains(response, 'Expected decision date stated by the customer')
        self.assertContains(response, 'Internal next check date')
        self.assertContains(response, f'Customer evidence {self.proof.pk}')
        self.assertContains(response, self.customer_date.strftime('%d %b %Y'))
        self.assertContains(response, self.today.strftime('%d %b %Y'))
        recorded = self.submission.outcomes.get()
        self.assertEqual(recorded.customer_expected_on, self.customer_date)
        self.assertEqual(recorded.followup_on, self.today)
        self.assertContains(self.client.get(reverse('rfp', args=[self.case.pk])), 'Customer expected decision')

    def test_exact_internal_reminder_is_due_only_for_current_pm_and_retires(self):
        peer = get_user_model().objects.create_user(username='sample-rfp-unassigned-reader')
        Grant.objects.bulk_create([Grant(case=self.case, user=peer, action=action)
                                   for action in ['case.read', 'rfp.read', 'rfp.prepare']])
        self.client.force_login(self.actor)
        outcome_url = reverse('factory_work_response', args=[self.work.pk])
        alerts_url = reverse('design_alerts')
        with timezone.override('Africa/Lagos'):
            tomorrow = timezone.localdate(self.observed_at) + timedelta(days=1)
            due = timezone.make_aware(datetime.combine(tomorrow, time(13, 4, 5)))
            command = {'action': 'outcome', 'target': self.submission.pk, 'revision': self.work.revision,
                'case_revision': rev(self.case), 'verdict': 'pending', 'role': 'Client', 'evidence': self.proof.pk,
                'observed_at': self.observed_at.isoformat(), 'note': 'Sample pending response, remind the assigned PM.',
                'customer_expected_on': self.customer_date.isoformat(), 'remind_at': due.strftime('%Y-%m-%dT%H:%M:%S')}
            self.assertContains(self.client.get(outcome_url, {'outcome': 'pending'}), 'Internal reminder time (Africa/Lagos)')
            self.assertNotContains(self.client.get(outcome_url, {'outcome': 'lost'}), 'name="remind_at"')
            saved = self.client.post(outcome_url, command, follow=True)
            self.assertContains(saved, '13:04:05 WAT')
            self.assertContains(saved, self.customer_date.strftime('%d %b %Y'))
            recorded = self.submission.outcomes.get()
            self.assertEqual(recorded.remind_at, due)
            self.assertIsNone(recorded.followup_on)
            with patch('apps.pmo.rfp_followup.timezone.now', return_value=due - timedelta(seconds=1)):
                self.assertNotContains(self.client.get(alerts_url), 'Bid follow-up due')
            with patch('apps.pmo.rfp_followup.timezone.now', return_value=due):
                self.assertContains(self.client.get(alerts_url), 'Bid follow-up due')
                self.assertContains(self.client.get(alerts_url), '13:04:05 WAT')
                self.client.force_login(peer)
                self.assertNotContains(self.client.get(alerts_url), 'Bid follow-up due')
                self.client.force_login(self.actor)
                self.record(result='won')
                self.assertNotContains(self.client.get(alerts_url), 'Bid follow-up due')
            recorded.refresh_from_db()
            self.assertEqual(recorded.remind_at, due)
            self.assertFalse(RFPFollowupDispatch.objects.filter(outcome__submission=self.submission).exists())

    def test_exact_reminder_rejects_invalid_or_combined_instants_in_native_and_db(self):
        due = self.observed_at + timedelta(seconds=5)
        for result, dates in [
            ('won', {'remind_at': due}),
            ('pending', {'remind_at': due, 'followup_on': self.today}),
            ('pending', {'remind_at': self.observed_at - timedelta(seconds=1)}),
            ('pending', {'remind_at': due.replace(tzinfo=None)}),
        ]:
            with self.subTest(result=result, dates=dates):
                with self.assertRaisesMessage(ValidationError, 'Choose one internal reminder time'):
                    self.record(result=result, **dates)
                if dates['remind_at'].tzinfo is not None:
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        RFPOutcome.objects.create(submission=self.submission, observed_at=self.observed_at,
                            result=result, role='Client', actor=self.actor, authority={}, evidence=self.proof, **dates)
        self.assertFalse(self.submission.outcomes.exists())
