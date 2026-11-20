"""Observed decline and correction on the same native internal delivery receipt."""

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.agents.models import AgentJob, CaseUpload
from apps.core.models import Case
from apps.documents.delivery import run_publication_once
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.pmo import commercial_client_response as domain
from apps.pmo.models import BaselineAdoption, ClientResponse
from tests import railway_sow_decline_seed as seed
from tests.helpers import rev
from tests.test_commercial_client_response import PrivateStore


class SowDeclineFixtureTests(TestCase):
    def test_browser_actions_record_decline_and_correction_without_superseding_delivery(self):
        self.assertEqual(connection.vendor, 'postgresql')
        recorder = get_user_model().objects.create_user(seed.RECORDER)
        sample = seed.prepare(recorder)
        case = Case.objects.get(pk=sample['case'])
        repeated = seed.prepare(recorder)
        self.assertTrue(repeated['preserved'])
        self.assertEqual(repeated['version'], sample['version'])
        for model in (Publication, PublicationJob, PublicationReceipt, CaseUpload, ClientResponse, BaselineAdoption, AgentJob):
            self.assertFalse(model.objects.exists(), model.__name__)
        with self.assertRaisesMessage(ValidationError, 'exact client delivery receipt'):
            domain.receipt_for(case, sample['proposal'], 0)

        self.client.force_login(recorder)
        self.assertContains(self.client.get(sample['documents']), 'Reserve publication')
        self.assertEqual(self.client.post(sample['documents'], {'action': 'publish',
            'version': sample['version'], 'revision': rev(case)}).status_code, 302)
        self.assertTrue(run_publication_once(case_id=case.pk))
        receipt = PublicationReceipt.objects.get(publication__version_id=sample['version'])
        self.assertEqual(receipt.recipient_id, recorder.pk)
        self.assertEqual(receipt.payload_sha256, sample['document_sha256'])
        replied_at = timezone.now().isoformat()

        def observe(variant, predecessor):
            proof = seed.sample_proof(sample, receipt.pk, variant)
            self.assertIn(str(receipt.pk).encode(), proof)
            upload = self.client.post(sample['response'], {'action': 'upload', 'revision': rev(case),
                'file': SimpleUploadedFile(seed.PROOF_NAMES[variant], proof)})
            self.assertEqual(upload.status_code, 302)
            source = CaseUpload.objects.get(case=case, actor=recorder, name=seed.PROOF_NAMES[variant])
            post = self.client.post(sample['response'], {'action': 'record', 'revision': rev(case),
                'operation_key': uuid4(), 'predecessor': predecessor or '', 'receipt': receipt.pk,
                'client_name': seed.CLIENT_NAMES[variant], 'responded_at': replied_at, 'outcome': 'declined',
                'proofs': [source.pk], 'genuine': 'on', 'note': f'SAMPLE {variant} witnessed reply to this exact delivery.'})
            self.assertEqual(post.status_code, 302)
            metadata = domain.latest(case)
            value, response = domain.read(recorder, case, metadata)
            self.assertEqual((value['receipt'], value['document_sha256'], value['predecessor']),
                (receipt.pk, sample['document_sha256'], predecessor))
            self.assertEqual((response.kind, value['proofs'][0]['id']), ('declined', source.pk))
            return metadata, response

        with patch('adapters.case_uploads.bucket', return_value=(PrivateStore(), 'private-sample')):
            initial, original = observe('initial', None)
            self.assertContains(self.client.get(sample['response']), 'Record a correction')
            corrected, current = observe('corrected', initial.pk)
            page = self.client.get(sample['response'])
            self.assertContains(page, 'The client declined')
            self.assertContains(page, seed.CLIENT_NAMES['corrected'])
            self.assertNotContains(page, 'Use the verified signed documents as the project baseline')
        self.assertNotEqual(initial.pk, corrected.pk)
        self.assertEqual(list(ClientResponse.objects.filter(receipt=receipt).order_by('pk').values_list('pk', flat=True)),
            [original.pk, current.pk])
        self.assertEqual(PublicationReceipt.objects.count(), 1)
        self.assertFalse(BaselineAdoption.objects.exists())
        files_after = CaseUpload.objects.count()
        preserved = seed.prepare(recorder)
        self.assertEqual((preserved['existing_delivery'], preserved['existing_responses']), (receipt.publication_id, 2))
        self.assertEqual(CaseUpload.objects.count(), files_after)
