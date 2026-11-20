from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.documents.models import PublicationReceipt
from apps.identity.models import Grant
from apps.pmo import delivery, delivery_closure
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.models import DeliveryRecord
from tests.helpers import rev
from tests.test_factory_hypercare import setup


class ReleaseEnvironmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = setup(configure=False)

    def test_hypercare_form_records_exact_environment_and_preserves_go_live_receipt(self):
        self.assertEqual(connection.vendor, 'postgresql')
        f = self.sample
        ready = f.ready()
        released_at = timezone.now()
        proof = f.e['completion']
        url = reverse('factory_detail', args=[f.work.pk])
        environment = 'Preview · Synthetic tenant'
        payload = {'action': 'hypercare_observation', 'kind': 'release', 'revision': f.work.revision,
            'case_revision': rev(f.case), 'readiness': ready.pk, 'released_at': released_at.isoformat(),
            'reference': 'SAMPLE-ACTUAL-RELEASE-LOG', 'evidence': proof.pk, 'note': 'Exact sample observation'}
        reader = get_user_model().objects.create_user(username='release-evidence-reader')
        Grant.objects.bulk_create([Grant(case=f.case, user=reader, action=action)
            for action in ('case.read', 'delivery.read', 'factory.read')])
        self.client.force_login(reader)
        self.assertNotContains(self.client.get(url), 'name="deployment_environment"')
        self.assertEqual(self.client.post(url, dict(payload, deployment_environment=environment)).status_code, 403)

        self.client.force_login(f.actor)
        self.assertContains(self.client.get(url), 'name="deployment_environment"')
        for invalid in ('x' * 161, 'Two\nlines'):
            response = self.client.post(url, dict(payload, deployment_environment=invalid))
            self.assertContains(response, 'Enter a release environment in plain text, up to 160 characters.')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d, kind='release_outcome').exists())
        self.assertRedirects(self.client.post(url, dict(payload, deployment_environment=f' {environment} ')), url)
        release = delivery.valid_release(f.d)
        self.assertEqual(release.data['deployment_environment'], environment)
        self.assertEqual(release.evidence_id, proof.pk)
        self.assertEqual(release.parent_id, ready.pk)
        self.assertFalse(release.snapshot['deployment_dispatched'])

        self.client.force_login(reader)
        page = self.client.get(url)
        for value in (f.candidate.reference, environment, payload['reference'], f'Evidence {proof.pk} · version {proof.version}'):
            self.assertContains(page, value)
        self.assertEqual(page.context['row']['hypercare']['release_observation']['released_at'], released_at)
        self.assertNotContains(page, 'Record actual release evidence')

        inputs = {key: f.evidence(kind).pk for key, kind in [('checklist', 'deployment_checklist'),
            ('incident_reporting', 'incident_reporting'), ('rollback', 'rollback_plan')]}
        version = draft_delivery_document(f.actor, f.case.pk, f.d.pk, 'go_live', f.t.pk, inputs, rev(f.case))
        receipt = f.publish(version)
        pm = f.evidence('signature', 'Exact sample PM signature')
        client = f.evidence('signature', 'Exact sample Client signature')
        outcome = delivery_closure.accept_go_live(f.actor, f.case.pk, f.d.pk, receipt.pk, pm.pk, client.pk,
            'Exact signatures for the published report', rev(f.case), attestation=f.attestation(receipt, pm, client))
        self.assertEqual(delivery_closure.accepted_go_live(f.d).pk, outcome.pk)
        self.assertEqual(PublicationReceipt.objects.get(publication__version=version).pk, receipt.pk)

    def test_native_entry_unchanged_for_historical_absence_and_bounded_readback(self):
        f = self.sample
        url = reverse('delivery', args=[f.case.pk])
        self.client.force_login(f.actor)
        self.assertContains(self.client.get(url), 'name="deployment_environment"')
        self.assertRedirects(self.client.post(url, {'action': 'release', 'revision': rev(f.case), 'dossier': f.d.pk,
            'released_at': timezone.now().isoformat(), 'external_ref': 'SAMPLE-HISTORICAL-RELEASE',
            'evidence': f.e['completion'].pk, 'note': 'Legacy entry without a reported environment'}), url)
        release = DeliveryRecord.objects.get(dossier=f.d, kind='release_outcome')
        self.assertNotIn('deployment_environment', release.data)
        self.assertFalse(release.snapshot['readiness_preceded'])
        with CaptureQueriesContext(connection) as captured:
            facts = delivery.release_observations(f.case, [f.d.pk])
        self.assertEqual(len(captured), 1)
        self.assertIsNone(facts[f.d.pk]['environment'])
        self.assertContains(self.client.get(url), '<dd>Not recorded</dd>', html=True)
        self.assertContains(self.client.get(reverse('factory_detail', args=[f.work.pk])), '<dd>Not recorded</dd>', html=True)

    def test_protected_release_proof_keeps_environment_and_reference_out_of_both_views(self):
        f = self.sample
        proof = f.evidence('approval_source', 'Restricted exact source')
        marker = 'Protected deployment marker'
        release = delivery.capture_release(f.actor, f.case.pk, f.d.pk, None, timezone.now(), marker, proof.pk,
            'Native protected release', rev(f.case), deployment_environment=marker)
        self.assertEqual(release.data['deployment_environment'], marker)
        self.assertEqual(delivery.release_observations(f.case, [f.d.pk]), {})
        self.client.force_login(f.actor)
        for route, key in [('delivery', f.case.pk), ('factory_detail', f.work.pk)]:
            self.assertNotContains(self.client.get(reverse(route, args=[key])), marker)
