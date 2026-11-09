"""Native PostgreSQL checks of exact historical owner attestations."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse

from apps.core.read_budget import ReadBudget, ReadLimit
from apps.core.services import add_evidence
from apps.documents import template_current as current, template_source_reader as reader
from apps.documents.controlled import register_template
from apps.identity.models import Grant
from apps.policy import scopes
from apps.policy.models import PolicyState
from apps.policy.services import reference_values, register_reference, resolve, save_draft, transition
from .document_helpers import DEFINITION
from .helpers import envelope, rev, setup_case
from .test_policy_scopes import source_version
from .test_template_current import claim, configure, scope


class TemplateOwnerReaderTests(TransactionTestCase):
    def setUp(self):
        self.owner, self.case = setup_case()
        self.evidence = add_evidence(self.owner, self.case.pk, 'policy_decision', 'Synthetic authority', 'synthetic:owner')
        self.template = register_template(self.owner, self.case.pk, 'Status report', DEFINITION,
                                          self.evidence.pk, rev(self.case))
        self.scope = scope(self.owner, self.case, self.evidence, document_type='status_report')
        self.observer = get_user_model().objects.create_user(username='document-observer')
        for action in ('case.read', 'document.read'):
            Grant.objects.create(case=self.case, user=self.observer, action=action)

    def pin(self, record, kind='claim'):
        return reader.read_owner_pin(self.observer, self.case.pk, kind, record.pk)[1]

    def configure(self):
        return configure(self.owner, self.case, self.evidence, [self.template], [(self.scope, self.owner)])

    def claim(self, confirmed=True):
        return claim(self.owner, self.case, self.scope, self.template, self.evidence, confirmed)

    def test_selected_claim_and_decision_use_original_recorder(self):
        self.configure()
        reported = self.claim(False)
        recorded = self.claim()
        decision = current.resolve_claims(self.owner, self.case.pk, self.scope.pk, recorded.pk,
                                          [reported.pk, recorded.pk], self.evidence.pk, 'Exact claims', rev(self.case))
        self.assertEqual(self.pin(reported), {'pinned': False, 'current': False})
        self.assertEqual(self.pin(recorded), {'pinned': True, 'current': True})
        self.assertEqual(self.pin(decision, 'decision'), {'pinned': True, 'current': True})
        self.client.force_login(self.observer)
        url = reverse('template_owner_pin_detail', args=(self.case.pk, 'claim', recorded.pk))
        self.assertContains(self.client.get(url), 'original recorder still holds')
        self.assertIn('no-store', self.client.get(url)['Cache-Control'])
        self.assertEqual(self.client.post(url).status_code, 405)

        Grant.objects.create(case=self.case, user=self.observer, action='document.template')
        Grant.objects.filter(case=self.case, user=self.owner, action='document.template').update(active=False)
        self.assertFalse(self.pin(recorded)['current'])
        self.assertFalse(self.pin(decision, 'decision')['current'])
        Grant.objects.filter(case=self.case, user=self.owner, action='document.template').update(active=True)
        self.configure()
        self.assertFalse(self.pin(recorded)['current'])
        Grant.objects.filter(case=self.case, user=self.observer, action='case.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_scoped_origin_and_engineering_hold(self):
        content = {'template_ids': [self.template.pk], 'retention_days': 30, 'repository': 'internal-versioned',
                   'template_owners': [{'scope_id': self.scope.pk, 'user_id': self.owner.pk}]}
        ref = register_reference(self.owner, self.case.pk, 'fixture:scoped-owner', 'schema:psl/document-storage/v3',
                                 content, self.evidence.pk)
        value = {'artifact_ref': ref.ref, 'artifact_version': ref.version, 'schema_ref': ref.schema_ref, 'sha256': ref.sha256}
        source = source_version(self.owner, self.case, self.evidence, 'project',
                                env=envelope(self.case, current.COMPONENT, value, self.evidence))
        policy = scopes.apply(self.owner, source.pk, self.case.pk, self.evidence.pk, [])
        transition(self.owner, policy.pk, 'validated')
        transition(self.owner, policy.pk, 'active')
        recorded = self.claim()
        queries = []

        def trace(execute, sql, params, many, context):
            queries.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(trace):
            self.assertTrue(self.pin(recorded)['current'])
        for column in ('envelope', 'content', 'binding_paths', 'bindings'):
            matching = [sql for sql in queries if f'."{column}"' in sql]
            self.assertTrue(matching, column)
            self.assertTrue(all('CASE WHEN' in sql for sql in matching), matching)
        self.assertTrue(any('pg_advisory_xact_lock' in sql for sql in queries))
        self.client.force_login(self.observer)
        url = reverse('template_owner_pin_detail', args=(self.case.pk, 'claim', recorded.pk))
        with patch.object(reader, 'ReadBudget', return_value=ReadBudget()) as factory:
            factory.return_value.remaining = 1
            response = self.client.get(url)
        self.assertContains(response, 'could not complete within the read limits', status_code=503)
        self.assertNotContains(response, 'no longer current', status_code=503)
        Grant.objects.filter(case=self.case, user=self.owner, action='policy.read').update(active=False)
        self.assertFalse(self.pin(recorded)['current'])
        Grant.objects.filter(case=self.case, user=self.owner, action='policy.read').update(active=True)
        scopes.transition(self.owner, source.pk, 'revoked')
        self.assertFalse(self.pin(recorded)['current'])

    def test_legacy_storage_shapes_are_readable_as_references_and_invalid_as_policy(self):
        policy = self.configure()
        recorded = self.claim()
        artifact = policy.envelope['value']['artifact_ref']
        expected = reference_values(policy)
        for value in (artifact, [artifact]):
            with self.subTest(value=value):
                legacy = save_draft(self.owner, self.case.pk, envelope(self.case, current.COMPONENT, value, self.evidence))
                stored = type(legacy).objects.defer('envelope').get(pk=legacy.pk)
                self.assertEqual(reference_values(stored, budget=ReadBudget()), expected)
                with self.assertRaises(ValidationError):
                    transition(self.owner, legacy.pk, 'validated')
                # Model a retained invalid row without changing production guards.
                PolicyState.objects.create(configuration=legacy, state='active', actor=self.owner)
                self.assertEqual(resolve(current.COMPONENT, self.case).status, 'INVALID')
                self.assertEqual(resolve(current.COMPONENT, self.case, budget=ReadBudget()).status, 'INVALID')
                self.assertEqual(self.pin(recorded), {'pinned': True, 'current': False})

    def test_budget_rejects_before_driver_receives_json(self):
        policy = self.configure()
        config = type(policy).objects.defer('envelope').get(pk=policy.pk)
        with connection.cursor() as cursor:
            cursor.execute('SELECT OCTET_LENGTH(envelope::text) FROM policy_configuration WHERE id=%s', [config.pk])
            size = cursor.fetchone()[0]
        budget = ReadBudget()
        budget.remaining = size - 1
        with self.assertRaises(ReadLimit):
            budget.load(config, 'envelope')
        self.assertIn('envelope', config.get_deferred_fields())
        self.assertEqual(budget.remaining, size - 1)
        budget.remaining = size
        self.assertEqual(budget.load(config, 'envelope'), policy.envelope)
        self.assertEqual(budget.remaining, 0)
