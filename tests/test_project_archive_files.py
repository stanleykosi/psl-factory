import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from adapters.project_archive import SyntheticObjectArchive
from apps.agents.file_draft_reviews import retain
from apps.agents.models import AgentJob, CaseUpload, FileDraftReview
from apps.identity.models import Grant
from apps.pmo import archive_transfer, delivery_closure
from apps.pmo.models import ArchiveCopyFile, ArchiveCopyJob, ArchiveCopyReceipt, SyntheticArchiveObject
from apps.policy.archive_transfer_validators import COMPONENT, VALUE
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_archive
from .helpers import rev
from .test_factory_archive import setup, ready


def configured(adapter='synthetic_archive/v1'):
    f = setup()
    ready(f)
    factory.run_until_wait(f.work.pk)
    f.work.refresh_from_db()
    value = json.loads(Path('fixtures/archive-file-transfer.json').read_text())
    value.pop('classification')
    value['adapter']=adapter
    value['operator_id'] = f.actor.pk
    f.transfer_policy = draft_operator_policy(f.actor, f.case.pk, COMPONENT, value,
        f.e['policy_decision'].pk, timezone.now())
    transition(f.actor, f.transfer_policy.pk, 'validated')
    transition(f.actor, f.transfer_policy.pk, 'active')
    return f


def reserve(f, extra=()):
    f.work.refresh_from_db()
    return archive_transfer.reserve(f.actor, f.work.pk, f.work.revision, rev(f.case),
                                    list(f.inventory.values()) + list(extra))


class LostCopyResponse(SyntheticObjectArchive):
    def copy(self, file, data):
        super().copy(file, data)
        raise TimeoutError('Synthetic response lost after the exact object was stored.')


class MissingCopyResponse(SyntheticObjectArchive):
    def copy(self, file, data):
        raise TimeoutError('Synthetic timeout before a store object was confirmed.')


class ArchiveFileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = configured()

    def test_selected_files_through_worker_byte_receipts_native_handover_and_factory_verification(self):
        f = self.f
        plan = reserve(f)
        with self.assertRaisesMessage(ValidationError, 'Confirm every reserved archive file'):
            delivery_closure.current_archive(f.d)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'waiting', f.work.finding)
        observation=f.work.activities.filter(kind='ACT04').latest('pk').attempts.filter(phase='observed').latest('pk')
        self.assertEqual(observation.result['file_archive']['plan_id'],plan.pk)
        self.assertEqual(len(observation.result['file_archive']['unconfirmed_file_ids']),3)
        for job in ArchiveCopyJob.objects.filter(file__plan=plan):
            self.assertTrue(archive_transfer.run_once(job.pk))
        result = archive_transfer.projection(f.actor, f.work)
        self.assertTrue(result['verified'], result['finding'])
        self.assertEqual(result['confirmed'], 3)
        self.assertEqual(ArchiveCopyReceipt.objects.filter(file__plan=plan).count(), 3)
        self.assertEqual(delivery_closure.current_archive(f.d).pk, plan.archive_id)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        verified=factory_archive.verify(f.work)
        self.assertEqual(verified['file_archive'], plan.pk)
        self.assertTrue(verified['file_bytes_verified'])
        self.assertFalse(verified['external_bytes_verified'])
        self.assertEqual(verified['verification_scope'],'synthetic_project_file_archive_byte_readback')
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertContains(page, 'Open Support handover')
        self.assertContains(page, 'synthetic acceptance store')
        self.assertNotContains(page, 'from the private file store')
        with self.assertRaises(DatabaseError), transaction.atomic():
            plan.files.update(sha256='0' * 64)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ArchiveCopyReceipt.objects.filter(file__plan=plan).delete()

    def test_interrupted_copy_recovers_original_receipt_without_another_copy(self):
        f = self.f
        plan = reserve(f)
        job = ArchiveCopyJob.objects.get(file=plan.files.order_by('pk').first())
        archive_transfer.run_once(job.pk, adapter=LostCopyResponse())
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        with self.assertRaises(ValidationError):
            archive_transfer.retry_missing(f.actor, job.pk, job.revision)
        self.assertTrue(archive_transfer.run_once(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, 'confirmed')
        self.assertEqual(job.attempts.filter(operation='copy').count(), 1)
        self.assertEqual(job.attempts.filter(operation='lookup').count(), 1)
        self.assertEqual(SyntheticArchiveObject.objects.filter(file=job.file).count(), 1)

    def test_only_confirmed_missing_file_can_be_retried_and_other_files_keep_their_state(self):
        f = self.f
        plan = reserve(f)
        job = ArchiveCopyJob.objects.get(file=plan.files.order_by('pk').first())
        archive_transfer.run_once(job.pk, adapter=MissingCopyResponse())
        job.refresh_from_db()
        self.client.force_login(f.actor)
        url = reverse('factory_detail', args=[f.work.pk])
        page = self.client.post(url, {'action': 'archive_file_lookup', 'job': job.pk,
            'job_revision': job.revision, 'revision': f.work.revision})
        self.assertRedirects(page, url)
        job.refresh_from_db()
        self.assertEqual(job.status, 'missing')
        page = self.client.get(url)
        self.assertContains(page, 'Retry missing file')
        self.assertContains(page, 'File not found')
        Grant.objects.get_or_create(case=f.case,user=f.operator,action='delivery.archive_files')
        other=archive_transfer.projection(f.operator,f.work)
        other_file=next(file for file in other['files'] if file.job.pk==job.pk)
        self.assertTrue(other_file.can_lookup)
        self.assertFalse(other_file.can_retry)
        with self.assertRaises(ValidationError):
            archive_transfer.retry_missing(f.operator,job.pk,job.revision)
        stale = job.revision
        archive_transfer.retry_missing(f.actor, job.pk, job.revision)
        with self.assertRaises(ValidationError):
            archive_transfer.retry_missing(f.actor, job.pk, stale)
        archive_transfer.run_once(job.pk)
        self.assertEqual(ArchiveCopyJob.objects.filter(file__plan=plan, status='confirmed').count(), 1)
        self.assertEqual(ArchiveCopyJob.objects.filter(file__plan=plan, status='pending').count(), 2)
        self.assertEqual(job.attempts.filter(operation='copy').count(), 2)

    def test_current_permission_and_policy_changes_hold_copy_but_preserve_prior_receipts(self):
        f = self.f
        plan = reserve(f)
        jobs = list(ArchiveCopyJob.objects.filter(file__plan=plan).order_by('pk'))
        archive_transfer.run_once(jobs[0].pk)
        receipt = ArchiveCopyReceipt.objects.get(file=jobs[0].file)
        Grant.objects.filter(case=f.case, user=f.actor, action='delivery.archive_files').update(active=False)
        archive_transfer.run_once(jobs[1].pk)
        jobs[1].refresh_from_db()
        self.assertEqual(jobs[1].status, 'held')
        self.assertEqual(jobs[1].attempts.latest('pk').outcome, 'held')
        self.assertFalse(SyntheticArchiveObject.objects.filter(file=jobs[1].file).exists())
        self.assertTrue(ArchiveCopyReceipt.objects.filter(pk=receipt.pk).exists())
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertNotContains(page, 'Prepare file archive</button>')
        self.assertNotContains(page, 'Check original file</button>')
        transition(f.actor, f.transfer_policy.pk, 'revoked')
        self.assertFalse(archive_transfer.projection(f.actor, f.work)['verified'])

    def test_file_list_reuses_the_reserved_plan_and_loads_metadata_only(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        f = self.f
        reserve(f)
        with CaptureQueriesContext(connection) as captured:
            state = archive_transfer.projection(f.actor, f.work)
        self.assertEqual(state['total'], 3)
        self.assertEqual(sum(group['total'] for group in state['groups']), 3)
        self.assertEqual({group['label'] for group in state['groups']}, {'Planning', 'Delivery and acceptance'})
        plan_reads = [query for query in captured.captured_queries if 'FROM "pmo_archivecopyplan"' in query['sql']]
        self.assertEqual(len(plan_reads), 1)
        self.assertFalse(any('pmo_syntheticarchiveobject' in query['sql'] for query in captured.captured_queries))

    def test_archive_detail_reuses_pure_provenance_reads_and_mutations_recheck_current_authority(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        f = self.f
        plan = reserve(f)
        job = plan.files.order_by('pk').first().job
        archive_transfer.run_once(job.pk, adapter=LostCopyResponse())
        self.client.force_login(f.actor)
        url = reverse('factory_detail', args=[f.work.pk])
        with CaptureQueriesContext(connection) as captured:
            page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Check original file')
        print('PSL_ARCHIVE_DETAIL_QUERIES=' + str(len(captured)), flush=True)
        self.assertLess(len(captured), 1800)
        job.refresh_from_db()
        self.assertRedirects(self.client.post(url, {'action': 'archive_file_lookup', 'job': job.pk,
            'job_revision': job.revision, 'revision': f.work.revision}), url)
        self.assertEqual(job.attempts.filter(operation='lookup').count(), 1)
        Grant.objects.filter(case=f.case, user=f.actor, action='delivery.archive_files').update(active=False)
        denied = self.client.post(url, {'action': 'archive_file_lookup', 'job': job.pk,
            'job_revision': job.revision, 'revision': f.work.revision})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(job.attempts.filter(operation='lookup').count(), 1)

    def test_actual_reviewed_upload_attachment_is_copied_with_its_source(self):
        f = self.f
        data = b'%PDF-1.4\nSynthetic private archive attachment\n%%EOF\n'
        sha = hashlib.sha256(data).hexdigest()
        upload = CaseUpload.objects.create(case=f.case, actor=f.actor, name='synthetic-archive.pdf',
                                          key=sha, sha256=sha, size=len(data))
        job = AgentJob.objects.create(upload=upload, actor=f.actor, role='A08', status='draft', result={
            'source_sha256': sha, 'summary': 'Synthetic attachment review.',
            'quotes': ['Synthetic private archive attachment'], 'gaps': [], 'model': 'synthetic-provider',
        })
        retain(f.actor, f.case, job.pk, {'note': 'Synthetic human accepts the exact attachment draft.'})
        review = FileDraftReview.objects.get(job=job)
        plan = reserve(f, [review.evidence_id])
        with patch('adapters.case_uploads.read', return_value=data) as read_store:
            for copy_job in ArchiveCopyJob.objects.filter(file__plan=plan):
                archive_transfer.run_once(copy_job.pk)
        self.assertEqual(read_store.call_count, 1)
        self.assertEqual(plan.files.count(), 5)
        archived = SyntheticArchiveObject.objects.get(file__plan=plan, file__upload=upload)
        self.assertEqual(bytes(archived.data), data)
        self.assertTrue(archive_transfer.projection(f.actor, f.work)['verified'])

    def test_store_rules_save_as_draft_and_bad_sources_do_not_reserve_effects(self):
        f = self.f
        self.client.force_login(f.actor)
        url = reverse('factory_detail', args=[f.work.pk])
        page = self.client.post(url, {'action': 'archive_file_rules', 'revision': f.work.revision,
            'case_revision': rev(f.case), 'adapter': 'synthetic_archive/v1', 'operator_id': f.actor.pk,
            'max_files': 20, 'max_bytes': 1048576, 'lease_seconds': 30, 'evidence_id': f.e['policy_decision'].pk})
        self.assertRedirects(page, url)
        from apps.policy.models import Configuration
        draft = Configuration.objects.filter(case=f.case, component=COMPONENT).latest('pk')
        self.assertNotEqual(draft.pk, f.transfer_policy.pk)
        self.assertEqual(draft.states.latest('pk').state, 'draft')
        with self.assertRaises(ValidationError):
            reserve(f, [99999999])
        self.assertFalse(ArchiveCopyJob.objects.exists())

    def test_missing_store_rules_hold_only_copy_and_show_plain_owner_controls(self):
        f=self.f
        transition(f.actor,f.transfer_policy.pk,'revoked')
        f.work.refresh_from_db()
        self.client.force_login(f.actor)
        page=self.client.post(reverse('factory_detail',args=[f.work.pk]),{
            'action':'archive_files','revision':f.work.revision,'case_revision':rev(f.case),
            'sources':[str(pk) for pk in f.inventory.values()]})
        self.assertContains(page,'Review the archive store and designated operator rules before copying files.')
        self.assertNotContains(page,'OPS.archive_file_transfer: MISSING')
        self.assertContains(page,'Prepare archive store rules for owner review')
        self.assertFalse(ArchiveCopyJob.objects.exists())
        self.assertIsNotNone(delivery_closure.current_archive(f.d))


class ArchiveFileConcurrencyTests(TransactionTestCase):
    def test_competing_workers_copy_one_exact_file_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections

        f = configured()
        plan = reserve(f)
        job = ArchiveCopyJob.objects.get(file=plan.files.order_by('pk').first())
        barrier = Barrier(2)

        def copy_file(_):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                return archive_transfer.run_once(job.pk)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(copy_file, range(2)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(SyntheticArchiveObject.objects.filter(file=job.file).count(), 1)
        self.assertEqual(ArchiveCopyReceipt.objects.filter(file=job.file).count(), 1)


class ArchiveFileValidatorTests(SimpleTestCase):
    def test_transfer_limits_provider_and_operator_are_typed(self):
        from apps.documents.contracts import validate

        base = {'adapter': 'synthetic_archive/v1', 'operator_id': 1, 'max_files': 10,
                'max_bytes': 1024, 'lease_seconds': 30}
        validate(VALUE, base)
        for changes in [{'max_files': 0}, {'max_bytes': '1024'}, {'operator_id': True}, {'adapter': 'unreviewed'}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                validate(VALUE, {**copy.deepcopy(base), **changes})

    def test_private_store_uses_conditional_copy_and_exact_byte_readback(self):
        from contextlib import contextmanager
        from io import BytesIO
        from types import SimpleNamespace
        from unittest.mock import Mock
        from adapters.project_archive import PrivateObjectArchive, object_key

        data = b'Synthetic immutable archive source.'
        file = SimpleNamespace(pk=7, plan_id=3, sha256=hashlib.sha256(data).hexdigest(), size=len(data),
            plan=SimpleNamespace(work=SimpleNamespace(case_id='synthetic-case')))
        client = Mock()
        client.get_object.return_value = {'Body': BytesIO(data)}

        @contextmanager
        def store():
            yield client, 'synthetic-private-store'

        with patch('adapters.case_uploads.storage_client', store):
            result = PrivateObjectArchive().copy(file, data)
        self.assertEqual(result, {'object_key': object_key(file), 'sha256': file.sha256, 'size': len(data)})
        client.put_object.assert_called_once_with(Bucket='synthetic-private-store', Key=object_key(file),
            Body=data, ContentType='application/octet-stream', IfNoneMatch='*')
