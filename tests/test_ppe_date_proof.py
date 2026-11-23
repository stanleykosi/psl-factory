"""Date PDF acceptance through native PostgreSQL records and scoped download."""

from contextlib import nullcontext
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.agents.models import CaseUpload
from apps.core.models import Audit
from apps.finance import ppe, ppe_dates
from apps.finance.models import ScheduleWork
from apps.identity.models import Grant
from apps.workflows import factory, factory_ppe, factory_ppe_date_proof
from tests import ppe_helpers, test_factory_ppe
from tests.helpers import rev
from tests.test_ppe_opening_proof import pdf_file


class PPEAssetDateProofTests(TestCase):
    def setUp(self):
        fixture = test_factory_ppe.FactoryPPETests()
        fixture.setUp()
        self.sample = fixture.f
        self.maker, self.case, self.reviewer = (self.sample[key] for key in ('actor', 'case', 'reviewer'))
        self.original = self.sample['register']
        self.asset_path = reverse('ppe', args=[self.case.pk])
        self.bucket = Mock()
        self.files = {}
        self.bucket.put_object.side_effect = lambda **args: self.files.__setitem__(args['Key'], args['Body'])
        self.bucket.get_object.side_effect = lambda **args: {'Body': BytesIO(self.files[args['Key']])}
        self.bucket.delete_object.side_effect = lambda **args: self.files.pop(args['Key'], None)
        storage = patch('adapters.case_uploads.storage_client', side_effect=lambda: nullcontext((self.bucket, 'test-bucket')))
        storage.start()
        self.addCleanup(storage.stop)
        self.client.force_login(self.maker)

    def date_command(self, content, *, expected=None):
        return {'action': 'record_dates', 'register': self.original.pk, 'asset_id': 'A1', 'delivery_date': '2026-10-02',
            'in_service_date': '2026-10-10', 'fraction_basis': ppe_dates.DERIVED, 'evidence': self.sample['e']['ppe_event'].pk,
            'revision': rev(self.case) if expected is None else expected,
            'file': SimpleUploadedFile('sample-date-explanation.pdf', content, content_type='application/pdf')}

    def test_api_register_capture_date_proof_and_independent_basis_review(self):
        url = f'/api/v1/projects/{self.case.pk}/asset-registers'
        initial = self.client.get(url)
        self.assertEqual(initial.status_code, 200, initial.content)
        self.assertIn(self.original.pk, [row['id'] for row in initial.json()['registers']])
        selection = {'case_revision': initial.json()['case_revision'], 'reference': 'asset-date-api',
                     'evidence_id': self.original.evidence_id}
        captured = self.client.post(url, selection, content_type='application/json')
        self.assertEqual(captured.status_code, 201, captured.content)
        created = captured.json()
        body, file = pdf_file()
        command = {'case_revision': created['case_revision'], 'asset_id': 'A1', 'delivery_date': '2026-10-02',
                   'in_service_date': '2026-10-10', 'fraction_basis': ppe_dates.DERIVED,
                   'evidence_id': self.sample['e']['ppe_event'].pk, 'file': file}
        created = self.client.post(f"{url}/{created['id']}/dates", command)
        self.assertEqual(created.status_code, 201, created.content)
        successor = ScheduleWork.objects.get(pk=created.json()['id'])
        ppe_helpers.review(self.sample, successor, 'register')
        work = factory_ppe.start(self.maker, self.case.pk, 'DATE-API', successor.pk, None,
                                 self.sample['parent'].pk, 'SAMPLE-DATED-ASSET', rev(self.case))
        factory.run_until_wait(work.pk)
        self.client.force_login(self.reviewer)
        detail = self.client.get(f'/api/v1/work/{work.pk}/assets')
        self.assertEqual(detail.status_code, 200, detail.content)
        page = detail.json()
        self.assertEqual(page['stage'], 'basis_review')
        self.assertIn({'target_id': successor.pk, 'purpose': 'basis', 'verdicts': ['approve', 'return', 'reject']},
                      page['review_options'])
        fact, = page['date_attachment_ids']
        proof = f'/api/v1/work/{work.pk}/assets/date-proofs/{fact}'
        downloaded = self.client.get(proof)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(b''.join(downloaded.streaming_content), body)
        self.assertIsNone(page['schedule'])
        Grant.objects.filter(case=self.case, user=self.reviewer, action='ppe.report').update(active=False)
        self.assertEqual(self.client.get(proof).status_code, 403)
        self.assertIsNone(self.client.get(f'/api/v1/work/{work.pk}/assets').json()['register'])

    def test_pdf_is_pinned_to_exact_dates_and_remains_separate_from_finance_approval(self):
        self.assertEqual(connection.vendor, 'postgresql')
        original_decisions = list(self.original.reviews.values_list('pk', flat=True))
        self.assertContains(self.client.get(self.asset_path), 'Date explanation PDF')
        body, _ = pdf_file()
        posted = self.date_command(body)
        self.assertRedirects(self.client.post(self.asset_path, posted), self.asset_path, fetch_redirect_response=False)
        self.assertRedirects(self.client.post(self.asset_path, self.date_command(body, expected=posted['revision'])),
                             self.asset_path, fetch_redirect_response=False)
        receipt = Audit.objects.get(case=self.case, action=factory_ppe_date_proof.ATTACHED)
        successor = ScheduleWork.objects.get(case=self.case, pk=receipt.data['register'])
        dates = successor.payload['assets'][0]['dates']
        self.assertEqual((dates['delivery_date'], dates['in_service_date'], dates['support_evidence_id']),
                         ('2026-10-02', '2026-10-10', self.sample['e']['ppe_event'].pk))
        self.assertEqual(dates['evidence_id'], receipt.data['fact'])
        self.assertEqual(list(self.original.reviews.values_list('pk', flat=True)), original_decisions)
        self.assertFalse(successor.reviews.exists())
        self.assertFalse(CaseUpload.objects.filter(case=self.case).exists())
        self.assertNotContains(self.client.get(reverse('case', args=[self.case.pk])), receipt.data['storage_key'])
        self.bucket.put_object.assert_called_once()

        ppe_helpers.review(self.sample, successor, 'register')
        work = factory_ppe.start(self.maker, self.case.pk, 'date-pdf-review', successor.pk, None,
                                 self.sample['parent'].pk, 'SAMPLE-DATED-ASSET', rev(self.case))
        factory.run_until_wait(work.pk)
        decision = reverse('factory_invoice_decision', args=[work.pk])
        proof = reverse('factory_ppe_date_proof', args=[work.pk, dates['evidence_id']])
        self.assertNotContains(self.client.get(decision), 'Approve exact basis')
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(decision), 'Date explanation proof')
        self.assertContains(self.client.get(decision), f'href="{proof}"')
        self.assertContains(self.client.get(decision), 'Approve exact basis')
        response = self.client.get(proof)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(b''.join(response.streaming_content), body)
        self.assertEqual(self.client.get(reverse('factory_ppe_date_proof', args=[work.pk, dates['support_evidence_id']])).status_code, 404)
        self.assertIsNone(factory_ppe.schedule(work))
        basis = ppe_helpers.review(self.sample, successor, 'basis')
        self.assertEqual(ppe.latest(successor, 'basis'), basis)

        self.files[receipt.data['storage_key']] = b'altered stored PDF'
        self.assertEqual(self.client.get(proof).status_code, 404)
        self.bucket.get_object.reset_mock()
        reader = get_user_model().objects.create_user('asset-date-metadata-reader')
        Grant.objects.bulk_create(Grant(case=self.case, user=reader, action=action)
                                  for action in ('case.read', 'finance.read', 'factory.read', 'ppe.read'))
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(decision), 'sample-date-explanation.pdf')
        self.assertIn(self.client.get(proof).status_code, (403, 404))
        self.bucket.get_object.assert_not_called()

    def test_invalid_pdf_and_failed_private_storage_keep_the_original_register(self):
        self.assertEqual(connection.vendor, 'postgresql')
        bad = self.client.post(self.asset_path, self.date_command(b'not a PDF'), follow=True)
        self.assertContains(bad, 'Choose a valid PDF proof file')
        self.bucket.put_object.assert_not_called()
        body, _ = pdf_file()

        def failing_put(**args):
            self.files[args['Key']] = args['Body']
            raise OSError('synthetic storage failure')

        self.bucket.put_object.side_effect = failing_put
        failed = self.client.post(self.asset_path, self.date_command(body), follow=True)
        self.assertContains(failed, 'Private storage is unavailable')
        self.assertEqual(self.files, {})
        self.bucket.delete_object.assert_called_once()
        self.assertFalse(Audit.objects.filter(case=self.case, action=factory_ppe_date_proof.ATTACHED).exists())
        self.assertFalse(ScheduleWork.objects.filter(case=self.case, kind='ppe_register',
            reference=self.original.reference, version__gt=self.original.version).exists())
