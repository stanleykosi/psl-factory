"""Actual PostgreSQL visibility, transaction and admission proof for source reads."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, connections, transaction
from django.test import TransactionTestCase
from django.urls import reverse

from apps.core.models import Case, Evidence
from apps.core.services import add_evidence
from apps.documents import template_current as current, template_source_reader as reader
from apps.documents.controlled import register_template
from apps.documents.template_access import visible_sources
from apps.identity.models import Grant
from .document_helpers import DEFINITION
from .helpers import rev, setup_case
from .test_template_current import claim, configure, scope


class TemplateSourceReaderTests(TransactionTestCase):
    def setUp(self):
        self.owner, self.case = setup_case()
        self.reader = get_user_model().objects.create_user(username='document-reader')
        for action in ('case.read', 'document.read'):
            Grant.objects.create(case=self.case, user=self.reader, action=action)
        self.source = self.capture('Exact private source <script>literal</script>')

    def capture(self, body):
        return current.capture_source(self.owner, self.case.pk, body, 'synthetic:source', rev(self.case))

    def url(self, source):
        return reverse('template_source_detail', args=(self.case.pk, source.pk))

    def read(self, source=None):
        return reader.read_source(self.reader, self.case.pk, (source or self.source).pk)

    def finance_scope(self, source, purpose):
        return scope(self.owner, self.case, source, document_type='finance_report', purpose=purpose, audience='internal')

    def test_http_and_fresh_principal_permission(self):
        before = rev(self.case)
        self.assertEqual(self.client.get(self.url(self.source)).status_code, 302)
        self.client.force_login(self.reader)
        response = self.client.get(self.url(self.source))
        self.assertContains(response, 'Exact private source &lt;script&gt;literal&lt;/script&gt;')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.post(self.url(self.source)).status_code, 405)
        self.assertEqual(rev(self.case), before)

        other_case = Case.objects.create(title='Different synthetic case', kind='project', synthetic=True)
        self.assertIsNone(reader.read_source(self.reader, other_case.pk, self.source.pk))
        for action in ('case.read', 'document.read'):
            Grant.objects.create(case=other_case, user=self.reader, action=action)
        self.assertIsNone(reader.read_source(self.reader, other_case.pk, self.source.pk))
        self.assertIsNone(reader.read_source(self.reader, self.case.pk, 2**63))
        self.assertIsNone(reader.read_source(self.reader, uuid4(), self.source.pk))
        unsupported = add_evidence(self.owner, self.case.pk, 'completion', 'Unrelated', 'synthetic:completion')
        self.assertEqual(self.client.get(self.url(unsupported)).status_code, 404)

        Grant.objects.filter(case=self.case, user=self.reader, action='document.read').update(active=False)
        self.assertEqual(self.client.get(self.url(self.source)).status_code, 403)
        get_user_model().objects.filter(pk=self.reader.pk).update(is_active=False)
        self.assertTrue(self.reader.is_active)
        with self.assertRaises(PermissionDenied):
            self.read()

    def test_exact_scope_and_all_historical_source_links_match_native(self):
        scope_source = self.source
        claim_source = self.capture('Claim source')
        retraction_source = self.capture('Retraction source')
        resolution_source = add_evidence(self.owner, self.case.pk, 'policy_decision', 'Resolution source', 'synthetic:resolution')
        policy_source = add_evidence(self.owner, self.case.pk, 'policy_decision', 'Policy source', 'synthetic:policy')
        ordinary_source = self.capture('Ordinary empty scope source')
        empty_finance_source = self.capture('Empty Finance scope source')
        case, owner = self.case, self.owner
        restricted = self.finance_scope(scope_source, 'Finance report')
        self.finance_scope(empty_finance_source, 'Empty Finance scope')
        scope(owner, case, ordinary_source)
        ordinary = scope(owner, case, ordinary_source, document_type='status_report',
                         purpose='Ordinary scope sharing the private claim source')
        ordinary_template = register_template(owner, case.pk, 'Status template', DEFINITION, policy_source.pk, rev(case))
        claim(owner, case, ordinary, ordinary_template, claim_source, False)
        template = register_template(owner, case.pk, 'Finance template', {
            'document_type': 'finance_report',
            'required_fields': ['executive_summary', 'financial_metrics', 'bu_totals'],
            'audience_fields': {'internal': ['executive_summary', 'financial_metrics', 'bu_totals']},
            'internal_review_required': False,
        }, policy_source.pk, rev(case))
        configure(owner, case, policy_source, [template], [(restricted, owner)])
        claimed = claim(owner, case, restricted, template, claim_source)
        current.resolve_claims(owner, case.pk, restricted.pk, claimed.pk, [claimed.pk],
                               resolution_source.pk, 'Reviewed fixture', rev(case))
        current.retract_claim(owner, case.pk, claimed.pk, retraction_source.pk, 'Retained history', rev(case))
        hidden = [scope_source, claim_source, retraction_source, resolution_source, empty_finance_source]
        visible = [ordinary_source, policy_source]
        native = set(visible_sources(self.reader, case).values_list('pk', flat=True))
        self.client.force_login(self.reader)
        for evidence in hidden + visible:
            with self.subTest(evidence=evidence.pk):
                self.assertEqual(evidence.pk in native, evidence in visible)
                self.assertEqual(self.client.get(self.url(evidence)).status_code, 200 if evidence in visible else 404)
        workbench = self.client.get(reverse('template_current', args=(case.pk,)))
        self.assertContains(workbench, 'Claim source requires additional access.')
        self.assertNotContains(workbench, self.url(claim_source))
        self.assertNotContains(workbench, claim_source.sha256)
        Grant.objects.create(case=case, user=self.reader, action='finance.read')
        for evidence in hidden:
            with self.subTest(authorised=evidence.pk):
                self.assertEqual(self.read(evidence)[1]['body'], evidence.body)

    def test_revocation_commits_between_metadata_and_body_under_snapshot(self):
        query_grant = Grant.objects.filter(case=self.case, user=self.reader, action='document.read')

        def revoke():
            try:
                return query_grant.update(active=False)
            finally:
                connections.close_all()

        def interleave(execute, sql, params, many, context):
            if sql.startswith('SELECT "core_evidence"."body"'):
                self.assertEqual(pool.submit(revoke).result(timeout=10), 1)
                self.assertTrue(query_grant.values_list('active', flat=True).get())
            return execute(sql, params, many, context)

        with ThreadPoolExecutor(max_workers=1) as pool, connection.execute_wrapper(interleave):
            self.assertEqual(self.read()[1]['body'], self.source.body)
        self.assertFalse(query_grant.values_list('active', flat=True).get())
        with self.assertRaises(PermissionDenied):
            self.read()

    def test_refuses_nested_entry_and_database_rejects_writes(self):
        with transaction.atomic(), self.assertRaises(reader.SourceReadUnavailable):
            self.read()

        def attempt_write(execute, sql, params, many, context):
            if 'OCTET_LENGTH' in sql:
                execute('UPDATE core_case SET revision = revision WHERE id = %s', [self.case.pk], False, context)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(attempt_write), self.assertRaises(DatabaseError) as caught:
            self.read()
        self.assertEqual(caught.exception.__cause__.sqlstate, '25006')
        self.assertTrue(connection.get_autocommit())
        self.assertEqual(self.read()[1]['body'], self.source.body)

    def test_query_cap_and_byte_admission_before_body_transfer(self):
        calls = []

        def record(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            # The outer wrapper also sees attempted SQL rejected by the reader.
            # Record completed execution only.
            calls.append(sql)
            return result

        with connection.execute_wrapper(record):
            self.read()
        count = sum(sql.startswith('SELECT') and 'set_config(' not in sql for sql in calls)
        self.assertLess(count, reader.MAX_QUERIES)
        self.assertIn('OCTET_LENGTH', calls[-2])
        self.assertTrue(calls[-1].startswith('SELECT "core_evidence"."body"'))
        with patch.object(reader, 'MAX_QUERIES', count):
            self.assertEqual(self.read()[1]['body'], self.source.body)
        calls.clear()
        with patch.object(reader, 'MAX_QUERIES', count - 1), connection.execute_wrapper(record):
            with self.assertRaises(reader.SourceReadUnavailable):
                self.read()
        self.assertIn('OCTET_LENGTH', calls[-1])

        boundary = Evidence.objects.create(case=self.case, kind=current.SOURCE_KIND, version=self.source.version + 1,
            body='é' * (reader.MAX_BODY_BYTES // 2), source='synthetic:at-limit', sha256='0' * 64, created_by=self.owner)
        self.assertEqual(self.read(boundary)[1]['body'], boundary.body)
        oversized = Evidence.objects.create(case=self.case, kind=current.SOURCE_KIND, version=self.source.version + 2,
            body='é' * (reader.MAX_BODY_BYTES // 2 + 1), source='synthetic:oversized', sha256='0' * 64, created_by=self.owner)
        calls.clear()
        with connection.execute_wrapper(record), self.assertRaises(reader.SourceReadUnavailable):
            self.read(oversized)
        self.assertIn('OCTET_LENGTH', calls[-1])
        self.client.force_login(self.reader)
        response = self.client.get(self.url(oversized))
        self.assertContains(response, 'Template source unavailable', status_code=503)
        self.assertNotContains(response, oversized.source, status_code=503)
        self.assertIn('no-store', response['Cache-Control'])

    def test_postgresql_statement_timeout_rolls_back_and_stays_local(self):
        with connection.cursor() as cursor:
            cursor.execute('SHOW statement_timeout')
            original_timeout = cursor.fetchone()[0]

        def stall(execute, sql, params, many, context):
            if 'OCTET_LENGTH' in sql:
                execute('SELECT pg_sleep(2)', None, False, context)
            return execute(sql, params, many, context)

        with patch.object(reader, 'STATEMENT_TIMEOUT_MS', 200), connection.execute_wrapper(stall):
            with self.assertRaises(reader.SourceReadUnavailable) as caught:
                self.read()
        self.assertEqual(caught.exception.__cause__.__cause__.sqlstate, '57014')
        self.assertTrue(connection.get_autocommit())
        with connection.cursor() as cursor:
            cursor.execute('SHOW statement_timeout')
            self.assertEqual(cursor.fetchone()[0], original_timeout)
        self.assertEqual(self.read()[1]['body'], self.source.body)
