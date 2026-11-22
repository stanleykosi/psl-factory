from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from adapters.publications import InternalPublicationAdapter, PublicationTimeoutAfterAccept
from apps.core.models import Audit
from apps.documents import delivery
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.identity.models import Grant
from apps.workflows import factory, factory_forecast, factory_forecast_recovery as recovery, factory_progress
from tests.forecast_helpers import review
from tests.helpers import rev
from tests import test_factory_forecast as original


class AcceptedWithDelayedReceipt(PublicationTimeoutAfterAccept):
    def lookup(self, publication):
        # The first adapter cannot see the original receipt after its acceptance.
        return None


class ForecastReceiptRecoveryTests(TestCase):
    def waiting_delivery(self, *, accepted=False, pause=False):
        self.assertEqual(connection.vendor, 'postgresql')
        sample = original.ForecastFactoryTests()
        sample.setUp()
        self.actor, self.case = sample.actor, sample.case
        self.work = sample.start()
        sample.advance()
        review(self.actor, self.case, factory_forecast.calculation(self.work, self.actor))
        self.progress = None
        if pause:
            factory_progress.set_progress(self.actor, self.work.pk, self.work.revision, True)
            self.progress = factory_progress.set_progress(self.actor, self.work.pk, self.work.revision, False)
        adapter = AcceptedWithDelayedReceipt() if accepted else original.PublicationTimeoutBeforeAcceptance()
        factory.run_until_wait(self.work.pk, adapter=adapter)
        self.work.refresh_from_db()
        self.job = PublicationJob.objects.get(publication__factory_work=self.work)
        self.assertEqual((self.work.status, self.job.status), ('waiting_effect', 'unknown'), self.work.finding)
        self.assertEqual(PublicationReceipt.objects.filter(publication=self.job.publication).exists(), accepted)
        self.path = reverse('factory_invoice_recovery', args=[self.work.pk])
        self.client.force_login(self.actor)

    def observation(self, outcome, **fields):
        return {'action': 'reconcile', 'record_observation': '1', 'job': self.job.pk, 'revision': self.work.revision,
                'case_revision': rev(self.case), 'outcome': outcome, **fields}

    def test_human_outcomes_and_private_proof_only_append_observations(self):
        self.waiting_delivery()
        page = self.client.get(self.path)
        self.assertContains(page, 'Record what happened')
        self.assertNotContains(page, 'Retry exact eligible delivery')
        self.assertNotContains(page, 'Cancel original delivery')
        self.assertNotContains(page, 'Recheck prerequisites')
        response = self.client.post(self.path, {'action': 'resume', 'revision': self.work.revision})
        self.assertContains(response, 'Check the original forecast delivery before continuing.')
        self.assertContains(response, 'Reconcile original delivery')
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'waiting_effect')
        self.assertContains(self.client.post(self.path, self.observation('delivered')), 'Choose one proof file')
        self.assertContains(self.client.post(self.path, self.observation('unknown', job=self.job.pk + 1)),
                            'Choose the original uncertain forecast delivery')
        initial_attempts = self.job.attempts
        with patch.object(delivery, 'run_publication_once', side_effect=AssertionError('Observations cannot dispatch')):
            for outcome in ('not_delivered', 'unknown'):
                self.assertRedirects(self.client.post(self.path, self.observation(outcome)), self.path,
                                     fetch_redirect_response=False)
                self.work.refresh_from_db()
            contents = b'Synthetic receipt screenshot text'
            with patch.object(recovery.case_uploads, 'put') as put:
                submission = self.observation('delivered', proof=SimpleUploadedFile('sample-proof.txt', contents))
                self.assertRedirects(self.client.post(self.path, submission), self.path, fetch_redirect_response=False)
                proof = Audit.objects.get(action=recovery.OBSERVED, data__outcome='delivered')
                put.assert_called_once_with(proof.data['proof']['key'], contents)
                self.assertContains(self.client.post(self.path, dict(submission, proof=SimpleUploadedFile('replay.txt', contents))),
                                    'Refresh the original forecast delivery')
                self.assertEqual(put.call_count, 1)
        self.assertEqual(list(recovery.observations(self.work).order_by('pk').values_list('data__outcome', flat=True)),
                         ['not_delivered', 'unknown', 'delivered'])
        proof_path = self.path + f'?observation_proof={proof.pk}'
        with patch.object(recovery.case_uploads, 'read', return_value=contents) as read:
            response = self.client.get(proof_path)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(b''.join(response.streaming_content), contents)
            Grant.objects.filter(case=self.case, user=self.actor, action='evidence.add').update(active=False)
            self.assertEqual(self.client.get(proof_path).status_code, 403)
            self.assertEqual(read.call_count, 1)
        self.work.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.status, self.job.status, self.job.attempts), ('waiting_effect', 'unknown', initial_attempts))
        self.assertFalse(PublicationReceipt.objects.filter(publication=self.job.publication).exists())

    def test_late_native_receipt_preserves_paused_background_request(self):
        self.waiting_delivery(accepted=True, pause=True)
        self.assertTrue(delivery.run_publication_once(job_id=self.job.pk, lookup_only=True))
        self.work.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.status, self.job.status), ('waiting_effect', 'confirmed'))
        self.assertContains(self.client.get(self.path), 'Check recorded forecast receipt')
        attempts = self.job.attempts
        with patch.object(delivery, 'run_publication_once', side_effect=AssertionError('Recorded receipt needs no lookup')):
            response = self.client.post(self.path, {'action': 'reconcile', 'revision': self.work.revision, 'job': self.job.pk})
            self.assertRedirects(response, self.path, fetch_redirect_response=False)
        self.work.refresh_from_db();self.progress.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.status, self.progress.status, self.job.attempts), ('ready', 'paused', attempts))
        receipt = PublicationReceipt.objects.get(publication=self.job.publication)
        self.assertEqual(Audit.objects.get(action='factory.forecast_receipt_checked').data['receipts'], [receipt.pk])
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        self.assertEqual(PublicationJob.objects.filter(publication__factory_work=self.work).count(), 1)

    def test_competing_lease_and_held_result_keep_original_work_waiting(self):
        self.waiting_delivery()
        saved_revision = self.work.revision

        def worker_claim(adapter, *, case_id, job_id, lookup_only):
            self.assertEqual((case_id, job_id, lookup_only), (self.case.pk, self.job.pk, True))
            self.assertIsNotNone(delivery.claim_publication(case_id=case_id, job_id=job_id))
            return False

        with patch.object(delivery, 'run_publication_once', side_effect=worker_claim):
            recovery.reconcile(self.actor, self.work.pk, saved_revision)
        self.work.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.status, self.job.status, self.work.revision), ('waiting_effect', 'leased', saved_revision))
        delivery.finish_publication(self.job.pk, self.job.fence, 'unknown')

        def worker_held(adapter, *, case_id, job_id, lookup_only):
            _, fence = delivery.claim_publication(case_id=case_id, job_id=job_id)
            delivery.finish_publication(job_id, fence, 'held', 'Synthetic competing worker held the operation')
            return True

        with patch.object(delivery, 'run_publication_once', side_effect=worker_held):
            recovery.reconcile(self.actor, self.work.pk, saved_revision)
        self.work.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.status, self.job.status, self.work.revision), ('waiting_effect', 'held', saved_revision))
        self.assertFalse(Audit.objects.filter(action='factory.forecast_receipt_checked').exists())

    def test_confirmed_lookup_does_not_advance_after_controller_revocation(self):
        self.waiting_delivery(accepted=True)

        class RevokeController(InternalPublicationAdapter):
            def lookup(adapter, publication):
                receipt = super().lookup(publication)
                Grant.objects.filter(case=self.case, user=self.actor, action='factory.execute').update(active=False)
                return receipt

            def deliver(adapter, job_id, fence):
                raise AssertionError('Reconciliation cannot transmit a forecast')

        with self.assertRaises(PermissionDenied):
            recovery.reconcile(self.actor, self.work.pk, self.work.revision, RevokeController())
        self.work.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.status, self.job.status), ('waiting_effect', 'confirmed'))
        self.assertFalse(Audit.objects.filter(action='factory.forecast_receipt_checked').exists())
        self.assertEqual(PublicationReceipt.objects.filter(publication=self.job.publication).count(), 1)

    def test_receipt_lookup_does_not_overwrite_newer_stop_instruction(self):
        self.waiting_delivery(accepted=True)
        revision = self.work.revision
        native_lookup = delivery.run_publication_once

        def cancel_after_lookup(adapter, *, case_id, job_id, lookup_only):
            self.assertTrue(native_lookup(adapter, case_id=case_id, job_id=job_id, lookup_only=lookup_only))
            factory_forecast.cancel(self.actor, self.work.pk, revision)
            return True

        with patch.object(delivery, 'run_publication_once', side_effect=cancel_after_lookup):
            recovery.reconcile(self.actor, self.work.pk, revision)
        self.work.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((self.work.cancel_requested, self.work.status, self.job.status), (True, 'followup_needed', 'confirmed'))
        self.assertFalse(Audit.objects.filter(action='factory.forecast_receipt_checked').exists())

    def test_proof_storage_failure_rolls_back_observation_and_cleans_staged_file(self):
        self.waiting_delivery()
        revision = self.work.revision
        with (patch.object(recovery.case_uploads, 'put', side_effect=OSError) as put,
              patch.object(recovery.case_uploads, 'discard_unbound') as discard):
            response = self.client.post(self.path, self.observation('delivered', proof=SimpleUploadedFile('proof.txt', b'test')))
            self.assertContains(response, 'Private proof storage is unavailable')
            discard.assert_called_once_with(put.call_args.args[0])
        self.work.refresh_from_db()
        self.assertEqual(self.work.revision, revision)
        self.assertFalse(recovery.observations(self.work).exists())
