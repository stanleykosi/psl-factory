from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from pypdf import PdfReader

from adapters.rfp_pdf import render, verify_pdf
from apps.core.models import Case
from apps.documents.controlled import current_version, reserve_publication, review_version
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_documents, rfp_submission_pack as packs
from apps.pmo.models import RFPDocumentBinding, RFPSubmission, RFPSubmissionArtifact, RFPSubmissionPack
from apps.pmo.rfp_submission_artifacts import materialize, requirement_findings
from apps.policy.services import register_reference
from apps.workflows import factory, factory_rfp
from apps.workflows.models import HumanTask
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
        self.assertFalse(RFPSubmissionArtifact.objects.exists())
        self.assertEqual(current_version(case, legacy.pk), legacy)
        decision_url = reverse('factory_invoice_decision', args=[work.pk])
        api_url = f'/api/v1/work/{work.pk}/bid-pack'

        def command(action, **fields):
            work.refresh_from_db()
            return self.client.post(decision_url, {'action': action, 'revision': work.revision,
                                                  'case_revision': rev(case), **fields})

        self.client.force_login(maker)
        self.assertContains(self.client.get(decision_url), 'Save pack draft')
        declared = {'pack-target': response.pk, 'pack-base': 0, 'pack-file_extension': 'PDF',
                    'pack-file_count': 1, 'pack-file_size_bytes': 100}
        invalid = command('submission_pack', **declared, **{'pack-cover_note': 'Draft note.'})
        self.assertContains(invalid, 'Enter both the stated byte limit')
        self.assertFalse(RFPSubmissionPack.objects.exists())
        first_note = 'Draft note. Quoted cost ₦20.00. Procurement review <final> & evidence.'
        first = command('submission_pack', **declared, **{'pack-file_size_rule': 'less_than',
                                                          'pack-cover_note': first_note})
        self.assertEqual(first.status_code, 302)
        pack = packs.current(response)
        self.assertEqual((pack.number, pack.source_id, pack.actor_id, pack.file_extension,
                          pack.file_count, pack.file_size_bytes, pack.file_size_rule),
                         (1, response.intake.evidence_id, maker.pk, 'pdf', 1, 100, 'less_than'))
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
        artifact = RFPSubmissionArtifact.objects.get(binding=binding)
        self.assertFalse(HumanTask.objects.filter(version=first_version).exists())
        self.assertContains(self.client.get(decision_url), 'Send for review')
        self.assertContains(command('submission_pack_review', pack=pack.pk, version=legacy.pk),
                            'Choose the exact current prepared pack')
        self.assertFalse(HumanTask.objects.filter(version=first_version).exists())
        self.assertEqual(command('submission_pack_review', pack=pack.pk, version=first_version.pk).status_code, 302)
        task = HumanTask.objects.get(version=first_version)
        self.assertEqual((task.status, task.created_by_id), ('open', maker.pk))
        self.assertEqual(command('submission_pack_review', pack=pack.pk, version=first_version.pk).status_code, 302)
        self.assertEqual(HumanTask.objects.get(version=first_version).pk, task.pk)
        self.assertNotContains(self.client.get(decision_url), '<button type="submit">Send for review</button>', html=True)
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(materialize(binding).pk, artifact.pk)
        self.assertEqual(artifact.payload_sha256, first_version.payload_sha256)
        self.assertGreater(artifact.size, 100)
        self.assertEqual(sha256(artifact.content).hexdigest(), artifact.sha256)
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPSubmissionArtifact.objects.filter(pk=artifact.pk).update(size=artifact.size + 1)
        with self.assertRaisesMessage(PermissionDenied, 'different authorised person'):
            review_version(maker, case.pk, first_version.pk, 'approve', 'Maker self-review.', rev(case))

        self.client.force_login(self.reviewer)
        pdf_url = reverse('rfp_submission_pdf', args=[case.pk, first_version.pk])
        file = self.client.get(pdf_url)
        self.assertEqual(file.status_code, 200)
        self.assertEqual(file.headers['Content-Type'], 'application/pdf')
        self.assertIn('no-store', file.headers['Cache-Control'])
        self.assertIn('inline;', file.headers['Content-Disposition'])
        original_pdf = b''.join(file.streaming_content)
        self.assertEqual(original_pdf, bytes(artifact.content))
        original_text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(original_pdf)).pages)
        for phrase in ('₦20.00', 'Procurement review <final> & evidence.', 'Cited coverage'):
            self.assertIn(phrase, original_text.replace('\n', ' '))
        other = Case.objects.create(tenant=case.tenant, kind='project', synthetic=True, title='Sample unrelated bid')
        Grant.objects.bulk_create([Grant(user=self.reviewer, case=other, action=permission)
                                   for permission in ('case.read', 'document.read', 'rfp.read')])
        self.assertEqual(self.client.get(reverse('rfp_submission_pdf', args=[other.pk, first_version.pk])).status_code, 404)
        read_grant = Grant.objects.filter(case=case, user=self.reviewer, action='document.read')
        read_grant.update(active=False)
        self.assertNotContains(self.client.get(decision_url), 'Draft note.')
        self.assertEqual(self.client.get(pdf_url).status_code, 403)
        read_grant.update(active=True)
        page = self.client.get(decision_url)
        for phrase in ['Client submission pack', 'Draft note.', 'Format PDF', 'Under 100 bytes per file',
                       'Final client response review', 'Open the full pack PDF', 'exceeds the requested file size']:
            self.assertContains(page, phrase)
        self.assertNotContains(page, 'Save pack draft')
        self.assertEqual(command('submission_pack_review', pack=pack.pk, version=first_version.pk).status_code, 403)
        with self.assertRaisesMessage(ValidationError, 'exceeds the requested file size'):
            review_version(self.reviewer, case.pk, first_version.pk, 'approve', 'File too large.', rev(case))
        self.assertEqual(command('submission_pack', **declared, **{'pack-file_size_rule': 'less_than',
                                                                  'pack-cover_note': 'Reviewer edit.'}).status_code, 403)
        return_note = 'Revise the cover note before final review.'
        returned = command('document', target=first_version.pk, role='PMO Lead', verdict='return', note=return_note)
        self.assertEqual(returned.status_code, 302)
        returned_page = self.client.get(decision_url)
        self.assertContains(returned_page, 'Returned for changes · Pack draft 1 · Document version 2')
        self.assertContains(returned_page, return_note)
        api = self.client.get(api_url)
        self.assertEqual(api.status_code, 200, api.content[:500])
        self.assertEqual(api.json()['decision']['note'], return_note)
        self.assertEqual(api.json()['document_version_id'], first_version.pk)
        read_grant.update(active=False)
        self.assertNotContains(self.client.get(decision_url), return_note)
        self.assertEqual(self.client.get(api_url).status_code, 403)
        read_grant.update(active=True)
        other_reader = get_user_model().objects.create_user('sample-pack-document-reader')
        Grant.objects.bulk_create(Grant(user=other_reader, case=case, action=action)
                                  for action in ('case.read', 'factory.read', 'rfp.read', 'document.read'))
        self.client.force_login(other_reader)
        other_page = self.client.get(decision_url)
        self.assertContains(other_page, 'Returned for changes · Pack draft 1 · Document version 2')
        self.assertNotContains(other_page, return_note)
        self.assertIsNone(self.client.get(api_url).json()['decision']['note'])
        self.assertFalse(Publication.objects.exists())

        self.client.force_login(maker)
        self.assertContains(self.client.get(decision_url), return_note)
        self.assertContains(self.client.get(reverse('factory_detail', args=[work.pk])), return_note)
        revised = dict(declared, **{'pack-base': pack.pk, 'pack-file_size_rule': 'less_than', 'pack-file_size_bytes': 20_000_000,
                                    'pack-cover_note': 'Revised cover note.'})
        work.refresh_from_db()
        saved = self.client.post(api_url, {'expected_revision': work.revision, 'case_revision': rev(case),
            'response_id': response.pk, 'base_pack_id': pack.pk, 'file_extension': 'PDF', 'file_count': 1,
            'file_size_rule': 'less_than', 'file_size_bytes': 20_000_000, 'cover_note': 'Revised cover note.'},
            content_type='application/json')
        self.assertEqual(saved.status_code, 200, saved.content[:500])
        successor = packs.current(response)
        self.assertEqual(saved.json()['pack_id'], successor.pk)
        self.assertIsNone(self.client.get(api_url).json()['decision'])
        self.assertEqual((successor.number, successor.supersedes_id), (2, pack.pk))
        self.assertEqual(pack.cover_note, first_note)
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
        self.assertNotContains(self.client.get(decision_url), return_note)
        successor_pdf = RFPSubmissionArtifact.objects.get(binding__version=exact)
        self.assertNotEqual(successor_pdf.sha256, artifact.sha256)
        self.assertEqual(requirement_findings(successor, successor_pdf), [])
        self.assertFalse(HumanTask.objects.filter(version=exact).exists())
        self.assertEqual(command('submission_pack_review', pack=successor.pk, version=exact.pk).status_code, 302)
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(decision_url), 'Revised cover note.')
        self.assertContains(self.client.get(decision_url), 'Matches the recorded file requirements.')
        old_file = self.client.get(pdf_url)
        self.assertEqual(b''.join(old_file.streaming_content), original_pdf)
        approved = command('document', target=exact.pk, role='PMO Lead', verdict='approve',
                           note='Reviewed the exact cover note, approved costing and declared file requirements.')
        self.assertEqual(approved.status_code, 302)
        self.assertEqual(exact.reviews.get().actor_id, self.reviewer.pk)
        api_submission = f'/api/v1/work/{work.pk}/bid-submission'
        summary = self.client.get(api_submission)
        self.assertEqual(summary.status_code, 200, summary.content)
        self.assertTrue(summary.json()['approval_recorded'])
        self.assertEqual(summary.json()['file']['sha256'], successor_pdf.sha256)
        download = self.client.get(f'{api_submission}/pdf/{exact.pk}')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), bytes(successor_pdf.content))
        self.client.force_login(maker)
        page = self.client.get(api_submission).json()
        blocked = self.client.post(api_submission, {key: page[key] for key in ('expected_revision', 'case_revision', 'version_id')},
                                   content_type='application/json')
        self.assertNotEqual(blocked.status_code, 202)
        with self.assertRaisesMessage(ValidationError, 'submission route does not carry the verified PDF'):
            reserve_publication(maker, case.pk, exact.pk, rev(case))
        self.assertFalse(Publication.objects.exists())
        self.assertFalse(RFPSubmission.objects.exists())


class RFPSubmissionPdfTests(SimpleTestCase):
    def test_render_exact_readable_text_and_check_the_actual_file_boundary(self):
        text = 'Quoted amount ₦20.00. Scope <needs review> & evidence.'
        payload = {'title': 'Sample client pack', 'sections': [{'heading': 'scope', 'text': text}]}
        data = render(payload)
        verify_pdf(data)
        self.assertEqual(render(payload), data)
        self.assertIn(text, PdfReader(BytesIO(data)).pages[0].extract_text())
        with self.assertRaises(ValidationError):
            verify_pdf(b'%PDF-not-a-valid-file')

        asset = SimpleNamespace(size=len(data))
        pack = SimpleNamespace(file_extension='pdf', file_count=1, file_size_rule='at_most', file_size_bytes=len(data))
        self.assertFalse(requirement_findings(pack, asset))
        pack.file_size_rule = 'less_than'
        self.assertEqual(requirement_findings(pack, asset), ['The PDF exceeds the requested file size limit.'])
        pack.file_size_bytes = None
        pack.file_extension = 'docx'
        pack.file_count = 2
        self.assertEqual(len(requirement_findings(pack, asset)), 2)
