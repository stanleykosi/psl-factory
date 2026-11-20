"""An initially missing receipt arrives on one original synthetic handover."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Audit
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.pmo.models import DeliveryRecord
from apps.workflows import factory_handover
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_handover_delayed_receipt_seed as seed
from tests.helpers import rev


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PSL_HANDOVER_DELAYED_RECEIPT_FIXTURE': '1'})
class HandoverDelayedReceiptSeedTests(TestCase):
    def test_lookup_miss_late_original_receipt_and_separate_support_reply(self):
        self.assertEqual(connection.vendor, 'postgresql')
        actor = get_user_model().objects.create_user('psl-agent-trial')
        sample = seed.prepare()
        work = FactoryWork.objects.get(pk=sample['work'])
        job = PublicationJob.objects.get(pk=sample['job'])
        recovery = sample['recovery_path']
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        with self.assertRaisesMessage(RuntimeError, 'Observe the first lookup miss'):
            seed.reveal(work.pk)

        self.client.force_login(actor)
        self.assertContains(self.client.get(recovery), 'Reconcile original delivery')
        self.assertRedirects(self.client.post(recovery, {'action': 'reconcile', 'revision': work.revision}),
                             recovery, fetch_redirect_response=False)
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        revealed = seed.reveal(work.pk)
        self.assertEqual(seed.reveal(work.pk), revealed)
        self.assertEqual((revealed['job'], revealed['version'], revealed['operation']),
                         (sample['job'], sample['version'], sample['operation']))
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting_effect')
        self.assertContains(self.client.get(recovery), 'Check recorded handover receipts')
        self.assertRedirects(self.client.post(recovery, {'action': 'reconcile', 'revision': work.revision}),
                             recovery, fetch_redirect_response=False)
        self.assertFalse(DeliveryRecord.objects.filter(dossier_id=work.request['dossier'], kind='handover').exists())

        work.refresh_from_db()
        receipt, = revealed['receipts']
        main = sample['work_path']
        self.assertContains(self.client.get(main), 'Record Support’s reply')
        reply = {'action': 'record_support_reply', 'revision': work.revision, 'case_revision': rev(work.case),
                 'receipt': receipt, 'status': 'received', 'predecessor': 0, 'role': 'PM', 'channel': 'email',
                 'responded_at': timezone.now().isoformat(), 'party': 'Sample Support lead', 'evidence': sample['proof'],
                 'note': 'The exact fictional package was received without gaps.'}
        self.assertRedirects(self.client.post(main, reply), main, fetch_redirect_response=False)
        work.refresh_from_db()
        self.assertRedirects(self.client.post(recovery, {'action': 'advance', 'revision': work.revision}),
                             recovery, fetch_redirect_response=False)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(factory_handover.verify(work, actor)['receipt_ids'], [receipt])
        self.assertEqual(Publication.objects.filter(factory_work=work).count(), 1)
        self.assertEqual(Audit.objects.filter(case=work.case, action=seed.WITNESS).count(), 1)
        self.assertEqual(seed.prepare(), sample | {'preserved': True})
