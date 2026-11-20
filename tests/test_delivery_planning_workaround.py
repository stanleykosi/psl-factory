from pathlib import Path
from uuid import uuid4
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Grant
from apps.pmo import client_uat, delivery, delivery_workarounds, issues
from apps.pmo.models import DeliverySource, Issue
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import COMPONENT, draft as draft_roles
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory_delivery
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.test_client_uat import ClientUATFixture


class PlanningWorkaroundTests(ClientUATFixture, TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.setup_uat()
        self.approver = get_user_model().objects.create_user('independent-planning-workaround-approver')
        for action in ('case.read', 'factory.read', 'delivery.read', 'delivery.planning_decide', 'engagement.read', 'issue.read'):
            Grant.objects.create(case=self.case, user=self.approver, action=action)
        roles = reference_values(active_component(COMPONENT, self.case))
        assignment = draft_roles(self.actor, self.case.pk, [*roles, {'role': 'PMO Lead', 'user_id': self.approver.pk},
                                 {'role': 'QA', 'user_id': self.actor.pk}],
                                 self.e['policy_decision'].pk, timezone.now())
        transition(self.actor, assignment.pk, 'validated')
        transition(self.actor, assignment.pk, 'active')
        artifact(self.actor, self.case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}, {'role': 'PM', 'actions': ['reopen']}]},
                 self.e['policy_decision'])
        self.rule()
        for kind in delivery.PLANNING:
            self.source(kind, {'requires_ui': False, 'client_signoff_required': False} if kind == 'ui_applicability' else {})
        self.issue_state = issues.log_issue(self.actor, self.case.pk, 'SAMPLE-LOGIN-ISSUE', 'Test login retry', 'Defect',
                                            self.actor.pk, 'Review the actual customer response', self.e['requirements'].pk,
                                            'Synthetic release check', rev(self.case), severity='Medium')
        self.returned = delivery.decide_planning(self.approver, self.case.pk, self.d.pk, 'return', self.e['plan'].pk,
                                                 'Review the linked issue or obtain written client acceptance.', rev(self.case),
                                                 issue_id=self.issue_state.issue_id)
        config = json.loads(Path('fixtures/factory-delivery.json').read_text())
        config.pop('classification')
        profile = draft_operator_policy(self.actor, self.case.pk, 'OPS.factory_delivery_execution', config,
                                        self.e['policy_decision'].pk, timezone.now())
        transition(self.actor, profile.pk, 'validated')
        transition(self.actor, profile.pk, 'active')
        self.work = factory_delivery.start(self.actor, self.case.pk, 'SAMPLE-RETURN-WORKAROUND', self.d.pk,
                                           'Synthetic exact Planning workaround', rev(self.case))
        self.url = reverse('factory_invoice_decision', args=[self.work.pk])
        self.target_source = self.target()
        self.workaround = 'For SAMPLE-LOGIN-ISSUE, use the agreed fictional retry prompt.'

    def reviewed_response(self, *, statement=None, outcome='approved_with_workaround', previous=None, responded_at=None):
        proof = self.proof(statement or f'SAMPLE Client Witness approved delivery-build. {self.workaround}')
        response = client_uat.record_response(self.actor, self.case.pk, self.target_source.pk,
            responded_at or timezone.now(), outcome, True, 'Fictional written customer response',
            self.workaround if outcome == 'approved_with_workaround' else None, None, [proof.pk],
            previous.pk if previous else None, uuid4(), rev(self.case))
        return response, self.review(response)

    def link_command(self, response, review):
        return {'return_id': self.returned.pk, 'issue_state_id': self.issue_state.pk, 'response_id': response.pk,
                'review_id': review.pk, 'note': 'The document identifies this exact fictional issue and workaround.'}

    def approve(self):
        return delivery.decide_planning(self.approver, self.case.pk, self.d.pk, 'approve', self.e['plan'].pk,
                                        'Independent sample decision on this reviewed link.', rev(self.case))

    def test_reviewed_written_workaround_reopens_only_the_exact_independent_decision(self):
        response, review = self.reviewed_response()
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(self.url), 'Link reviewed client workaround')
        self.assertNotContains(self.client.get(self.url), 'Approve exact Planning exit')
        command = self.link_command(response, review)
        command.update(action='delivery_workaround', revision=self.work.revision, case_revision=rev(self.case))
        invalid = self.client.post(self.url, command | {'issue_state_id': self.issue_state.pk + 1})
        self.assertContains(invalid, 'The linked issue changed')
        self.assertFalse(DeliverySource.objects.filter(dossier=self.d, kind=delivery_workarounds.KIND).exists())
        self.assertRedirects(self.client.post(self.url, command), self.url, fetch_redirect_response=False)
        link = DeliverySource.objects.get(dossier=self.d, kind=delivery_workarounds.KIND)
        self.assertEqual(link.payload['return_id'], self.returned.pk)
        self.assertEqual(link.payload['review_id'], review.pk)
        self.assertNotIn(self.workaround, str(link.payload))
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeliverySource.objects.filter(pk=link.pk).update(payload={})
        with self.assertRaisesMessage(ValidationError, 'Use the current human-reviewed client workaround'):
            delivery.verify_source(self.actor, self.case.pk, link.pk, rev(self.case))
        with self.assertRaises(PermissionDenied):
            delivery.decide_planning(self.actor, self.case.pk, self.d.pk, 'approve', self.e['plan'].pk,
                                     'The recorder cannot self-approve.', rev(self.case))
        self.assertNotContains(self.client.get(self.url), 'Approve exact Planning exit')

        self.client.force_login(self.approver)
        page = self.client.get(self.url)
        self.assertContains(page, 'Approve exact Planning exit')
        self.assertContains(page, self.workaround)
        access = Grant.objects.filter(case=self.case, user=self.approver, action='engagement.read')
        access.update(active=False)
        blocked = self.client.get(self.url)
        self.assertNotContains(blocked, self.workaround)
        self.assertNotContains(blocked, 'Approve exact Planning exit')
        with self.assertRaises(PermissionDenied):
            self.approve()
        access.update(active=True)
        page = factory_delivery.projection(self.approver, self.work)
        decision = {'action': 'delivery_decision', 'revision': self.work.revision, 'case_revision': rev(self.case),
                    'packet': page['decision_packet'], 'verdict': 'approve', 'evidence': self.e['plan'].pk,
                    'note': 'Independent sample review of this exact workaround.'}
        self.assertRedirects(self.client.post(self.url, decision), self.url, fetch_redirect_response=False)
        approved = delivery.approved_plan(self.d)
        self.assertEqual((approved.actor_id, approved.parent_id), (self.approver.pk, self.returned.pk))
        self.assertEqual(approved.data['issue_remedy']['source_id'], link.pk)
        issue = Issue.objects.select_related('current').get(pk=self.issue_state.issue_id)
        self.assertEqual((issue.current.status, issue.current_id), ('Open', self.issue_state.pk))
        self.assertFalse(self.d.records.filter(kind__in=('release_ready', 'release_outcome', 'go_live', 'closure')).exists())
        with self.assertRaises(ValidationError):
            delivery.readiness_inputs(self.d)
        issue_access = Grant.objects.filter(case=self.case, user=self.approver, action='issue.read')
        issue_access.update(active=False)
        with self.assertRaises(PermissionDenied):
            delivery.approved_plan(self.d)
        with self.assertRaises(PermissionDenied):
            delivery.record_progress(self.actor, self.case.pk, self.d.pk, 'progress', self.e['requirements'].pk,
                                     'Sample continuation requires the current Planning approver.', rev(self.case))
        self.assertEqual(delivery.latest(self.d, 'planning_decision').pk, approved.pk)
        issue_access.update(active=True)

        self.reviewed_response(previous=response, outcome='changes_requested')
        with self.assertRaises(ValidationError):
            delivery.approved_plan(self.d)
        with self.assertRaises(ValidationError):
            self.approve()
        self.assertNotContains(self.client.get(self.url), 'Approve exact Planning exit')
        self.assertEqual(delivery.latest(self.d, 'planning_decision').pk, approved.pk)
        repeated_return = delivery.decide_planning(self.approver, self.case.pk, self.d.pk, 'return',
            self.e['plan'].pk, 'The written workaround now needs another review.', rev(self.case))
        self.assertEqual(repeated_return.parent_id, approved.pk)
        self.assertEqual(repeated_return.data['blocking_issue'], {'issue': issue.pk, 'state': self.issue_state.pk})

    def test_fix_approval_retains_the_original_return_when_the_issue_reopens(self):
        response, review = self.reviewed_response()
        link = delivery_workarounds.record(self.actor, self.case.pk, self.d.pk, rev(self.case),
                                           **self.link_command(response, review))
        workaround_approval = self.approve()
        self.assertEqual(workaround_approval.data['issue_remedy']['source_id'], link.pk)
        issue_id = self.issue_state.issue_id
        proof = self.evidence('resolution', 'Synthetic regression test observed the concrete login fix.')
        acknowledged = issues.update_issue(self.actor, self.case.pk, issue_id, self.issue_state.pk, 'acknowledge',
                                           proof.pk, 'Acknowledged the original sample issue.', rev(self.case))
        fixed = issues.update_issue(self.actor, self.case.pk, issue_id, acknowledged.pk, 'resolve', proof.pk,
                                    'The synthetic verification confirmed the concrete fix.', rev(self.case), fix_id=proof.pk)
        fixed_approval = self.approve()
        self.assertEqual(fixed_approval.parent_id, workaround_approval.pk)
        self.assertEqual(fixed_approval.data['blocking_decision_id'], self.returned.pk)
        self.assertEqual(fixed_approval.data['issue_remedy'], {'issue': issue_id, 'state': fixed.pk, 'fix': proof.pk})
        self.assertEqual(delivery.approved_plan(self.d).pk, fixed_approval.pk)

        for role in ('QA', 'PM'):
            issues.close_issue_log(self.actor, self.case.pk, issue_id, fixed.pk, role, proof.pk,
                                   'Sample closure entry for the exact fixed state.', rev(self.case))
        closed = Issue.objects.get(pk=issue_id).current
        reopened = issues.reopen_issue(self.actor, self.case.pk, issue_id, closed.pk, 'PM', self.e['requirements'].pk,
                                       'The sample fault recurred after closure.', 'Investigate the recurrence.', rev(self.case))
        self.assertEqual(reopened.status, 'Open')
        with self.assertRaises(ValidationError):
            delivery.approved_plan(self.d)
        with self.assertRaises(ValidationError):
            self.approve()
        self.client.force_login(self.approver)
        self.assertNotContains(self.client.get(self.url), 'Approve exact Planning exit')
        self.assertEqual(delivery.latest(self.d, 'planning_decision').pk, fixed_approval.pk)
        fresh_return = delivery.decide_planning(self.approver, self.case.pk, self.d.pk, 'return',
            self.e['plan'].pk, 'Review the reopened issue before a fresh decision.', rev(self.case))
        self.assertEqual(fresh_return.data['blocking_issue'], {'issue': issue_id, 'state': reopened.pk})
        self.assertFalse(self.d.records.filter(kind__in=('release_ready', 'release_outcome', 'go_live', 'closure')).exists())

    def test_generic_delivery_history_withholds_private_client_records_and_link_payload(self):
        response, review = self.reviewed_response()
        command = self.link_command(response, review) | {'note': 'PRIVATE-WORKAROUND-LINK-MARKER'}
        link = delivery_workarounds.record(self.actor, self.case.pk, self.d.pk, rev(self.case), **command)
        self.approve()
        reader = get_user_model().objects.create_user('ordinary-delivery-source-reader')
        for action in ('case.read', 'delivery.read'):
            Grant.objects.create(case=self.case, user=reader, action=action)
        self.client.force_login(reader)
        page = self.client.get(reverse('delivery', args=[self.case.pk]))
        self.assertContains(page, 'owned:registration')
        for value in (response.external_ref, link.external_ref, self.workaround, command['note'], 'Record or review the client response'):
            self.assertNotContains(page, value)
        dossier = page.context['dossiers'][0]
        self.assertTrue(all('payload' in row.get_deferred_fields() for row in dossier.visible_sources))
        self.assertTrue(all({'data', 'snapshot'}.issubset(row.get_deferred_fields()) for row in dossier.visible_records))
        scoped = reverse('client_uat', args=[self.case.pk, self.d.pk])
        self.assertEqual(self.client.get(scoped).status_code, 403)
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(scoped), self.workaround)

    def test_proof_must_refer_to_the_exact_issue_in_the_same_written_approval(self):
        response, review = self.reviewed_response(
            statement='SAMPLE Client Witness approved delivery-build. For SAMPLE-LOGIN-ISSUE-OTHER, use the agreed fictional retry prompt.')
        with self.assertRaisesMessage(ValidationError, 'The same reviewed file must name this issue'):
            delivery_workarounds.record(self.actor, self.case.pk, self.d.pk, rev(self.case),
                                        **self.link_command(response, review))
        self.assertFalse(DeliverySource.objects.filter(dossier=self.d, kind=delivery_workarounds.KIND).exists())
        self.assertEqual(delivery.latest(self.d, 'planning_decision').pk, self.returned.pk)
