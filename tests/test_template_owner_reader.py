"""Native PostgreSQL checks of exact historical owner attestations."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.test import TransactionTestCase
from django.urls import reverse

from apps.core.read_budget import ReadBudget, ReadLimit
from apps.core.services import add_evidence
from apps.documents import template_current as current, template_source_reader as reader
from apps.documents.controlled import register_template
from apps.documents.models import TemplateClaim
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
        inventory_url = reverse('template_owner_pin_detail', args=(self.case.pk, 'decision', decision.pk))
        inventory = self.client.get(inventory_url, {'inventory': 1})
        self.assertContains(inventory, f'{reported.pk}, {recorded.pk}')
        self.assertNotContains(inventory, 'original recorder still holds')
        self.assertEqual(self.client.get(url, {'inventory': 1}).status_code, 404)

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

    def test_selected_history_preserves_order_and_projects_only_metadata(self):
        policy = self.configure()
        recorded = self.claim()
        reported = self.claim(False)
        decision = current.resolve_claims(self.owner, self.case.pk, self.scope.pk, recorded.pk,
                                          [recorded.pk, reported.pk], self.evidence.pk, 'Private decision note', rev(self.case))
        retracted = current.retract_claim(self.owner, self.case.pk, reported.pk, self.evidence.pk,
                                          'Private retraction note', rev(self.case))
        selection = [f'retraction:{retracted.pk}', f'decision:{decision.pk}', f'claim:{recorded.pk}', f'claim:{reported.pk}']
        self.client.force_login(self.observer)
        url = reverse('template_owner_metadata', args=(self.case.pk,))
        queries = []

        def trace(execute, sql, params, many, context):
            queries.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(trace):
            _, records = reader.read_owner_metadata(self.observer, self.case.pk, selection)
        expected = [
            ('retraction', retracted.pk, None), ('decision', decision.pk, policy.pk),
            ('claim', recorded.pk, policy.pk), ('claim', reported.pk, None),
        ]
        self.assertEqual(records, [
            {'kind': kind, 'id': pk, 'policy_id': pin, 'scope_id': self.scope.pk} for kind, pk, pin in expected
        ])
        for column in ('note', 'claim_ids', 'selected_claim_id', 'body', 'envelope', 'actor_id'):
            self.assertFalse(any(f'."{column}"' in sql for sql in queries), column)
        response = self.client.get(url, {'record': selection})
        self.assertContains(response, 'Selected template history')
        self.assertNotContains(response, 'Private decision note')
        self.assertNotContains(response, 'Private retraction note')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.post(url, {'record': selection}).status_code, 405)
        self.assertContains(self.client.get(reverse('template_current', args=(self.case.pk,))), 'Review selected history')

    def test_history_is_atomic_for_missing_foreign_and_hidden_records(self):
        ordinary = self.claim(False)
        foreign_owner, foreign_case = setup_case(username='other-owner')
        foreign_evidence = add_evidence(foreign_owner, foreign_case.pk, 'policy_decision', 'Other case', 'synthetic:other')
        foreign_template = register_template(foreign_owner, foreign_case.pk, 'Other report', DEFINITION,
                                            foreign_evidence.pk, rev(foreign_case))
        foreign_scope = scope(foreign_owner, foreign_case, foreign_evidence, document_type='status_report')
        foreign = claim(foreign_owner, foreign_case, foreign_scope, foreign_template, foreign_evidence, False)
        finance_template = register_template(self.owner, self.case.pk, 'Finance report', {
            'document_type': 'finance_report',
            'required_fields': ['executive_summary', 'financial_metrics', 'bu_totals'],
            'audience_fields': {'internal': ['executive_summary', 'financial_metrics', 'bu_totals']},
            'internal_review_required': False,
        }, self.evidence.pk, rev(self.case))
        finance_scope = scope(self.owner, self.case, self.evidence, document_type='finance_report', audience='internal')
        private = claim(self.owner, self.case, finance_scope, finance_template, self.evidence, False)
        token = f'claim:{ordinary.pk}'
        self.client.force_login(self.observer)
        url = reverse('template_owner_metadata', args=(self.case.pk,))
        for pk in (foreign.pk, private.pk, 2**63 - 1):
            response = self.client.get(url, {'record': [token, f'claim:{pk}']})
            self.assertNotContains(response, f'Claim #{ordinary.pk}', status_code=404)
        # The selected scope is visible although its evidence is also linked
        # to the hidden Finance scope. Historical pointers disclose no source.
        self.assertIsNone(reader.read_source(self.observer, self.case.pk, self.evidence.pk))
        self.assertEqual(len(reader.read_owner_metadata(self.observer, self.case.pk, [token])[1]), 1)

        grant = Grant.objects.create(case=self.case, user=self.observer, action='finance.read')
        selection = [token, f'claim:{private.pk}']

        def revoke():
            try:
                return Grant.objects.filter(pk=grant.pk).update(active=False)
            finally:
                connections.close_all()

        def interleave(execute, sql, params, many, context):
            if 'FROM "documents_templateclaim"' in sql and '"documents_templateclaim"."owner_policy_id"' in sql:
                self.assertEqual(pool.submit(revoke).result(timeout=10), 1)
            return execute(sql, params, many, context)

        with ThreadPoolExecutor(max_workers=1) as pool, connection.execute_wrapper(interleave):
            self.assertEqual(len(reader.read_owner_metadata(self.observer, self.case.pk, selection)[1]), 2)
        self.assertIsNone(reader.read_owner_metadata(self.observer, self.case.pk, selection))

    def test_history_at_selection_limit_uses_the_same_number_of_queries(self):
        claims = TemplateClaim.objects.bulk_create([
            TemplateClaim(scope=self.scope, template=self.template, actor=self.owner,
                          evidence=self.evidence, note='Synthetic recorded claim')
            for _ in range(reader.MAX_OWNER_RECORDS)
        ])
        selection = [f'claim:{record.pk}' for record in claims]
        calls = []

        def trace(execute, sql, params, many, context):
            calls.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(trace):
            reader.read_owner_metadata(self.observer, self.case.pk, selection[:1])
        count = len(calls)
        calls.clear()
        with connection.execute_wrapper(trace):
            self.assertEqual(len(reader.read_owner_metadata(self.observer, self.case.pk, selection)[1]), len(selection))
        self.assertEqual(len(calls), count)

        calls.clear()
        for invalid in ([], selection + ['claim:1'], [selection[0]] * 2, ['claim:01'], ['source:1'], ['claim:٢']):
            with connection.execute_wrapper(trace), self.assertRaises(reader.InvalidOwnerSelection):
                reader.read_owner_metadata(self.observer, self.case.pk, invalid)
        self.assertEqual(calls, [])
        self.client.force_login(self.observer)
        url = reverse('template_owner_metadata', args=(self.case.pk,))
        self.assertContains(self.client.get(url, {'record': [selection[0]] * 2}), 'distinct records', status_code=400)
        with patch.object(reader, 'MAX_QUERIES', 3):
            response = self.client.get(url, {'record': selection[:1]})
        self.assertContains(response, 'within the read limits', status_code=503)
        self.assertNotContains(response, f'Claim #{claims[0].pk}', status_code=503)
