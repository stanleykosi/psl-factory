"""Handover recovery reads the existing delivery and retains human acknowledgements."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from adapters.publications import InternalPublicationAdapter, PublicationTimeoutAfterAccept
from apps.core.models import Audit
from apps.documents import delivery
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.identity.models import Grant
from apps.workflows import factory, factory_handover, factory_progress
from apps.workflows.models import FactoryProgress
from tests.test_factory_handover import ack, ready, setup


class HandoverReceiptRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = setup()
        ready(cls.sample)

    def waiting(self, adapter, *, pause=False):
        self.assertEqual(connection.vendor, 'postgresql')
        sample = self.sample
        work = sample.work
        progress = None
        if pause:
            factory_progress.set_progress(sample.actor, work.pk, work.revision, True)
            progress = factory_progress.set_progress(sample.actor, work.pk, work.revision, False)
        factory.run_until_wait(work.pk, adapter=adapter)
        job = PublicationJob.objects.get(publication__factory_work=work)
        work.refresh_from_db()
        self.assertEqual((work.status, job.status), ('waiting_effect', 'unknown'))
        self.client.force_login(sample.actor)
        return sample, job, progress, reverse('factory_invoice_recovery', args=[work.pk])

    def test_missing_receipt_stays_uncertain_without_a_background_request_or_repeated_send(self):
        class LostBeforeAcceptance(InternalPublicationAdapter):
            sends = 0

            def deliver(self, job_id, fence):
                self.sends += 1
                raise TimeoutError('The synthetic original has no recorded confirmation.')

        adapter = LostBeforeAcceptance()
        sample, job, _, path = self.waiting(adapter)
        self.assertFalse(FactoryProgress.objects.filter(work=sample.work).exists())
        self.assertEqual(adapter.sends, 1)
        page = self.client.get(path)
        self.assertContains(page, 'Reconcile original delivery')
        self.assertNotContains(page, 'Cancel unreceived delivery')
        self.assertNotContains(page, 'Retry original delivery')
        with patch.object(InternalPublicationAdapter, 'deliver', side_effect=AssertionError('Recovery cannot send')):
            self.assertTrue(delivery.run_publication_once(case_id=sample.case.pk, job_id=job.pk))
            self.assertRedirects(self.client.post(path, {'action': 'reconcile', 'revision': sample.work.revision}),
                                 path, fetch_redirect_response=False)
        sample.work.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual((sample.work.status, job.status), ('waiting_effect', 'unknown'))
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        self.assertEqual(Publication.objects.filter(factory_work=sample.work).count(), 1)

    def test_confirmed_original_receipt_acknowledges_same_work_and_keeps_pause_and_human_wait(self):
        class LateReceipt(PublicationTimeoutAfterAccept):
            def lookup(self, publication):
                return None

        sample, job, progress, path = self.waiting(LateReceipt(), pause=True)
        original = PublicationReceipt.objects.get(publication=job.publication)
        self.assertTrue(delivery.run_publication_once(case_id=sample.case.pk, job_id=job.pk, lookup_only=True))
        job.refresh_from_db()
        sample.work.refresh_from_db()
        self.assertEqual((job.status, sample.work.status), ('confirmed', 'waiting_effect'))

        reader = get_user_model().objects.create_user('read-only-handover-recovery')
        Grant.objects.bulk_create([Grant(case=sample.case, user=reader, action=action)
                                   for action in ('case.read', 'delivery.read', 'factory.read')])
        self.client.force_login(reader)
        command = {'action': 'reconcile', 'revision': sample.work.revision}
        self.assertNotContains(self.client.get(path), 'Check recorded handover receipts')
        self.assertEqual(self.client.post(path, command).status_code, 403)

        self.client.force_login(sample.actor)
        page = self.client.get(path)
        self.assertContains(page, 'Check recorded handover receipts')
        self.assertNotContains(page, 'Record your actual receipt or gaps')
        authority = Grant.objects.filter(case=sample.case, user=job.publication.actor, action='document.publish')
        self.assertEqual(authority.update(active=False), 1)
        self.assertNotContains(self.client.get(path), 'Check recorded handover receipts')
        self.assertContains(self.client.post(path, command), 'Handover publisher no longer has current project permissions')
        authority.update(active=True)
        self.assertFalse(sample.d.records.filter(kind='handover').exists())

        same_attempt = (job.fence, job.attempts)
        with patch.object(delivery, 'run_publication_once', side_effect=AssertionError('The receipt already exists')):
            self.assertRedirects(self.client.post(path, command), path, fetch_redirect_response=False)
            self.assertContains(self.client.post(path, command), 'Refresh the exact original handover delivery')
        sample.work.refresh_from_db()
        progress.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual((sample.work.status, progress.status), ('ready', 'paused'))
        self.assertEqual((job.fence, job.attempts), same_attempt)
        self.assertFalse(sample.d.records.filter(kind='handover').exists())
        proof = Audit.objects.get(case=sample.case, action='factory.handover_receipt_checked')
        self.assertEqual(proof.data, {'work': sample.work.pk, 'publication_job': job.pk, 'receipts': [original.pk]})

        ack(sample)
        factory.run_until_wait(sample.work.pk)
        sample.work.refresh_from_db()
        self.assertEqual(sample.work.status, 'verified')
        self.assertEqual(factory_handover.verify(sample.work)['receipt_ids'], [original.pk])
        self.assertEqual(Publication.objects.filter(factory_work=sample.work).count(), 1)
