"""Supply private milestone proof through the claimed invoice information request."""

from contextlib import nullcontext
from io import BytesIO
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adapters import case_uploads
from apps.agents.models import CaseUpload
from apps.core.evidence_access import INVOICE_MILESTONE_PROOF as KIND, public_evidence
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance.models import InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_progress
from apps.workflows.factory_invoice_information import SOURCE
from apps.workflows.models import HumanTask, InvoiceMilestoneProof, TaskEvent
from tests.factory_helpers import fixture
from tests.helpers import rev


NOTE = 'SAMPLE client returned a signed test page for this exact milestone.'


def pdf(title):
    from pypdf import PdfWriter

    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({'/Title': title})
    writer.write(output)
    return output.getvalue()


class InvoiceMilestoneProofTests(TestCase):
    def test_private_pdf_and_successor_unlock_only_exact_draft_and_finance_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = fixture(configure=False, required_evidence_kinds=['completion', KIND])
        actor, case, work = data['actor'], data['case'], data['work']
        make_user = get_user_model().objects.create_user
        supplier = make_user('sample-invoice-milestone-evidence-owner')
        reviewer = make_user('sample-invoice-milestone-reviewer')
        ordinary = make_user('sample-invoice-milestone-reader')
        actors = [(supplier, ['factory.information', 'evidence.add']), (reviewer, ['finance.invoice.review']),
                  (ordinary, [])]
        Grant.objects.bulk_create([
            Grant(case=case, user=user, action=action)
            for user, extra in actors for action in ['case.read', 'factory.read', 'finance.read', *extra]
        ])
        rule = draft_operator_policy(actor, case.pk, 'OPS.factory_execution',
            dict(data['value'], information_resolver_id=supplier.pk), data['evidence']['policy_decision'].pk,
            timezone.now())
        finance_role = role_assignments.draft(actor, case.pk, [{'role': 'Finance', 'user_id': reviewer.pk}],
                                             data['evidence']['policy_decision'].pk, timezone.now())
        for configuration in [rule, finance_role]:
            transition(actor, configuration.pk, 'validated')
            transition(actor, configuration.pk, 'active')
        bogus = add_evidence(actor, case.pk, KIND, 'A bare claim cannot satisfy the request.', SOURCE, rev(case))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        task = HumanTask.objects.get(case=case, kind='factory_information', status='open', context__work=work.pk)
        self.assertIsNone(work.invoice_id, work.finding)
        self.assertFalse(public_evidence(case.evidence.filter(pk=bogus.pk)).exists())
        original_completion = data['handoff'].milestone.evidence_id
        progress = factory_progress.set_progress(actor, work.pk, work.revision, True)
        self.assertEqual(factory_progress.run_once(), progress.pk)
        progress.refresh_from_db()
        self.assertEqual(progress.status, 'waiting')
        self.assertGreater(progress.available_at, timezone.now())
        decision = reverse('factory_invoice_decision', args=[work.pk])
        files = reverse('case_uploads', args=[case.pk])
        stored = {}
        storage = Mock()
        storage.put_object.side_effect = lambda **kwargs: stored.update({kwargs['Key']: kwargs['Body']})
        storage.get_object.side_effect = lambda **kwargs: {'Body': BytesIO(stored[kwargs['Key']])}

        def upload(name, contents):
            response = self.client.post(files, {'action': 'upload', 'file': SimpleUploadedFile(name, contents)})
            self.assertRedirects(response, files, fetch_redirect_response=False)
            return CaseUpload.objects.get(case=case, actor=supplier, name=name)

        def payload(file, previous=None):
            task.refresh_from_db()
            return {'action': 'invoice_milestone_proof', 'task': task.pk, 'task_revision': task.revision,
                    'case_revision': rev(case), 'upload': file.pk, 'proof_operation': str(uuid4()),
                    'previous': previous or '', 'proof_note': NOTE}

        self.client.force_login(reviewer)
        self.assertNotContains(self.client.get(decision), 'Supply evidence')
        self.client.force_login(supplier)
        with patch.object(case_uploads, 'storage_client', side_effect=lambda: nullcontext((storage, 'fake-private'))):
            first_bytes, corrected_bytes = pdf('original synthetic sign-off'), pdf('corrected synthetic sign-off')
            original_upload = upload('sample-signoff.pdf', first_bytes)
            corrected_upload = upload('sample-signoff-corrected.pdf', corrected_bytes)
            unclaimed = self.client.post(decision, payload(original_upload))
            self.assertContains(unclaimed, 'current claimed evidence request')
            storage.get_object.assert_not_called()
            claim = {'action': 'claim', 'task': task.pk, 'task_revision': task.revision}
            self.assertRedirects(self.client.post(decision, claim), decision, fetch_redirect_response=False)
            self.assertContains(self.client.get(decision), data['handoff'].milestone.name)
            text = {'action': 'information', 'task': task.pk, 'task_revision': task.revision,
                    'case_revision': rev(case), 'kind': KIND, 'body': 'Signed as text', 'source': 'synthetic:text'}
            self.assertContains(self.client.post(decision, text), 'original private PDF')
            foreign = Case.objects.create(tenant=case.tenant, title='Separate sample', kind='project', synthetic=True)
            wrong_file = CaseUpload.objects.create(case=foreign, actor=supplier, name='outside.pdf',
                key='outside', size=original_upload.size, sha256=original_upload.sha256)
            self.assertContains(self.client.post(decision, payload(wrong_file)), 'original private PDF')
            self.assertFalse(InvoiceMilestoneProof.objects.exists())
            storage.get_object.assert_not_called()

            first_submit = payload(original_upload)
            stored[original_upload.key] = b'different bytes'
            self.assertContains(self.client.post(decision, first_submit), 'File integrity check failed')
            self.assertFalse(InvoiceMilestoneProof.objects.exists())
            stored[original_upload.key] = first_bytes
            for _ in range(2):
                self.assertRedirects(self.client.post(decision, first_submit), decision, fetch_redirect_response=False)
            first = InvoiceMilestoneProof.objects.get(task=task)
            self.assertEqual(first.handoff_id, data['handoff'].pk)
            self.assertEqual(first.upload_id, original_upload.pk)
            self.assertContains(self.client.get(decision), NOTE)
            progress.refresh_from_db()
            self.assertLessEqual(progress.available_at, timezone.now())

            self.assertContains(self.client.post(decision, payload(corrected_upload)), 'exact previous proof')
            self.assertRedirects(self.client.post(decision, payload(corrected_upload, first.pk)), decision,
                                 fetch_redirect_response=False)
            current = InvoiceMilestoneProof.objects.get(work=work, previous=first)
            self.assertEqual(current.upload_id, corrected_upload.pk)
            with self.assertRaises(DatabaseError), transaction.atomic():
                InvoiceMilestoneProof.objects.filter(pk=first.pk).update(note='Rewrite history')
            self.assertEqual(storage.put_object.call_count, 2)

            source_grant = Grant.objects.filter(case=case, user=supplier, action='factory.information')
            source_grant.update(active=False)
            factory.run_until_wait(work.pk)
            work.refresh_from_db()
            self.assertIsNone(work.invoice_id, work.finding)
            source_grant.update(active=True)
            for _ in range(10):
                if factory_progress.run_once() is None:
                    break
                work.refresh_from_db()
                if work.invoice_id and HumanTask.objects.filter(case=case, kind='factory_review', status='open',
                                                                 context__work=work.pk).exists():
                    break
            self.assertIsNotNone(work.invoice_id, work.finding)
            data['handoff'].milestone.refresh_from_db()
            self.assertEqual(data['handoff'].milestone.evidence_id, original_completion)
            readback = TaskEvent.objects.get(task=task, action='factory.information_verified')
            self.assertIn(current.evidence_id, readback.data['evidence_ids'])
            self.assertFalse(InvoiceReview.objects.filter(invoice=work.invoice).exists())
            native = HumanTask.objects.get(case=case, kind='factory_review', status='open', context__work=work.pk)
            self.assertEqual(native.context['packet']['factory_sources']['evidence'][KIND]['id'], current.evidence_id)

            proof_link = reverse('factory_invoice_milestone_proof', args=[work.pk, current.pk])
            self.client.force_login(ordinary)
            self.assertNotContains(self.client.get(decision), NOTE)
            self.assertNotContains(self.client.get(decision), corrected_upload.name)
            self.assertEqual(self.client.get(proof_link).status_code, 404)
            self.client.force_login(reviewer)
            self.assertContains(self.client.get(decision), proof_link)
            result = self.client.get(proof_link)
            self.assertEqual((result.status_code, b''.join(result.streaming_content)), (200, corrected_bytes))
            self.assertIn('attachment', result['Content-Disposition'])
            self.assertEqual(self.client.get(reverse('factory_invoice_milestone_proof',
                                                     args=[work.pk, first.pk])).status_code, 404)
            response = self.client.post(decision, {'action': 'claim', 'task': native.pk, 'task_revision': native.revision})
            self.assertRedirects(response, decision, fetch_redirect_response=False)
            native.refresh_from_db()
            response = self.client.post(decision, {'action': 'decide', 'task': native.pk,
                'task_revision': native.revision, 'verdict': 'approve', 'evidence': data['proof'].pk,
                'reason': 'Reviewed the exact corrected milestone attachment and the invoice amount.'})
            self.assertRedirects(response, decision, fetch_redirect_response=False)
            self.assertEqual(InvoiceReview.objects.get(invoice=work.invoice).actor_id, reviewer.pk)
            self.assertFalse(InvoiceJob.objects.filter(invoice__case=case).exists())
            self.assertFalse(InvoiceIssue.objects.filter(invoice__case=case).exists())
