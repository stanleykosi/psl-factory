import hashlib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.agents.models import CaseUpload
from apps.core.models import Case
from apps.pmo.delivery import valid_release
from apps.pmo.models import DeliveryDossier
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests import railway_release_escalation_walkthrough_seed as seed


class ReleasePrivateLogTests(TestCase):
    def test_select_exact_private_pdf_and_keep_original_release_scope(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        actor = users.create_user('sample-release-pdf-operator')
        reader = users.create_user('sample-release-pdf-reader')
        objects = {}
        with patch('adapters.case_uploads.put', side_effect=objects.__setitem__):
            sample = seed.prepare_case(actor, 'release_file')
        self.assertEqual(seed.prepare_case(actor, 'release_file'), sample | {'preserved': True})
        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        case = work.case
        seed.grant(case, reader, ('case.read', 'factory.read', 'delivery.read'))
        upload = CaseUpload.objects.get(pk=sample['private_log'])
        data = objects[upload.key]
        self.assertEqual(hashlib.sha256(data).hexdigest(), sample['file_sha256'])
        other = CaseUpload.objects.create(case=case, actor=reader, name='restricted-other.pdf', key='test-release-other',
                                          size=len(data), sha256=upload.sha256)
        wrong_case = Case.objects.create(tenant=case.tenant, title='Grounded different fixture workspace', synthetic=True)
        wrong = CaseUpload.objects.create(case=wrong_case, actor=actor, name='different-workspace.pdf', key='test-release-wrong',
                                          size=len(data), sha256=upload.sha256)
        self.client.force_login(actor)
        page = self.client.get(sample['path'])
        self.assertContains(page, seed.FILE_NAME)
        self.assertNotContains(page, other.name)
        self.assertNotContains(page, wrong.name)
        payload = {'action': 'hypercare_observation', 'kind': 'release', 'revision': work.revision,
            'case_revision': rev(case), 'readiness': sample['readiness'], 'released_at': sample['released_at'],
            'deployment_environment': sample['environment'], 'reference': sample['reference'],
            'evidence': sample['evidence'], 'note': sample['note']}
        dossier = DeliveryDossier.objects.get(pk=sample['dossier'])
        with patch('adapters.case_uploads.read', return_value=b'invalid') as storage:
            for invalid in (other.pk, wrong.pk, upload.pk):
                bad = self.client.post(sample['path'], payload | {'private_log': invalid}, follow=True)
                self.assertIn(bad.status_code, (200, 400))
                self.assertFalse(dossier.records.filter(kind='release_outcome').exists())
            storage.assert_called_once_with(upload)
        with patch('adapters.case_uploads.read', return_value=data) as storage:
            self.assertRedirects(self.client.post(sample['path'], payload | {'private_log': upload.pk}),
                                 sample['path'], fetch_redirect_response=False)
            storage.assert_called_once_with(upload)
        outcome = valid_release(dossier)
        self.assertEqual(outcome.data['private_log'], {'upload': upload.pk, 'sha256': upload.sha256, 'size': upload.size})
        self.assertEqual(outcome.evidence_id, sample['evidence'])
        self.assertFalse(outcome.snapshot['deployment_dispatched'])
        self.assertEqual(dossier.records.filter(kind='release_outcome').count(), 1)
        owner_page = self.client.get(sample['path'])
        download = reverse('case_upload_download', args=[case.pk, upload.pk])
        self.assertContains(owner_page, download)
        with patch('adapters.case_uploads.read', return_value=data):
            response = self.client.get(download)
            self.assertEqual(b''.join(response.streaming_content), data)
        self.client.force_login(reader)
        self.assertContains(self.client.get(sample['path']), sample['reference'])
        self.assertNotContains(self.client.get(sample['path']), seed.FILE_NAME)
        self.assertEqual(self.client.get(download).status_code, 404)
