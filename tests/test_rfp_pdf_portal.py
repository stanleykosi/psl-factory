"""The scoped manual receipt identifies the same PDF the reviewer approved."""

import json
from datetime import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import reserve_publication, review_version
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_portal
from apps.pmo.models import RFPDocumentBinding, RFPPortalReceipt, RFPSubmission, RFPSubmissionArtifact
from apps.pmo.rfp_outcomes import historical_submission
from apps.workflows import factory, factory_rfp
from tests import railway_rfp_submission_pack_seed as sample
from tests.helpers import rev


class RecordedPortalProofTests(SimpleTestCase):
    def test_original_v1_proof_remains_readable_with_a_saved_companion_pdf(self):
        moment = timezone.now()
        version = SimpleNamespace(pk=10, payload_sha256='a' * 64)
        route = {'destination_ref': 'synthetic:client-portal'}
        data = {'schema': rfp_portal.SCHEMA, 'version': version.pk, 'sha256': version.payload_sha256,
                'destination': route['destination_ref'], 'reference': 'SAMPLE-ORIGINAL',
                'received_at': moment.isoformat()}
        evidence = SimpleNamespace(body=json.dumps(data))
        artifact = SimpleNamespace(sha256='b' * 64)
        with self.assertRaisesMessage(ValidationError, 'PDF fingerprint'):
            rfp_portal.proof(evidence, version, route, artifact=artifact)
        self.assertEqual(rfp_portal.proof(evidence, version, route, artifact=artifact, historical=True),
                         ('SAMPLE-ORIGINAL', moment))


class RFPReviewedPDFPortalTests(TestCase):
    def test_manual_pdf_receipt_binds_exact_approved_artifact_through_verified_outcome(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        maker = users.create_user('sample-pdf-portal-maker')
        reviewer = users.create_user('sample-pdf-portal-reviewer')
        case = Case.objects.create(tenant='test-pdf-portal', kind='project', synthetic=True, title='Sample PDF portal bid')
        work, response, _, _, _ = sample.prepared_bid(maker, reviewer, case)
        Grant.objects.bulk_create([Grant(case=case, user=maker, action=action)
                                   for action in ('rfp.outcome', 'rfp.dispose', 'document.publish')])
        self.client.force_login(maker)
        decision_url = reverse('factory_invoice_decision', args=[work.pk])
        response_url = reverse('factory_work_response', args=[work.pk])

        def command(url, action, **data):
            work.refresh_from_db()
            return self.client.post(url, {'action': action, 'revision': work.revision,
                                          'case_revision': rev(case), **data})

        posted = command(decision_url, 'submission_pack', **{
            'pack-target': response.pk, 'pack-base': 0, 'pack-cover_note': sample.COVER_NOTE,
            'pack-file_extension': 'PDF', 'pack-file_count': 1, 'pack-file_size_rule': 'less_than',
            'pack-file_size_bytes': 20_000_000,
        })
        self.assertEqual(posted.status_code, 302)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        version = factory_rfp.review_document(work)
        self.assertIsNotNone(version, work.finding)
        binding = RFPDocumentBinding.objects.get(version=version)
        artifact = RFPSubmissionArtifact.objects.get(binding=binding)
        self.assertEqual(command(decision_url, 'submission_pack_review', pack=binding.snapshot['submission_pack'],
                                 version=version.pk).status_code, 302)
        self.assertLess(artifact.size, 20_000_000)
        self.assertNotContains(self.client.get(response_url), '<button>Record portal receipt</button>', html=True)
        review = review_version(reviewer, case.pk, version.pk, 'approve', 'Reviewed exact PDF and declarations.', rev(case))
        self.assertContains(self.client.get(response_url), 'Inspect the reviewed PDF fingerprint')
        self.assertContains(self.client.get(response_url), artifact.sha256)
        with self.assertRaisesMessage(ValidationError, 'manual client portal'):
            reserve_publication(maker, case.pk, version.pk, rev(case))

        fields = {'schema': rfp_portal.PDF_SCHEMA, 'version': version.pk, 'sha256': version.payload_sha256,
                  'artifact_sha256': artifact.sha256, 'destination': binding.snapshot['route']['destination_ref'],
                  'reference': 'SAMPLE-PDF-PORTAL-001', 'received_at': timezone.now().isoformat()}
        attestation = 'Checked the PDF receipt recorded by the synthetic portal.'

        def receipt_proof(data, label):
            return add_evidence(maker, case.pk, 'rfp_portal_receipt', json.dumps(data), 'synthetic:' + label)

        wrong = receipt_proof({**fields, 'artifact_sha256': '0' * 64}, 'wrong-pdf')
        missing_digest = fields.copy()
        missing_digest.pop('artifact_sha256')
        legacy = receipt_proof({**missing_digest, 'schema': rfp_portal.SCHEMA}, 'no-pdf-proof')
        self.client.force_login(reviewer)
        self.assertNotContains(self.client.get(response_url), '<button>Record portal receipt</button>', html=True)
        self.assertEqual(command(response_url, 'portal_receipt', target=version.pk, evidence=wrong.pk,
                                 note=attestation).status_code, 403)
        self.client.force_login(maker)
        for proof in (wrong, legacy):
            invalid = command(response_url, 'portal_receipt', target=version.pk, evidence=proof.pk, note=attestation)
            self.assertContains(invalid, 'PDF fingerprint')
            self.assertFalse(RFPSubmission.objects.exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            detached = RFPSubmission.objects.create(response=response, version=version, snapshot=binding.snapshot,
                receipt_ids=[], submitted_at=datetime.fromisoformat(fields['received_at']), late=False, actor=maker)
            RFPPortalReceipt.objects.create(submission=detached, review=review, evidence=legacy,
                                            reference=fields['reference'], note=attestation, actor=maker)
        self.assertFalse(RFPSubmission.objects.exists())

        exact = receipt_proof(fields, 'matching-pdf')
        self.assertEqual(command(response_url, 'portal_receipt', target=version.pk, evidence=exact.pk,
                                 note=attestation).status_code, 302)
        submission = RFPSubmission.objects.get(version=version)
        self.assertEqual(submission.portal_receipt.evidence_id, exact.pk)
        self.assertEqual(submission.portal_receipt.review_id, review.pk)
        self.assertEqual(historical_submission(case, submission), response)
        self.assertEqual(rfp_portal.record(maker, case.pk, version.pk, exact.pk, attestation, rev(case)), submission)
        self.assertEqual(RFPPortalReceipt.objects.count(), 1)
        received = self.client.get(response_url)
        self.assertContains(received, fields['reference'])
        self.assertContains(received, 'Open the PDF named in this receipt')

        award = add_evidence(maker, case.pk, 'rfp_outcome', 'Actual fictional client award for the submitted bid.',
                             'synthetic:portal-pdf-award')
        rfp.outcome(maker, case.pk, submission.pk, 'won', timezone.now(), 'Client', award.pk,
                    'Recorded the exact fictional customer award.', rev(case))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(factory_rfp.verify(work)['portal_receipt'], submission.portal_receipt.pk)
        self.assertEqual(rfp_portal.record(maker, case.pk, version.pk, exact.pk, attestation, rev(case)), submission)
        self.assertFalse(Publication.objects.exists())
