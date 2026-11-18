import copy

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.agents.costing import investigate
from apps.identity.models import Grant
from apps.pmo import costing, costing_proposals as domain
from apps.pmo.costing_proposal_models import CostingProposal, CostingProposalDecision
from apps.policy.costing_proposal_validators import COMPONENT
from apps.policy.services import resolve, transition
from tests.costing_helpers import evidence, fixture, run, policy as costing_policy
from tests.helpers import rev
from tests.operator_helpers import policy


class CostingProposalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = fixture()
        value = copy.deepcopy(cls.data['rule'].payload)
        value['calculator_version'] = 'v2'
        value['parameters'][0]['value'] = '12.00'
        cls.source = evidence(cls.data, 'p14_rule', value)

    def proposal(self, key='change'):
        data = self.data
        return domain.propose(data['actor'], data['case'].pk, data['rule'].pk,
                              self.source.pk, 'SAMPLE revised rate evidence', key)

    def configure(self, reviewer=None, role='PMO'):
        data = self.data
        return policy(data, COMPONENT, {'reviewer_id': (reviewer or data['owner']).pk,
            'reviewer_role': role, 'independent_review': True})

    def decision(self, proposal, verdict='confirm', actor=None):
        data = self.data
        return domain.decide(actor or data['owner'], data['case'].pk, proposal.pk,
            verdict, 'SAMPLE exact version reviewed', data['review_evidence'].pk)

    def test_pending_proposal_retains_current_calculator_and_can_be_withdrawn_without_policy(self):
        data = self.data
        proposal = self.proposal()
        self.assertEqual(run(data).result['values'][0]['value'], '20.00')
        self.assertEqual(resolve(COMPONENT, data['case']).status, 'MISSING')
        with self.assertRaises(ValidationError):
            self.decision(proposal)
        result = self.decision(proposal, 'withdraw', data['actor'])
        self.assertIsNone(result.rule_id)
        self.assertEqual(run(data, key='after-withdrawal').result['values'][0]['value'], '20.00')

    def test_independent_review_records_exact_native_source_with_original_preparer_and_fresh_owner_checks(self):
        data = self.data
        proposal = self.proposal()
        self.configure()
        decision = self.decision(proposal)
        self.assertEqual(decision.rule.version, 2)
        self.assertEqual(decision.rule.actor, data['actor'])
        self.assertEqual(decision.rule.sha256, proposal.sha256)
        self.assertEqual(decision.actor, data['owner'])
        self.assertEqual(self.decision(proposal).pk, decision.pk)
        with self.assertRaises(ValidationError):
            costing.confirmed(decision.rule)
        with self.assertRaises(ValidationError):
            run(data)
        with self.assertRaises(ValidationError):
            self.decision(proposal, 'return')

    def test_proposer_and_unassigned_reviewer_cannot_confirm_and_configured_path_has_no_legacy_bypass(self):
        data = self.data
        proposal = self.proposal()
        self.configure()
        with self.assertRaises(PermissionDenied):
            self.decision(proposal, actor=data['actor'])
        with self.assertRaises(PermissionDenied):
            self.decision(proposal, actor=data['tester'])
        with self.assertRaises(ValidationError):
            costing.capture_rule(data['actor'], data['case'].pk, data['rule'].reference,
                                 self.source.pk, predecessor=data['rule'].pk)
        self.assertEqual(run(data).result['status'], 'known')

    def test_return_and_revoke_do_not_remove_the_current_calculator(self):
        data = self.data
        proposal = self.proposal()
        config = self.configure()
        self.assertIsNone(self.decision(proposal, 'return').rule_id)
        next_proposal = self.proposal('revised-proposal')
        transition(data['actor'], config.pk, 'revoked')
        with self.assertRaises(ValidationError):
            self.decision(next_proposal)
        self.assertEqual(run(data).result['status'], 'known')

    def test_source_actor_reviewer_and_role_permissions_are_current(self):
        data = self.data
        proposal = self.proposal()
        self.configure()
        for actor, action in [(data['actor'], 'costing.capture'),
                              (data['actor'], 'costing.source.read'),
                              (data['owner'], 'costing.rule.review')]:
            grant = Grant.objects.get(case=data['case'], user=actor, action=action)
            grant.active = False
            grant.save(update_fields=['active'])
            with self.assertRaises(PermissionDenied):
                self.decision(proposal)
            grant.active = True
            grant.save(update_fields=['active'])
        self.configure(data['owner'], role='CEO')
        with self.assertRaises(PermissionDenied):
            self.decision(proposal)
        self.assertFalse(CostingProposalDecision.objects.exists())

    def test_proposal_intent_stale_writes_and_real_sql_immutability(self):
        data = self.data
        proposal = self.proposal()
        self.assertEqual(self.proposal().pk, proposal.pk)
        with self.assertRaises(ValidationError):
            domain.propose(data['actor'], data['case'].pk, data['rule'].pk,
                self.source.pk, 'Different intent', 'change')
        self.configure()
        with self.assertRaises(ValidationError):
            domain.decide(data['owner'], data['case'].pk, proposal.pk, 'confirm',
                'Stale decision', data['review_evidence'].pk, expected=rev(data['case']) - 1)
        decision = self.decision(proposal)
        for model, pk, field, value in [(CostingProposal, proposal.pk, 'reason', 'overwrite'),
                (CostingProposalDecision, decision.pk, 'verdict', 'withdraw')]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=pk).update(**{field: value})
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('DELETE FROM ' + model._meta.db_table + ' WHERE id = %s', [pk])

    def test_ui_own_waiting_reviewer_return_and_source_access(self):
        data = self.data
        proposal = self.proposal()
        self.configure()
        url = reverse('costing_proposal', args=[data['case'].pk, proposal.pk])
        self.client.force_login(data['actor'])
        page = self.client.get(url)
        self.assertContains(page, 'Withdraw proposal')
        self.assertNotContains(page, 'Record decision')
        self.assertContains(page, '12.00')
        self.client.force_login(data['owner'])
        self.assertContains(self.client.get(url), 'Record decision')
        response = self.client.post(url, {'revision': rev(data['case']), 'verdict': 'return',
            'note': 'SAMPLE needs clearer rate evidence', 'evidence': data['review_evidence'].pk})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(url), 'SAMPLE needs clearer rate evidence')
        Grant.objects.filter(case=data['case'], user=data['owner'],
                             action='costing.source.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_typed_unset_reviewer_and_bounded_agent_inventory(self):
        data = self.data
        proposal = self.proposal()
        policy(data, COMPONENT, {'reviewer_id': None, 'reviewer_role': None, 'independent_review': True})
        self.assertEqual(resolve(COMPONENT, data['case']).status, 'ACTIVE')
        with self.assertRaisesMessage(ValidationError, 'Choose the independent calculator reviewer'):
            self.decision(proposal)
        result = investigate(data['actor'], data['case'].pk)
        self.assertEqual(result.result['pending_version_proposals'], [{'proposal': proposal.pk,
            'base_version': 1, 'status': 'awaiting_independent_review'}])
        self.assertNotIn('12.00', str(result.result))
        self.assertFalse(result.result['case_cost_approved'])

    def test_reviewed_source_continues_through_native_owners_examples_activation_and_calculation(self):
        data = self.data
        original = run(data)
        proposal = self.proposal()
        review_policy = self.configure()
        decision = self.decision(proposal)
        rule = decision.rule
        rule_review = costing.review(data['owner'], data['case'].pk, rule.pk, None,
            'confirm', 'source-owner-confirm', data['review_evidence'].pk)
        examples = copy.deepcopy(data['oracle'].payload)
        examples.update(rule_sha256=rule.sha256, calculator_version='v2')
        examples['scenarios'][0]['expected']['values'][0]['value'] = '24.00'
        examples['scenarios'][2]['expected']['values'][0]['value'] = '1.21'
        oracle = costing.capture_oracle(data['tester'], data['case'].pk, rule.pk,
            'independent-v2', evidence(data, 'p14_oracle', examples).pk)
        oracle_review = costing.review(data['tester'], data['case'].pk, rule.pk, oracle.pk,
            'confirm', 'examples-owner-confirm', data['review_evidence'].pk)
        value = {'rule_id': rule.pk, 'rule_sha256': rule.sha256, 'rule_review_id': rule_review.pk,
                 'oracle_id': oracle.pk, 'oracle_sha256': oracle.sha256,
                 'oracle_review_id': oracle_review.pk}
        costing_policy(data, value)
        result = run(data, key='reviewed-version-2')
        self.assertEqual(result.result['values'][0]['value'], '24.00')
        self.assertTrue(all(row['matches'] for row in result.result['oracle_results']))
        original.refresh_from_db()
        self.assertEqual(original.result['values'][0]['value'], '20.00')
        self.assertFalse(costing.report(data['actor'], data['case'].pk, original.pk)['current_usable'])
        transition(data['actor'], review_policy.pk, 'revoked')
        with self.assertRaises(ValidationError):
            costing.current_source(rule)
        self.assertFalse(costing.report(data['actor'], data['case'].pk, result.pk)['current_usable'])


class CostingProposalTemplateTests(SimpleTestCase):
    def test_template_and_typed_form_compile(self):
        from django.template.loader import get_template
        from apps.pmo.costing_proposal_views import DecisionForm

        self.assertIsNotNone(get_template('pmo/costing_proposal.html'))
        self.assertIn('note', DecisionForm.base_fields)
