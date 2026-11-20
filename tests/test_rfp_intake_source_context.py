from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ClientContactRevision
from apps.core.services import add_evidence
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp
from apps.pmo.models import RFPCase, RFPIntake, RFPIntakeSourceContext, RFPSubmission
from apps.pmo.rfp_intake_context import SourceContext, validate
from apps.policy.models import Configuration
from tests.helpers import rev, setup_case
from tests.test_rfp_intake_upload import word_file


class RFPIntakeSourceContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case()
        cls.reader = get_user_model().objects.create_user(username='sample-rfp-context-reader')
        Grant.objects.bulk_create([Grant(case=cls.case, user=cls.reader, action=action)
                                   for action in ('case.read', 'rfp.read')])
        cls.source = add_evidence(cls.actor, cls.case.pk, 'rfp_intake',
            'SAMPLE Prospect named Sample Reconciliation. Submit to https://supplier.example.invalid/bids.',
            'synthetic:rfp-context-source')

    def setUp(self):
        self.client.force_login(self.actor)
        self.url = reverse('rfp', args=[self.case.pk])
        self.received_at = (timezone.now() - timedelta(minutes=2)).replace(microsecond=0)
        self.command = {'action': 'intake', 'revision': rev(self.case), 'reference': 'SAMPLE-RFP-SOURCE-CONTEXT',
            'received_at': self.received_at.isoformat(), 'deadline_status': 'unknown', 'note': 'Confirmed source receipt.'}
        self.context = {'prospect_name': 'Sample Reconciliation', 'submission_method': 'portal',
                        'submission_target': 'https://supplier.example.invalid/bids'}

    def current_intake(self):
        return RFPCase.objects.get(case=self.case).current_intake

    def test_attested_context_uses_exact_source_and_target_is_plain_text(self):
        self.assertEqual(connection.vendor, 'postgresql')
        command = {**self.command, **self.context, 'evidence': self.source.pk}
        self.assertContains(self.client.post(self.url, command), 'Confirm these facts appear in the received source.')
        self.assertFalse(RFPCase.objects.filter(case=self.case).exists())
        self.assertEqual(self.client.post(self.url, {**command, 'context_attested': 'on'}).status_code, 302)
        receipt = self.current_intake()
        self.assertEqual(receipt.evidence_id, self.source.pk)
        recorded = RFPIntakeSourceContext.objects.get(intake=receipt)
        self.assertEqual(recorded.submission_method, self.context['submission_method'])
        page = self.client.get(self.url)
        self.assertContains(page, self.context['prospect_name'])
        self.assertContains(page, self.context['submission_target'])
        self.assertNotContains(page, f'href="{self.context["submission_target"]}"')
        self.assertFalse(ClientContactRevision.objects.filter(case=self.case).exists())
        self.assertFalse(Configuration.objects.filter(case=self.case).exists())
        self.assertFalse(RFPSubmission.objects.filter(response__rfp=receipt.rfp).exists())
        self.assertFalse(Publication.objects.filter(version__document__case=self.case).exists())

    def test_source_and_reader_authority_are_checked_before_loading_observations(self):
        self.assertEqual(self.client.post(self.url, {**self.command, **self.context,
            'context_attested': 'on', 'evidence': self.source.pk}).status_code, 302)
        self.client.force_login(self.reader)
        with CaptureQueriesContext(connection) as checks:
            page = self.client.get(self.url)
            self.assertNotContains(page, self.context['submission_target'])
        self.assertFalse(any('"pmo_rfpintakesourcecontext"."submission_target"' in row['sql'] for row in checks))
        Grant.objects.create(case=self.case, user=self.reader, action='document.read')
        self.assertContains(self.client.get(self.url), self.context['submission_target'])
        Grant.objects.filter(case=self.case, user=self.actor, action='evidence.add').update(active=False)
        with CaptureQueriesContext(connection) as checks:
            self.assertNotContains(self.client.get(self.url), self.context['submission_target'])
        self.assertFalse(any('"pmo_rfpintakesourcecontext"."submission_target"' in row['sql'] for row in checks))

    def test_same_uploaded_receipt_replays_only_with_the_same_source_facts(self):
        command = {**self.command, **self.context, 'context_attested': 'on'}
        first_file = word_file()
        content = first_file.read()
        first_file.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        def file():
            return SimpleUploadedFile(first_file.name, content)

        with patch('adapters.case_uploads.put') as put:
            self.assertEqual(self.client.post(self.url, {**command, 'rfp_file': first_file}).status_code, 302)
            first = self.current_intake()
            self.assertEqual(self.client.post(self.url, {**command, 'rfp_file': file()}).status_code, 302)
            stale = self.client.post(self.url, {**command, 'submission_target': 'Other portal', 'rfp_file': file()})
            self.assertContains(stale, 'Stale revision')
            put.assert_called_once()
            page = self.client.get(self.url)
            self.assertContains(page, self.context['submission_target'])
            self.assertContains(page, 'Open original bid document')
        self.assertEqual(RFPIntake.objects.filter(rfp__case=self.case).count(), 1)
        self.assertEqual(RFPIntakeSourceContext.objects.get(intake=first).submission_target, self.context['submission_target'])

    def test_legacy_unknown_and_db_constraints(self):
        self.assertEqual(self.client.post(self.url, {**self.command, 'evidence': self.source.pk}).status_code, 302)
        legacy = self.current_intake()
        self.assertFalse(RFPIntakeSourceContext.objects.filter(intake=legacy).exists())
        self.assertNotContains(self.client.get(self.url), 'Recorded submission instructions')
        for value in (SourceContext(submission_target='Unknown'), SourceContext(submission_method='email', submission_target='bad'),
                      SourceContext(submission_method='portal', submission_target='https://user:password@example.invalid/')):
            with self.assertRaises(ValidationError):
                validate(value, True)
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPIntakeSourceContext.objects.create(intake=legacy, submission_method='not_stated', submission_target='Invalid')
        current = rfp.intake(self.actor, self.case.pk, self.command['reference'], self.source.pk, self.received_at,
            'unknown', None, None, 'Separate receipt revision', rev(self.case),
            source_context=SourceContext(submission_method='not_stated'), context_attested=True)
        revision = RFPIntakeSourceContext.objects.get(intake=current)
        self.assertEqual(revision.submission_method, 'not_stated')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPIntakeSourceContext.objects.create(intake=legacy, prospect_name='Stale source')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPIntakeSourceContext.objects.filter(pk=revision.pk).update(submission_method='email')
