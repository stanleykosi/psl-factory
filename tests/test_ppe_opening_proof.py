"""Private asset proof recovery with native reviews and a checked storage adapter."""

from contextlib import nullcontext
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import CaseUpload
from apps.core.evidence_access import PPE_OPENING_SOURCE, public_evidence
from apps.core.models import Audit
from apps.finance.models import ScheduleWork
from apps.identity.models import Grant
from apps.workflows import factory_progress, factory_ppe as flow, factory_ppe_opening
from tests import ppe_helpers, test_factory_ppe
from tests.helpers import rev


def pdf_file():
    from pypdf import PdfWriter

    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    contents = buffer.getvalue()
    return contents, SimpleUploadedFile('sample-opening-proof.pdf', contents, content_type='application/pdf')


class PPEOpeningProofTests(TestCase):
    def setUp(self):
        fixture = test_factory_ppe.FactoryPPETests()
        fixture.setUp()
        self.data = fixture.f
        data = self.data
        native_body = data['ppe']['body']
        earlier_label = date.fromisoformat(native_body['period_end']) - timedelta(days=1)
        data['register'] = ppe_helpers.capture(data, dict(native_body, label_as_of=earlier_label.isoformat()))
        ppe_helpers.review(data, data['register'], 'register')
        ppe_helpers.review(data, data['register'], 'basis')
        self.work = fixture.start()
        self.job = factory_progress.set_progress(data['actor'], self.work.pk, self.work.revision, True)
        self.drain('waiting')
        self.original = flow.schedule(self.work)
        self.assertIsNotNone(self.original, self.work.finding)
        self.decision = reverse('factory_invoice_decision', args=[self.work.pk])
        self.recovery = reverse('factory_invoice_recovery', args=[self.work.pk])
        self.returning = flow.review(data['reviewer'], self.work.pk, self.work.revision, rev(data['case']), self.original.pk,
                                    'schedule', 'return', data['e']['finance_review'].pk, 'Attach exact opening proof.')
        self.job.refresh_from_db()
        self.assertLessEqual(self.job.available_at, timezone.now())
        self.drain('waiting')
        self.client.force_login(data['actor'])

        self.objects = {}
        self.bucket = Mock()
        self.bucket.put_object.side_effect = lambda **values: self.objects.__setitem__(values['Key'], values['Body'])
        self.bucket.get_object.side_effect = lambda **values: {'Body': BytesIO(self.objects[values['Key']])}
        self.bucket.delete_object.side_effect = lambda **values: self.objects.pop(values['Key'], None)
        storage = patch('adapters.case_uploads.storage_client', side_effect=lambda: nullcontext((self.bucket, 'test-bucket')))
        storage.start()
        self.addCleanup(storage.stop)

    def drain(self, status):
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), self.job.pk)
            self.job.refresh_from_db()
            if self.job.status != 'queued':
                break
        self.work.refresh_from_db()
        self.assertEqual(self.job.status, status, self.job.observation)

    def command(self, file):
        return {'action': 'attach_opening_proof', 'target_id': self.original.pk, 'review_id': self.returning.pk,
                'revision': self.work.revision, 'case_revision': rev(self.data['case']),
                'reason': 'The exact private opening proof was supplied.', 'file': file}

    def test_private_upload_rebuilds_exact_register_and_requires_fresh_native_decisions(self):
        data = self.data
        paused = factory_progress.set_progress(data['actor'], self.work.pk, self.work.revision, False)
        original_register = data['register']
        self.assertContains(self.client.get(self.recovery), 'Correct and resubmit')
        self.assertContains(self.client.get(self.recovery), 'Select corrected sources and rebuild')
        payload, file = pdf_file()
        command = self.command(file)
        self.assertRedirects(self.client.post(self.recovery, command), self.recovery, fetch_redirect_response=False)
        self.work.refresh_from_db()
        paused.refresh_from_db()
        self.assertEqual(paused.status, 'paused')
        successor, _ = flow.source(self.work, data['actor'])
        opening_id = successor.payload['opening_evidence_id']
        self.assertEqual(successor.payload, dict(original_register.payload, opening_evidence_id=opening_id))
        self.assertEqual(successor.version, original_register.version + 1)
        self.assertEqual(successor.evidence.source, PPE_OPENING_SOURCE)
        self.assertFalse(successor.reviews.exists())
        self.assertEqual(self.original.reviews.get().pk, self.returning.pk)
        self.assertFalse(public_evidence(data['case'].evidence.filter(pk__in=[opening_id, successor.evidence_id])).exists())
        self.assertFalse(CaseUpload.objects.filter(case=data['case']).exists())
        self.assertEqual(self.bucket.put_object.call_count, 1)
        self.assertNotEqual(self.client.post(self.recovery, dict(command, file=pdf_file()[1])).status_code, 302)
        self.assertEqual(self.bucket.put_object.call_count, 1)

        proof_path = reverse('factory_ppe_opening_proof', args=[self.work.pk, successor.pk])
        reader = get_user_model().objects.create_user('sample-ppe-metadata-reader')
        for action in ['case.read', 'factory.read', 'finance.read', 'ppe.read']:
            Grant.objects.create(user=reader, case=data['case'], action=action)
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(self.decision), 'sample-opening-proof.pdf')
        self.assertIn(self.client.get(proof_path).status_code, (403, 404))
        self.bucket.get_object.assert_not_called()
        self.client.force_login(data['reviewer'])
        self.assertContains(self.client.get(self.decision), 'Open private opening proof')
        downloaded = self.client.get(proof_path)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(b''.join(downloaded.streaming_content), payload)
        self.assertIn('no-store', downloaded.headers['Cache-Control'])
        self.assertEqual(self.client.get(reverse('factory_ppe_opening_proof', args=[self.work.pk, original_register.pk])).status_code,
                         404)

        factory_progress.set_progress(data['actor'], self.work.pk, self.work.revision, True)
        self.drain('waiting')
        self.assertIsNone(flow.schedule(self.work))
        flow.review(data['reviewer'], self.work.pk, self.work.revision, rev(data['case']), successor.pk, 'register',
                    'approve', data['e']['finance_review'].pk, 'Reviewed the exact new source and its private proof.')
        self.drain('waiting')
        self.assertIsNone(flow.schedule(self.work))
        self.assertContains(self.client.get(self.decision), 'Approve exact basis')
        date_proof = ppe_helpers.evidence(data, 'ppe_basis_explanation', 'Synthetic explanation for October reporting dates.')
        flow.review(data['reviewer'], self.work.pk, self.work.revision, rev(data['case']), successor.pk, 'basis',
                    'approve', date_proof.pk, 'Reviewed the separate reporting dates.')
        self.drain('waiting')
        calculated = flow.schedule(self.work)
        self.assertEqual(calculated.version, self.original.version + 1)
        self.assertFalse(calculated.reviews.exists())
        flow.review(data['reviewer'], self.work.pk, self.work.revision, rev(data['case']), calculated.pk, 'schedule',
                    'approve', data['e']['finance_review'].pk, 'Reviewed the exact new schedule.')
        self.drain('finished')
        self.assertFalse(flow.verify(self.work, data['actor'])['ledger_posted'])
        report_path = reverse('ppe_report', args=[data['case'].pk, calculated.pk])
        self.assertEqual(self.client.get(report_path).status_code, 200)
        self.bucket.get_object.reset_mock()
        Grant.objects.filter(user=data['actor'], case=data['case'], action='factory.manage').update(active=False)
        self.assertEqual(self.client.get(proof_path).status_code, 403)
        self.assertEqual(self.client.get(report_path).status_code, 403)
        self.assertEqual(self.client.get(report_path + '?format=json').status_code, 403)
        self.assertNotContains(self.client.get(self.decision), 'Open private opening proof')
        self.bucket.get_object.assert_not_called()
        self.assertEqual(self.original.reviews.get().pk, self.returning.pk)
        self.assertEqual(calculated.reviews.get().verdict, 'approve')
        self.assertTrue(Audit.objects.filter(case=data['case'], action=factory_ppe_opening.ATTACHED).exists())

    def test_failed_private_storage_cleans_unbound_object_and_preserves_old_source(self):
        data = self.data
        original_head = self.work.source_head_id
        count = ScheduleWork.objects.filter(case=data['case']).count()
        revision = rev(data['case'])
        self.job.refresh_from_db()
        availability = self.job.available_at

        malformed = SimpleUploadedFile('opening.pdf', b'not a PDF', content_type='application/pdf')
        self.assertContains(self.client.post(self.recovery, self.command(malformed)), 'Choose a valid PDF proof file.')
        self.bucket.put_object.assert_not_called()

        def fail_after_storage(**values):
            self.objects[values['Key']] = values['Body']
            raise OSError('Synthetic uncertain storage response')

        self.bucket.put_object.side_effect = fail_after_storage
        self.assertContains(self.client.post(self.recovery, self.command(pdf_file()[1])), 'Private storage is unavailable')
        self.assertEqual(self.objects, {})
        self.assertEqual(self.bucket.delete_object.call_count, 1)
        self.assertFalse(Audit.objects.filter(case=data['case'], action=factory_ppe_opening.ATTACHED).exists())
        self.assertFalse(data['case'].evidence.filter(source=PPE_OPENING_SOURCE).exists())
        self.work.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(self.work.source_head_id, original_head)
        self.assertEqual(self.job.available_at, availability)
        self.assertEqual(rev(data['case']), revision)
        self.assertEqual(ScheduleWork.objects.filter(case=data['case']).count(), count)
