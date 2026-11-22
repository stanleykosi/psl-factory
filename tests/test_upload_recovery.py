import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents import file_draft_reviews, upload_jobs, upload_recovery
from apps.agents.models import AgentJob, CaseUpload
from apps.agents.upload_views import queue_draft
from apps.core.models import Audit
from apps.identity.models import Grant
from tests.helpers import setup_case


class UploadRecoveryFixture:
    def setup_recovery(self):
        self.actor, self.case = setup_case(username='sample-file-review-owner')
        self.source = b'SAMPLE source with an observed result.\nIndependent approval is missing.'
        self.upload = CaseUpload.objects.create(case=self.case, actor=self.actor, name='SAMPLE-proof.txt',
            key='sample-upload-recovery', sha256=hashlib.sha256(self.source).hexdigest(), size=len(self.source))
        self.url = reverse('case_uploads', args=[self.case.pk])
        self.environment = patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic/model', 'OPENROUTER_API_KEY': 'fake'})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def values(self, job):
        return {'attempt_pin': upload_recovery.pin(job), 'reason': 'SAMPLE source checked; another review is needed.',
                'confirm': 'on'}

    def output(self):
        return {'summary': 'SAMPLE observed result; approval still missing.', 'quotes': ['1'], 'gaps': ['Approval is missing.']}

    def draft_result(self):
        return {**self.output(), 'quotes': [self.source.decode().splitlines()[0]],
                'model': 'synthetic/model', 'source_sha256': self.upload.sha256}


class UploadRecoveryTests(UploadRecoveryFixture, TestCase):
    def setUp(self):
        self.setup_recovery()
        self.client.force_login(self.actor)

    def test_all_eight_retry_stopped_attempts_then_retain_human_review_without_repeating_it(self):
        with patch('adapters.case_uploads.read', return_value=self.source), \
             patch('adapters.openrouter.review', side_effect=TimeoutError):
            for role in upload_jobs.ROLES:
                job = queue_draft(self.actor, self.upload, role)
                self.assertTrue(upload_jobs.run_once())
                job.refresh_from_db()
                self.assertEqual(job.status, 'held')
                self.assertEqual(job.attempt, 1)
                self.assertEqual(job.settled_token, job.claim_token)
                with self.assertRaises(ValidationError):
                    queue_draft(self.actor, self.upload, role)
        for job in AgentJob.objects.order_by('pk'):
            stopped_claim = job.claim_token
            upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
            with patch('adapters.case_uploads.read', return_value=self.source), \
                 patch('adapters.openrouter.review', side_effect=lambda *_: self.output()) as provider:
                self.assertTrue(upload_jobs.run_once())
                provider.assert_called_once()
            job.refresh_from_db()
            self.assertEqual(job.status, 'draft')
            self.assertEqual(job.attempt, 2)
            self.assertNotEqual(job.claim_token, stopped_claim)
            self.assertEqual(job.result['source_sha256'], self.upload.sha256)
            file_draft_reviews.retain(self.actor, self.case, job.pk, {'note': 'SAMPLE checked the exact source.'})
            job.refresh_from_db()
            evidence = job.file_review.evidence_id
            with self.assertRaises(ValidationError):
                upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
            self.assertEqual(queue_draft(self.actor, self.upload, job.role).pk, job.pk)
            self.assertEqual(job.file_review.evidence_id, evidence)
        self.assertEqual(Audit.objects.filter(case=self.case, action='file_agent.recovery_requested').count(), 8)
        self.assertEqual(Audit.objects.filter(case=self.case, action='file_agent.claimed').count(), 16)

    def test_recovery_requires_current_owner_reason_acknowledgement_and_exact_attempt_in_ui(self):
        job = queue_draft(self.actor, self.upload, 'A07')
        claim = upload_jobs.claim_next()
        upload_jobs.finish(claim, failure='provider_unavailable')
        job.refresh_from_db()
        response = self.client.get(self.url)
        self.assertContains(response, 'File review needs attention')
        self.assertContains(response, 'may have been processed')
        self.assertEqual(response['Cache-Control'], 'no-store')
        for invalid in [{'reason': ''}, {'confirm': ''}, {'attempt_pin': '0' * 64}]:
            response = self.client.post(self.url, {'action': 'retry', 'job': job.pk, **self.values(job), **invalid})
            self.assertEqual(response.status_code, 200)
            job.refresh_from_db()
            self.assertEqual(job.status, 'held')
        other = get_user_model().objects.create_user(username='another-sample-reader')
        for action in ['case.read', 'agent.extract']:
            Grant.objects.create(user=other, case=self.case, action=action)
        with self.assertRaises(ValidationError):
            upload_recovery.retry(other, self.case, job.pk, self.values(job))
        Grant.objects.filter(user=self.actor, case=self.case, action='agent.extract').update(active=False)
        with self.assertRaises(PermissionDenied):
            upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
        self.assertNotContains(self.client.get(self.url), 'Try this file review again')

    def test_expired_legacy_attempt_recovers_without_claiming_a_provider_receipt_or_rewriting_results(self):
        old = {'summary': 'Retained older unaccepted result'}
        job = AgentJob.objects.create(upload=self.upload, actor=self.actor, role='A04', status='running',
            started_at=timezone.now() - timedelta(minutes=11), result=old)
        self.assertTrue(upload_recovery.available(job))
        queued = upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
        self.assertEqual(queued.status, 'queued')
        self.assertEqual(queued.result, old)
        audit = Audit.objects.get(action='file_agent.recovery_requested', case=self.case)
        self.assertEqual(audit.data['provider_result'], 'unknown')
        self.assertNotContains(self.client.get(self.url), old['summary'])
        with self.assertRaises(ValidationError):
            upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))

    def test_source_permissions_are_rechecked_before_model_dispatch_and_before_completion(self):
        job = queue_draft(self.actor, self.upload, 'A02')
        def revoke_before_dispatch(*_):
            Grant.objects.filter(user=self.actor, case=self.case, action='agent.extract').update(active=False)
            return self.source
        with patch('adapters.case_uploads.read', side_effect=revoke_before_dispatch), \
             patch('adapters.openrouter.review') as provider:
            self.assertTrue(upload_jobs.run_once())
            provider.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, 'held')
        self.assertEqual(job.result, {})
        Grant.objects.filter(user=self.actor, case=self.case, action='agent.extract').update(active=True)
        upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
        def deactivate_after_response(*_):
            get_user_model().objects.filter(pk=self.actor.pk).update(is_active=False)
            return self.output()
        with patch('adapters.case_uploads.read', return_value=self.source), \
             patch('adapters.openrouter.review', side_effect=deactivate_after_response):
            self.assertTrue(upload_jobs.run_once())
        job.refresh_from_db()
        self.assertEqual(job.status, 'held')
        self.assertEqual(job.result, {})
        self.assertTrue(self.actor.is_active)  # stale Python principal must not authorize recovery
        with self.assertRaises(PermissionDenied):
            upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))

    def test_sql_fences_legacy_status_only_completion_and_reviewed_reset(self):
        job = queue_draft(self.actor, self.upload, 'A08')
        claim = upload_jobs.claim_next()
        for status in ['draft', 'held', 'interrupted']:
            with self.assertRaises(DatabaseError), transaction.atomic():
                AgentJob.objects.filter(pk=job.pk).update(status=status)
        self.assertTrue(upload_jobs.finish(claim, self.draft_result()))
        file_draft_reviews.retain(self.actor, self.case, job.pk, {'note': 'SAMPLE proof checked.'})
        with self.assertRaises(DatabaseError), transaction.atomic():
            AgentJob.objects.filter(pk=job.pk).update(status='queued')
        with self.assertRaises(DatabaseError), transaction.atomic():
            AgentJob.objects.filter(pk=job.pk).update(actor=get_user_model().objects.create_user(username='wrong-source-owner'))

    def test_old_worker_cannot_claim_new_jobs_or_finish_legacy_running_work_after_upgrade(self):
        job = queue_draft(self.actor, self.upload, 'A01')
        with self.assertRaises(DatabaseError), transaction.atomic():
            AgentJob.objects.filter(pk=job.pk).update(status='running', started_at=timezone.now())
        legacy = AgentJob.objects.create(upload=self.upload, actor=self.actor, role='A02', status='running',
                                        started_at=timezone.now() - timedelta(minutes=11))
        for status in ['draft', 'held']:
            with self.assertRaises(DatabaseError), transaction.atomic():
                AgentJob.objects.filter(pk=legacy.pk).update(status=status)
        upload_recovery.retry(self.actor, self.case, legacy.pk, self.values(legacy))
        claims = [upload_jobs.claim_next(), upload_jobs.claim_next()]
        self.assertCountEqual([claim.pk for claim in claims], [job.pk, legacy.pk])
        for claim in claims:
            self.assertIsNotNone(claim.claim_token)
            self.assertTrue(upload_jobs.finish(claim, self.draft_result()))

    def test_unusable_draft_requires_explicit_recovery_and_history_does_not_load_audit_bodies(self):
        job = AgentJob.objects.create(upload=self.upload, actor=self.actor, role='A05', status='draft',
                                      result={'summary': 'SAMPLE old unaccepted draft'})
        with self.assertRaises(ValidationError):
            queue_draft(self.actor, self.upload, 'A05')
        self.assertContains(self.client.get(self.url), 'Try this file review again')
        values = self.values(job)
        response = self.client.post(self.url, {'action': 'retry', 'job': job.pk, **values, 'confirm': ''})
        self.assertContains(response, values['reason'])
        self.assertEqual(self.client.post(self.url, {'action': 'retry', 'job': job.pk, **values}).status_code, 302)
        with self.assertNumQueries(4):
            history = upload_recovery.histories(self.actor, self.case, [job])
        self.assertEqual(history[job.pk][0]['reason'], values['reason'])
        self.assertNotIn('previous_result_sha256', str(history))
        self.assertContains(self.client.get(self.url), 'File review history')
        other = get_user_model().objects.create_user(username='not-the-file-uploader')
        for action in ['case.read', 'agent.extract']:
            Grant.objects.create(user=other, case=self.case, action=action)
        with self.assertRaises(PermissionDenied):
            upload_recovery.histories(other, self.case, [job])

    def test_expired_completion_stays_interrupted_even_before_an_operator_requests_recovery(self):
        queue_draft(self.actor, self.upload, 'A06')
        claim = upload_jobs.claim_next()
        with patch('apps.agents.upload_jobs.timezone.now', return_value=timezone.now() + timedelta(minutes=11)):
            self.assertFalse(upload_jobs.finish(claim, self.draft_result()))
        claim.refresh_from_db()
        self.assertEqual(claim.status, 'interrupted')
        self.assertEqual(claim.result, {})
        self.assertTrue(upload_recovery.available(claim))

    def test_additive_browser_fixture_uses_native_attempt_and_does_not_reset_recovered_work(self):
        from tests.railway_upload_recovery_seed import SOURCE, prepare
        trial = get_user_model().objects.create_user(username='psl-agent-trial')
        with patch.dict(os.environ, {'PSL_UPLOAD_RECOVERY_FIXTURE': '1'}), \
             patch('adapters.case_uploads.put') as store, patch('adapters.case_uploads.read', return_value=SOURCE):
            os.environ.pop('OPENROUTER_MODEL', None)
            os.environ.pop('OPENROUTER_API_KEY', None)
            created = prepare()
            self.assertNotIn('OPENROUTER_MODEL', os.environ)
            self.assertNotIn('OPENROUTER_API_KEY', os.environ)
            store.assert_called_once()
            job = AgentJob.objects.get(pk=created['job'])
            self.assertEqual(job.status, 'held')
            self.assertFalse(created['actual_model_request_sent'])
            upload_recovery.retry(trial, job.upload.case, job.pk, self.values(job))
            again = prepare()
            self.assertTrue(again['already_prepared'])
            self.assertEqual(again['current_status'], 'queued')
            self.assertEqual(AgentJob.objects.get(pk=job.pk).attempt, 1)
            store.assert_called_once()

    def test_browser_fixture_refuses_pending_other_work_before_private_storage_or_case_creation(self):
        from tests.railway_upload_recovery_seed import TENANT, prepare
        get_user_model().objects.create_user(username='psl-agent-trial')
        job = queue_draft(self.actor, self.upload, 'A01')
        with patch.dict(os.environ, {'PSL_UPLOAD_RECOVERY_FIXTURE': '1'}), patch('adapters.case_uploads.put') as store:
            with self.assertRaises(RuntimeError):
                prepare()
            store.assert_not_called()
        self.assertFalse(CaseUpload.objects.filter(case__tenant=TENANT).exists())
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.attempt, 0)

    def test_visible_pending_work_uses_shared_edit_preserving_progress_and_truthful_prior_attempt_copy(self):
        job = queue_draft(self.actor, self.upload, 'A07')
        pending = self.client.get(self.url)
        self.assertContains(pending, 'data-work-watch')
        self.assertContains(pending, 'work-progress.js')
        self.assertContains(pending, 'data-preserve-form="false"')
        invalid = self.client.post(self.url, {'action': 'queue', 'upload': self.upload.pk, 'role': 'BAD'})
        self.assertContains(invalid, 'data-preserve-form="true"')
        claim = upload_jobs.claim_next()
        upload_jobs.finish(claim, failure='provider_unavailable')
        job.refresh_from_db()
        self.assertNotContains(self.client.get(self.url), 'data-work-watch')
        upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
        queued = self.client.get(self.url)
        self.assertContains(queued, 'Previous file review attempt 1')
        self.assertContains(queued, 'data-work-watch')
        new = upload_jobs.claim_next()
        upload_jobs.finish(new, self.draft_result())
        finished = self.client.get(self.url)
        self.assertNotContains(finished, 'data-work-watch')
        self.assertContains(finished, 'Draft ready for human review')

    def test_parallel_review_handoff_and_recovery_labels_target_only_their_own_agent_form(self):
        reviewed = {'A01', 'A04'}
        stopped = {'A03', 'A05'}
        for role in upload_jobs.ROLES:
            if role == 'A06':
                continue
            job = queue_draft(self.actor, self.upload, role)
            with patch('adapters.case_uploads.read', return_value=self.source), \
                 patch('adapters.openrouter.review', side_effect=TimeoutError if role in stopped else lambda *_: self.output()):
                upload_jobs.run_once()
            if role in reviewed:
                file_draft_reviews.retain(self.actor, self.case, job.pk, {'note': 'SAMPLE multiple agents awaiting separate handoffs.'})
        queue_draft(self.actor, self.upload, 'A06')
        response = self.client.get(self.url)
        class Labels(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.targets, self.stack, self.inputs = [], [], [], {}
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids.append(attrs['id'])
                if tag == 'article':
                    self.stack.append(attrs.get('id'))
                if tag == 'label' and 'for' in attrs:
                    self.targets.append((attrs['for'], self.stack[-1] if self.stack else None))
                if tag in {'input', 'textarea', 'select'} and 'id' in attrs:
                    self.inputs[attrs['id']] = self.stack[-1] if self.stack else None
            def handle_endtag(self, tag):
                if tag == 'article':
                    self.stack.pop()
        parser = Labels()
        parser.feed(response.content.decode())
        self.assertEqual(len(parser.ids), len(set(parser.ids)), 'Agent forms must never share element identifiers')
        relevant = [(target, card) for target, card in parser.targets if card]
        self.assertGreater(len(relevant), 10)
        for target, card in relevant:
            self.assertEqual(parser.inputs.get(target), card, 'Every form label must target a control in its own agent card')
        self.assertContains(response, 'file-handoff-')
        self.assertContains(response, 'file-recovery-')
        self.assertContains(response, 'file-review-')


class UploadRecoveryConcurrencyTests(UploadRecoveryFixture, TransactionTestCase):
    def setUp(self):
        self.setup_recovery()

    def threaded(self, operation):
        close_old_connections()
        try:
            return operation()
        finally:
            connection.close()

    def test_two_connections_reserve_one_attempt_and_one_human_retry(self):
        job = queue_draft(self.actor, self.upload, 'A03')
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: self.threaded(upload_jobs.claim_next), range(2)))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        claim = next(claim for claim in claims if claim)
        upload_jobs.finish(claim, failure='provider_unavailable')
        job.refresh_from_db()
        values = self.values(job)
        def retry():
            try:
                upload_recovery.retry(self.actor, self.case, job.pk, values)
                return 'queued'
            except ValidationError:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.threaded(retry), range(2)))
        self.assertCountEqual(results, ['queued', 'stale'])
        self.assertEqual(Audit.objects.filter(action='file_agent.recovery_requested', case=self.case).count(), 1)

    def test_old_running_worker_cannot_overwrite_recovered_attempt(self):
        job = queue_draft(self.actor, self.upload, 'A01')
        entered, release = Event(), Event()
        def blocked_provider(*_):
            entered.set()
            if not release.wait(25):
                raise TimeoutError('Test provider was not released')
            return {'summary': 'OLD attempt must not win', 'quotes': ['1'], 'gaps': []}
        with patch('adapters.case_uploads.read', return_value=self.source), \
             patch('adapters.openrouter.review', side_effect=blocked_provider), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.threaded, upload_jobs.run_once)
            try:
                self.assertTrue(entered.wait(15))
                job.refresh_from_db()
                old_claim = job.claim_token
                with self.assertRaises(ValidationError):
                    upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
                with patch('apps.agents.upload_recovery.timezone.now', return_value=timezone.now() + timedelta(minutes=11)):
                    upload_recovery.retry(self.actor, self.case, job.pk, self.values(job))
                new = upload_jobs.claim_next()
                self.assertNotEqual(new.claim_token, old_claim)
                self.assertTrue(upload_jobs.finish(new, self.draft_result()))
            finally:
                release.set()
            self.assertTrue(future.result(timeout=20))
        job.refresh_from_db()
        self.assertEqual(job.status, 'draft')
        self.assertEqual(job.attempt, 2)
        self.assertEqual(job.result['summary'], self.draft_result()['summary'])
        self.assertEqual(Audit.objects.filter(case=self.case, action='file_agent.draft').count(), 1)
