"""Protected-binding workbench measurements using real PostgreSQL relations."""
import json
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Evidence
from apps.core.evidence_access import CONFIRMED_CHANGE_SOURCE, public_evidence
from apps.core.read_budget import ReadBudget, ReadLimit
from apps.core.services import add_evidence
from apps.documents import template_current
from apps.documents.controlled import register_template
from apps.documents.models import Document, Version
from apps.documents.template_access import visible_scopes, visible_sources, visible_templates
from apps.finance.analysis import capture_source
from apps.finance.models import FinanceDocumentBinding, FinanceRun, FinancialImport, ForecastScenario
from apps.finance.statement_ppe import denied_statement_runs
from apps.identity.models import Grant
from apps.pmo import leadership_reporting as reports
from apps.pmo.models import MinutesReportBinding
from .document_helpers import artifact
from .finance_analysis_helpers import declared_units
from .helpers import rev, setup_case
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
        source = self.finance_input(self.actor, self.case)
        self.run = FinanceRun.objects.create(case=self.case, source=source, kind='statement',
            request={}, snapshot={'inputs': []}, result={}, operation_key='protected-binding-fixture', actor=self.actor)
        self.finance_doc = Document.objects.create(case=self.case, title='Synthetic statement versions', owner=self.actor)
        self.finance_source = self.bind_claim(self.finance_template, 'finance_report')
        self.url = reverse('template_current', args=(self.case.pk,))
        self.client.force_login(self.reader)

    def finance_input(self, actor, case):
        proof = add_evidence(actor, case.pk, 'finance_source', 'Synthetic finance source', 'synthetic:finance')
        imported = FinancialImport.objects.create(case=case, evidence=proof, source_sha256=proof.sha256, rows=[], findings=[])
        units = declared_units(actor, case, imported)
        return capture_source(actor, case.pk, imported.pk, 'Synthetic-entity', 'accrual',
                              timezone.now(), 'partial', None, proof.pk, rev(case), unit_declaration=units)

    def bind_claim(self, template, document_type):
        source = template_current.capture_source(self.actor, self.case.pk, 'Synthetic template rationale',
                                                 f'synthetic:{document_type}', rev(self.case))
        selected = scope(self.actor, self.case, source, document_type=document_type, audience='internal')
        claim(self.actor, self.case, selected, template, source, False)
        return source

    def add_versions(self, reports_count, finance_count, *, manifest=None, distinct=False):
        def versions(document, template, count):
            start = document.versions.count() + 1
            return Version.objects.bulk_create([
                Version(document=document, template=template, number=number, audience='internal', fields={},
                        source_manifest=[], baseline_manifest={}, payload={}, payload_sha256='0' * 64, created_by=self.actor)
                for number in range(start, start + count)
            ])
        report_bindings = []
        for version in versions(self.report.version.document, self.report_template, reports_count):
            selected = manifest or self.report.manifest
            if distinct:
                narrative = add_evidence(self.actor, self.case.pk, reports.CONTENT,
                    self.case.evidence.get(pk=selected['content']['id']).body, f'synthetic:report-{version.pk}')
                source = add_evidence(self.actor, self.case.pk, 'completion', 'Synthetic cited fact', f'synthetic:fact-{version.pk}')
                selected = dict(selected, content={'id': narrative.pk, 'sha256': narrative.sha256},
                    sources=[*selected['sources'], {'id': source.pk, 'version': source.version, 'sha256': source.sha256}])
            report_bindings.append(MinutesReportBinding(version=version, report=self.report.report, manifest=selected))
        MinutesReportBinding.objects.bulk_create(report_bindings)
        FinanceDocumentBinding.objects.bulk_create([
            FinanceDocumentBinding(version=version, run=self.run if not distinct else FinanceRun.objects.create(
                case=self.case, source=self.run.source, kind='statement', request={}, snapshot={'inputs': []},
                result={}, operation_key=f'scale-statement-{version.pk}', actor=self.actor), snapshot={})
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

    def test_distinct_pmo_and_finance_bindings(self):
        self.add_versions(2, 5, distinct=True)
        small, small_count = self.measured_page('3 distinct PMO / 5 distinct Finance')
        self.add_versions(45, 43, distinct=True)
        large, large_count = self.measured_page('48 distinct PMO / 48 distinct Finance')
        self.assertContains(small, 'Protected leadership template')
        self.assertContains(large, 'Protected leadership template')
        self.assertContains(large, 'Finance statement template')
        self.assertLessEqual(large_count, small_count + 4)
        Grant.objects.filter(case=self.case, user=self.reader, action='meeting.read').update(active=False)
        denied, _ = self.measured_page('distinct bindings after grant withdrawal')
        self.assertNotContains(denied, 'Protected leadership template')
        self.assertNotContains(denied, f'sources/{self.report_source.pk}/')
        self.assertContains(denied, 'Finance statement template')

    def test_native_and_batched_privacy_agree_on_confirmed_change_and_legacy_forecast(self):
        confirmed = add_evidence(self.actor, self.case.pk, 'document', 'Synthetic confirmed change', CONFIRMED_CHANGE_SOURCE)
        legacy = add_evidence(self.actor, self.case.pk, 'document', 'Synthetic historical link', 'synthetic:legacy')
        Grant.objects.get_or_create(case=self.case, user=self.reader, action='change.read')
        manifest = dict(self.report.manifest, changes=[[1, 1, confirmed.pk]],
            sources=[*self.report.manifest['sources'], {'id': confirmed.pk}, {'id': legacy.pk}])
        self.add_versions(1, 0, manifest=manifest)

        def forecast(reference, pk):
            ForecastScenario.objects.create(case=self.case, reference=reference, number=1, evidence=self.owner,
                payload={'items': [{'evidence_id': pk}]}, reason='Synthetic history fixture', actor=self.actor)

        forecast('LEGACY-STRING', str(legacy.pk))
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=legacy.pk)).exists())
        for budget in (None, ReadBudget()):
            self.assertTrue(visible_templates(self.reader, self.case, budget=budget).filter(pk=self.report_template.pk).exists())
        forecast('EXACT-PRIVATE', confirmed.pk)
        for budget in (None, ReadBudget()):
            self.assertFalse(visible_templates(self.reader, self.case, budget=budget).filter(pk=self.report_template.pk).exists())

    def test_distinct_ppe_run_classifications_keep_owning_case_grants_separate(self):
        other_actor, other_case = setup_case(username='distinct-finance-owner')
        other_source = self.finance_input(other_actor, other_case)
        for action in ('case.read', 'finance.read'):
            Grant.objects.create(case=other_case, user=self.reader, action=action)
        primary_grant = Grant.objects.create(case=self.case, user=self.reader, action='ppe.read')

        def statement_runs(source, actor):
            return FinanceRun.objects.bulk_create([
                FinanceRun(case_id=source.case_id, source=source, actor=actor, kind='statement', request={},
                           snapshot={'inputs': [{'declaration': {'source_type': 'ppe_schedule'}}]}, result={},
                           operation_key=f'scale-ppe-{source.pk}-{number}')
                for number in range(12)
            ])

        first = statement_runs(self.run.source, self.actor)
        second = statement_runs(other_source, other_actor)
        records = list(FinanceRun.objects.filter(pk__in=[run.pk for run in first + second]).only('kind', 'case_id'))
        with CaptureQueriesContext(connection) as queries:
            denied = denied_statement_runs(self.reader, records, ReadBudget())
        self.assertEqual(len(queries), 2)
        self.assertEqual(set(denied), {run.pk for run in second})
        Grant.objects.filter(pk=primary_grant.pk).update(active=False)
        Grant.objects.create(case=other_case, user=self.reader, action='ppe.read')
        self.assertEqual(set(denied_statement_runs(self.reader, records, ReadBudget())), {run.pk for run in first})
