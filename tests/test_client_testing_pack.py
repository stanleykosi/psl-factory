from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.upload_views import upload_file
from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from apps.pmo import client_testing_pack as service
from apps.pmo.models import ClientUATGateBinding, DeliverySource

from .helpers import rev
from .test_client_uat import ClientUATFixture


class ClientTestingPackTests(ClientUATFixture, TestCase):
    def setUp(self):
        self.setup_uat()
        self.pack_file = upload_file(self.actor, self.case, SimpleUploadedFile('sample-testing-pack.txt', b'SAMPLE pack for delivery-build'))
        self.receipt = upload_file(self.actor, self.case, SimpleUploadedFile('sample-delivery-proof.txt', b'SAMPLE original delivery receipt'))

    def pack(self, target):
        return service.record_pack(self.actor, self.case.pk, self.d.pk, rev(self.case), target.pk, uuid4(),
                                   self.pack_file.pk, self.receipt.pk, 'SAMPLE original receipt 24',
                                   timezone.now() - timedelta(hours=1))

    def test_reviewed_receipt_controls_editable_reminder_and_reply_closes_wait(self):
        target = self.target()
        path = reverse('client_uat_pack', args=[self.case.pk, self.d.pk])
        self.client.force_login(self.actor)
        start = timezone.localtime(timezone.now()) - timedelta(hours=1)
        response = self.client.post(path, {'action': 'record', 'revision': rev(self.case), 'target': target.pk, 'key': uuid4(),
                                   'pack_file': self.pack_file.pk, 'receipt_file': self.receipt.pk,
                                   'reference': 'SAMPLE original receipt 24', 'received_at': start.strftime('%Y-%m-%dT%H:%M')})
        self.assertRedirects(response, path, fetch_redirect_response=False)
        pack = service.current_pack(self.actor, self.d, target)
        self.assertContains(self.client.get(path), 'Delivery proof awaiting review')
        self.assertNotContains(self.client.get(path), 'Save response dates')
        self.assertFalse(public_evidence(self.case.evidence.filter(pk=pack.evidence_id)).exists())
        self.rule()

        proof_url = reverse('client_uat_pack_file', args=[self.case.pk, self.d.pk, pack.pk, 'receipt'])
        proof = self.client.get(proof_url)
        self.assertEqual(b''.join(proof.streaming_content), b'SAMPLE original delivery receipt')
        response = self.client.post(path, {'action': 'verify', 'revision': rev(self.case), 'target': target.pk,
                                   'row': pack.pk, 'checked': 'on', 'note': 'Checked the original synthetic channel receipt.'})
        self.assertRedirects(response, path, fetch_redirect_response=False)
        check = service.current_review(pack)
        self.assertContains(self.client.get(path), 'Delivery proof confirmed')
        now = timezone.now()
        first = service.schedule(self.actor, self.case.pk, self.d.pk, rev(self.case), target.pk, pack.pk, None,
                                 uuid4(), now + timedelta(days=3), now + timedelta(days=2), 'Original expected response date')
        second = service.schedule(self.actor, self.case.pk, self.d.pk, rev(self.case), target.pk, pack.pk, first.pk,
                                  uuid4(), now + timedelta(days=3), now + timedelta(days=1), 'Client requested an earlier follow-up')
        self.assertEqual((second.payload['review'], second.payload['previous']), (check.pk, first.pk))
        self.assertContains(self.client.get(path), 'Change reminder')
        with self.assertRaisesMessage(ValidationError, 'response window changed'):
            service.schedule(self.actor, self.case.pk, self.d.pk, rev(self.case), target.pk, pack.pk, first.pk,
                             uuid4(), now + timedelta(days=3), None, 'Older form trying to cancel')
        self.response(target)
        self.assertContains(self.client.get(path), 'The client has replied.')
        self.assertNotContains(self.client.get(path), 'Save response dates')
        self.assertEqual(DeliverySource.objects.filter(pk__in=[first.pk, second.pk]).count(), 2)
        self.assertFalse(ClientUATGateBinding.objects.exists())

    def test_recorder_cannot_review_when_independence_is_configured_and_target_correction_fences_old_pack(self):
        self.rule(independent_review=True)
        target = self.target()
        pack = self.pack(target)
        stranger = get_user_model().objects.create_user('sample-pack-read-only')
        Grant.objects.bulk_create([Grant(case=self.case, user=stranger, action=action) for action in (
            'case.read', 'delivery.read', 'engagement.read')])
        self.client.force_login(stranger)
        url = reverse('client_uat_pack_file', args=[self.case.pk, self.d.pk, pack.pk, 'pack'])
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            service.confirm_pack(self.actor, self.case.pk, self.d.pk, rev(self.case), target.pk, pack.pk, 'Own pack')
        latest = self.target(target)
        self.assertIsNone(service.current_pack(self.actor, self.d, latest))
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code, 404)
        with self.assertRaisesMessage(ValidationError, 'current request'):
            service.confirm_pack(self.actor, self.case.pk, self.d.pk, rev(self.case), target.pk, pack.pk, 'Old target')
        self.assertTrue(DeliverySource.objects.filter(pk=pack.pk).exists())
