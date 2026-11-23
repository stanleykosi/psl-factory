"""The explicit Handover action reserves only its current reviewed package."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from adapters.publications import InternalPublicationAdapter
from apps.documents import delivery
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.workflows import factory, factory_handover
from tests.helpers import rev
from tests.test_factory_handover import ready, setup


class HandoverPublishTests(TestCase):
    def test_exact_publish_queues_one_reservation_and_uncertainty_only_exposes_recovery(self):
        self.assertEqual(connection.vendor, 'postgresql')
        sample = setup(review=True)
        ready(sample)
        work = sample.work
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        version = factory_handover.document(work)
        main = reverse('factory_detail', args=[work.pk])
        recovery = reverse('factory_invoice_recovery', args=[work.pk])
        self.client.force_login(sample.actor)
        rows = Publication.objects.filter(factory_work=work)
        self.assertNotContains(self.client.get(main), 'Publish to Support')

        def command(**changes):
            work.refresh_from_db()
            return {'action': 'publish', 'revision': work.revision, 'case_revision': rev(work.case),
                    'version': version.pk, **changes}

        self.assertContains(self.client.post(main, command()), 'required approval before publishing')
        self.assertFalse(rows.exists())
        review = factory_handover.review(sample.actor, work.pk, work.revision, rev(sample.case), version.pk,
                                         'approve', 'Reviewed the exact fictional internal Support package.')
        page = self.client.get(main)
        self.assertContains(page, 'Publish to Support')
        self.assertNotContains(page, 'Continue eligible work')

        reader = get_user_model().objects.create_user('handover-publish-reader')
        Grant.objects.bulk_create([Grant(case=sample.case, user=reader, action=action)
                                   for action in ('case.read', 'delivery.read', 'factory.read')])
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(main), 'Publish to Support')
        self.assertEqual(self.client.post(main, command()).status_code, 403)
        self.client.force_login(sample.actor)
        for invalid in (command(version=version.pk + 1), command(revision=work.revision - 1),
                        command(case_revision=rev(work.case) - 1)):
            self.assertEqual(self.client.post(main, invalid).status_code, 200)
            self.assertFalse(rows.exists())

        publish = command()
        self.assertRedirects(self.client.post(main, publish), main, fetch_redirect_response=False)
        publication = rows.get()
        self.assertEqual((publication.version_id, publication.actor_id, publication.review_id),
                         (version.pk, sample.publisher.pk, review.pk))
        self.assertEqual(publication.job.status, 'pending')
        self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
        self.assertEqual(self.client.post(main, publish).status_code, 200)

        class UnseenReceipt(InternalPublicationAdapter):
            def deliver(self, job_id, fence):
                raise TimeoutError('Synthetic delivery confirmation is missing.')

        self.assertTrue(delivery.run_publication_once(UnseenReceipt(), case_id=work.case_id,
                                                       job_id=publication.job.pk))
        self.assertNotContains(self.client.get(main), 'Publish to Support')
        self.assertContains(self.client.get(recovery), 'Reconcile original delivery')
        self.assertContains(self.client.post(main, command()), 'Check the original handover delivery')
        with patch.object(InternalPublicationAdapter, 'deliver', side_effect=AssertionError('Recovery cannot send')):
            self.assertRedirects(self.client.post(recovery, {'action': 'reconcile', 'revision': work.revision}),
                                 recovery, fetch_redirect_response=False)
        publication.job.refresh_from_db()
        self.assertEqual(publication.job.status, 'unknown')
        self.assertEqual(rows.count(), 1)
        self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
