from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse

from apps.documents.controlled import current_version, reserve_publication, review_version
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_documents, rfp_submission_pack as packs
from apps.pmo.models import RFPDocumentBinding, RFPSubmission, RFPSubmissionPack
from apps.policy.services import register_reference
from apps.workflows import factory, factory_rfp
from tests import factory_rfp_helpers as fixture
from tests.helpers import activate, rev


class RFPSubmissionPackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = fixture.configured(reference='SYNTHETIC-PACK')
        maker, case, proof = (cls.data['actor'], cls.data['case'], cls.data['evidence']['policy_decision'])
        cls.reviewer = get_user_model().objects.create_user(username='sample-pack-reviewer')
        Grant.objects.bulk_create([
            Grant(case=case, user=cls.reviewer, action=action)
            for action in ('case.read', 'factory.read', 'rfp.read', 'rfp.review',
                           'document.read', 'document.review_controlled')
        ])
        roles = {'PM': maker, 'Head of PMO': maker, 'CEO': maker, 'Client': maker,
                 'Engineering Lead': maker, 'PMO Lead': cls.reviewer}
        refs = [register_reference(maker, case.pk, 'pack:' + role, 'schema:psl/role-assignment/v1',
                                   {'role': role, 'user_id': user.pk}, proof.pk).ref
                for role, user in roles.items()]
        activate(maker, case, 'D05.role_principal_assignments', refs, proof)
        rfp.assign(maker, case.pk, maker, 'CEO', proof.pk, 'Reaffirm the synthetic response assignment.', rev(case))

    def test_pack_draft_return_and_exact_review_preserve_legacy_snapshot(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = self.data
        maker, case, proof = data['actor'], data['case'], data['evidence']['policy_decision']
        work = fixture.start(data)
        factory.run_until_wait(work.pk)
        response = factory_rfp.response_for(work)
        self.assertIsNotNone(response, work.finding)
        for role, actor in [('Engineering Lead', maker), ('PMO Lead', self.reviewer)]:
            rfp.review(actor, case.pk, response.pk, role, 'approve', proof.pk, 'Reviewed exact response.', rev(case))
        fixture.costing_review(data, response)

        legacy = rfp_documents.draft(maker, case.pk, response.pk, data['template'].pk,
                                    data['route']['key'], rev(case))
        original = RFPDocumentBinding.objects.get(version=legacy).snapshot
        self.assertNotIn('submission_pack', original)
        self.assertEqual(current_version(case, legacy.pk), legacy)
        decision_url = reverse('factory_invoice_decision', args=[work.pk])

        def command(action, **fields):
            work.refresh_from_db()
            return self.client.post(decision_url, {'action': action, 'revision': work.revision,
                                                  'case_revision': rev(case), **fields})

        self.client.force_login(maker)
        self.assertContains(self.client.get(decision_url), 'Save pack draft')
        declared = {'pack-target': response.pk, 'pack-base': 0, 'pack-file_extension': 'PDF',
                    'pack-file_count': 1, 'pack-file_size_bytes': 20_000_000}
        invalid = command('submission_pack', **declared, **{'pack-cover_note': 'Draft note.'})
        self.assertContains(invalid, 'Enter both the stated byte limit')
        self.assertFalse(RFPSubmissionPack.objects.exists())
        first = command('submission_pack', **declared, **{'pack-file_size_rule': 'less_than',
                                                          'pack-cover_note': 'Draft note.'})
        self.assertEqual(first.status_code, 302)
        pack = packs.current(response)
        self.assertEqual((pack.number, pack.source_id, pack.actor_id, pack.file_extension,
                          pack.file_count, pack.file_size_bytes, pack.file_size_rule),
                         (1, response.intake.evidence_id, maker.pk, 'pdf', 1, 20_000_000, 'less_than'))
        self.assertEqual(RFPDocumentBinding.objects.get(version=legacy).snapshot, original)
        with self.assertRaisesMessage(ValidationError, 'draft and review a new exact response'):
            current_version(case, legacy.pk)

        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        first_version = factory_rfp.review_document(work)
        self.assertIsNotNone(first_version, work.finding)
        binding = RFPDocumentBinding.objects.get(version=first_version)
        self.assertEqual((first_version.document_id, first_version.number), (legacy.document_id, 2))
        self.assertEqual(binding.snapshot['submission_pack'], pack.pk)
        self.assertEqual(binding.snapshot['costing_decisions'], original['costing_decisions'])
        self.assertEqual(binding.snapshot['reviews'], original['reviews'])
        with self.assertRaisesMessage(PermissionDenied, 'different authorised person'):
            review_version(maker, case.pk, first_version.pk, 'approve', 'Maker self-review.', rev(case))

        self.client.force_login(self.reviewer)
        read_grant = Grant.objects.filter(case=case, user=self.reviewer, action='document.read')
        read_grant.update(active=False)
        self.assertNotContains(self.client.get(decision_url), 'Draft note.')
        read_grant.update(active=True)
        page = self.client.get(decision_url)
        for phrase in ['Client submission pack', 'Draft note.', 'Format PDF', 'Under 20,000,000 bytes per file',
                       'Final client response review']:
            self.assertContains(page, phrase)
        self.assertNotContains(page, 'Save pack draft')
        self.assertEqual(command('submission_pack', **declared, **{'pack-file_size_rule': 'less_than',
                                                                  'pack-cover_note': 'Reviewer edit.'}).status_code, 403)
        returned = command('document', target=first_version.pk, role='PMO Lead', verdict='return',
                           note='Revise the cover note before final review.')
        self.assertEqual(returned.status_code, 302)

        self.client.force_login(maker)
        revised = dict(declared, **{'pack-base': pack.pk, 'pack-file_size_rule': 'less_than',
                                    'pack-cover_note': 'Revised cover note.'})
        self.assertEqual(command('submission_pack', **revised).status_code, 302)
        successor = packs.current(response)
        self.assertEqual((successor.number, successor.supersedes_id), (2, pack.pk))
        self.assertEqual(pack.cover_note, 'Draft note.')
        self.assertContains(command('submission_pack', **revised), 'pack changed')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPSubmissionPack.objects.filter(pk=pack.pk).update(cover_note='A rewritten original')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPSubmissionPack.objects.create(response=response, number=3, supersedes=successor,
                                             source=proof, actor=maker)

        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        exact = factory_rfp.review_document(work)
        self.assertIsNotNone(exact, work.finding)
        self.assertEqual((exact.document_id, exact.number), (legacy.document_id, 3))
        self.assertNotEqual(exact.payload_sha256, first_version.payload_sha256)
        self.assertEqual(first_version.reviews.get().verdict, 'return')
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(decision_url), 'Revised cover note.')
        approved = command('document', target=exact.pk, role='PMO Lead', verdict='approve',
                           note='Reviewed the exact cover note, approved costing and declared file requirements.')
        self.assertEqual(approved.status_code, 302)
        self.assertEqual(exact.reviews.get().actor_id, self.reviewer.pk)
        with self.assertRaisesMessage(ValidationError, 'Verify that the client files'):
            reserve_publication(maker, case.pk, exact.pk, rev(case))
        self.assertFalse(Publication.objects.exists())
        self.assertFalse(RFPSubmission.objects.exists())
