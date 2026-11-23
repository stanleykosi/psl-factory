"""Synthetic PostgreSQL acceptance for the restricted held-row combination review."""

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance import payroll as native
from apps.finance.payroll_draft_matching import VERDICT
from apps.finance.payroll_models import PayrollInput, PayrollPublication, PayrollReportReceipt, PayrollReview, PayrollRun
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.payroll_validators import MERGE
from apps.policy.services import transition
from apps.workflows import factory, factory_payroll as flow
from apps.workflows.models import FactoryAttempt

from .helpers import rev
from .test_payroll_row_controls import configured, conflicts


class PayrollDraftMatchingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = configured(preparer_receipt=False)
        f = cls.sample
        conflicts(f)
        settings = json.loads(Path('fixtures/factory-payroll.json').read_text())
        settings.pop('classification')
        profile = draft_operator_policy(f['owner'], f['case'].pk, 'OPS.factory_payroll_execution',
                                        settings, f['e']['policy_decision'].pk, timezone.now())
        transition(f['owner'], profile.pk, 'validated')
        transition(f['owner'], profile.pk, 'active')
        Grant.objects.create(case=f['case'], user=f['manager'], action='factory.read')

    def begin(self):
        f = self.sample
        self.work = flow.start(f['preparer'], f['case'].pk, 'held-payroll', f['request'].pk,
                               {'input_ids': [row.pk for row in f['inputs']], 'hr_snapshot_id': f['hr'].pk},
                               'Synthetic held combination', rev(f['case']))
        self.combined = flow.human_action(f['preparer'], self.work.pk, self.work.revision, rev(f['case']),
                                          'working', {'stage': 'combine'})
        self.work.refresh_from_db()
        self.assertEqual(self.combined.metadata['status'], 'held')

    def review(self, *, verdict=VERDICT, key='explicit-draft-review'):
        f = self.sample
        return native.review(f['reviewer'], f['case'].pk, 'run', self.combined.pk, verdict, key,
                             f['e']['payroll_review'].pk, rev(f['case']))

    def test_exact_review_and_own_hr_receipt_continue_only_to_a_private_held_match(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.begin()
        f = self.sample
        decision_url = reverse('factory_invoice_decision', args=[self.work.pk])
        recovery_url = reverse('factory_invoice_recovery', args=[self.work.pk])
        self.client.force_login(f['preparer'])
        self.assertNotContains(self.client.get(decision_url), 'Approve eligible rows for draft matching')
        self.client.force_login(f['reviewer'])
        decision_page = self.client.get(decision_url)
        self.assertContains(decision_page, '100 TEST + Unknown')
        self.assertContains(decision_page, 'Approve eligible rows for draft matching')
        with self.assertRaisesMessage(ValidationError, 'exceptions prevent approval'):
            self.review(verdict='approve', key='full-approval')
        with self.assertRaisesMessage(ValidationError, 'only to a held combination'):
            native.review(f['reviewer'], f['case'].pk, 'input', f['inputs'][1].pk, VERDICT, 'wrong-subject',
                          f['e']['payroll_review'].pk, rev(f['case']))

        response = self.client.post(decision_url, {'action': 'review', 'revision': self.work.revision,
            'case_revision': rev(f['case']), 'kind': 'run', 'subject_id': self.combined.pk,
            'operation_key': 'explicit-draft-review', 'verdict': VERDICT, 'evidence_id': f['e']['payroll_review'].pk})
        self.assertEqual(response.status_code, 302)
        approval = PayrollReview.objects.get(run=self.combined)
        self.assertEqual(self.review().pk, approval.pk)
        self.assertEqual((approval.verdict, approval.subject_sha256), (VERDICT, self.combined.sha256))
        pin = approval.authority['draft_match']
        self.assertEqual((pin['eligible_rows'], pin['held_rows']), (1, 2))
        self.assertFalse(pin['publication_authorized'])
        with self.assertRaisesMessage(ValidationError, 'Current exact payroll review'):
            native.current_review(self.combined)
        def forbidden(_):
            raise AssertionError('A status read loaded payroll rows')
        with patch.object(PayrollInput, 'payload', property(forbidden)), patch.object(PayrollRun, 'result', property(forbidden)):
            self.assertEqual(flow.report(self.work)['stage'], 'draft_match')
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.assertFalse(PayrollRun.objects.filter(kind='match').exists())
        self.client.force_login(f['preparer'])
        self.assertContains(self.client.get(recovery_url), 'Confirm HR snapshot receipt')
        receipt = self.client.post(recovery_url, {'action': 'receive_hr', 'revision': self.work.revision,
            'case_revision': rev(f['case']), 'snapshot_id': f['hr'].pk, 'evidence_id': f['e']['hr_disclosure_decision'].pk})
        self.assertEqual(receipt.status_code, 302)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        state = flow.report(self.work)
        self.assertEqual(state['stage'], 'draft_match_held', self.work.finding)
        draft = PayrollRun.objects.get(pk=state['draft_match']['run'])
        self.assertEqual(draft.metadata['intent']['draft_review_id'], approval.pk)
        self.assertEqual(draft.metadata['status'], 'held')
        rows = {row['employee_id']: row for row in draft.result['rows']}
        self.assertEqual((rows['E001']['amount'], rows['E001']['bu']), ('100', 'BU-A'))
        self.assertEqual((rows['E002']['amount'], rows['E002']['bu'], rows['E002']['match_status']),
                         (None, None, 'held_payroll_source'))
        self.assertEqual([row['row_ref'] for row in rows['E002']['provenance']], ['B1', 'B2'])
        self.assertEqual([row['source_amount'] for row in f['inputs'][1].payload['rows']], ['150', '200', '50'])
        page = self.client.get(recovery_url)
        self.assertContains(page, 'Resolve the held payroll sources before a report.')
        self.assertContains(page, 'Held payroll source')
        self.assertNotContains(page, 'Prepare draft staff-cost totals')
        self.assertNotContains(page, 'Publish exact reviewed aggregate')
        self.client.force_login(f['manager'])
        self.assertEqual(self.client.get(recovery_url).status_code, 403)
        self.assertFalse(PayrollRun.objects.filter(kind='aggregate').exists())
        self.assertFalse(PayrollPublication.objects.exists())
        self.assertFalse(PayrollReportReceipt.objects.exists())
        attempts = json.dumps(list(FactoryAttempt.objects.filter(activity__work=self.work).values_list('result', flat=True)))
        self.assertNotIn('E001', attempts)
        self.assertNotIn('E002', attempts)

    def test_database_and_native_commands_keep_the_scoped_review_out_of_release(self):
        self.begin()
        f = self.sample
        case, maker, reviewer = f['case'], f['preparer'], f['reviewer']
        approval = self.review()
        flow.human_action(maker, self.work.pk, self.work.revision, rev(case), 'receive_hr',
                          {'snapshot_id': f['hr'].pk, 'evidence_id': f['e']['hr_disclosure_decision'].pk})
        draft = native.match(maker, case.pk, self.combined.pk, f['hr'].pk, 'db-guard-draft', rev(case),
                             draft_review_id=approval.pk)
        with self.assertRaisesMessage(ValidationError, 'cannot prepare staff-cost totals'):
            native.aggregate(maker, case.pk, draft.pk, 'forbidden-native-totals', rev(case))
        with self.assertRaisesMessage(ValidationError, 'Only an aggregate'):
            native.publish(maker, case.pk, draft.pk, 'forbidden-native-publish', rev(case))
        with self.assertRaisesMessage(DatabaseError, 'Held payroll cannot receive a full approval'), transaction.atomic():
            PayrollReview.objects.create(request=f['request'], run=draft, operation_key='raw-full-review', verdict='approve',
                authority=approval.authority, subject_sha256=draft.sha256, evidence=approval.evidence, actor=reviewer)
        forged = deepcopy(approval.authority)
        forged['draft_match']['eligible_rows'] = 2
        with self.assertRaisesMessage(DatabaseError, 'Exact held and eligible payroll row counts'), transaction.atomic():
            PayrollReview.objects.create(request=f['request'], run=self.combined, operation_key='raw-inflated-scope',
                verdict=VERDICT, authority=forged, subject_sha256=self.combined.sha256,
                evidence=approval.evidence, actor=reviewer)
        attempted = dict(request=f['request'], parent=self.combined, hr_snapshot=f['hr'], kind='match',
                         sha256=draft.sha256, metadata=deepcopy(draft.metadata), result=draft.result,
                         retain_until=draft.retain_until, actor=maker)
        attempted['metadata']['status'] = 'complete'
        with self.assertRaisesMessage(DatabaseError, 'A draft-only match'), transaction.atomic():
            PayrollRun.objects.create(operation_key='raw-complete-match', **attempted)
        attempted.update(parent=draft, hr_snapshot=None, kind='aggregate')
        with self.assertRaisesMessage(DatabaseError, 'cannot supply another payroll run'), transaction.atomic():
            PayrollRun.objects.create(operation_key='raw-aggregate-from-draft', **attempted)
        with self.assertRaisesMessage(DatabaseError, 'cannot authorise publication'), transaction.atomic():
            PayrollPublication.objects.create(request=f['request'], run=draft, review=approval, version=1,
                operation_key='raw-publish-draft', payload={}, policy_ids={}, actor=maker)
        self.assertFalse(PayrollPublication.objects.exists())
        self.assertFalse(PayrollReportReceipt.objects.exists())

    def test_revoked_reviewer_or_changed_merge_rule_cannot_progress_the_draft(self):
        self.begin()
        f = self.sample
        case, maker, reviewer = f['case'], f['preparer'], f['reviewer']
        approval = self.review()
        with self.assertRaisesMessage(ValidationError, 'your exact receipt'):
            native.match(maker, case.pk, self.combined.pk, f['hr'].pk, 'missing-hr-receipt', rev(case),
                         draft_review_id=approval.pk)
        grant = Grant.objects.get(case=case, user=reviewer, action='payroll.review')
        grant.active = False
        grant.save(update_fields=['active'])
        with self.assertRaises(PermissionDenied):
            native.match(maker, case.pk, self.combined.pk, f['hr'].pk, 'revoked-reviewer', rev(case),
                         draft_review_id=approval.pk)
        self.assertEqual(flow.report(self.work)['stage'], 'input_review')
        grant.active = True
        grant.save(update_fields=['active'])
        transition(f['owner'], f['policies'][MERGE].pk, 'revoked')
        with self.assertRaises(ValidationError):
            native.match(maker, case.pk, self.combined.pk, f['hr'].pk, 'revoked-rule', rev(case),
                         draft_review_id=approval.pk)
        self.assertFalse(PayrollRun.objects.filter(kind='match').exists())
        self.assertTrue(PayrollReview.objects.filter(pk=approval.pk, verdict=VERDICT).exists())
