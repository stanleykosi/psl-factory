"""P41 native factory integration; only transport uncertainty is synthetic.

These checks do not establish full-process acceptance or live distribution.
"""
import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, DatabaseError, transaction
from django.urls import reverse
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from adapters.publications import InternalPublicationAdapter, PublicationTimeoutAfterAccept
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.documents.controlled import register_template, publication_requirements
from apps.documents.models import Publication, PublicationJob, PublicationReceipt, ControlledReview
from apps.identity.models import Grant
from apps.pmo.meetings import create_action, change_action
from apps.pmo.models import MinutesReportBinding
from apps.pmo.reporting import draft_period_report
from apps.workflows.factory_reporting_views import InputsForm
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, register_reference, transition
from apps.workflows import factory, factory_reporting as reporting
from apps.workflows.models import FactoryWork, FactoryAttempt, HumanTask
from tests.document_helpers import artifact
from tests.helpers import activate, rev, setup_case
from tests.meeting_helpers import meetings_fixture


class LookupOnlyPublicationAdapter(InternalPublicationAdapter):
    """Recovery must inspect the original receipt, never repeat delivery."""
    def __init__(self):
        self.looked_up = []

    def lookup(self, publication):
        self.looked_up.append(publication.pk)
        return super().lookup(publication)

    def deliver(self, job_id, fence):
        raise AssertionError('Uncertain accepted publication must be looked up first')


class FactoryReportingTests(TestCase):
    def setUp(self):
        (self.actor, self.case, self.owner, self.notes, self.minutes,
         self.old_template, self.meeting, self.recipient) = meetings_fixture()
        fields = ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']
        self.template = register_template(
            self.actor, self.case.pk, 'Client weekly report',
            {'document_type': 'status_report', 'required_fields': fields,
             'audience_fields': {'client': fields}}, self.owner.pk, rev(self.case))
        artifact(self.actor, self.case, 'D11.template_storage_retention_rules',
                 'schema:psl/document-storage/v1',
                 {'template_ids': [self.template.pk, self.old_template.pk],
                  'repository': 'internal-versioned', 'retention_days': 30}, self.owner)
        self.preparer = get_user_model().objects.create_user('weekly-report-preparer')
        for action in ['case.read', 'report.read', 'factory.execute', 'report.draft',
                       'document.draft', 'document.request_review', 'evidence.add',
                       'meeting.read', 'issue.read', 'change.read', 'delivery.read', 'rfp.read']:
            Grant.objects.create(case=self.case, user=self.preparer, action=action)
        for action in ['report.read', 'factory.read', 'factory.execute', 'factory.start',
                       'factory.manage', 'document.publish', 'document.operate', 'meeting.read',
                       'issue.read', 'change.read', 'delivery.read', 'rfp.read']:
            Grant.objects.get_or_create(case=self.case, user=self.actor, action=action)
        self.configure()
        self.item = create_action(
            self.actor, self.case.pk, 'INTERNAL-ACTION-SECRET',
            'PRIVATE DIAGNOSIS: vendor credentials leaked in raw notes',
            self.actor.pk, timezone.now() + timedelta(days=1), self.notes.pk,
            'Internal commitment', rev(self.case), self.meeting.meeting_id)
        self.narrative = {
            'status': 'Integration testing completed for the current release',
            'risks': 'Client acceptance remains pending',
            'timeline': 'The current release milestone remains under review',
            'next_steps': 'Project owner will confirm the outstanding acceptance evidence',
        }
        self.content_body = {
            'protocol': 'pmo-weekly-client-content/v1',
            'sections': {topic: {'text': text, 'evidence_ids': [self.notes.pk]}
                         for topic, text in self.narrative.items()},
        }
        self.content = add_evidence(
            self.actor, self.case.pk, 'agent_private_report_content',
            json.dumps(self.content_body), 'synthetic:human-authored-client-report')
        now = timezone.now()
        self.inputs = {'start_at': (now - timedelta(days=7)).isoformat(),
                       'end_at': now.isoformat(),
                       'template_id': self.template.pk, 'content_id': self.content.pk}

    def configure(self, **overrides):
        value = json.loads(Path('fixtures/factory-reporting.json').read_text())
        value.pop('classification')
        value.update(preparer_id=self.preparer.pk, executor_id=self.actor.pk)
        value.update(overrides)
        self.config = draft_operator_policy(
            self.actor, self.case.pk, 'OPS.factory_reporting_execution', value,
            self.owner.pk, timezone.now())
        transition(self.actor, self.config.pk, 'validated')
        transition(self.actor, self.config.pk, 'active')

    def start_work(self, key='WEEKLY-1', inputs=None):
        self.work = reporting.start(self.actor, self.case.pk, key,
                                    inputs or self.inputs, 'Weekly client report', rev(self.case))
        return self.work

    def advance(self):
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()

    def review(self, verdict='approve'):
        self.work.refresh_from_db()
        version = reporting.document(self.work)
        self.assertIsNotNone(version, self.work.finding)
        reporting.review(self.actor, self.work.pk, self.work.revision,
                         rev(self.case), version.pk, verdict,
                         'PMO Lead reviewed exact client content and source coverage')
        return version

    def correct(self, inputs=None):
        self.work.refresh_from_db()
        result = reporting.correct(self.actor, self.work.pk, self.work.revision,
                                   rev(self.case), inputs or self.inputs,
                                   'Human requests current source-bound report revision')
        self.work.refresh_from_db()
        return result

    def finish(self):
        self.advance()
        self.review()
        self.advance()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        proof = reporting.verify(self.work)
        self.assertTrue(proof['verified'])
        self.assertEqual(len(proof['receipt_ids']), 1)
        return proof

    def uncertain_publication(self):
        self.start_work()
        self.advance()
        self.review()
        for _ in range(20):
            factory.run_once(self.work.pk, adapter=PublicationTimeoutAfterAccept())
            self.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=self.work, status='unknown').exists():
                break
        job = PublicationJob.objects.get(publication__factory_work=self.work)
        self.assertEqual(job.status, 'unknown', self.work.finding)
        return job, PublicationReceipt.objects.get(publication=job.publication)

    def test_full_chain_has_useful_investigation_exact_human_review_and_receipt(self):
        self.start_work()
        self.advance()
        version = reporting.document(self.work)
        self.assertIsNotNone(version, self.work.finding)
        self.assertEqual(version.audience, 'client')
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())
        self.assertTrue(HumanTask.objects.filter(version=version, status='open').exists())
        investigation = self.work.activities.filter(kind='ACT04', status='succeeded')
        self.assertTrue(investigation.exists())
        observed = FactoryAttempt.objects.filter(
            activity__in=investigation, phase='observed').order_by('-pk').first()
        self.assertIsNotNone(observed)
        self.assertTrue(observed.result['investigation'])
        binding = MinutesReportBinding.objects.get(version=version)
        self.assertTrue(binding.manifest)
        self.assertEqual(binding.manifest['source_mode'], 'weekly_client_facts/v1')
        self.assertEqual(set(binding.manifest), {'source_mode', 'meetings', 'actions', 'milestones', 'issues', 'changes', 'client_content'})
        self.assertEqual(binding.report.kind, 'weekly_client')
        self.assertEqual(binding.report.start_at.isoformat(), self.inputs['start_at'])
        self.review()
        self.advance()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        proof = reporting.verify(self.work)
        receipt = PublicationReceipt.objects.get(publication__factory_work=self.work)
        self.assertEqual(proof['receipt_ids'], [receipt.pk])
        self.assertEqual(receipt.payload, version.payload)
        self.assertEqual(receipt.payload_sha256, version.payload_sha256)
        self.assertEqual(receipt.publication.factory_source_id, self.work.source_head_id)
        self.assertEqual(connection.vendor, 'postgresql')

    def test_client_payload_is_four_topic_aggregate_without_internal_source_text(self):
        self.start_work()
        self.finish()
        version = reporting.document(self.work)
        body = json.dumps(version.payload)
        receipt = PublicationReceipt.objects.get(publication__factory_work=self.work)
        for text in self.narrative.values():
            self.assertIn(text, body)
            self.assertIn(text, json.dumps(receipt.payload))
        for key in ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']:
            self.assertIn(key, body)
        for private in ['PRIVATE DIAGNOSIS', 'INTERNAL-ACTION-SECRET',
                        'Confirm the current delivery plan.', 'Investigate the dependency',
                        'Owner reference #', 'fix evidence #', 'root cause #']:
            self.assertNotIn(private, body)
        self.assertIn('coverage', body.lower())
        self.assertTrue(any(word in body.lower() for word in ['partial', 'not complete', 'not a complete']))
        self.assertTrue(MinutesReportBinding.objects.get(version=version).manifest)

    def test_missing_template_holds_drafting_but_preserves_investigation_and_intake(self):
        self.start_work(inputs=dict(self.inputs, template_id=None))
        self.advance()
        self.assertIsNone(reporting.document(self.work))
        self.assertNotEqual(self.work.status, 'verified')
        self.assertTrue(self.work.activities.filter(kind='ACT04', status='succeeded').exists())
        self.assertFalse(Publication.objects.exists())
        self.correct()
        self.finish()

    def test_missing_preparer_holds_only_dependent_action(self):
        self.configure(preparer_id=None)
        self.start_work()
        self.advance()
        self.assertIsNone(reporting.document(self.work))
        self.assertTrue(self.work.activities.filter(kind='ACT04', status='succeeded').exists())
        self.assertFalse(Publication.objects.exists())
        spent = self.work.budget_used
        self.configure()
        factory.adopt_profile(self.actor, self.work.pk, self.work.revision,
                              self.config.pk, 'Human adopts configured report preparer')
        self.work.refresh_from_db()
        self.assertEqual(self.work.budget_used, spent)
        self.finish()

    def test_incomplete_legacy_template_cannot_be_used_for_new_factory_client_path(self):
        with self.assertRaises(ValidationError):
            self.start_work(inputs=dict(self.inputs, template_id=self.old_template.pk))
        self.assertFalse(FactoryWork.objects.filter(definition=reporting.DEFINITION).exists())
        self.assertFalse(Publication.objects.exists())

    def test_missing_client_content_is_investigated_but_cannot_be_drafted(self):
        self.start_work(inputs=dict(self.inputs, content_id=None))
        self.advance()
        self.assertTrue(self.work.activities.filter(kind='ACT04', status='succeeded').exists())
        self.assertIsNone(reporting.document(self.work))
        self.assertFalse(Publication.objects.exists())
        self.correct()
        self.finish()

    def test_missing_topic_is_rejected_or_held_without_drafting(self):
        del self.content_body['sections']['risks']
        invalid = add_evidence(self.actor, self.case.pk, 'agent_private_report_content',
                               json.dumps(self.content_body), 'synthetic:missing-risk-topic')
        try:
            self.start_work(inputs=dict(self.inputs, content_id=invalid.pk))
        except ValidationError:
            self.assertFalse(FactoryWork.objects.filter(definition=reporting.DEFINITION).exists())
        else:
            self.advance()
            self.assertIsNone(reporting.document(self.work))
        self.assertFalse(Publication.objects.exists())

    def test_blank_topic_is_rejected_or_held_without_drafting(self):
        self.content_body['sections']['timeline']['text'] = '   '
        invalid = add_evidence(self.actor, self.case.pk, 'agent_private_report_content',
                               json.dumps(self.content_body), 'synthetic:blank-timeline')
        try:
            self.start_work(inputs=dict(self.inputs, content_id=invalid.pk))
        except ValidationError:
            self.assertFalse(FactoryWork.objects.filter(definition=reporting.DEFINITION).exists())
        else:
            self.advance()
            self.assertIsNone(reporting.document(self.work))
        self.assertFalse(Publication.objects.exists())

    def test_uncited_topic_is_rejected_or_held_without_drafting(self):
        self.content_body['sections']['status']['evidence_ids'] = []
        invalid = add_evidence(self.actor, self.case.pk, 'agent_private_report_content',
                               json.dumps(self.content_body), 'synthetic:uncited-progress')
        try:
            self.start_work(inputs=dict(self.inputs, content_id=invalid.pk))
        except ValidationError:
            self.assertFalse(FactoryWork.objects.filter(definition=reporting.DEFINITION).exists())
        else:
            self.advance()
            self.assertIsNone(reporting.document(self.work))
        self.assertFalse(Publication.objects.exists())

    def test_foreign_citation_is_rejected_or_held_without_drafting(self):
        actor, case = setup_case(username='foreign-report-owner')
        foreign = add_evidence(actor, case.pk, 'meeting_notes',
                               'Other project evidence', 'synthetic:foreign-project')
        self.content_body['sections']['next_steps']['evidence_ids'] = [foreign.pk]
        invalid = add_evidence(self.actor, self.case.pk, 'agent_private_report_content',
                               json.dumps(self.content_body), 'synthetic:foreign-citation')
        try:
            self.start_work(inputs=dict(self.inputs, content_id=invalid.pk))
        except ValidationError:
            self.assertFalse(FactoryWork.objects.filter(definition=reporting.DEFINITION).exists())
        else:
            self.advance()
            self.assertIsNone(reporting.document(self.work))
        self.assertFalse(Publication.objects.exists())

    def test_returned_report_requires_explicit_rework_and_new_exact_version_review(self):
        artifact(self.actor, self.case, 'D05.decision_action_matrix',
                 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, self.owner)
        self.start_work()
        self.advance()
        old = self.review('return')
        self.advance()
        self.assertFalse(Publication.objects.exists())
        spent = self.work.budget_used
        self.correct()
        self.assertEqual(self.work.budget_used, spent)
        self.advance()
        new = reporting.document(self.work)
        self.assertNotEqual(new.pk, old.pk)
        with self.assertRaises(ValidationError):
            reporting.review(self.actor, self.work.pk, self.work.revision,
                             rev(self.case), old.pk, 'approve', 'Stale outward report')
        self.review()
        self.advance()
        self.assertEqual(self.work.status, 'verified', self.work.finding)

    def test_changed_native_action_requires_source_rework_without_resetting_allowance(self):
        self.start_work()
        self.advance()
        old = self.review()
        change_action(self.actor, self.case.pk, self.item.pk, 'complete', self.notes.pk,
                      'Actual evidence-backed completion', rev(self.case), 1)
        self.advance()
        self.assertFalse(PublicationReceipt.objects.exists())
        spent = self.work.budget_used
        self.correct()
        self.assertEqual(self.work.budget_used, spent)
        self.finish()
        self.assertNotEqual(reporting.document(self.work).pk, old.pk)

    def test_current_preparer_grant_is_required_after_draft(self):
        self.start_work()
        self.advance()
        self.review()
        Grant.objects.filter(case=self.case, user=self.preparer, action='report.draft').update(active=False)
        self.advance()
        self.assertFalse(PublicationReceipt.objects.exists())
        self.assertNotEqual(self.work.status, 'verified')

    def test_changed_recipients_invalidate_prior_verification_without_fabricated_receipt(self):
        self.start_work()
        self.finish()
        current = active_component('D11.recipient_grant_refs', self.case)
        recipient = get_user_model().objects.create_user('additional-weekly-recipient')
        Grant.objects.create(case=self.case, user=recipient, action='document.receive:client')
        ref = register_reference(self.actor, self.case.pk, 'weekly:new-recipient',
                                 'schema:psl/document-recipient/v1',
                                 {'audience': 'client', 'user_id': recipient.pk}, self.owner.pk)
        activate(self.actor, self.case, 'D11.recipient_grant_refs',
                 current.envelope['value'] + [ref.ref], self.owner)
        with self.assertRaises(ValidationError):
            reporting.verify(self.work)
        self.assertEqual(PublicationReceipt.objects.count(), 1)

    def test_duplicate_and_stale_intake_do_not_replace_source_or_reset_work(self):
        self.start_work()
        head = self.work.source_head_id
        again = reporting.start(self.actor, self.case.pk, 'WEEKLY-1', self.inputs,
                                'Weekly client report', rev(self.case))
        self.assertEqual(again.pk, self.work.pk)
        self.assertEqual(FactoryWork.objects.filter(definition=reporting.DEFINITION).count(), 1)
        with self.assertRaises(ValidationError):
            reporting.start(self.actor, self.case.pk, 'WEEKLY-1',
                            dict(self.inputs, end_at=(timezone.now()+timedelta(days=1)).isoformat()),
                            'Changed period', rev(self.case))
        with self.assertRaises(ValidationError):
            reporting.correct(self.actor, self.work.pk, self.work.revision + 1,
                              rev(self.case), self.inputs, 'Stale screen')
        self.work.refresh_from_db()
        self.assertEqual(self.work.source_head_id, head)
        self.assertEqual(Evidence.objects.filter(case=self.case, kind=reporting.KIND).count(), 1)

    def test_naive_and_nonpositive_reporting_windows_are_rejected(self):
        for inputs in [dict(self.inputs, start_at='2026-10-01T09:00:00'),
                       dict(self.inputs, end_at=self.inputs['start_at'])]:
            with self.subTest(inputs=inputs), self.assertRaises(ValidationError):
                self.start_work(inputs=inputs)
        self.assertFalse(FactoryWork.objects.filter(definition=reporting.DEFINITION).exists())

    def test_revoked_source_reader_cannot_read_private_intake(self):
        self.start_work()
        Grant.objects.filter(case=self.case, user=self.actor, action='report.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            reporting.source(self.work)

    def test_unrelated_work_receipt_cannot_satisfy_verification(self):
        self.start_work()
        self.finish()
        first = self.work
        next_inputs = dict(self.inputs,
                           start_at=(timezone.now()-timedelta(days=14)).isoformat(),
                           end_at=(timezone.now()-timedelta(days=7)).isoformat())
        self.start_work(key='WEEKLY-2', inputs=next_inputs)
        self.advance()
        self.review()
        with self.assertRaises(ValidationError):
            reporting.verify(self.work)
        first_job = PublicationJob.objects.get(publication__factory_work=first)
        with self.assertRaises(ValidationError):
            reporting.operate(self.actor, self.work.pk, self.work.revision,
                              rev(self.case), first_job.pk, 'retry', 'Wrong work delivery')
        self.assertEqual(PublicationReceipt.objects.count(), 1)

    def test_uncertain_accepted_effect_is_lookup_first_after_publisher_permission_withdrawal(self):
        job, receipt = self.uncertain_publication()
        Grant.objects.filter(case=self.case, user=self.actor, action='document.publish').update(active=False)
        adapter = LookupOnlyPublicationAdapter()
        spent = self.work.budget_used
        reporting.reconcile(self.actor, self.work.pk, self.work.revision, adapter=adapter)
        self.work.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(job.status, 'confirmed')
        self.assertEqual(adapter.looked_up, [job.publication_id])
        self.assertEqual(self.work.budget_used, spent)
        self.assertEqual(PublicationReceipt.objects.get(publication=job.publication).pk, receipt.pk)
        self.assertEqual(Publication.objects.filter(factory_work=self.work).count(), 1)
        with self.assertRaises((PermissionDenied, ValidationError)):
            reporting.verify(self.work)

    def test_cancelled_uncertain_work_reconciles_original_receipt_and_cannot_restart(self):
        job, receipt = self.uncertain_publication()
        with self.assertRaises(ValidationError):
            self.correct()
        reporting.cancel(self.actor, self.work.pk, self.work.revision)
        self.work.refresh_from_db()
        spent = self.work.budget_used
        reporting.reconcile(self.actor, self.work.pk, self.work.revision,
                            adapter=LookupOnlyPublicationAdapter())
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'followup_needed')
        self.assertEqual(self.work.budget_used, spent)
        self.assertEqual(PublicationReceipt.objects.get(publication=job.publication).pk, receipt.pk)
        with self.assertRaises(ValidationError):
            reporting.restart(self.actor, self.work.pk, self.work.revision,
                              rev(self.case), 'Cannot undo already delivered client report')

    def test_restart_stopped_preparation_retains_history_and_spent_allowance(self):
        self.start_work()
        self.advance()
        old_head = self.work.source_head_id
        old_activities = list(self.work.activities.values_list('pk', flat=True))
        reporting.cancel(self.actor, self.work.pk, self.work.revision)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'cancelled')
        spent = self.work.budget_used
        reporting.restart(self.actor, self.work.pk, self.work.revision,
                          rev(self.case), 'Fresh human instruction to prepare current weekly report')
        self.work.refresh_from_db()
        self.assertEqual(self.work.budget_used, spent)
        self.assertNotEqual(self.work.source_head_id, old_head)
        self.assertTrue(set(old_activities).issubset(set(self.work.activities.values_list('pk', flat=True))))
        self.assertFalse(self.work.cancel_requested)
        self.finish()


    def test_historical_source_and_ui_deny_withdrawn_native_read_permission(self):
        self.start_work()
        self.advance()
        Grant.objects.filter(case=self.case, user=self.actor, action='meeting.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            reporting.source(self.work, self.actor, current=False)
        with self.assertRaises(PermissionDenied):
            reporting.projection(self.actor, self.work)
        self.client.force_login(self.actor)
        response = self.client.get(reverse('factory_detail', args=[self.work.pk]))
        self.assertIn(response.status_code, [403, 404])
        self.assertNotContains(response, 'Selected private source inventory', status_code=response.status_code)
        self.assertNotContains(response, self.narrative['status'], status_code=response.status_code)

    def test_citation_choices_exclude_ungranted_native_sources(self):
        form = InputsForm(self.case, actor=self.actor)
        self.assertIn(self.notes.pk, form.fields['citation_ids'].queryset.values_list('pk', flat=True))
        Grant.objects.filter(case=self.case, user=self.actor, action='meeting.read').update(active=False)
        form = InputsForm(self.case, actor=self.actor)
        self.assertNotIn(self.notes.pk, form.fields['citation_ids'].queryset.values_list('pk', flat=True))
        self.assertNotIn(self.owner.pk, form.fields['citation_ids'].queryset.values_list('pk', flat=True))

    def test_native_safe_draft_requires_native_source_read_grants(self):
        Grant.objects.filter(case=self.case, user=self.preparer, action='meeting.read').update(active=False)
        self.assertTrue(Grant.objects.filter(case=self.case, user=self.preparer,
                                            action='report.draft', active=True).exists())
        with self.assertRaises(PermissionDenied):
            draft_period_report(self.preparer, self.case.pk, 'weekly_client',
                                self.inputs['start_at'], self.inputs['end_at'],
                                self.template.pk, 'client', rev(self.case),
                                client_safe=True, client_content_id=self.content.pk)
        self.assertFalse(MinutesReportBinding.objects.exists())

    def test_native_safe_draft_requires_report_read_grant(self):
        Grant.objects.filter(case=self.case, user=self.preparer, action='report.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            draft_period_report(self.preparer, self.case.pk, 'weekly_client',
                                self.inputs['start_at'], self.inputs['end_at'],
                                self.template.pk, 'client', rev(self.case),
                                client_safe=True, client_content_id=self.content.pk)
        self.assertFalse(MinutesReportBinding.objects.exists())

    def test_native_safe_reuse_is_explicitly_forbidden_even_for_existing_safe_report(self):
        self.start_work()
        self.advance()
        original = reporting.document(self.work)
        self.assertIsNotNone(original)
        with self.assertRaises(ValidationError):
            draft_period_report(self.preparer, self.case.pk, 'weekly_client',
                                self.inputs['start_at'], self.inputs['end_at'],
                                self.template.pk, 'client', rev(self.case),
                                reuse_existing=True, client_safe=True,
                                client_content_id=self.content.pk)
        self.assertEqual(MinutesReportBinding.objects.count(), 1)
        self.assertEqual(reporting.document(self.work).pk, original.pk)

    def test_direct_publication_insert_rejects_revoked_pmo_lead_assignment(self):
        self.start_work()
        self.advance()
        version = self.review()
        review = version.reviews.latest('pk')
        policies, recipients, retention = publication_requirements(self.case, version)
        roles = active_component('D05.role_principal_assignments', self.case)
        transition(self.actor, roles.pk, 'revoked')
        self.assertTrue(Grant.objects.filter(case=self.case, user=self.actor,
                                            action='document.review_controlled', active=True).exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            Publication.objects.create(
                version=version, review=review, actor=self.actor,
                policies=policies, recipient_ids=recipients, retention_days=retention,
                operation_key='forged:revoked-weekly-review', factory_work=self.work,
                factory_policy=self.work.policy, factory_source=self.work.source_head)
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())

    def test_direct_verified_update_rejects_revoked_pmo_lead_assignment(self):
        self.start_work()
        self.finish()
        roles = active_component('D05.role_principal_assignments', self.case)
        transition(self.actor, roles.pk, 'revoked')
        self.assertTrue(Grant.objects.filter(case=self.case, user=self.actor,
                                            action='document.review_controlled', active=True).exists())
        with self.assertRaises((ValidationError, PermissionDenied)):
            reporting.verify(self.work)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_direct_forged_review_cannot_authorize_factory_publication(self):
        self.start_work()
        self.advance()
        version = self.review()
        legitimate = version.reviews.latest('pk')
        policies, recipients, retention = publication_requirements(self.case, version)
        outsider = get_user_model().objects.create_user('unassigned-weekly-reviewer')
        for action in ['case.read', 'report.read', 'document.review_controlled']:
            Grant.objects.create(case=self.case, user=outsider, action=action)
        with self.assertRaises(DatabaseError), transaction.atomic():
            forged = ControlledReview.objects.create(
                version=version, actor=outsider, verdict='approve',
                note='Forged approval with copied legitimate authority metadata',
                authority=legitimate.authority, delegated=False,
                payload_sha256=version.payload_sha256)
            Publication.objects.create(
                version=version, review=forged, actor=self.actor,
                policies=policies, recipient_ids=recipients, retention_days=retention,
                operation_key='forged:unassigned-weekly-reviewer', factory_work=self.work,
                factory_policy=self.work.policy, factory_source=self.work.source_head)
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())
        self.assertEqual(version.reviews.count(), 1)

    def test_every_recipient_gets_exact_payload_and_receipts_cannot_be_rewritten(self):
        second = get_user_model().objects.create_user('second-weekly-recipient')
        Grant.objects.create(case=self.case, user=second, action='document.receive:client')
        reference = register_reference(
            self.actor, self.case.pk, 'weekly:second-recipient',
            'schema:psl/document-recipient/v1',
            {'audience': 'client', 'user_id': second.pk}, self.owner.pk)
        current = active_component('D11.recipient_grant_refs', self.case)
        activate(self.actor, self.case, 'D11.recipient_grant_refs',
                 current.envelope['value'] + [reference.ref], self.owner)
        self.start_work()
        self.advance()
        version = self.review()
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.advance()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        receipts = list(PublicationReceipt.objects.filter(publication__factory_work=self.work))
        self.assertEqual({r.recipient_id for r in receipts}, {self.recipient.pk, second.pk})
        self.assertEqual(set(reporting.verify(self.work)['receipt_ids']), {r.pk for r in receipts})
        for receipt in receipts:
            self.assertEqual(receipt.payload, version.payload)
            self.assertEqual(receipt.payload_sha256, version.payload_sha256)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PublicationReceipt.objects.filter(pk=receipts[0].pk).update(payload={'sections': []})

    def test_returned_review_history_cannot_be_forged_into_publication(self):
        artifact(self.actor, self.case, 'D05.decision_action_matrix',
                 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, self.owner)
        self.start_work()
        self.advance()
        returned = self.review('return')
        decision = returned.reviews.latest('pk')
        policies, recipients, retention = publication_requirements(self.case, returned)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Publication.objects.create(
                version=returned, review=decision, actor=self.actor,
                policies=policies, recipient_ids=recipients, retention_days=retention,
                operation_key='forged:returned-weekly-report', factory_work=self.work,
                factory_policy=self.work.policy, factory_source=self.work.source_head)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.correct()
        self.finish()
        decision.refresh_from_db()
        self.assertEqual(decision.verdict, 'return')
        self.assertFalse(Publication.objects.filter(version=returned).exists())
        self.assertNotEqual(reporting.document(self.work).pk, returned.pk)

    def test_direct_publication_rejects_current_pmo_lead_reassignment(self):
        from apps.policy.role_assignments import draft
        from apps.policy.services import reference_values
        self.start_work()
        self.advance()
        version = self.review()
        decision = version.reviews.latest('pk')
        policies, recipients, retention = publication_requirements(self.case, version)
        prior = active_component('D05.role_principal_assignments', self.case)
        new_lead = get_user_model().objects.create_user('replacement-weekly-pmo-lead')
        Grant.objects.create(case=self.case, user=new_lead, action='document.review_controlled')
        assignments = [dict(item, user_id=new_lead.pk) if item['role'] == 'PMO Lead' else item
                       for item in reference_values(prior)]
        successor = draft(self.actor, self.case.pk, assignments, self.owner.pk, timezone.now())
        transition(self.actor, successor.pk, 'validated')
        transition(self.actor, successor.pk, 'active')
        self.assertTrue(Grant.objects.filter(case=self.case, user=self.actor,
                                            action='document.review_controlled', active=True).exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            Publication.objects.create(
                version=version, review=decision, actor=self.actor,
                policies=policies, recipient_ids=recipients, retention_days=retention,
                operation_key='forged:reassigned-weekly-review', factory_work=self.work,
                factory_policy=self.work.policy, factory_source=self.work.source_head)
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())

    def test_native_binding_revalidates_exact_declared_client_fact_subset(self):
        from apps.pmo.reporting import binding_manifest
        self.start_work()
        self.advance()
        version = reporting.document(self.work)
        binding = MinutesReportBinding.objects.get(version=version)
        self.assertEqual(binding.manifest, binding_manifest(binding))
        self.assertEqual(set(binding.manifest), {'source_mode', 'meetings', 'actions', 'milestones', 'issues', 'changes', 'client_content'})
        change_action(self.actor, self.case.pk, self.item.pk, 'complete', self.notes.pk,
                      'Source-owned completion changes exact selected fact set', rev(self.case), 1)
        self.assertNotEqual(binding.manifest, binding_manifest(binding))
        with self.assertRaises(ValidationError):
            reporting.bound_document(self.work)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_reporting_document(%s,%s,%s)',
                           [self.work.pk, self.work.source_head_id, version.pk])
            self.assertEqual(cursor.fetchone(), (False,))

    def test_intake_and_review_ui_preserve_read_only_observations(self):
        self.client.force_login(self.actor)
        url = reverse('factory_create')
        response = self.client.get(url, {'definition': reporting.DEFINITION, 'case': self.case.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selected period')
        response = self.client.post(url, dict(self.inputs, definition=reporting.DEFINITION,
                                             case=self.case.pk, revision=rev(self.case),
                                             key='WEEKLY-UI', reference='Client weekly reporting UI'))
        self.assertEqual(response.status_code, 302)
        self.work = FactoryWork.objects.get(case=self.case, key='WEEKLY-UI')
        self.advance()
        version = reporting.document(self.work)
        detail = reverse('factory_detail', args=[self.work.pk])
        before = (rev(self.case), self.work.revision, Evidence.objects.count(),
                  FactoryAttempt.objects.count(), HumanTask.objects.count(), Publication.objects.count())
        response = self.client.get(detail)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Source investigation')
        self.assertContains(response, self.narrative['status'])
        self.assertNotContains(response, 'Reviewed weekly client report')
        self.work.refresh_from_db()
        self.assertEqual(before, (rev(self.case), self.work.revision, Evidence.objects.count(),
                                  FactoryAttempt.objects.count(), HumanTask.objects.count(), Publication.objects.count()))
        response = self.client.post(detail, {'action': 'review', 'revision': self.work.revision,
                                            'case_revision': rev(self.case), 'version': version.pk,
                                            'verdict': 'approve', 'note': 'PMO Lead meaning and safety review in native work UI'})
        self.assertEqual(response.status_code, 302)
        self.advance()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        self.assertContains(self.client.get(detail), 'Recorded delivery')

    def test_reporting_policy_cannot_replace_prescribed_native_review_role(self):
        original = self.config.pk
        with self.assertRaises(ValidationError):
            self.configure(review_role='PM')
        self.assertEqual(active_component('OPS.factory_reporting_execution', self.case).pk, original)

    def test_p52_scope_and_dependencies_are_explicit_generated_coverage_not_raw_facts(self):
        from apps.pmo.reporting import CLIENT_SCOPE_COVERAGE, CLIENT_DEPENDENCY_COVERAGE
        self.start_work()
        self.finish()
        version = reporting.document(self.work)
        self.assertEqual(len(version.payload['sections']), 7)
        self.assertEqual(version.fields['scope']['text'], CLIENT_SCOPE_COVERAGE)
        self.assertEqual(version.fields['dependencies']['text'], CLIENT_DEPENDENCY_COVERAGE)
        receipt = PublicationReceipt.objects.get(publication__factory_work=self.work)
        self.assertEqual(receipt.payload, version.payload)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_reporting_document(%s,%s,%s)',
                           [self.work.pk, self.work.source_head_id, version.pk])
            self.assertEqual(cursor.fetchone(), (True,))
        self.assertTrue(all(field['evidence_ids'] == [version.source_manifest[0]['id']] for field in version.fields.values()))

    def test_exact_generated_projection_is_the_only_outward_source_reference(self):
        from apps.documents.controlled import create_version
        from apps.core.evidence_access import public_evidence
        self.start_work()
        self.finish()
        version = reporting.document(self.work)
        self.assertEqual(len(version.source_manifest), 1)
        projection = Evidence.objects.get(pk=version.source_manifest[0]['id'])
        self.assertEqual(projection.kind, 'ops_client_report_projection')
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=projection.pk)).exists())
        self.assertNotEqual(projection.pk, self.content.pk)
        self.assertNotEqual(projection.pk, self.notes.pk)
        self.assertTrue(all(field['evidence_ids'] == [projection.pk] for field in version.fields.values()))
        binding = MinutesReportBinding.objects.get(version=version)
        self.assertEqual(binding.manifest['client_content'], {'id': self.content.pk, 'sha256': self.content.sha256})
        with self.assertRaises(ValidationError):
            create_version(self.preparer, self.case.pk, self.template.pk, 'No public private-source bypass',
                           'client', version.fields, rev(self.case))

    def test_authorized_p56_native_source_remains_private_but_can_support_client_projection(self):
        from apps.workflows import factory_change_intake as intake
        from apps.core.evidence_access import public_evidence
        from tests.test_change_intake import BODY, fields
        receipt = intake.receive(self.actor, self.case.pk, 'P41-P56-source',
                                 BODY + '\nPRIVATE_P56_DIAGNOSIS', 'synthetic:report-change', rev(self.case))
        confirmed = intake.confirm(self.actor, self.case.pk, receipt.pk, None,
                                   fields(description='PRIVATE_P56_DIAGNOSIS in the captured source'),
                                   'PM confirmed the exact request fields', rev(self.case))
        evidence = confirmed.version.evidence
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=evidence.pk)).exists())
        for section in self.content_body['sections'].values():
            section['evidence_ids'] = [evidence.pk]
        content = add_evidence(self.actor, self.case.pk, 'agent_private_report_content',
                               json.dumps(self.content_body), 'synthetic:P56-backed-client-content')
        self.start_work(inputs=dict(self.inputs, content_id=content.pk))
        self.finish()
        version = reporting.document(self.work)
        self.assertNotIn('PRIVATE_P56_DIAGNOSIS', json.dumps(version.payload))
        self.assertNotIn(evidence.pk, [x['id'] for x in version.source_manifest])
        self.assertNotIn(evidence.pk, [pk for field in version.fields.values() for pk in field['evidence_ids']])
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=evidence.pk)).exists())

    def test_restricted_other_domain_citation_never_uses_private_projection_bypass(self):
        private = add_evidence(self.actor, self.case.pk, 'forecast_sensitive_source',
                               'PRIVATE_OTHER_DOMAIN_RAW', 'synthetic:ungranted-source')
        create_action(self.actor, self.case.pk, 'RESTRICTED-SOURCE-ACTION',
                      'Source body is not granted by meeting access', self.actor.pk,
                      timezone.now() + timedelta(days=1), private.pk, 'Recorded source reference', rev(self.case))
        for section in self.content_body['sections'].values():
            section['evidence_ids'] = [private.pk]
        content = add_evidence(self.actor, self.case.pk, 'agent_private_report_content',
                               json.dumps(self.content_body), 'synthetic:invalid-private-citation')
        self.start_work(inputs=dict(self.inputs, content_id=content.pk))
        self.advance()
        self.assertIsNone(reporting.document(self.work))
        self.assertFalse(Evidence.objects.filter(kind='ops_client_report_projection').exists())
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())

    def test_equivalent_timezone_period_reuses_same_work_identity(self):
        from datetime import datetime, timezone as datetime_timezone
        self.start_work()
        original = self.work.pk
        offset = datetime_timezone(timedelta(hours=3))
        alternate = dict(self.inputs,
                         start_at=datetime.fromisoformat(self.inputs['start_at']).astimezone(offset).isoformat(),
                         end_at=datetime.fromisoformat(self.inputs['end_at']).astimezone(offset).isoformat())
        duplicate = reporting.start(self.actor, self.case.pk, 'SAME-INSTANT-NEW-KEY', alternate,
                                    'Weekly client report', rev(self.case))
        self.assertEqual(duplicate.pk, original)
        self.assertEqual(FactoryWork.objects.filter(definition=reporting.DEFINITION).count(), 1)

    def test_direct_verification_rejects_withdrawn_source_owner_authority(self):
        self.start_work()
        self.finish()
        Grant.objects.filter(case=self.case, user=self.actor, action='factory.start').update(active=False)
        with self.assertRaises(PermissionDenied):
            reporting.verify(self.work)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_changed_baseline_invalidates_native_and_sql_report_binding(self):
        from apps.pmo.models import Baseline
        self.start_work()
        self.advance()
        version = self.review()
        selected = {kind: add_evidence(self.actor, self.case.pk, kind,
                                      'Synthetic updated ' + kind, 'synthetic:baseline-change')
                    for kind in ['plan', 'costing', 'sow']}
        Baseline.objects.create(case=self.case, **selected)
        with self.assertRaises(ValidationError):
            reporting.bound_document(self.work)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_reporting_document(%s,%s,%s)',
                           [self.work.pk, self.work.source_head_id, version.pk])
            self.assertEqual(cursor.fetchone(), (False,))

    def test_cited_human_source_is_private_and_generic_drafting_cannot_export_it(self):
        from apps.core.evidence_access import public_evidence, restricted
        from apps.documents.controlled import create_version
        self.assertTrue(restricted(self.content))
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=self.content.pk)).exists())
        fields = {key: {'text': 'This public route cannot disclose private source lineage',
                        'evidence_ids': [self.content.pk]}
                  for key in ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']}
        with self.assertRaises(ValidationError):
            create_version(self.preparer, self.case.pk, self.template.pk, 'Private narrative bypass',
                           'client', fields, rev(self.case))
        self.start_work()
        self.finish()
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=self.content.pk)).exists())
        self.assertTrue(all(self.content.pk not in section['evidence_ids']
                            for section in reporting.document(self.work).fields.values()))

    def test_explicit_safe_revision_preserves_existing_native_report_title_and_history(self):
        from datetime import datetime, timezone as datetime_timezone
        offset = datetime_timezone(timedelta(hours=3))
        old = draft_period_report(self.preparer, self.case.pk, 'weekly_client',
                                  datetime.fromisoformat(self.inputs['start_at']).astimezone(offset),
                                  datetime.fromisoformat(self.inputs['end_at']).astimezone(offset),
                                  self.old_template.pk, 'client', rev(self.case))
        self.start_work()
        self.finish()
        current = reporting.document(self.work)
        self.assertEqual(current.document_id, old.version.document_id)
        self.assertEqual(current.document.title, old.version.document.title)
        self.assertNotEqual(current.pk, old.version_id)
        self.assertEqual(MinutesReportBinding.objects.filter(report=old.report).count(), 2)
        self.assertEqual(old.manifest.get('source_mode'), None)
        self.assertEqual(MinutesReportBinding.objects.get(version=current).manifest['source_mode'], 'weekly_client_facts/v1')


    def reserve_native_report(self, unbound=False):
        from apps.documents.controlled import reserve_publication
        self.start_work()
        self.advance()
        version = self.review()
        publication = reserve_publication(self.actor, self.case.pk, version.pk, rev(self.case),
                                          factory_work_id=None if unbound else self.work.pk)
        return PublicationJob.objects.get(publication=publication)

    def unknown_native_report(self, unbound=False):
        from apps.documents.delivery import run_publication_once
        class TimeoutBeforeAccept(InternalPublicationAdapter):
            def deliver(self, job_id, fence):
                raise TimeoutError('Synthetic uncertain transport before receipt observation')
        job = self.reserve_native_report(unbound)
        run_publication_once(adapter=TimeoutBeforeAccept(), job_id=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        return job

    def lookup_without_resend(self, job, failed=False):
        from apps.documents.delivery import run_publication_once
        class LookupProbe(InternalPublicationAdapter):
            looked_up = False
            def lookup(probe, publication):
                probe.looked_up = True
                if failed:
                    raise ValidationError('Synthetic incomplete receipt lookup observation')
                return None
            def deliver(probe, job_id, fence):
                raise AssertionError('Generic worker must never repeat an uncertain P41 effect')
        adapter = LookupProbe()
        run_publication_once(adapter=adapter, job_id=job.pk)
        self.assertTrue(adapter.looked_up)
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())

    def test_generic_worker_and_operator_cannot_bypass_uncertain_bound_report(self):
        from apps.documents.delivery import operate_publication
        job = self.unknown_native_report()
        Grant.objects.filter(case=self.case, user=self.actor, action='document.publish').update(active=False)
        self.lookup_without_resend(job)
        for action in ['cancel', 'retry']:
            with self.assertRaises(ValidationError):
                operate_publication(self.actor, self.case.pk, job.pk, action,
                                    'Cannot downgrade original uncertainty', rev(self.case))
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')

    def test_generic_worker_protects_exact_native_client_binding_without_factory_scope(self):
        from apps.documents.delivery import operate_publication
        job = self.unknown_native_report(unbound=True)
        self.assertIsNone(job.publication.factory_work_id)
        self.lookup_without_resend(job)
        with self.assertRaises(ValidationError):
            operate_publication(self.actor, self.case.pk, job.pk, 'cancel',
                                'Native binding still has unresolved original effect', rev(self.case))
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')

    def test_generic_expired_lease_is_uncertain_not_operator_cancellable_or_resendable(self):
        from apps.documents.delivery import claim_publication, operate_publication
        job = self.reserve_native_report()
        lease = claim_publication(job_id=job.pk)
        self.assertEqual(lease[0], job.pk)
        PublicationJob.objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            operate_publication(self.actor, self.case.pk, job.pk, 'cancel',
                                'Expired original lease is not confirmed absent', rev(self.case))
        self.lookup_without_resend(job)

    def test_failed_generic_receipt_lookup_preserves_original_unknown_state(self):
        from apps.documents.delivery import operate_publication
        job = self.unknown_native_report()
        self.lookup_without_resend(job, failed=True)
        with self.assertRaises(ValidationError):
            operate_publication(self.actor, self.case.pk, job.pk, 'cancel',
                                'Failed lookup does not make an uncertain effect cancellable', rev(self.case))
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')

    def test_generic_unattempted_pending_publication_remains_cancellable(self):
        from apps.documents.delivery import operate_publication
        job = self.reserve_native_report()
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.attempts, 0)
        operate_publication(self.actor, self.case.pk, job.pk, 'cancel',
                            'Owner cancels before any delivery attempt', rev(self.case))
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())


class FactoryReportingConcurrencyTests(TransactionTestCase):
    setUp = FactoryReportingTests.setUp
    configure = FactoryReportingTests.configure

    def test_two_connections_keep_one_exact_period_work_and_intake(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        gate = Barrier(2)
        def receive():
            close_old_connections()
            try:
                gate.wait(timeout=10)
                return reporting.start(self.actor, self.case.pk, 'PARALLEL-WEEKLY', self.inputs,
                                       'Same explicit weekly report', None).pk
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(receive) for _ in range(2)]
            identities = [future.result(timeout=30) for future in futures]
        self.assertEqual(identities[0], identities[1])
        self.assertEqual(FactoryWork.objects.filter(definition=reporting.DEFINITION).count(), 1)
        self.assertEqual(Evidence.objects.filter(case=self.case, kind=reporting.KIND).count(), 1)
        self.assertFalse(Publication.objects.exists())
