from contextlib import redirect_stdout
from io import StringIO
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core import setup_rules
from apps.core.models import Audit, Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy import scopes
from apps.policy.models import Configuration
from apps.policy.services import reference_values, register_reference, resolve, save_draft, transition
from tests import document_helpers, railway_setup_rules_walkthrough_seed as seed
from tests.billing_helpers import coverage, stage_policy
from tests.helpers import envelope, rev, setup_case, signed


class SetupRulesTests(TestCase):
    def test_guarded_existing_trial_sees_current_rules_and_two_independent_errors(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user('psl-agent-trial')
        environment = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                       'PGDATABASE': 'isolated-preview', seed.GUARD: '1'}
        with patch.dict('os.environ', environment | {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'Setup walkthrough guard'):
                seed.run()
        with patch.dict('os.environ', environment), redirect_stdout(StringIO()) as output:
            seed.run()
        sample = json.loads(output.getvalue())
        self.assertEqual(sample['case'], str(seed.CASE_ID))
        self.client.force_login(trial)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(sample['rules'])
        self.assertLessEqual(len(queries), setup_rules.BOARD_QUERY_LIMIT + 16)
        self.assertContains(response, 'Current rules')
        self.assertContains(response, 'Keep the balance owed and request proof')
        self.assertContains(response, 'Internal versioned archive for 30 days')
        self.assertContains(response, 'Chief executive')
        self.assertContains(response, reverse('policy', args=[seed.CASE_ID]))
        self.assertNotContains(response, 'D05.decision_action_matrix')
        rows = response.context['rule_rows']
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]['roles'], (seed.ROLE,))
        self.assertEqual(rows[0]['version'], 1)
        self.assertEqual(rows[6]['status'], 'MISSING')
        case = Case.objects.get(pk=seed.CASE_ID)
        before = (case.revision, Audit.objects.filter(case=case).count())
        form = {'role': sample['role'], 'principal': sample['principal'], 'delegate': sample['wrong_person'],
                'starts': sample['starts'], 'ends': sample['invalid_end'], 'effective': sample['effective'],
                'evidence': sample['evidence'], 'revision': rev(case)}
        self.assertContains(self.client.get(sample['delegation']), 'Sample Finance Staff (Finance)')
        denied = self.client.post(sample['delegation'], form)
        self.assertContains(denied, 'Choose someone with a current project management lead assignment.')
        self.assertContains(denied, 'Enter a time after the start.')
        self.assertEqual(denied.context['form']['ends'].value(), sample['invalid_end'])
        self.assertEqual(denied.context['form']['delegate'].value(), str(sample['wrong_person']))
        self.assertFalse(Configuration.objects.filter(case=case, component='D05.delegation_rules').exists())
        self.assertEqual((rev(case), Audit.objects.filter(case=case).count()), before)

        self.assertEqual(self.client.post(sample['delegation'], {
            **form, 'delegate': sample['valid_person'], 'ends': sample['valid_end'],
        }).status_code, 302)
        draft = Configuration.objects.get(case=case, component='D05.delegation_rules')
        self.assertEqual(reference_values(draft)[0]['delegate_id'], sample['valid_person'])
        self.assertEqual(list(draft.states.values_list('state', flat=True)), ['draft'])

    def test_original_role_scope_and_lookup_budget_precede_loading_rule_value(self):
        actor, case = setup_case()
        owner_case = Case.objects.create(title='Source settings', tenant=case.tenant, kind='project', synthetic=True)
        local = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic local policy proof', 'synthetic:setup-rules')
        source_permissions = ('case.read', 'policy.read', 'policy.configure', 'policy.activate', 'evidence.add', 'rfp.read')
        Grant.objects.bulk_create([Grant(case=owner_case, user=actor, action=action) for action in source_permissions])
        proof = add_evidence(actor, owner_case.pk, 'policy_decision', 'Synthetic shared policy source', 'synthetic:setup-rules')
        ref = register_reference(actor, owner_case.pk, 'sample:rules', 'schema:psl/decision-actions/v2',
                                 {'rfp': {'assignment_roles': ['PM']}}, proof.pk)
        source = save_draft(actor, owner_case.pk, envelope(owner_case, setup_rules.MATRIX,
            {'artifact_ref': ref.ref, 'artifact_version': ref.version, 'sha256': ref.sha256, 'schema_ref': ref.schema_ref}, proof))
        transition(actor, source.pk, 'validated')
        reusable = scopes.create(actor, source.pk, 'organization', owner_case.tenant, [])
        scopes.transition(actor, reusable.pk, 'validated')
        scopes.transition(actor, reusable.pk, 'active')
        applied = scopes.apply(actor, reusable.pk, case.pk, local.pk, [])
        transition(actor, applied.pk, 'validated')
        transition(actor, applied.pk, 'active')

        self.client.force_login(actor)
        url = reverse('workspace_settings', args=[case.pk])
        rows = self.client.get(url, {'area': 'rules'}).context['rule_rows']
        self.assertEqual(rows[0]['roles'], ('PM',))
        self.assertEqual(rows[0]['version'], applied.revision)
        revoke = Grant.objects.get(case=owner_case, user=actor, action='rfp.read')
        Grant.objects.filter(pk=revoke.pk).update(active=False)
        with patch.object(setup_rules, 'resolve', wraps=resolve) as reader:
            denied = self.client.get(url, {'area': 'rules'}).context['rule_rows'][0]
        self.assertEqual(denied['status'], 'UNAVAILABLE')
        self.assertIsNone(denied['version'])
        self.assertFalse(denied['roles'])
        self.assertNotIn(setup_rules.MATRIX, [call.args[0] for call in reader.call_args_list])
        Grant.objects.filter(pk=revoke.pk).update(active=True)
        with patch.object(setup_rules, 'COMPONENT_QUERY_LIMIT', 0):
            bounded = self.client.get(url, {'area': 'rules'}).context['rule_rows'][0]
        self.assertEqual(bounded['status'], 'UNKNOWN')
        self.assertFalse(bounded['roles'])
        self.assertIsNone(bounded['version'])

    def test_billing_terms_follow_only_exact_signed_agreement_and_domain_read(self):
        actor, case = setup_case()
        sources = signed(actor, case)
        contract = coverage(actor, case)
        stage_policy(actor, case, contract, sources['signature'])
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic separate rule', 'synthetic:setup-rules')
        document_helpers.artifact(actor, case, setup_rules.MATRIX, 'schema:psl/decision-actions/v2',
                                  {'rfp': {'outcome_roles': ['CEO']}}, proof)
        self.client.force_login(actor)
        url = reverse('workspace_settings', args=[case.pk])
        shown = self.client.get(url, {'area': 'rules'}).context['rule_rows']
        self.assertEqual(shown[6]['value'], 'From the signed agreement')
        self.assertTrue(shown[6]['details'])
        self.assertEqual(shown[7]['roles'], ('CEO',))
        Grant.objects.filter(case=case, user=actor, action='finance.read').update(active=False)
        with patch.object(setup_rules, 'resolve', wraps=resolve) as reader:
            hidden = self.client.get(url, {'area': 'rules'}).context['rule_rows']
        self.assertEqual(hidden[6]['status'], 'UNAVAILABLE')
        self.assertIsNone(hidden[6]['url'])
        self.assertFalse(hidden[6]['details'])
        self.assertNotIn(setup_rules.PAYMENT_TERMS, [call.args[0] for call in reader.call_args_list])
        self.assertEqual(hidden[7]['roles'], ('CEO',))
