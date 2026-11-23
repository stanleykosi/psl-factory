"""A late exact receipt can settle the original minutes work without redispatch."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from apps.core.models import Audit, Evidence
from apps.documents import delivery
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.identity.models import Grant
from apps.workflows import factory_minutes, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_minutes_delayed_receipt_seed as seed


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PSL_MINUTES_DELAYED_RECEIPT_FIXTURE': '1'})
class DelayedMinutesReceiptTests(TransactionTestCase):
    def test_original_receipt_with_authority_and_paused_progress(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        operator = users.create_user('psl-agent-trial')
        fixture = seed.prepare()
        work = FactoryWork.objects.get(pk=fixture['work'])
        job = PublicationJob.objects.get(pk=fixture['job'])
        progress = FactoryProgress.objects.get(work=work)
        path = fixture['path']
        self.assertEqual((work.status, job.status, progress.status), ('waiting_effect', 'unknown', 'paused'))
        self.assertEqual(seed.prepare(), fixture | {'preserved': True})
        with self.assertRaisesMessage(RuntimeError, 'Observe the initial receipt lookup miss'):
            seed.reveal(work.pk)

        reader = users.create_user('late-minutes-read-only')
        Grant.objects.bulk_create([Grant(case=work.case, user=reader, action=action)
                                   for action in ('case.read', 'meeting.read', 'factory.read')])
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(path), 'Look up original receipt')
        command = {'action': 'reconcile', 'revision': work.revision}
        self.assertEqual(self.client.post(path, command).status_code, 403)

        self.client.force_login(operator)
        self.assertContains(self.client.get(path), 'Look up original receipt')
        self.assertRedirects(self.client.post(path, command), path, fetch_redirect_response=False)
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        witness = Evidence.objects.get(case=work.case, kind=seed.WITNESS)
        self.assertEqual(witness.source, fixture['operation'])

        late = seed.reveal(work.pk)
        self.assertEqual(seed.reveal(work.pk), late)
        work.refresh_from_db()
        job.refresh_from_db()
        progress.refresh_from_db()
        self.assertEqual((work.status, job.status, progress.status), ('waiting_effect', 'confirmed', 'paused'))
        self.assertEqual((late['job'], late['publication'], late['version'], late['operation']),
                         (fixture['job'], fixture['publication'], fixture['version'], fixture['operation']))
        receipts = list(PublicationReceipt.objects.filter(publication=job.publication).order_by('pk'))
        self.assertTrue(receipts)
        self.assertEqual([receipt.pk for receipt in receipts], late['receipt_ids'])
        for receipt in receipts:
            self.assertEqual(receipt.operation_key, f"{fixture['operation']}:user:{receipt.recipient_id}")
        recorded = self.client.get(path)
        self.assertContains(recorded, 'Check recorded minutes receipts')
        self.assertNotContains(recorded, 'Continue in background')

        authority = Grant.objects.get(user=operator, case=work.case, action='document.publish')
        Grant.objects.filter(pk=authority.pk).update(active=False)
        command['revision'] = work.revision
        self.assertNotContains(self.client.get(path), 'Check recorded minutes receipts')
        self.assertEqual(self.client.post(path, command).status_code, 403)
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting_effect')
        Grant.objects.filter(pk=authority.pk).update(active=True)

        saved_attempts = (job.fence, job.attempts)
        with patch.object(delivery, 'run_publication_once', side_effect=AssertionError('Original receipt needs no adapter')):
            self.assertRedirects(self.client.post(path, command), path, fetch_redirect_response=False)
            repeated = self.client.post(path, command)
            self.assertContains(repeated, 'Refresh exact original minutes delivery')
        work.refresh_from_db()
        progress.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual((work.status, progress.status, progress.requested_by_id), ('ready', 'paused', operator.pk))
        self.assertEqual((job.fence, job.attempts), saved_attempts)
        check = Audit.objects.get(case=work.case, action='factory.minutes_receipt_checked')
        self.assertEqual(check.data, {'work': work.pk, 'publication_job': job.pk, 'receipts': late['receipt_ids']})

        self.assertContains(self.client.get(path), 'Continue in background')
        self.assertRedirects(self.client.post(path, {'action': 'advance', 'revision': work.revision}), path,
                             fetch_redirect_response=False)
        with patch.object(delivery, 'run_publication_once', side_effect=AssertionError('Confirmed minutes cannot resend')):
            for _ in range(15):
                self.assertEqual(factory_progress.run_once(), progress.pk)
                progress.refresh_from_db()
                if progress.status != 'queued':
                    break
        work.refresh_from_db()
        self.assertEqual((work.status, progress.status), ('verified', 'finished'))
        self.assertEqual(factory_minutes.verify(work, operator)['receipt_ids'], late['receipt_ids'])
        self.assertEqual(Publication.objects.filter(factory_work=work).count(), 1)
        self.assertEqual(Evidence.objects.filter(case=work.case, kind=seed.WITNESS).count(), 1)
