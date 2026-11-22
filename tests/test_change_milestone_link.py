from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.core.services import add_evidence
from apps.finance.models import BillingPreparation, Invoice
from apps.identity.models import Grant
from apps.pmo.change_execution import record_execution
from apps.pmo.change_stage_links import record
from apps.pmo.changes import log_change
from apps.pmo.models import ChangeMilestoneLink
from tests.billing_helpers import coverage, policy, stage_policy
from tests.helpers import rev
from tests import test_commercial_changes as native


class ChangeMilestoneLinkTests(TestCase):
    assessments = native.ControlledChangeTests.assessments

    def setUp(self):
        native.ControlledChangeTests.setUp(self)
        self.coverage = coverage(self.actor, self.case)
        stage_policy(self.actor, self.case, self.coverage, self.e['signature'])
        self.terms = policy(self.actor, self.case, 'D12.stage_terms', [
            {'coverage_id': self.coverage.pk, 'stage': 'uat', 'amount': '17.25', 'due_date': None},
            {'coverage_id': self.coverage.pk, 'stage': 'completion', 'amount': '42.50', 'due_date': None},
        ])
        policy(self.actor, self.case, 'D12.completion_billing_predicate_ref', {
            'coverage_id': self.coverage.pk, 'stage': 'completion', 'milestone_name': 'Go-live',
        })
        self.authorization = native.ChangeExecutionTests.authorized(self)
        self.source_plan = add_evidence(self.actor, self.case.pk, 'plan', 'Owner plan records sample added scope',
                                        'synthetic:milestone-link')
        self.plan = record_execution(self.actor, self.case.pk, self.authorization.pk, 'plan_updated',
                                     self.source_plan.pk, 'Captured exact scope', rev(self.case))
        self.milestones = reverse('design_project_tab', args=[self.case.pk, 'milestones'])
        self.form = reverse('design_change_milestone_link', args=[self.case.pk])
        self.client.force_login(self.actor)

    def post(self, stage='completion', expected=None):
        return self.client.post(self.form, {'stage': stage, 'plan': self.plan.pk, 'scope_note': 'Sample SMS reminders',
                                           'revision': rev(self.case) if expected is None else expected})

    def reader(self, *actions):
        reader = get_user_model().objects.create_user(username='milestone-reader')
        Grant.objects.bulk_create(Grant(user=reader, case=self.case, action=action)
                                  for action in ('case.read', *actions))
        self.client.force_login(reader)
        return reader

    def test_signed_amount_and_exact_source_survive_native_link_and_are_scoped(self):
        form = self.client.get(self.form)
        self.assertContains(form, 'Go-live')
        self.assertContains(form, 'CR-001 · version 1')
        initial = self.client.get(self.milestones)
        self.assertContains(initial, 'NGN 42.50')
        self.assertNotContains(initial, 'Sample SMS reminders')
        self.assertRedirects(self.post(), self.milestones)
        [saved] = ChangeMilestoneLink.objects.filter(case=self.case)
        self.assertEqual((saved.version_id, saved.plan_event_id, saved.original_plan_id, saved.signed_id, saved.terms_id),
                         (self.cv.pk, self.plan.pk, self.source_plan.pk, self.e['signature'].pk, self.terms.pk))
        page = self.client.get(self.milestones)
        self.assertContains(page, 'NGN 42.50')
        self.assertContains(page, 'Sample SMS reminders')
        self.assertContains(page, 'Additional amount unknown.')
        self.assertContains(page, f'Original project plan evidence {self.source_plan.pk}')
        completion = next(stage for stage in page.context['stages']['rows'] if stage['key'] == 'completion')
        self.assertEqual(completion['amount'], '42.50')
        self.assertFalse(completion['invoices'])
        self.assertFalse(BillingPreparation.objects.filter(coverage=self.coverage).exists())
        self.assertFalse(Invoice.objects.filter(case=self.case).exists())

        reader = self.reader('finance.read')
        restricted_page = self.client.get(self.milestones)
        self.assertContains(restricted_page, 'NGN 42.50')
        self.assertNotContains(restricted_page, 'Sample SMS reminders')
        self.assertNotContains(restricted_page, 'Recorded completions')
        self.assertEqual(self.client.get(self.form).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        Grant.objects.create(user=reader, case=self.case, action='change.read')
        reader_page = self.client.get(self.milestones)
        self.assertContains(reader_page, 'Sample SMS reminders')
        self.assertNotContains(reader_page, 'Link a change')
        self.assertEqual(self.post().status_code, 403)
        Grant.objects.filter(user=reader, case=self.case, action='finance.read').update(active=False)
        self.assertEqual(self.client.get(self.milestones).status_code, 404)

    def test_stale_revision_plan_and_wrong_original_proof_cannot_repoint_history(self):
        old_revision = rev(self.case) - 1
        self.assertContains(self.post(expected=old_revision), 'Stale revision', status_code=400)
        self.assertFalse(ChangeMilestoneLink.objects.filter(case=self.case).exists())
        incorrect = add_evidence(self.actor, self.case.pk, 'plan', 'Another unbound project plan', 'synthetic:unbound')
        with self.assertRaises(DatabaseError), transaction.atomic():
            ChangeMilestoneLink.objects.create(case=self.case, version=self.cv, plan_event=self.plan,
                original_plan=incorrect, signed=self.e['signature'], coverage=self.coverage, terms=self.terms,
                stage='completion', scope_note='Wrong proof', actor=self.actor)
        self.assertRedirects(self.post(), self.milestones)
        [saved] = ChangeMilestoneLink.objects.filter(case=self.case)
        with self.assertRaisesMessage(ValidationError, 'already has a milestone link'):
            record(self.actor, self.case.pk, stage='uat', plan_id=self.plan.pk, scope_note='Move', expected=rev(self.case))
        with self.assertRaises(DatabaseError), transaction.atomic():
            ChangeMilestoneLink.objects.filter(pk=saved.pk).update(stage='uat')

        log_change(self.actor, self.case.pk, self.cv.change.reference, 'Normal', 'Delivery', 'New exact scope',
                   'New owner version', self.source.pk, rev(self.case))
        with self.assertRaisesMessage(ValidationError, 'latest plan for a current change'):
            record(self.actor, self.case.pk, stage='completion', plan_id=self.plan.pk,
                   scope_note='Use the old plan anyway', expected=rev(self.case))
        page = self.client.get(self.milestones)
        self.assertContains(page, 'NGN 42.50')
        self.assertNotContains(page, 'Sample SMS reminders')
        self.assertEqual(ChangeMilestoneLink.objects.get(pk=saved.pk).stage, 'completion')
