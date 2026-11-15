from django.db import connection
from django.test import TestCase

from apps.core.services import add_evidence
from apps.policy.services import resolve, save_draft, transition
from tests.helpers import activate, envelope, setup_case


class PolicyResolutionLoadingTests(TestCase):
    component = 'D04.iana_timezone'

    def setUp(self):
        self.actor, self.case = setup_case()
        self.evidence = add_evidence(self.actor, self.case.pk, 'policy_decision',
                                     'Synthetic timezone choice', 'synthetic:resolver')

    def resolution_queries(self):
        queries = []

        def capture(execute, sql, params, many, context):
            if sql.lstrip().startswith('SELECT') and 'FROM "policy_configuration"' in sql:
                queries.append((sql, params))
            return execute(sql, params, many, context)

        with connection.execute_wrapper(capture):
            result = resolve(self.component, self.case)
        self.assertTrue(queries)
        return result, queries

    def test_only_the_selected_envelope_is_loaded(self):
        draft = envelope(self.case, self.component, 'UTC', self.evidence)
        draft['unvalidated_note'] = 'x' * 200000
        save_draft(self.actor, self.case.pk, draft)
        selected = activate(self.actor, self.case, self.component, 'UTC', self.evidence)
        save_draft(self.actor, self.case.pk, draft)

        result, queries = self.resolution_queries()
        self.assertEqual((result.status, result.configuration.pk), ('ACTIVE', selected.pk))
        envelope_loads = [params for sql, params in queries if '"envelope"' in sql]
        self.assertEqual(envelope_loads, [(selected.pk,)])

    def test_unactivated_and_revoked_versions_leave_payloads_unloaded(self):
        draft = save_draft(self.actor, self.case.pk,
                           envelope(self.case, self.component, 'UTC', self.evidence))
        transition(self.actor, draft.pk, 'validated')
        result, queries = self.resolution_queries()
        self.assertEqual(result.status, 'MISSING')
        self.assertTrue(all('"envelope"' not in sql for sql, _ in queries))

        activate(self.actor, self.case, self.component, 'UTC', self.evidence)
        latest = activate(self.actor, self.case, self.component, 'Africa/Lagos', self.evidence)
        transition(self.actor, latest.pk, 'revoked')
        result, queries = self.resolution_queries()
        self.assertEqual(result.status, 'REVOKED')
        self.assertTrue(all('"envelope"' not in sql for sql, _ in queries))
