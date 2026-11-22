"""Fresh bid intake uses actual PostgreSQL transactions and a synthetic storage adapter."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import AgentRun, CaseUpload
from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence
from apps.documents.models import Publication
from apps.identity import intake as identity
from apps.identity.intake_models import CaseIntake
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_fresh_intake, rfp_intake_context, rfp_intake_upload
from apps.pmo.models import RFPAssignment, RFPIntake, RFPStagedUpload, RFPSubmission
from tests.helpers import rev
from tests.test_rfp_intake_upload import PRIVATE_TEXT, pdf_file, word_file


TENANT = 'sample-bid-intake-organization'


def delegated_scope():
    actions = sorted(rfp_fresh_intake.GRANTS)
    return {'format': 'psl.tenant-access/v1', 'create_cases': True, 'manage_access': False,
            'kinds': ['project'], 'classification': 'synthetic', 'allowed_actions': actions, 'initial_actions': actions}


def authorized_operator():
    users = get_user_model().objects
    administrator = users.create_superuser('sample-bid-bootstrap')
    recorder = users.create_user('sample-bid-intake-recorder')
    return administrator, recorder, provision(administrator, recorder, delegated_scope())


def provision(administrator, recorder, scope, *, tenant=TENANT, enabled=True):
    return identity.provision(administrator, recorder, tenant, scope, timezone.now() + timedelta(hours=1), enabled,
                              'Synthetic workspace creation permission for an intake test.')


def word_with_deadline(deadline):
    source, result = BytesIO(word_file().read()), BytesIO()
    with ZipFile(source) as original, ZipFile(result, 'w') as revised:
        for name in original.namelist():
            data = original.read(name)
            if name == 'word/document.xml':
                data = data.replace(b'</w:t>', f' · Bid deadline: {deadline.isoformat()}</w:t>'.encode())
            revised.writestr(name, data)
    return SimpleUploadedFile('SAMPLE-deadline.docx', result.getvalue())


class FreshBidIntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.administrator, cls.recorder, cls.authority = authorized_operator()

    def setUp(self):
        self.key = uuid4()
        self.received = (timezone.now() - timedelta(minutes=5)).replace(microsecond=0)
        self.url = reverse('factory_create') + '?definition=received-bid'
        self.client.force_login(self.recorder)
        self.command = {'definition': rfp_fresh_intake.LINE, 'authority': self.authority.pk,
            'start_key': self.key, 'reference': 'SAMPLE-RECEIVED-BID', 'received_at': self.received.isoformat(),
            'deadline_status': 'unknown', 'deadline_at': '', 'prospect_name': 'Sample Port Authority',
            'submission_method': 'email', 'submission_target': 'procurement@example.invalid', 'context_attested': 'on'}

    def assert_no_intake(self):
        for model in (Case, CaseIntake, RFPIntake, CaseUpload, Grant, Evidence):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_api_and_form_share_the_original_file_receipt_and_delegation(self):
        url = '/api/v1/received-bids'
        orgs = self.client.get(url + '/organisations').json()['items']
        self.assertEqual(orgs, [{'id':self.authority.pk,'organisation':self.authority.tenant}])
        with patch('adapters.case_uploads.put') as put:
            invalid = self.client.post(url, {**self.command, 'definition': 'planning/v1', 'document': pdf_file()})
            self.assertEqual(invalid.status_code, 422)
            put.assert_not_called()
            first = self.client.post(url, {**self.command, 'document':pdf_file()})
            self.assertEqual(first.status_code,200,first.content)
            second = self.client.post(self.url, {**self.command,'document':pdf_file()})
            self.assertRedirects(second,first.json()['django_url'],fetch_redirect_response=False)
            self.assertEqual(first.json()['receipt_id'], RFPIntake.objects.get().pk)
            typed = {key: value for key, value in self.command.items() if key not in {'definition', 'deadline_at'}}
            replay = self.client.post(url, {**typed, 'context_attested': 'true', 'document': pdf_file()})
            self.assertEqual(replay.status_code, 200, replay.content)
            self.assertEqual(replay.json()['receipt_id'], first.json()['receipt_id'])
            self.assertEqual(put.call_count,1)
            self.client.force_login(self.administrator)
            self.assertFalse(self.client.get(url + '/organisations').json()['items'])
            self.assertEqual(self.client.post(url,{**self.command,'document':pdf_file()}).status_code,403)

    def test_start_work_records_one_new_workspace_with_exact_private_file(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertFalse(Grant.objects.filter(user=self.recorder).exists())
        self.assertContains(self.client.get(reverse('factory_intake')), 'Log a received bid')
        self.assertContains(self.client.get(self.url), 'Attach the bid document')
        document = pdf_file()
        original = document.read()
        document.seek(0)
        with patch('adapters.case_uploads.put') as store:
            accepted = self.client.post(self.url, {**self.command, 'document': document})
            self.assertEqual(accepted.status_code, 302)
            receipt = RFPIntake.objects.get()
            case = receipt.rfp.case
            location = f"{reverse('rfp', args=[case.pk])}?received={receipt.pk}"
            proof_url = reverse('rfp_intake_attachment', args=[case.pk, receipt.pk])
            self.assertRedirects(accepted, location, fetch_redirect_response=False)
            self.assertEqual((case.tenant, case.kind, case.synthetic), (TENANT, 'project', True))
            self.assertEqual(case.caseintake.authority_id, self.authority.pk)
            self.assertEqual(set(Grant.objects.filter(case=case, user=self.recorder).values_list('action', flat=True)), rfp_fresh_intake.GRANTS)
            self.assertEqual((receipt.received_at, receipt.deadline_status, receipt.deadline_at), (self.received, 'unknown', None))
            self.assertEqual(receipt.observed_context.submission_target, 'procurement@example.invalid')
            self.assertNotIn(PRIVATE_TEXT, receipt.evidence.body)
            attachment = rfp_intake_upload.attachment_for(self.recorder, case, receipt)
            store.assert_called_once_with(attachment.key, original)
            successor_source = add_evidence(self.recorder, case.pk, 'rfp_intake', 'Later recorded source.', 'synthetic:later-bid-copy')
            successor = rfp.intake(self.recorder, case.pk, receipt.rfp.reference, successor_source.pk,
                self.received, 'not_stated', None, None, 'The later copy expressly states no deadline.', rev(case))
            repeat = rfp_fresh_intake.record(self.recorder, self.authority.pk, self.key, receipt.rfp.reference,
                self.received, 'unknown', None, SimpleUploadedFile('SAMPLE-renamed.pdf', original),
                source_context=rfp_intake_context.from_intake(receipt), context_attested=True)
            self.assertEqual((repeat.pk, repeat.rfp.current_intake_id), (receipt.pk, successor.pk))
            original_link = self.client.post(self.url, {**self.command,
                'document': SimpleUploadedFile('SAMPLE-renamed.pdf', original)})
            self.assertRedirects(original_link, location, fetch_redirect_response=False)
            readback = self.client.get(location)
            self.assertContains(readback, 'Original bid receipt')
            self.assertContains(readback, proof_url)
            self.assertNotContains(readback, PRIVATE_TEXT)
            changed = self.client.post(self.url, {**self.command, 'submission_target': 'different@example.invalid',
                'document': SimpleUploadedFile('SAMPLE-renamed.pdf', original)})
            self.assertContains(changed, 'This start request already has different details')
            store.assert_called_once()
        self.assertEqual(Case.objects.count(), 1)
        self.assertEqual(CaseUpload.objects.count(), 1)
        self.assertEqual(Audit.objects.filter(action=rfp_fresh_intake.ACTION).count(), 1)
        for model in (RFPAssignment, RFPSubmission, Publication, AgentRun):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_stated_deadline_has_evidence_bound_to_the_attachment(self):
        deadline = self.received + timedelta(days=3)
        document = word_with_deadline(deadline)
        fingerprint = hashlib.sha256(document.read()).hexdigest()
        document.seek(0)
        with patch('adapters.case_uploads.put'):
            invalid = self.client.post(self.url, {**self.command, 'deadline_status': 'stated', 'document': word_file()})
            self.assertContains(invalid, 'Enter the deadline only when it is stated')
            self.assert_no_intake()
            recorded = self.client.post(self.url, {**self.command, 'deadline_status': 'stated',
                'deadline_at': deadline.isoformat(), 'document': document})
        self.assertEqual(recorded.status_code, 302)
        intake = RFPIntake.objects.get()
        proof = intake.deadline_evidence
        self.assertEqual((proof.case_id, proof.created_by_id, proof.source),
            (intake.rfp.case_id, self.recorder.pk, rfp_fresh_intake.DEADLINE_SOURCE))
        self.assertEqual(json.loads(proof.body), {'schema': 'psl.rfp-upload-deadline-observation/v1',
            'deadline': deadline.isoformat(), 'attachment_sha256': fingerprint})

    def test_stale_scope_missing_actions_and_malformed_file_cannot_create_workspace(self):
        missing = delegated_scope()
        missing['initial_actions'].remove('document.read')
        successor = provision(self.administrator, self.recorder, missing)
        with patch('apps.pmo.rfp_intake_upload.read_file') as read, patch('adapters.case_uploads.put') as store:
            chooser = self.client.get(reverse('factory_intake'))
            self.assertContains(chooser, 'value="received-bid" required disabled')
            self.assertNotIn(rfp_fresh_intake.LINE, {option['definition'] for option in chooser.context['options']})
            self.assertEqual(self.client.get(self.url).status_code, 403)
            for stale_scope in (self.authority, successor):
                with self.assertRaises(PermissionDenied):
                    rfp_fresh_intake.record(self.recorder, stale_scope.pk, self.key, 'SAMPLE-BID', self.received,
                                           'unknown', None, word_file())
            read.assert_not_called()
            store.assert_not_called()
        fresh = provision(self.administrator, self.recorder, delegated_scope())
        with patch('adapters.case_uploads.put') as store:
            bad = self.client.post(self.url, {**self.command, 'authority': fresh.pk,
                'document': SimpleUploadedFile('SAMPLE-bad.docx', b'broken')})
            self.assertContains(bad, 'The file could not be read')
            store.assert_not_called()
        self.assert_no_intake()

    def test_storage_failure_rolls_back_workspace_and_retains_unbound_intent(self):
        with (
            patch('adapters.case_uploads.put', side_effect=OSError('Synthetic failed upload')) as store,
            patch('adapters.case_uploads.discard_unbound') as discard,
        ):
            failure = self.client.post(self.url, {**self.command, 'document': word_file()})
            self.assertContains(failure, 'Private storage is unavailable')
            store.assert_called_once()
            discard.assert_not_called()
        staged = RFPStagedUpload.objects.get(authority=self.authority, actor=self.recorder)
        self.assertEqual(staged.key, store.call_args.args[0])
        self.assertIsNone(staged.upload_id)
        self.assert_no_intake()
        self.assertFalse(Audit.objects.filter(action=rfp_fresh_intake.ACTION).exists())


class FreshBidIntakeConcurrencyTests(TransactionTestCase):
    def test_simultaneous_equal_retries_commit_one_workspace_and_attachment(self):
        _, actor, authority = authorized_operator()
        file = word_file()
        data = file.read()
        start_key, received = uuid4(), timezone.now() - timedelta(minutes=1)
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                return rfp_fresh_intake.record(actor, authority.pk, start_key, 'SAMPLE-CONCURRENT-BID', received,
                    'not_stated', None, SimpleUploadedFile('SAMPLE-bid.docx', data)).pk
            finally:
                close_old_connections()

        with patch('adapters.case_uploads.put') as put, ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(submit)
            second = workers.submit(submit)
            self.assertEqual(first.result(timeout=30), second.result(timeout=30))
            put.assert_called_once()
        self.assertEqual(connection.vendor, 'postgresql')
        for model in (Case, CaseIntake, RFPIntake, CaseUpload):
            self.assertEqual(model.objects.count(), 1, model.__name__)
