"""An isolated PostgreSQL process can stop after the private write and before commit."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, OperationalError, close_old_connections, connection, transaction
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import CaseUpload
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import rfp_fresh_intake, rfp_intake_upload, rfp_staged_uploads
from apps.pmo.models import RFPIntake, RFPStagedUpload
from tests.helpers import rev, setup_case, worker_test_environment
from tests.test_rfp_fresh_intake import authorized_operator
from tests.test_rfp_intake_upload import PRIVATE_TEXT, word_file


INTERRUPT_AFTER_PUT = '''
import os
import sys
from pathlib import Path
from uuid import UUID
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from unittest.mock import patch
from apps.pmo import rfp_fresh_intake

actor_id, authority_id, request_key, received, document = sys.argv[1:]
assert connection.vendor == 'postgresql' and connection.settings_dict['NAME'].startswith('test_')
actor = get_user_model().objects.get(pk=actor_id)
document = Path(document)

def stop_after_storage(key, data):
    (document.parent / key).write_bytes(data)
    os._exit(47)

with patch('adapters.case_uploads.put', side_effect=stop_after_storage):
    rfp_fresh_intake.record(actor, int(authority_id), UUID(request_key), 'SAMPLE-INTERRUPTED-BID',
        received, 'not_stated', None, SimpleUploadedFile(document.name, document.read_bytes()))
'''


class IsolatedObjects:
    def __init__(self, directory):
        self.directory = directory
        self.has_reply = False

    def get_object(self, *, Bucket, Key):
        if not self.has_reply:
            raise OSError('Synthetic original is not yet observable.')
        return {'Body': BytesIO((self.directory / Key).read_bytes())}


class RFPStagedUploadTests(TransactionTestCase):
    def test_process_exit_after_put_keeps_exact_reservation_and_reuses_verified_private_bytes(self):
        _, actor, authority = authorized_operator()
        started, received = uuid4(), timezone.now() - timedelta(minutes=1)
        data = word_file().read()
        self.client.force_login(actor)
        with TemporaryDirectory(prefix='psl-bid-upload-test-') as temporary:
            directory = Path(temporary)
            document = directory / 'SAMPLE-bid.docx'
            document.write_bytes(data)
            child = subprocess.run([sys.executable, '-c', INTERRUPT_AFTER_PUT, str(actor.pk), str(authority.pk),
                str(started), received.isoformat(), str(document)], env=worker_test_environment(connection),
                capture_output=True, text=True, timeout=60)
            self.assertEqual(child.returncode, 47, child.stderr)
            row = RFPStagedUpload.objects.get(actor=actor, authority=authority)
            self.assertIsNone(row.upload_id)
            self.assertFalse(Case.objects.exists())
            self.assertFalse(CaseUpload.objects.exists())
            self.assertEqual((directory / row.key).read_bytes(), data)
            with transaction.atomic(), self.assertRaises(DatabaseError):
                RFPStagedUpload.objects.filter(pk=row.pk).update(size=row.size + 1)

            def again(reference='SAMPLE-INTERRUPTED-BID'):
                return rfp_fresh_intake.record(actor, authority.pk, started, reference, received, 'not_stated', None,
                    SimpleUploadedFile(document.name, data))

            store = IsolatedObjects(directory)
            with (patch('adapters.case_uploads.bucket', return_value=(store, 'isolated-test')),
                  patch('adapters.case_uploads.put') as put, patch('adapters.case_uploads.discard_unbound') as discard):
                with self.assertRaisesMessage(ValidationError, 'earlier file write could not be confirmed'):
                    again()
                with self.assertRaisesMessage(ValidationError, 'different details'):
                    again('SAMPLE-DIFFERENT-BID')
                self.assertFalse(Case.objects.exists())
                store.has_reply = True
                url = reverse('rfp_staged_uploads') + f'?check={row.pk}'
                page = self.client.get(url)
                self.assertContains(page, 'Original file verified')
                self.assertNotContains(page, row.key)
                self.assertNotContains(page, PRIVATE_TEXT)
                self.assertFalse(Case.objects.exists())
                recovered = again()
                self.assertEqual(again().pk, recovered.pk)
                put.assert_not_called()
                discard.assert_not_called()
            row.refresh_from_db()
            self.assertEqual(row.intake_id, recovered.pk)
            self.assertEqual((row.upload.key, row.upload.sha256, row.upload.size), (row.key, row.sha256, row.size))
            self.assertEqual(RFPIntake.objects.count(), 1)
            self.assertContains(self.client.get(url), 'Attached to the recorded bid')

    def test_lost_commit_ack_retry_returns_the_original_without_storage_calls(self):
        _, actor, authority = authorized_operator()
        started, received = uuid4(), timezone.now() - timedelta(minutes=1)
        data = word_file().read()
        real_commit = connection.commit
        commits = 0

        def commit_then_interrupt():
            nonlocal commits
            real_commit()
            commits += 1
            if commits == 2:
                raise OperationalError('Synthetic lost domain commit acknowledgement.')

        def submit():
            return rfp_fresh_intake.record(actor, authority.pk, started, 'SAMPLE-LOST-ACK-BID', received, 'unknown',
                                           None, SimpleUploadedFile('SAMPLE-bid.docx', data))

        with (patch('adapters.case_uploads.put') as put, patch('adapters.case_uploads.read') as read,
              patch('adapters.case_uploads.discard_unbound') as discard):
            with patch.object(connection, 'commit', side_effect=commit_then_interrupt), self.assertRaises(OperationalError):
                submit()
            row = RFPStagedUpload.objects.get(actor=actor)
            self.assertIsNotNone(row.upload_id)
            self.assertEqual(submit().pk, row.intake_id)
            put.assert_called_once_with(row.key, data)
            read.assert_not_called()
            discard.assert_not_called()

    def test_stale_source_wrong_storage_and_revoked_owner_cannot_probe_the_object(self):
        actor, case = setup_case()
        received = timezone.now() - timedelta(minutes=1)
        with patch('adapters.case_uploads.put', side_effect=OSError('Synthetic failed write')):
            with self.assertRaises(ValidationError):
                rfp_intake_upload.record(actor, case.pk, 'SAMPLE-BID', received, 'unknown', None, None,
                                         'Unconfirmed deadline.', rev(case), word_file())
        row = RFPStagedUpload.objects.get(case=case)
        self.client.force_login(actor)
        url = reverse('rfp_staged_uploads') + f'?check={row.pk}'
        with patch('adapters.case_uploads.read') as read:
            with patch('apps.pmo.rfp_staged_uploads.storage_identity', return_value='0' * 64):
                self.assertContains(self.client.get(url), 'The original private storage or database has changed.')
            add_evidence(actor, case.pk, 'requirements', 'Synthetic successor source.', 'synthetic:successor')
            self.assertContains(self.client.get(url), 'The workspace has changed.')
            Grant.objects.filter(case=case, user=actor, action='document.read').update(active=False)
            self.assertEqual(self.client.get(url).status_code, 404)
            other, _ = setup_case(username='sample-other-bid-recorder')
            self.client.force_login(other)
            self.assertEqual(self.client.get(url).status_code, 404)
            read.assert_not_called()

    def test_owner_read_check_skips_a_live_writer_and_observes_the_committed_binding(self):
        actor, case = setup_case()
        received = timezone.now() - timedelta(minutes=1)
        expected = rev(case)
        writing, finish = Event(), Event()

        def put(key, data):
            writing.set()
            if not finish.wait(timeout=25):
                raise OSError('Timed out waiting for the synthetic probe.')

        def write():
            close_old_connections()
            try:
                return rfp_intake_upload.record(actor, case.pk, 'SAMPLE-LIVE-BID', received, 'unknown', None, None,
                                               'Synthetic evidence.', expected, word_file()).pk
            finally:
                close_old_connections()

        self.client.force_login(actor)
        with (patch('adapters.case_uploads.put', side_effect=put) as storage,
              patch('adapters.case_uploads.read') as read, ThreadPoolExecutor(max_workers=1) as workers):
            pending = workers.submit(write)
            try:
                self.assertTrue(writing.wait(timeout=20))
                row = RFPStagedUpload.objects.get(case=case)
                url = reverse('rfp_staged_uploads') + f'?check={row.pk}'
                self.assertContains(self.client.get(url), 'The original upload is still being recorded.')
                read.assert_not_called()
            finally:
                finish.set()
            intake_id = pending.result(timeout=30)
            self.assertContains(self.client.get(url), 'Attached to the recorded bid')
            row.refresh_from_db()
            self.assertEqual(row.intake_id, intake_id)
            storage.assert_called_once()
            read.assert_not_called()
