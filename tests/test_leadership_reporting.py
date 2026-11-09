"""Provisional P40/P42 native tests, not factory/full-process acceptance."""
import json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from apps.core.services import add_evidence
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.documents.controlled import register_template, request_review, review_version, reserve_publication, current_version
from apps.documents.models import Version, PublicationReceipt
from apps.documents.delivery import run_publication_once
from adapters.publications import InternalPublicationAdapter, PublicationTimeoutAfterAccept
from apps.policy.services import register_reference
from apps.pmo import leadership_reporting as reports
from apps.pmo.meetings import record_meeting
from tests.meeting_helpers import meetings_fixture
from tests.document_helpers import artifact
from tests.helpers import activate, rev


class LookupOnly(InternalPublicationAdapter):
    def deliver(self, *args): raise AssertionError('Never redispatch uncertain original')


class LeadershipReportTests(TestCase):
    def setUp(self):
        self.actor, self.case, self.owner, self.notes, _, _, self.meeting, self.recipient = meetings_fixture()
        self.start = timezone.now()-timedelta(days=35)
        self.end = timezone.now()
        self.selections = {k: [] for k in reports.DOMAINS}
        self.selections['meetings'] = [self.meeting.meeting_id]
        for action in ['report.read', 'report.draft', 'meeting.read', 'issue.read', 'change.read']:
            Grant.objects.get_or_create(case=self.case, user=self.actor, action=action)
        for action in ['document.receive:internal', 'report.read', 'meeting.read']:
            Grant.objects.get_or_create(case=self.case, user=self.recipient, action=action)
        ref = register_reference(self.actor, self.case.pk, 'internal-recipient', 'schema:psl/document-recipient/v1',
            {'audience': 'internal', 'user_id': self.recipient.pk}, self.owner.pk)
        activate(self.actor, self.case, 'D11.recipient_grant_refs', [ref.ref], self.owner)
        artifact(self.actor, self.case, reports.AUDIENCE_COMPONENT, 'schema:psl/leadership-audience/v1', {key: ([self.recipient.pk] if key.endswith(':internal') else None) for key in reports.AUDIENCE_PURPOSES}, self.owner)
        self.kind = 'monthly_executive'
        self.configure(self.kind)

    def configure(self, kind):
        artifact(self.actor, self.case, reports.REVIEW_COMPONENT, 'schema:psl/leadership-review-authority/v1', {'role':'PMO Lead'}, self.owner)
        fields = ['executive_summary', *reports.THEMES[kind]]
        self.template = register_template(self.actor, self.case.pk, 'Leadership '+kind,
            {'document_type': 'status_report', 'required_fields': fields, 'internal_review_required': kind=='monthly_executive',
             'audience_fields': {'internal': fields}}, self.owner.pk, rev(self.case))
        artifact(self.actor, self.case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
                 {'template_ids': [self.template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, self.owner)
        self.payload = {'protocol': reports.MODE, 'kind': kind, 'sections': {
            theme: {'text': 'The selected meeting does not establish complete '+theme.replace('_', ' ')+' coverage.',
                    'coverage': 'unknown', 'evidence_ids': [self.notes.pk]} for theme in reports.THEMES[kind]}}
        self.save_content()

    def save_content(self):
        self.content = add_evidence(self.actor, self.case.pk, reports.CONTENT, json.dumps(self.payload), 'Synthetic human-authored narrative')

    def prepare(self, **kwargs):
        args = dict(actor=self.actor, case_id=self.case.pk, kind=self.kind, start=self.start, end=self.end,
                    template_id=self.template.pk, audience='internal', selections=self.selections,
                    content_id=self.content.pk, expected=rev(self.case))
        args.update(kwargs)
        return reports.prepare(**args)

    def approve(self, binding):
        request_review(self.actor, self.case.pk, binding.version_id, rev(self.case))
        review_version(self.actor, self.case.pk, binding.version_id, 'approve', 'Exact cited themes and missing coverage reviewed', rev(self.case))

    def test_tuesday_cited_themes_unknowns_idempotency_and_receipts(self):
        self.kind='internal_tuesday'; self.configure(self.kind)
        b = self.prepare(); self.assertEqual(self.prepare().pk, b.pk)
        self.assertEqual(set(b.version.fields), {'executive_summary', *reports.THEMES[self.kind]})
        self.assertNotIn(self.notes.body, json.dumps(b.version.payload))
        with self.assertRaises(ValidationError): reports.verify(self.actor, b)
        if self.kind=='monthly_executive': self.approve(b)
        p = reserve_publication(self.actor, self.case.pk, b.version_id, rev(self.case))
        self.assertTrue(run_publication_once(case_id=self.case.pk, job_id=p.job.pk))
        self.assertTrue(reports.verify(self.actor, b)['verified'])
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(), 1)

    def test_monthly_35_day_window_and_all_required_themes(self):
        self.kind = 'monthly_executive'; self.configure(self.kind)
        b = self.prepare()
        self.assertIn('critical_incidents', b.version.fields)
        self.assertIn('performance', b.version.fields)
        self.assertNotIn('financial_metrics', b.version.fields)
        investigation = reports.investigate(self.actor, self.case, self.kind, self.start, self.end, 'internal', self.selections, self.content.pk)
        self.assertEqual(investigation['themes']['performance']['coverage'], 'unknown')
        self.assertFalse(investigation['approval_granted'])

    def test_missing_theme_or_uncited_claim_cannot_write(self):
        self.payload['sections'].pop(next(iter(reports.THEMES[self.kind]))); self.save_content()
        before = (Evidence.objects.count(), Version.objects.count())
        with self.assertRaises(ValidationError): self.prepare()
        self.assertEqual(before, (Evidence.objects.count(), Version.objects.count()))

    def test_no_client_projection_or_unreviewed_template(self):
        with self.assertRaises(ValidationError): self.prepare(audience='client')
        fields = ['executive_summary', *reports.THEMES[self.kind]]
        template = register_template(self.actor, self.case.pk, 'No review', {'document_type': 'status_report',
            'required_fields': fields, 'internal_review_required': False, 'audience_fields': {'internal': fields}}, self.owner.pk, rev(self.case))
        with self.assertRaises(ValidationError): self.prepare(template_id=template.pk)

    def test_source_grant_withdrawal_prevents_prepare_and_historical_read(self):
        b = self.prepare()
        Grant.objects.filter(case=self.case, user=self.actor, action='meeting.read').update(active=False)
        with self.assertRaises(PermissionDenied): self.prepare()
        with self.assertRaises(PermissionDenied): reports.binding_access(self.actor, b.version)
        self.client.force_login(self.actor)
        response = self.client.get(reverse('documents', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'The selected meeting does not establish complete')

    def test_recipient_requires_source_domain_not_just_document_receipt(self):
        b = self.prepare(); self.approve(b)
        Grant.objects.filter(case=self.case, user=self.recipient, action='meeting.read').update(active=False)
        with self.assertRaises(PermissionDenied): reserve_publication(self.actor, self.case.pk, b.version_id, rev(self.case))
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_returned_revision_preserves_previous_source_history(self):
        artifact(self.actor, self.case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, self.owner)
        b = self.prepare(); request_review(self.actor, self.case.pk, b.version_id, rev(self.case))
        review_version(self.actor, self.case.pk, b.version_id, 'return', 'Explain the dependency source gap', rev(self.case))
        successor = self.prepare()
        self.assertNotEqual(successor.version_id, b.version_id)
        self.assertEqual(successor.version.document_id, b.version.document_id)
        self.assertEqual(b.version.reviews.get().verdict, 'return')

    def test_current_source_change_invalidates_verified_report(self):
        b = self.prepare(); self.approve(b)
        p = reserve_publication(self.actor, self.case.pk, b.version_id, rev(self.case)); run_publication_once(case_id=self.case.pk, job_id=p.job.pk)
        record_meeting(self.actor, self.case.pk, 'STATUS-001', 'status', timezone.now()-timedelta(minutes=10),
            'Updated progress', 'New source version', [self.actor.pk], [], self.notes.pk, rev(self.case), self.meeting.meeting_id)
        with self.assertRaises(ValidationError): reports.verify(self.actor, b)
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(), 1)

    def test_uncertain_delivery_uses_original_receipt_without_resend(self):
        b = self.prepare(); self.approve(b)
        p = reserve_publication(self.actor, self.case.pk, b.version_id, rev(self.case))
        run_publication_once(PublicationTimeoutAfterAccept(), case_id=self.case.pk, job_id=p.job.pk)
        p.job.refresh_from_db(); self.assertEqual(p.job.status, 'unknown')
        run_publication_once(LookupOnly(), case_id=self.case.pk, job_id=p.job.pk)
        p.job.refresh_from_db(); self.assertEqual(p.job.status, 'confirmed')
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(), 1)

    def test_typed_http_preparation_and_repeated_post(self):
        self.client.force_login(self.actor)
        url = reverse('leadership_report', args=[self.case.pk, self.kind])
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {'start_at': self.start.isoformat(), 'end_at': self.end.isoformat(), 'revision': rev(self.case),
                'audience': 'internal', 'template': self.template.pk, 'source_meetings': [self.meeting.meeting_id]}
        for theme in reports.THEMES[self.kind]:
            data.update({theme: self.payload['sections'][theme]['text'], theme+'_coverage': 'unknown', theme+'_citations': [self.notes.pk]})
        response = self.client.post(url, data)
        self.assertContains(response, 'Draft prepared')
        count = Version.objects.count(); data['revision'] = rev(self.case)
        self.assertContains(self.client.post(url, data), 'Draft prepared')
        self.assertEqual(Version.objects.count(), count)

    def test_historical_recipient_inbox_hides_withdrawn_source_access(self):
        b = self.prepare(); self.approve(b)
        p = reserve_publication(self.actor, self.case.pk, b.version_id, rev(self.case))
        run_publication_once(case_id=self.case.pk, job_id=p.job.pk)
        self.client.force_login(self.recipient)
        self.assertContains(self.client.get(reverse('document_inbox')), 'The selected meeting')
        Grant.objects.filter(case=self.case, user=self.recipient, action='meeting.read').update(active=False)
        self.assertNotContains(self.client.get(reverse('document_inbox')), 'The selected meeting')
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(), 1)

    def test_unappointed_reviewer_cannot_approve(self):
        b = self.prepare(); request_review(self.actor, self.case.pk, b.version_id, rev(self.case))
        other = get_user_model().objects.create_user('unappointed-report-reviewer')
        for action in ['case.read', 'document.review_controlled', 'report.read', 'meeting.read']:
            Grant.objects.create(case=self.case, user=other, action=action)
        with self.assertRaises(PermissionDenied):
            review_version(other, self.case.pk, b.version_id, 'approve', 'A grant is not role authority', rev(self.case))
        self.assertFalse(b.version.reviews.exists())

    def test_omitted_native_source_cannot_support_a_claim(self):
        self.selections['meetings'] = []
        with self.assertRaises(ValidationError): self.prepare()
        self.assertFalse(Version.objects.exists())

    def test_source_selection_preserves_exact_timestamp_precision(self):
        self.start = self.start.replace(microsecond=123456)
        self.end = (self.end-timedelta(seconds=1)).replace(microsecond=234567)
        b = self.prepare(); b.report.refresh_from_db()
        self.assertEqual(b.report.start_at.microsecond, 123456)
        self.assertEqual(b.report.end_at.microsecond, 234567)

    def test_shared_evidence_keeps_overlapping_domain_permission(self):
        from apps.pmo.issues import log_issue
        log_issue(self.actor, self.case.pk, 'REUSED-ISSUE', 'Shared source incident', 'Production',
                  self.actor.pk, 'Investigate shared evidence', self.notes.pk, 'Native source reuse', rev(self.case))
        b = self.prepare()
        self.assertIn('issue.read', b.manifest['source_actions'])
        with self.assertRaises(PermissionDenied): reports.binding_access(self.recipient, b.version)
        Grant.objects.filter(case=self.case, user=self.actor, action='issue.read').update(active=False)
        with self.assertRaises(PermissionDenied): self.prepare()

    def test_monthly_explicit_critical_incident_source(self):
        from apps.pmo.issues import log_issue
        self.kind = 'monthly_executive'; self.configure(self.kind)
        e = add_evidence(self.actor, self.case.pk, 'incident_report', 'Recorded critical incident; recovery remains pending', 'Synthetic PMO incident')
        state = log_issue(self.actor, self.case.pk, 'CRITICAL-1', 'Recorded delivery incident', 'Production',
            self.actor.pk, 'Confirm recovery evidence', e.pk, 'PM records explicit severity', rev(self.case), 'Critical')
        self.selections['issues'] = [state.issue_id]
        self.payload['sections']['critical_incidents'] = {'text': 'Recorded critical incident recovery remains pending.',
            'coverage': 'partial', 'evidence_ids': [e.pk]}
        self.save_content()
        b = self.prepare()
        self.assertEqual(b.manifest['issues'], [[state.issue_id, state.pk, e.pk]])
        self.assertIn('recovery remains pending', b.version.fields['critical_incidents']['text'])

    def test_later_shared_domain_link_also_restricts_historical_access(self):
        from apps.pmo.issues import log_issue
        from apps.documents import template_current
        from apps.documents.template_access import visible_sources
        from .test_template_current import claim, scope

        b = self.prepare()
        reports.binding_access(self.recipient, b.version)
        source = template_current.capture_source(self.actor, self.case.pk, 'Private template rationale',
                                                 'synthetic:leadership-template', rev(self.case))
        applicability = scope(self.actor, self.case, source, document_type='status_report', audience='internal')
        claim(self.actor, self.case, applicability, self.template, source, False)
        Grant.objects.get_or_create(case=self.case, user=self.recipient, action='document.read')
        self.assertTrue(visible_sources(self.recipient, self.case, source_id=source.pk).exists())
        log_issue(self.actor, self.case.pk, 'LATER-ISSUE', 'Later shared source incident', 'Production',
                  self.actor.pk, 'Investigate shared evidence', self.notes.pk, 'Native source reuse', rev(self.case))
        with self.assertRaises(PermissionDenied): reports.binding_access(self.recipient, b.version)
        self.assertFalse(visible_sources(self.recipient, self.case).filter(pk=source.pk).exists())
        self.assertFalse(visible_sources(self.recipient, self.case, source_id=source.pk).exists())

    def escalation(self):
        from apps.pmo.issues import log_issue
        from apps.pmo.escalations import capture_profile, request_escalation
        state = log_issue(self.actor, self.case.pk, 'REPORT-ESC', 'Client dependency', 'Delivery',
            self.actor.pk, 'Request dependency evidence', self.notes.pk, 'Selected PMO source', rev(self.case), 'High')
        profile = capture_profile(self.actor, self.case.pk, state.issue_id, state.pk, 'client_dependent', True,
            None, self.notes.pk, 'Explicit dependency impact', rev(self.case))
        request = request_escalation(self.actor, self.case.pk, profile.pk, 'escalate', 'Client',
            self.notes.pk, 'Request escalation, no communication yet', rev(self.case))
        self.selections['escalations'] = [request.pk]
        return state, profile, request

    def test_selected_escalation_decision_successor_invalidates_report(self):
        from apps.pmo.escalations import decide_escalation
        self.kind = 'monthly_executive'; self.configure(self.kind)
        state, profile, request = self.escalation()
        b = self.prepare()
        self.assertEqual(b.manifest['escalation_decisions'], [[request.pk, None]])
        decide_escalation(self.actor, self.case.pk, request.pk, 'Head of PMO', 'approve',
            'Explicit human escalation decision', rev(self.case))
        with self.assertRaises(ValidationError): current_version(self.case, b.version_id)

    def test_selected_escalation_requires_current_native_profile(self):
        from apps.pmo.escalations import capture_profile
        state, profile, request = self.escalation()
        b = self.prepare()
        capture_profile(self.actor, self.case.pk, state.issue_id, state.pk, 'internal', False,
            None, self.notes.pk, 'Source-owned revised dependency classification', rev(self.case))
        with self.assertRaises(ValidationError): self.prepare()
        with self.assertRaises(ValidationError): current_version(self.case, b.version_id)
