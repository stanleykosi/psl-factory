import hashlib
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from adapters import case_uploads
from apps.agents.models import CaseUpload
from apps.core.models import Case
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo.changes import impact
from apps.pmo.models import ChangeAuthorization, ChangeVersion
from apps.workflows import factory_change
from apps.workflows.models import FactoryWork
from tests import railway_change_impact_seed as seed
from tests.helpers import rev


class LocalObjectStorage:
    def __init__(self, objects=None):
        self.objects = {} if objects is None else objects
        self.reads = []

    @contextmanager
    def connection(self):
        yield self, 'test-private-files'

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        self.reads.append(Key)
        return {'Body': BytesIO(self.objects[Key])}


class ChangeImpactWalkthroughTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trial = get_user_model().objects.create_user('psl-agent-trial')
        storage = LocalObjectStorage()
        with patch.object(case_uploads, 'storage_client', storage.connection):
            cls.sample = seed.prepare(cls.trial)
        cls.objects = storage.objects
        cls.workspace = Case.objects.get(pk=seed.CASE_ID)
        cls.version = ChangeVersion.objects.get(pk=cls.sample['version'])
        cls.work = FactoryWork.objects.get(pk=cls.sample['work'])

    def setUp(self):
        self.client.force_login(self.trial)
        self.storage = LocalObjectStorage(dict(self.objects))

    def fields(self):
        return {'action': 'assess', 'revision': self.work.revision, 'case_revision': rev(self.workspace),
                'change_version': self.version.pk, 'contributor': 'Security', 'evidence': self.sample['evidence'],
                'note': 'Recorded from the sample Security owner statement and private assessment.',
                'cost_impact': 'false', 'timeline_impact': 'false', 'client_facing': 'false',
                'impact_discipline': self.sample['discipline'], 'impact_timeline': 'The current dates are retained.',
                'impact_cost_resource': 'Already included in the time set aside for review.',
                'impact_risk': 'No new privacy exposure was reported.',
                'impact_dependency': 'The current provider remains required.',
                'effort_person_days': self.sample['effort'], 'proof_upload': self.sample['upload']}

    def test_latest_security_effort_and_private_proof_preserve_assessments_without_authorizing(self):
        self.assertEqual(connection.vendor, 'postgresql')
        with patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                                       'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', seed.GUARD: '0',
                                       'PGDATABASE': 'isolated-preview'}):
            with self.assertRaisesMessage(RuntimeError, 'Normal change impact fixture guard'):
                seed.run()
        file = CaseUpload.objects.get(pk=self.sample['upload'])
        path = self.sample['path']
        with patch.object(case_uploads, 'storage_client', self.storage.connection):
            first = self.client.get(path)
            self.assertContains(first, 'Impact assessments')
            self.assertContains(first, 'Unknown')
            self.assertContains(first, 'Upload a private assessment PDF')
            self.assertContains(first, self.sample['file'])
            self.assertEqual(len(first.context['impact_rows']), 4)
            self.assertEqual(self.storage.reads, [])
            fields = self.fields()
            saved = self.client.post(path, fields)
            self.assertRedirects(saved, path, fetch_redirect_response=False)
            self.assertEqual(self.storage.reads, [file.key])
            after = self.client.get(path)
            self.assertContains(after, '0.5 person-days')
            self.assertContains(after, self.sample['discipline'])
            private = reverse('case_upload_download', args=[self.workspace.pk, file.pk])
            self.assertContains(after, private)
            self.assertEqual(self.storage.reads, [file.key])
            download = self.client.get(private)
            self.assertEqual(hashlib.sha256(b''.join(download.streaming_content)).hexdigest(), file.sha256)
        latest = self.version.assessments.filter(contributor='Security').latest('pk')
        self.assertEqual(latest.impact_details['effort_person_days'], '0.5')
        self.assertEqual(latest.impact_details['private_proof'],
                         {'upload': file.pk, 'sha256': file.sha256, 'size': file.size})
        self.assertEqual(after.context['impact_rows'][-1]['record'].pk, latest.pk)
        self.assertEqual(self.version.assessments.count(), 5)
        self.assertEqual(list(self.version.assessments.exclude(pk=latest.pk).order_by('pk')
                              .values_list('pk', flat=True)), self.sample['initial'])
        ids, flags = impact(self.version)
        self.assertIn(latest.pk, ids)
        self.assertFalse(flags['cost_impact'])
        self.assertNotContains(self.client.post(path, fields), 'Controlled change action recorded')
        self.assertEqual(self.version.assessments.count(), 5)
        self.assertFalse(self.version.decisions.exists())
        self.assertFalse(ChangeAuthorization.objects.filter(version=self.version).exists())
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())
        self.assertNotIn('private_proof', factory_change.report(self.work)['owner_impacts'][-1]['impact_details'])

        reader = get_user_model().objects.create_user('sample-impact-read-only')
        Grant.objects.bulk_create([Grant(case=self.workspace, user=reader, action=action) for action in (
            'case.read', 'change.read', 'factory.read', 'evidence.add',
        )])
        self.client.force_login(reader)
        shared = self.client.get(path)
        self.assertContains(shared, '0.5 person-days')
        self.assertNotContains(shared, file.name)
        self.assertNotContains(shared, private)
        self.assertEqual(self.client.get(private).status_code, 404)

    def test_invalid_estimates_and_foreign_file_stop_before_any_proof_read_or_change(self):
        file = CaseUpload.objects.create(case=self.workspace, actor_id=self.sample['owner'],
            name='other-assessment.pdf', key='isolated-owner-file', sha256='a' * 64, size=100)
        fields = self.fields()
        with patch.object(case_uploads, 'storage_client', self.storage.connection):
            for value in ('-1', '0', 'NaN', '0.0001'):
                response = self.client.post(self.sample['path'], {**fields, 'effort_person_days': value})
                self.assertContains(response, 'positive')
            forged_file = self.client.post(self.sample['path'], {**fields, 'proof_upload': file.pk})
            self.assertContains(forged_file, 'Choose a private PDF assessment proof you uploaded to this project.')
        self.assertEqual(self.storage.reads, [])
        self.assertEqual(self.version.assessments.count(), 4)
