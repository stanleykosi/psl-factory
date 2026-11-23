from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Grant
from apps.pmo import costing, costing_studio
from apps.pmo.costing_models import CostingRule
from apps.policy import scopes
from apps.policy.costing_drafts import draft_costing_policy
from apps.policy.services import transition
from tests.costing_helpers import evidence, fixture, run
from tests.helpers import project_evidence, rev, setup_case


class StudioCostingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.studio = fixture()
        data = cls.studio
        draft = draft_costing_policy(data['actor'], data['case'].pk, data['policy_value'],
            data['sources']['policy_decision'].pk, timezone.now() - timedelta(seconds=1))
        transition(data['actor'], draft.pk, 'validated')
        cls.source = scopes.create(data['actor'], draft.pk, 'organization', data['case'].tenant, [])
        scopes.transition(data['actor'], cls.source.pk, 'validated')
        scopes.transition(data['actor'], cls.source.pk, 'active')
        actor, case = setup_case(username='studio-project-preparer')
        cls.project = {'actor': actor, 'case': case, 'sources': project_evidence(actor, case)}
        cls.project['inputs'] = evidence(cls.project, 'p14_inputs', data['values']['scenarios'][0]['inputs'])
        Grant.objects.bulk_create([Grant(case=data['case'], user=actor, action=action)
            for action in ['case.read', 'costing.read', 'costing.source.read']])

    def apply(self):
        project = self.project
        draft = costing_studio.draft_application(project['actor'], project['case'].pk,
            self.source.pk, project['sources']['policy_decision'].pk,
            timezone.now() - timedelta(seconds=1))
        transition(project['actor'], draft.pk, 'validated')
        transition(project['actor'], draft.pk, 'active')
        return draft

    def test_shared_calculator_uses_original_rule_examples_and_project_inputs_without_copying_sources(self):
        project = self.project
        self.apply()
        result = run(project)
        self.assertEqual(result.case_id, project['case'].pk)
        self.assertEqual(result.rule_id, self.studio['rule'].pk)
        self.assertEqual(result.result['values'][0]['value'], '20.00')
        self.assertFalse(CostingRule.objects.filter(case=project['case']).exists())
        binding = costing.bind(project['actor'], project['case'].pk, result.pk)
        self.assertEqual(binding.costing.case_id, project['case'].pk)
        costing.verify_costing(binding.costing, project['sources']['plan'].pk)

    def test_scope_revocation_holds_only_dependent_calculation_and_retains_prior_result(self):
        project = self.project
        self.apply()
        result = run(project)
        scopes.transition(self.studio['actor'], self.source.pk, 'revoked')
        with self.assertRaises(ValidationError):
            run(project, key='after-source-revocation')
        self.assertFalse(costing.report(project['actor'], project['case'].pk, result.pk)['current_usable'])
        result.refresh_from_db()
        self.assertEqual(result.result['values'][0]['value'], '20.00')
        self.assertEqual(evidence(project, 'p14_inputs', self.studio['values']['scenarios'][1]['inputs']).kind,
                         'p14_inputs')

    def test_current_project_preparer_needs_original_studio_source_access(self):
        project = self.project
        self.apply()
        Grant.objects.filter(case=self.studio['case'], user=project['actor'],
                             action='costing.source.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            run(project)
        self.client.force_login(project['actor'])
        page = self.client.get(reverse('costing', args=[project['case'].pk]))
        self.assertNotContains(page, 'Studio calculator used by this project')

    def test_original_owner_authority_is_revalidated_in_the_source_scope(self):
        project = self.project
        self.apply()
        Grant.objects.filter(case=self.studio['case'], user=self.studio['tester'],
                             action='costing.oracle.review').update(active=False)
        with self.assertRaises(ValidationError):
            run(project)

    def test_cross_organization_and_synthetic_boundary_cannot_apply_a_studio_source(self):
        project = self.project
        for changed in ['tenant', 'synthetic']:
            case = project['case']
            original = getattr(case, changed)
            setattr(case, changed, 'unrelated-organization' if changed == 'tenant' else False)
            case.save(update_fields=[changed])
            with self.assertRaises(ValidationError):
                self.apply()
            setattr(case, changed, original)
            case.save(update_fields=[changed])

    def test_project_ui_selects_exact_studio_source_and_keeps_activation_separate(self):
        project = self.project
        self.client.force_login(project['actor'])
        url = reverse('costing', args=[project['case'].pk])
        self.assertContains(self.client.get(url), 'Use a reviewed studio calculator')
        response = self.client.post(url, {'action': 'studio_policy',
            'revision': rev(project['case']), 'studio_source': self.source.pk,
            'evidence': project['sources']['policy_decision'].pk,
            'effective_from': (timezone.now() - timedelta(seconds=1)).isoformat()})
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(ValidationError):
            run(project)
        self.apply()
        self.assertContains(self.client.get(url), 'Studio calculator used by this project')

    def test_explicit_studio_pins_cannot_substitute_different_rule_or_examples(self):
        project = self.project
        value = dict(self.studio['policy_value'], studio_source_id=self.source.pk, rule_id=999999)
        draft = draft_costing_policy(project['actor'], project['case'].pk, value,
            project['sources']['policy_decision'].pk, timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            transition(project['actor'], draft.pk, 'validated')

    def test_normal_commercial_intake_and_start_form_use_the_exact_shared_rule(self):
        from apps.pmo import commercial_intake
        from apps.workflows.factory_views import CommercialStartForm
        from apps.agents.costing import investigate

        project = self.project
        self.apply()
        form = CommercialStartForm(project['actor'], case_id=project['case'].pk)
        self.assertIn(self.studio['rule'], form.fields['rule_id'].queryset)
        self.assertIn(self.studio['oracle'], form.fields['oracle_id'].queryset)
        value = {key: None for key in commercial_intake.VALUE['properties']}
        value.update(rule_id=self.studio['rule'].pk, oracle_id=self.studio['oracle'].pk,
                     inputs=project['inputs'].pk)
        commercial_intake.validate_sources(project['actor'], project['case'], value)
        result = investigate(project['actor'], project['case'].pk)
        self.assertEqual(result.result['studio_source']['rule'], self.studio['rule'].pk)
        self.assertNotIn('20.00', str(result.result))
