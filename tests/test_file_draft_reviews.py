import hashlib
import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.file_draft_reviews import draft_digest
from apps.agents.models import AgentJob, FileDraftReview
from apps.agents.upload_jobs import ROLES, run_once
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import gates, planning
from tests.helpers import rev, setup_case


class FileDraftReviewTests(TestCase):
    def setUp(self):
        self.actor, self.case = setup_case()
        self.client.force_login(self.actor)
        self.url = reverse('case_uploads', args=[self.case.pk])
        self.source = b'Synthetic work was observed.\nIndependent verification is pending.'
        self.fixture_output = {'summary': 'Original model summary', 'quotes': ['1'], 'gaps': ['Original question']}

    def queue(self, roles):
        with patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic/model', 'OPENROUTER_API_KEY': 'fake'}), \
             patch('adapters.case_uploads.put') as store, patch('adapters.case_uploads.read', return_value=self.source), \
             patch('adapters.openrouter.review', side_effect=lambda *_: self.fixture_output.copy()):
            response = self.client.post(self.url, {'action': 'upload',
                'file': SimpleUploadedFile('review.txt', self.source)})
            self.assertEqual(response.status_code, 302)
            store.assert_called_once()
            upload = self.case.caseupload_set.get()
            self.assertEqual(upload.sha256, hashlib.sha256(self.source).hexdigest())
            for role in roles:
                self.assertEqual(self.client.post(self.url, {'action': 'queue', 'upload': upload.pk, 'role': role}).status_code, 302)
                self.assertTrue(run_once())
        return {job.role: job for job in AgentJob.objects.filter(upload=upload)}

    def review(self, job, **overrides):
        fields = {'action': 'review', 'job': job.pk, 'draft': draft_digest(job), 'summary': 'Human-corrected summary',
                  'gaps': 'Confirm the responsible owner', 'quotes': 'Forged excerpt', 'note': 'Checked the source'}
        return self.client.post(self.url, {**fields, **overrides})

    def test_all_specialists_consume_human_edits_with_original_excerpts_and_one_receipt(self):
        jobs = self.queue(ROLES)
        source = add_evidence(self.actor, self.case.pk, 'requirements', 'Synthetic release requirements', 'synthetic:release')
        candidate = gates.register_candidate(self.actor, self.case.pk, 'CHECK-1', source.pk, rev(self.case))
        self.assertContains(self.client.get(self.url), 'Original model summary')
        self.assertContains(self.review(jobs['A01'], draft='0' * 64), 'This draft changed')
        self.assertFalse(FileDraftReview.objects.exists())
        handoff = {'action': 'handoff', 'confirm': 'on', 'title': 'Investigate synthetic issue', 'owner': self.actor.pk,
                   'next_action': 'Check the record', 'start': '2020-01-01', 'end': '2020-01-31',
                   'occurred_at': timezone.now().isoformat(), 'purpose': 'Review trial', 'candidate': candidate.pk,
                   'gate': next(iter(gates.GATE_OWNERS)), 'external_ref': 'synthetic:gate'}
        for role, job in jobs.items():
            with self.subTest(role=role):
                self.assertEqual(self.review(job).status_code, 302)
                job.refresh_from_db()
                review = FileDraftReview.objects.get(job=job)
                self.assertEqual(review.draft_sha256, draft_digest(job))
                self.assertEqual(job.result['summary'], self.fixture_output['summary'])
                self.assertIn('Human-corrected summary', review.evidence.body)
                self.assertIn('Synthetic work was observed.', review.evidence.body)
                self.assertNotIn('Forged excerpt', review.evidence.body)
                response = self.client.post(self.url, {**handoff, 'job': job.pk})
                self.assertEqual(response.status_code, 302, response.context and response.context['error'])
                job.refresh_from_db()
                record = job.result['workflow_record']
                self.assertEqual(self.client.post(self.url, {**handoff, 'job': job.pk}).status_code, 302)
                job.refresh_from_db()
                self.assertEqual(job.result['workflow_record'], record)
        _, packet = planning.packet(self.case, jobs['A04'].result['workflow_record'])
        self.assertEqual(packet['payload']['questions'][0]['detail'], 'Confirm the responsible owner')
        self.assertContains(self.client.get(self.url), 'Human-corrected summary')

    def test_legacy_acceptance_preserves_model_output_and_revocation_blocks_review(self):
        job = self.queue(['A02'])['A02']
        grant = Grant.objects.get(case=self.case, user=self.actor, action='document.review')
        grant.active = False
        grant.save(update_fields=['active'])
        self.assertNotContains(self.client.get(self.url), 'Save as reviewed case evidence')
        self.assertEqual(self.review(job).status_code, 403)
        self.assertFalse(FileDraftReview.objects.exists())
        grant.active = True
        grant.save(update_fields=['active'])
        self.assertEqual(self.client.post(self.url, {'action': 'review', 'job': job.pk, 'note': 'Checked the source'}).status_code, 302)
        self.assertEqual(FileDraftReview.objects.get(job=job).summary, self.fixture_output['summary'])
