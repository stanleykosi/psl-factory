from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import AgentRun, CaseUpload
from apps.core.services import add_evidence
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import rfp_intake_upload
from apps.pmo.models import RFPAssignment, RFPCase, RFPIntake, RFPSubmission
from tests.helpers import rev, setup_case


PRIVATE_TEXT = 'SAMPLE confidential bid scope'


def word_file(*, package=True):
    content = BytesIO()
    with ZipFile(content, 'w') as archive:
        if package:
            archive.writestr('[Content_Types].xml',
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            archive.writestr('_rels/.rels',
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml',
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body><w:p><w:r><w:t>{PRIVATE_TEXT}</w:t></w:r></w:p></w:body></w:document>')
    return SimpleUploadedFile('SAMPLE-bid.docx', content.getvalue())


def pdf_file():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer, content = PdfWriter(), BytesIO()
    page = writer.add_blank_page(width=500, height=230)
    name = NameObject
    page[name('/Resources')] = DictionaryObject({name('/Font'): DictionaryObject({name('/F1'): DictionaryObject({
        name('/Type'): name('/Font'), name('/Subtype'): name('/Type1'), name('/BaseFont'): name('/Helvetica'),
    })})})
    stream = DecodedStreamObject()
    stream.set_data(f'BT /F1 16 Tf 48 180 Td ({PRIVATE_TEXT}) Tj ET'.encode())
    page[name('/Contents')] = stream
    writer.write(content)
    return SimpleUploadedFile('SAMPLE-bid.pdf', content.getvalue())


class RFPIntakeAttachmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case = setup_case()
        cls.reader = get_user_model().objects.create_user(username='sample-rfp-intake-reader')
        Grant.objects.bulk_create([Grant(case=cls.case, user=cls.reader, action=action)
            for action in ('case.read', 'rfp.read', 'rfp.intake', 'evidence.add')])

    def setUp(self):
        self.client.force_login(self.actor)
        self.url = reverse('rfp', args=[self.case.pk])
        self.received = (timezone.now() - timedelta(minutes=2)).replace(microsecond=0)
        self.command = {'action': 'intake', 'revision': rev(self.case), 'reference': 'SAMPLE-PRIVATE-RFP',
            'received_at': self.received.isoformat(), 'deadline_status': 'unknown',
            'note': 'The supplied bid has no confirmed deadline yet.'}

    def test_word_intake_binds_exact_original_and_protects_source_before_read(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertContains(self.client.get(self.url), 'Attach the bid document')
        file = word_file()
        original = file.read()
        file.seek(0)
        with patch('adapters.case_uploads.put') as put:
            self.assertEqual(self.client.post(self.url, {**self.command, 'rfp_file': file}).status_code, 302)
        intake = RFPCase.objects.get(case=self.case).current_intake
        attachment = rfp_intake_upload.attachment_for(self.actor, self.case, intake)
        put.assert_called_once_with(attachment.key, original)
        self.assertNotIn(PRIVATE_TEXT, intake.evidence.body)
        self.assertIsNone(intake.deadline_at)
        self.assertFalse(RFPAssignment.objects.filter(intake=intake).exists())
        self.assertFalse(RFPSubmission.objects.filter(response__rfp=intake.rfp).exists())
        self.assertFalse(Publication.objects.filter(version__document__case=self.case).exists())
        page = self.client.get(self.url)
        self.assertContains(page, 'Open original bid document')
        self.assertNotContains(page, PRIVATE_TEXT)
        with patch('adapters.case_uploads.read') as read:
            result = self.client.post(self.url, {'action': 'investigate', 'revision': rev(self.case)})
            self.assertEqual(result.status_code, 302)
            read.assert_not_called()
        investigation = AgentRun.objects.get(case=self.case, process_id='P47')
        self.assertEqual(investigation.evidence_id, intake.evidence_id)
        self.assertFalse(investigation.result['submission_dispatched'])
        proof_url = reverse('rfp_intake_attachment', args=[self.case.pk, intake.pk])
        with patch('adapters.case_uploads.read', return_value=original) as read:
            proof = self.client.get(proof_url)
            self.assertEqual(b''.join(proof.streaming_content), original)
            self.assertIn('private', proof['Cache-Control'])
            read.assert_called_once_with(attachment)
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(self.url), 'Open original bid document')
        with patch('adapters.case_uploads.read') as read:
            self.assertEqual(self.client.get(proof_url).status_code, 403)
            read.assert_not_called()
        Grant.objects.create(case=self.case, user=self.reader, action='document.read')
        Grant.objects.filter(case=self.case, user=self.actor, action='evidence.add').update(active=False)
        with patch('adapters.case_uploads.read') as read:
            self.assertEqual(self.client.get(proof_url).status_code, 403)
            read.assert_not_called()

    def test_pdf_retry_returns_current_exact_receipt_and_stale_different_form_cannot_replace_it(self):
        file = pdf_file()
        original = file.read()
        file.seek(0)
        with patch('adapters.case_uploads.put') as put:
            self.assertEqual(self.client.post(self.url, {**self.command, 'rfp_file': file}).status_code, 302)
            duplicate = SimpleUploadedFile('SAMPLE-renamed.pdf', original)
            self.assertEqual(self.client.post(self.url, {**self.command, 'rfp_file': duplicate}).status_code, 302)
            stale = self.client.post(self.url, {**self.command, 'note': 'Different observation.', 'rfp_file': pdf_file()})
            self.assertContains(stale, 'Stale revision')
            put.assert_called_once()
        self.assertEqual(RFPIntake.objects.filter(rfp__case=self.case).count(), 1)
        self.assertEqual(CaseUpload.objects.filter(case=self.case).count(), 1)

    def test_unauthorized_and_invalid_requests_never_reach_storage(self):
        with patch('adapters.case_uploads.put') as put:
            with patch('apps.pmo.rfp_intake_upload.read_file') as read:
                with self.assertRaises(PermissionDenied):
                    rfp_intake_upload.record(self.reader, self.case.pk, self.command['reference'], self.received,
                        'unknown', None, None, self.command['note'], self.command['revision'], word_file())
                read.assert_not_called()
            bad_file = SimpleUploadedFile('SAMPLE-malformed.docx', b'not a Word package')
            invalid = self.client.post(self.url, {**self.command, 'rfp_file': bad_file})
            self.assertContains(invalid, 'could not be read as a Word or PDF document')
            self.assertContains(invalid, self.command['reference'])
            incomplete = self.client.post(self.url, {**self.command, 'rfp_file': word_file(package=False)})
            self.assertContains(incomplete, 'does not match its Word format')
            extra = self.client.post(self.url, {**self.command, 'rfp_file': [word_file(), word_file()]})
            self.assertContains(extra, 'Attach only one bid document')
            put.assert_not_called()
        self.assertFalse(RFPCase.objects.filter(case=self.case).exists())

    def test_failed_storage_discards_unbound_key_and_legacy_source_can_still_be_recorded(self):
        with (patch('adapters.case_uploads.put', side_effect=OSError) as put,
              patch('adapters.case_uploads.discard_unbound') as discard):
            failed = self.client.post(self.url, {**self.command, 'rfp_file': word_file()})
            self.assertContains(failed, 'Private storage is unavailable')
            discard.assert_called_once_with(put.call_args.args[0])
        self.assertFalse(RFPCase.objects.filter(case=self.case).exists())
        self.assertFalse(CaseUpload.objects.filter(case=self.case).exists())
        self.assertFalse(self.case.evidence.filter(source=rfp_intake_upload.SOURCE).exists())
        self.assertEqual(rev(self.case), self.command['revision'])

        source = add_evidence(self.actor, self.case.pk, 'rfp_intake', 'SAMPLE existing bid', 'synthetic:existing-bid')
        command = {**self.command, 'revision': rev(self.case), 'evidence': source.pk}
        with patch('adapters.case_uploads.put') as put:
            ambiguous = self.client.post(self.url, {**command, 'rfp_file': word_file()})
            self.assertContains(ambiguous, 'Choose one existing source or attach one bid document')
            self.assertEqual(self.client.post(self.url, command).status_code, 302)
            put.assert_not_called()
        current = RFPCase.objects.get(case=self.case).current_intake
        self.assertEqual(current.evidence_id, source.pk)
        self.assertIsNone(rfp_intake_upload.attachment_for(self.actor, self.case, current))
