"""Protected-binding workbench measurements using real PostgreSQL relations."""
import json
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Evidence
from apps.core.read_budget import ReadBudget, ReadLimit
from apps.core.services import add_evidence
from apps.documents import template_current
from apps.documents.controlled import register_template
from apps.documents.models import Document, Version
from apps.documents.template_access import visible_scopes, visible_sources, visible_templates
from apps.finance.analysis import capture_source
from apps.finance.models import FinanceDocumentBinding, FinanceRun, FinancialImport
from apps.identity.models import Grant
from apps.pmo import leadership_reporting as reports
from apps.pmo.models import MinutesReportBinding
from .document_helpers import artifact
from .finance_analysis_helpers import declared_units
from .helpers import rev
from .meeting_helpers import meetings_fixture
from .test_template_current import claim, scope


class TemplateProtectedBindingScaleTests(TestCase):
    def setUp(self):
        self.actor, self.case, self.owner, self.notes, _, _, meeting, self.reader = meetings_fixture()
        for action in ('case.read', 'document.read', 'report.read', 'meeting.read', 'finance.read'):
            Grant.objects.get_or_create(case=self.case, user=self.reader, action=action)
        kind = 'monthly_executive'
        fields = ['executive_summary', *reports.THEMES[kind]]
        self.report_template = register_template(self.actor, self.case.pk, 'Protected leadership template', {
            'document_type': 'status_report', 'required_fields': fields, 'internal_review_required': True,
            'audience_fields': {'internal': fields},
        }, self.owner.pk, rev(self.case))
        artifact(self.actor, self.case, template_current.COMPONENT, 'schema:psl/document-storage/v1',
                 {'template_ids': [self.report_template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, self.owner)
        content = add_evidence(self.actor, self.case.pk, reports.CONTENT, json.dumps({
            'protocol': reports.MODE, 'kind': kind, 'sections': {
                theme: {'text': 'Synthetic report source', 'coverage': 'unknown', 'evidence_ids': [self.notes.pk]}
                for theme in reports.THEMES[kind]
            },
        }), 'synthetic:report')
        selections = {domain: [] for domain in reports.DOMAINS}
        selections['meetings'] = [meeting.meeting_id]
        self.report = reports.prepare(self.actor, self.case.pk, kind, timezone.now() - timedelta(days=30),
            timezone.now(), self.report_template.pk, 'internal', selections, content.pk, rev(self.case))
        self.report_source = self.bind_claim(self.report_template, 'status_report')
        self.finance_template = register_template(self.actor, self.case.pk, 'Finance statement template', {
            'document_type': 'finance_report', 'internal_review_required': False,
            'required_fields': ['executive_summary', 'financial_metrics', 'bu_totals'],
            'audience_fields': {'internal': ['executive_summary', 'financial_metrics', 'bu_totals']},
        }, self.owner.pk, rev(self.case))
        proof = add_evidence(self.actor, self.case.pk, 'finance_source', 'Synthetic finance source', 'synthetic:finance')
        imported = FinancialImport.objects.create(case=self.case, evidence=proof, source_sha256=proof.sha256, rows=[], findings=[])
        units = declared_units(self.actor, self.case, imported)
        source = capture_source(self.actor, self.case.pk, imported.pk, 'Synthetic-entity', 'accrual',
                                timezone.now(), 'partial', None, proof.pk, rev(self.case),
                                unit_declaration=units)
        self.run = FinanceRun.objects.create(case=self.case, source=source, kind='statement',
            request={}, snapshot={'inputs': []}, result={}, operation_key='protected-binding-fixture', actor=self.actor)
        self.finance_doc = Document.objects.create(case=self.case, title='Synthetic statement versions', owner=self.actor)
        self.finance_source = self.bind_claim(self.finance_template, 'finance_report')
        self.url = reverse('template_current', args=(self.case.pk,))
        self.client.force_login(self.reader)

    def bind_claim(self, template, document_type):
        source = template_current.capture_source(self.actor, self.case.pk, 'Synthetic template rationale',
                                                 f'synthetic:{document_type}', rev(self.case))
        selected = scope(self.actor, self.case, source, document_type=document_type, audience='internal')
        claim(self.actor, self.case, selected, template, source, False)
        return source

    def add_versions(self, reports_count, finance_count, *, manifest=None):
        def versions(document, template, count):
            start = document.versions.count() + 1
            return Version.objects.bulk_create([
                Version(document=document, template=template, number=number, audience='internal', fields={},
                        source_manifest=[], baseline_manifest={}, payload={}, payload_sha256='0' * 64, created_by=self.actor)
                for number in range(start, start + count)
            ])
        MinutesReportBinding.objects.bulk_create([
            MinutesReportBinding(version=version, report=self.report.report, manifest=manifest or self.report.manifest)
            for version in versions(self.report.version.document, self.report_template, reports_count)
        ])
        FinanceDocumentBinding.objects.bulk_create([
            FinanceDocumentBinding(version=version, run=self.run, snapshot={})
            for version in versions(self.finance_doc, self.finance_template, finance_count)
        ])

    def measured_page(self, label):
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(self.url)
        print(f'Protected workbench {label}: HTTP {page.status_code}, {len(queries)} SQL statements')
        return page, len(queries)

    def test_protected_binding_scale_and_fresh_authority(self):
        self.add_versions(2, 5)
        small, small_count = self.measured_page('3 PMO / 5 Finance')
        self.assertContains(small, 'Protected leadership template')
        self.add_versions(45, 115)
        large, large_count = self.measured_page('48 PMO / 120 Finance')
        self.assertContains(large, 'Protected leadership template')
        self.assertContains(large, 'Finance statement template')
        self.assertLessEqual(large_count, small_count + 3)

        Grant.objects.filter(case=self.case, user=self.reader, action='meeting.read').update(active=False)
        denied, _ = self.measured_page('meeting grant withdrawn')
        self.assertNotContains(denied, 'Protected leadership template')
        self.assertNotContains(denied, f'sources/{self.report_source.pk}/')
        self.assertContains(denied, 'Finance statement template')
        self.assertTrue(visible_templates(self.reader, self.case).filter(pk=self.finance_template.pk).exists())
        self.assertFalse(visible_scopes(self.reader, self.case).filter(evidence=self.report_source).exists())
        self.assertFalse(visible_sources(self.reader, self.case, source_id=self.report_source.pk).exists())

    def test_single_denied_binding_still_hides_the_template(self):
        self.add_versions(6, 0)
        allowed, _ = self.measured_page('matching reports')
        self.assertContains(allowed, 'Protected leadership template')
        manifest = dict(self.report.manifest, source_actions=[*self.report.manifest['source_actions'], 'issue.read'])
        self.add_versions(1, 0, manifest=manifest)
        hidden, _ = self.measured_page('mixed authorization inputs')
        self.assertNotContains(hidden, 'Protected leadership template')
        self.assertFalse(visible_templates(self.reader, self.case).filter(pk=self.report_template.pk).exists())
        Grant.objects.create(case=self.case, user=self.reader, action='issue.read')
        reopened, _ = self.measured_page('exact additional grant')
        self.assertContains(reopened, 'Protected leadership template')

    def test_batch_payload_admission_checks_total_and_per_value(self):
        evidence = list(Evidence.objects.filter(pk__in=[self.report_source.pk, self.finance_source.pk]).only('id'))
        size = len(self.report_source.body.encode())
        budget = ReadBudget()
        budget.remaining = 2 * size - 1
        with self.assertRaises(ReadLimit):
            budget.load_many(evidence, 'body', ceiling=size)
        self.assertTrue(all('body' in row.get_deferred_fields() for row in evidence))
        self.assertEqual(budget.remaining, 2 * size - 1)
        budget.remaining = 2 * size
        with self.assertRaises(ReadLimit):
            budget.load_many(evidence, 'body', ceiling=size - 1)
        self.assertTrue(all('body' in row.get_deferred_fields() for row in evidence))
        with CaptureQueriesContext(connection) as queries:
            budget.load_many(evidence, 'body', ceiling=size)
        self.assertEqual(len(queries), 1)
        self.assertIn('SUM(', queries[0]['sql'])
        self.assertEqual(budget.remaining, 0)
        self.assertTrue(all(row.body == self.report_source.body for row in evidence))
