from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case, Evidence
from apps.identity.models import Grant
from apps.pmo import costing
from apps.pmo.costing_models import CostingOracle, CostingRun
from apps.pmo.costing_proposal_models import CostingProposalDecision
from tests.helpers import rev
from tests.railway_costing_review_seed import CASE_ID, TRIAL, activate_reviewed, prepare, supplied


class CostingReviewFixtureTests(TestCase):
    def setUp(self):
        self.trial = get_user_model().objects.create_user(TRIAL)
        self.sample = prepare()
        self.case = Case.objects.get(pk=CASE_ID)
        self.client.force_login(self.trial)

    def test_independent_expected_examples_exact_review_then_current_activation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = self.sample
        with self.assertRaisesMessage(RuntimeError, 'actual exact Trial proposal confirmation'):
            activate_reviewed()
        proof = Evidence.objects.get(pk=data['example_proof'])
        self.assertEqual(proof.created_by_id, data['oracle_owner'])
        self.assertNotEqual(proof.created_by_id, self.trial.pk)
        default = self.client.get(data['url'])
        self.assertContains(default, 'Compare proposed examples')
        self.assertContains(default, 'Sample independent version 2 examples')
        normal = default.context['selected_example']
        self.assertFalse(normal['before_matches'])
        self.assertTrue(normal['after_matches'])
        self.assertEqual((normal['before']['values'][0]['value'], normal['after']['values'][0]['value'],
                          normal['expected']['values'][0]['value']), ('20.00', '24.00', '24.00'))
        cases = self.client.get(data['comparison'] + '&example=rounding')
        self.assertContains(cases, '1.21')
        self.assertTrue(cases.context['selected_example']['after_matches'])
        unknown = self.client.get(data['comparison'] + '&example=unknown')
        self.assertEqual(unknown.context['selected_example']['after']['status'], 'held')
        self.assertIsNone(unknown.context['selected_example']['after']['values'][0]['value'])
        self.assertTrue(unknown.context['selected_example']['after_matches'])
        original = self.client.get(data['url'], {'examples': data['oracle']}).context['selected_example']
        self.assertEqual(original['expected']['values'][0]['value'], '20.00')
        self.assertFalse(original['after_matches'])

        self.assertRedirects(self.client.post(data['url'], {'revision': rev(self.case), 'verdict': 'confirm',
            'note': 'SAMPLE checked all independent matches', 'evidence': data['trial_proof']}), data['url'])
        reviewed = self.client.get(data['url'])
        self.assertContains(reviewed, 'SAMPLE checked all independent matches')
        self.assertNotContains(reviewed, 'is active for new calculations')
        confirmed = CostingProposalDecision.objects.get(proposal_id=data['proposal'], actor=self.trial)
        self.assertFalse(CostingOracle.objects.filter(rule=confirmed.rule).exists())
        activation = activate_reviewed()
        self.assertEqual(activation['decision'], confirmed.pk)
        self.assertEqual(costing.configured(self.case, self.trial)[1].pk, confirmed.rule_id)
        self.assertEqual(CostingOracle.objects.get(rule=confirmed.rule).evidence_id, proof.pk)
        self.assertEqual(CostingRun.objects.get(pk=activation['new_run']).result['values'][0]['value'], '24.00')
        self.assertEqual(CostingRun.objects.get(pk=data['old_run']).result['values'][0]['value'], '20.00')
        self.assertContains(self.client.get(data['url']), 'Version 2 is active for new calculations')
        self.assertTrue(activate_reviewed()['activation_preserved'])

    def test_only_current_independent_author_is_eligible_to_supply_the_proposal_examples(self):
        data = self.sample
        maker = get_user_model().objects.get(pk=data['maker'])
        proof = Evidence.objects.get(pk=data['example_proof'])
        wrong_actor = supplied(maker, self.case, 'p14_oracle', proof.body, 'same-payload-wrong-author')
        self.assertEqual(self.client.get(data['url'], {'proposed_examples': wrong_actor.pk}).status_code, 404)
        Grant.objects.filter(case=self.case, user_id=data['oracle_owner'], action='costing.oracle.review').update(active=False)
        self.assertEqual(self.client.get(data['comparison']).status_code, 404)
        default = self.client.get(data['url'])
        self.assertNotContains(default, 'Sample independent version 2 examples')
        self.assertContains(default, 'Differs from expected result')
        self.assertFalse(CostingProposalDecision.objects.filter(proposal_id=data['proposal']).exists())
