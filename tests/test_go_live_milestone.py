"""Optional human PM milestone after real native go-live publications and sign-off."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.finance.models import BillingCoverage, Handoff, InvoicePreparation
from apps.identity.models import Grant
from apps.pmo.models import Baseline, Milestone
from apps.policy.go_live_milestone_validators import COMPONENT
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_go_live, factory_go_live_milestone as handoff
from apps.workflows.models import Outbox
from apps.workflows.services import run_once
from tests.helpers import rev, setup_case
from tests.test_factory_go_live import accept, review, setup


class GoLiveMilestoneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = f = setup()
        factory.run_until_wait(f.work.pk)
        review(f)
        factory.run_until_wait(f.work.pk)
        cls.acceptance = accept(f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        if f.work.status != 'verified':
            raise AssertionError(f.work.finding)
        cls.decision = f.evidence('policy_decision', 'Synthetic owner approved close of rollout for this dossier.')
        cls.source_owner = get_user_model().objects.create_user('synthetic-milestone-source-owner')
        Grant.objects.create(case=f.case, user=cls.source_owner, action='evidence.add')
        cls.completion = add_evidence(
            cls.source_owner, f.case.pk, 'completion',
            'Synthetic completion observation independent of the release and signatures.', 'synthetic:milestone-test',
        )
        cls.baseline_id = Baseline.objects.get(case=f.case).signed_id

    def setUp(self):
        self.f = self.fixture
        self.case = self.f.case
        self.work = self.f.work
        self.url = reverse('factory_detail', args=[self.work.pk])
        self.policy_url = reverse('policy', args=[self.case.pk])
        self.client.force_login(self.f.actor)

    def mapping_data(self, name='Close of rollout'):
        return {'dossier_id': self.f.d.pk, 'baseline_signature_id': self.baseline_id, 'milestone_name': name}

    def draft_from_page(self, name='Close of rollout'):
        response = self.client.post(self.url, {
            'action': 'draft_milestone_mapping', 'revision': self.work.revision,
            'case_revision': rev(self.case), 'milestone_name': name, 'owner_decision': self.decision.pk,
        })
        self.assertRedirects(response, self.policy_url, fetch_redirect_response=False)
        config = Configuration.objects.filter(case=self.case, component=COMPONENT).latest('revision')
        self.assertEqual(config.states.get().state, 'draft')
        return config

    def approve(self, configuration):
        for action in ('validated', 'active'):
            self.assertRedirects(self.client.post(self.policy_url, {
                'action': action, 'configuration': configuration.pk,
            }), self.policy_url, fetch_redirect_response=False)
        self.assertEqual(configuration.states.latest('pk').state, 'active')

    def record_data(self, configuration):
        return {
            'action': 'record_milestone', 'revision': self.work.revision, 'case_revision': rev(self.case),
            'milestone_mapping': configuration.pk, 'acceptance': self.acceptance.pk,
            'completion_evidence': self.completion.pk,
        }

    def assert_no_milestone(self):
        self.assertFalse(Milestone.objects.filter(case=self.case).exists())
        self.assertFalse(Outbox.objects.filter(case=self.case).exists())
        self.assertFalse(Handoff.objects.filter(case=self.case).exists())

    def test_current_pmo_lead_confirms_exact_milestone_and_creates_finance_handoff(self):
        from tests.helpers import admit_department

        lead, member = admit_department(self.f.actor, self.case, 'pmo-lead', member=True)
        url = f'/api/v1/work/{self.work.pk}'
        command = {'expected_revision': self.work.revision, 'case_revision': rev(self.case),
                   'action': 'confirm_and_complete', 'name': 'Production rollout',
                   'acceptance_id': self.acceptance.pk, 'evidence_id': self.completion.pk,
                   'note': 'Checked the live rollout and accepted delivery record.'}
        self.client.force_login(member)
        self.assertIn(self.client.post(url + '/go-live-milestone', command, content_type='application/json').status_code,
                      (403, 404))
        self.assert_no_milestone()
        self.client.force_login(lead)
        panel = self.client.get(url + '/go-live-replies')
        self.assertEqual(panel.status_code, 200, panel.content)
        self.assertTrue(panel.json()['milestone']['can_confirm'], panel.json())
        wrong = self.client.post(url + '/go-live-milestone', {**command, 'evidence_id': self.decision.pk},
                                 content_type='application/json')
        self.assertGreaterEqual(wrong.status_code, 400)
        self.assert_no_milestone()
        response = self.client.post(url + '/go-live-milestone', command, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        milestone = Milestone.objects.get(case=self.case)
        self.assertEqual((milestone.completed_by_id, milestone.evidence_id), (lead.pk, self.completion.pk))
        readback = self.client.get(url + '/go-live-replies').json()['milestone']
        self.assertEqual(readback['confirmation']['actor_id'], lead.pk)
        self.assertEqual(readback['confirmation']['note'], command['note'])
        self.assertEqual(readback['recorded_id'], milestone.pk)
        self.assertTrue(Outbox.objects.filter(case=self.case, milestone=milestone, status='pending').exists())
        self.assertTrue(run_once(case_id=self.case.pk))
        self.assertTrue(Handoff.objects.filter(case=self.case).exists())
        duplicate = self.client.post(url + '/go-live-milestone', {**command, 'case_revision': rev(self.case)},
                                     content_type='application/json')
        self.assertGreaterEqual(duplicate.status_code, 400)
        self.assertEqual(Milestone.objects.filter(case=self.case).count(), 1)

    def test_approved_mapping_allows_one_explicit_pm_record_and_existing_internal_handoff(self):
        self.assertEqual(connection.vendor, 'postgresql')
        page = self.client.get(self.url)
        self.assertContains(page, 'Milestone handoff settings')
        self.assertContains(page, 'Actual PM and Client sign-off recorded')
        self.assertNotContains(page, 'Confirm milestone completion')
        self.assertContains(self.client.get(reverse('case', args=[self.case.pk])), 'Complete a milestone')
        self.assert_no_milestone()
        configuration = self.draft_from_page()
        self.assertNotContains(self.client.get(self.url), 'Confirm milestone completion')
        self.assertContains(self.client.post(self.url, self.record_data(configuration)),
                            'An approved milestone mapping must be current for this project and delivery.')
        self.assert_no_milestone()
        self.approve(configuration)
        page = self.client.get(self.url)
        form_state = page.context['milestone_panel']['completion']
        self.assertEqual(form_state['name'], 'Close of rollout')
        self.assertEqual(form_state['acceptance'], self.acceptance.pk)
        self.assertEqual([source['pk'] for source in form_state['sources']], [self.completion.pk])
        self.assertNotContains(page, self.completion.body)
        self.assert_no_milestone()

        data = self.record_data(configuration)
        self.assertRedirects(self.client.post(self.url, data), self.url, fetch_redirect_response=False)
        milestone = Milestone.objects.get(case=self.case)
        self.assertEqual((milestone.name, milestone.evidence_id, milestone.completed_by_id),
                         ('Close of rollout', self.completion.pk, self.f.actor.pk))
        job = Outbox.objects.get(case=self.case, milestone=milestone)
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.payload, {
            'milestone_id': milestone.pk, 'name': milestone.name,
            'evidence_id': self.completion.pk, 'evidence_sha256': self.completion.sha256,
        })
        self.assertFalse(Handoff.objects.filter(case=self.case).exists())
        proof = factory_go_live.verify(self.work, self.f.actor)
        trace = Audit.objects.get(case=self.case, action=handoff.RECORDED)
        for key, value in {
            'work': self.work.pk, 'head': self.work.source_head_id, 'dossier': self.f.d.pk,
            'configuration': configuration.pk, 'baseline_signature': self.baseline_id,
            'acceptance': self.acceptance.pk, 'report_version': proof['document_version'],
            'receipt': self.acceptance.data['receipt_id'], 'evidence': self.completion.pk, 'milestone': milestone.pk,
        }.items():
            self.assertEqual(trace.data[key], value)
        page = self.client.get(self.url)
        self.assertContains(page, 'Milestone completed')
        self.assertNotContains(page, 'Confirm milestone completion')
        self.assertContains(self.client.post(self.url, data), 'Stale revision')
        successor = self.draft_from_page('Different proposed milestone')
        self.approve(successor)
        self.assertContains(self.client.post(self.url, self.record_data(successor)),
                            'A milestone has already been recorded from this go-live dossier.')
        self.assertEqual(Milestone.objects.filter(case=self.case).count(), 1)
        self.assertEqual(Outbox.objects.filter(case=self.case).count(), 1)
        self.assertEqual(Audit.objects.filter(case=self.case, action=handoff.RECORDED).count(), 1)
        self.assertTrue(run_once(case_id=self.case.pk))
        self.assertFalse(run_once(case_id=self.case.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, 'confirmed')
        self.assertEqual(Handoff.objects.get(case=self.case).operation_key, job.operation_key)
        self.assertFalse(BillingCoverage.objects.filter(case=self.case).exists())
        self.assertFalse(InvoicePreparation.objects.filter(handoff__case=self.case).exists())

    def test_current_role_and_source_proof_are_required_at_submit(self):
        configuration = self.draft_from_page()
        self.approve(configuration)
        self.assertContains(self.client.get(self.url), 'Confirm milestone completion')
        data = self.record_data(configuration)
        self.assertContains(self.client.post(self.url, {**data, 'revision': self.work.revision - 1}),
                            'Go-live work changed')
        self.assertContains(self.client.post(self.url, {**data, 'acceptance': self.acceptance.pk + 1}),
                            'Go-live acceptance changed')
        self.assertContains(self.client.post(self.url, {**data, 'completion_evidence': self.f.e['completion'].pk}),
                            'Choose separate current project completion evidence')
        other_pm = get_user_model().objects.create_user('synthetic-milestone-unassigned-pm')
        Grant.objects.bulk_create([Grant(case=self.case, user=other_pm, action=action) for action in
                                   ('case.read', 'factory.read', 'delivery.read', 'milestone.complete')])
        self.client.force_login(other_pm)
        self.assertNotContains(self.client.get(self.url), 'Confirm milestone completion')
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.client.force_login(self.f.actor)

        successor = self.draft_from_page('Confirmed rollout complete')
        self.approve(successor)
        self.assertContains(self.client.post(self.url, data), 'The approved milestone mapping changed.')
        data = self.record_data(successor)
        grant = Grant.objects.get(case=self.case, user=self.source_owner, action='evidence.add')
        Grant.objects.filter(pk=grant.pk).update(active=False)
        self.assertNotContains(self.client.get(self.url), 'Confirm milestone completion')
        self.assertContains(self.client.post(self.url, data), 'Choose separate current project completion evidence')
        Grant.objects.filter(pk=grant.pk).update(active=True)
        completion_grant = Grant.objects.get(case=self.case, user=self.f.actor, action='milestone.complete')
        Grant.objects.filter(pk=completion_grant.pk).update(active=False)
        self.assertNotContains(self.client.get(self.url), 'Confirm milestone completion')
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        Grant.objects.filter(pk=completion_grant.pk).update(active=True)
        Grant.objects.filter(case=self.case, user=self.f.actor, action='delivery.manage').update(active=False)
        self.assertNotContains(self.client.get(self.url), 'Confirm milestone completion')
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.assert_no_milestone()

    def test_typed_mapping_rejects_wrong_baseline_case_or_decision_before_activation(self):
        for invalid in ({
            'dossier_id': self.f.d.pk + 1,
        }, {
            'baseline_signature_id': self.baseline_id + 1,
        }, {
            'milestone_name': '  ',
        }):
            draft = draft_operator_policy(self.f.actor, self.case.pk, COMPONENT,
                {**self.mapping_data(), **invalid}, self.decision.pk, timezone.now())
            with self.assertRaises(ValidationError):
                transition(self.f.actor, draft.pk, 'validated')
            self.assertEqual(draft.states.get().state, 'draft')
        foreign_actor, foreign_case = setup_case(username='synthetic-foreign-milestone-decision')
        foreign_decision = add_evidence(foreign_actor, foreign_case.pk, 'policy_decision',
            'Decision registered for a separate synthetic project.', 'synthetic:milestone-test')
        response = self.client.post(self.url, {
            'action': 'draft_milestone_mapping', 'revision': self.work.revision,
            'case_revision': rev(self.case), 'milestone_name': 'Close of rollout', 'owner_decision': foreign_decision.pk,
        })
        self.assertContains(response, 'Choose current owner-decision evidence from this project.')
        self.assertNotContains(self.client.get(self.url), 'Confirm milestone completion')
        self.assertTrue(all(config.states.count() == 1
                            for config in Configuration.objects.filter(case=self.case, component=COMPONENT)))
        self.assert_no_milestone()
