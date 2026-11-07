"""Synthetic owner inventory and exact native selected-line evidence only."""
import copy
import json
from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from apps.core.services import add_evidence
from apps.finance import analysis, statements
from apps.policy.services import transition, reference_values
from apps.policy.statement_completeness import inventory, METHOD
from apps.identity.models import Grant
from tests import test_finance_statements as legacy_statements
from tests.helpers import rev


class StatementCompletenessTests(TestCase):
    setUpTestData = classmethod(legacy_statements.StatementTests.setUpTestData.__func__)
    configure = classmethod(legacy_statements.StatementTests.configure.__func__)
    assemble = legacy_statements.StatementTests.assemble

    def rowsets(self):
        from django.db import connection
        result = {}
        with connection.cursor() as cursor:
            for name in connection.introspection.table_names():
                cursor.execute("SELECT count(*), md5(COALESCE(string_agg(row_to_json(t)::text, chr(10) ORDER BY row_to_json(t)::text),'')) FROM " + connection.ops.quote_name(name) + ' t')
                result[name] = cursor.fetchone()
        return result

    def value(self):
        value = copy.deepcopy(self.contract_value)
        value['completeness'] = {
            'inventory_evidence_id': 1,
            'layout': [{key: value['inputs'][0][key] for key in
                        ['destination', 'source_kind', 'unit', 'destination_sign']}],
            'checks': [{'key': 'equity_exact', 'method': METHOD,
                        'destinations': ['C30'], 'oracle_evidence_id': None}]}
        self.bind_inventory(value)
        self.bind_oracle(value)
        return value

    def bind_inventory(self, value):
        value['completeness']['inventory_evidence_id'] = add_evidence(
            self.a, self.c.pk, 'policy_decision', json.dumps(inventory(value)),
            'synthetic:independent-required-inventory').pk

    def bind_oracle(self, value, amount='12', unit='major_currency'):
        check = value['completeness']['checks'][0]
        payload = {key: value[key] for key in ['entity', 'period', 'currency', 'accounting_basis']}
        payload.update(check_key=check['key'], method=check['method'],
                       values={'C30': {'value': amount, 'unit': unit}})
        check['oracle_evidence_id'] = add_evidence(
            self.a, self.c.pk, 'finance_oracle', json.dumps(payload),
            'synthetic:independent-required-check').pk

    def test_typed_native_coverage_exact_provenance_and_http_view(self):
        value = self.value()
        contract = self.configure(value)
        self.assertEqual(reference_values(contract)[0], value)
        run = self.assemble(contract)
        coverage = run.result['completeness']
        self.assertEqual(coverage['inventory_status'], 'covered')
        self.assertEqual(coverage['check_status'], 'matched')
        self.assertFalse(run.result['whole_statement_certified'])
        self.assertFalse(coverage['whole_statement_certified'])
        self.assertEqual(coverage['scope'], 'configured_inventory_only')
        self.assertEqual(run.snapshot['completeness_contract'], value['completeness'])
        self.assertEqual(run.snapshot['inputs'][0]['operation_key'], self.r.operation_key)
        self.assertEqual(run.snapshot['inputs'][0]['result_hash'], analysis.digest(self.r.result))
        self.assertTrue(set(coverage['evidence_ids']) <= set(run.result['source_evidence_ids']))
        self.assertEqual(self.assemble(contract).pk, run.pk)
        self.assertFalse(analysis.certification_findings(run))
        self.assertEqual(run.statement_inputs.get().source_review_id, self.output_review.pk)
        from apps.agents.finance_analysis import investigate_finance
        log = investigate_finance(self.a, self.c.pk, run.pk, rev(self.c))
        self.assertFalse(log.result['approval_granted'])
        self.assertTrue(set(coverage['evidence_ids']) <= {item['id'] for item in log.result['citations']})
        self.client.force_login(self.a)
        before_rows = self.rowsets()
        before = self.c.revision
        response = self.client.get(f'/cases/{self.c.pk}/finance/')
        self.assertContains(response, 'Whole-statement certification: not established')
        self.assertContains(response, 'HOD statement decisions still needed')
        self.assertContains(response, 'equity_exact')
        self.c.refresh_from_db()
        self.assertEqual(before, self.c.revision)
        self.assertEqual(before_rows, self.rowsets())

    def test_missing_inventory_and_missing_required_line_hold_only_v2_output(self):
        value = copy.deepcopy(self.contract_value)
        value['completeness'] = None
        run = self.assemble(self.configure(value))
        self.assertEqual(run.result['completeness']['inventory_status'], 'held')
        self.assertTrue(analysis.certification_findings(run))
        self.assertFalse(analysis.certification_findings(self.r))
        value = self.value()
        value['completeness']['layout'].append(dict(value['completeness']['layout'][0], destination='AssetNote', source_kind='note'))
        self.bind_inventory(value)
        run = self.assemble(self.configure(value))
        self.assertEqual(run.result['completeness']['missing_destinations'], ['AssetNote'])
        self.assertEqual(run.result['completeness']['check_status'], 'held')
        self.assertTrue(analysis.certification_findings(run))
        with self.assertRaises(ValidationError):
            analysis.review(self.reviewer, self.c.pk, 'output', run.pk, 'Finance', 'approve',
                            self.e['finance_review'].pk, 'Cannot certify incomplete inventory', rev(self.c))

    def test_unapproved_extra_inventory_and_kind_mismatch(self):
        value = self.value()
        value['completeness']['layout'][0]['source_kind'] = 'note'
        with self.assertRaises(ValidationError):
            self.configure(value)  # Independently supplied evidence was not changed.
        self.bind_inventory(value)
        run = self.assemble(self.configure(value))
        self.assertIn('source_kind', ' '.join(run.result['findings']))
        self.assertEqual(run.result['completeness']['inventory_status'], 'held')
        value = self.value()
        value['completeness']['layout'][0]['destination'] = 'Other'
        value['completeness']['checks'][0].update(destinations=['Other'], oracle_evidence_id=None)
        self.bind_inventory(value)
        run = self.assemble(self.configure(value))
        self.assertEqual(run.result['completeness']['unexpected_destinations'], ['C30'])
        self.assertEqual(run.result['completeness']['missing_destinations'], ['Other'])

    def test_unsupported_missing_and_mismatched_checks_are_not_passes(self):
        value = self.value()
        value['completeness']['checks'][0].update(method='unimplemented_owner_balance_v1', oracle_evidence_id=None)
        self.bind_inventory(value)
        run = self.assemble(self.configure(value))
        self.assertIn('Unsupported statement check method', ' '.join(run.result['findings']))
        self.assertEqual(run.result['completeness']['check_status'], 'held')
        value = self.value()
        value['completeness']['checks'][0]['oracle_evidence_id'] = None
        run = self.assemble(self.configure(value))
        self.assertIn('Approved check oracle evidence is missing', ' '.join(run.result['findings']))
        value = self.value()
        self.bind_oracle(value, amount='13')
        run = self.assemble(self.configure(value))
        self.assertIn('Approved check oracle differs: C30', ' '.join(run.result['findings']))
        self.assertTrue(analysis.certification_findings(run))

    def test_malformed_unknown_wrong_basis_and_wrong_unit_oracle_rejected(self):
        for amount, unit in [(None, 'major_currency'), ('12', 'thousands_currency')]:
            value = self.value()
            self.bind_oracle(value, amount=amount, unit=unit)
            with self.assertRaises(ValidationError):
                self.configure(value)
        for field in ['layout', 'checks']:
            value = self.value()
            value['completeness'][field] = []
            with self.assertRaises(ValidationError):
                self.configure(value)
        value = self.value()
        value['period'] = '2099-01'
        self.bind_inventory(value)
        with self.assertRaises(ValidationError):
            self.configure(value)
        value = self.value()
        value['completeness']['checks'].append(copy.deepcopy(value['completeness']['checks'][0]))
        self.bind_inventory(value)
        with self.assertRaises(ValidationError):
            self.configure(value)

    def test_revoked_policy_review_and_actor_access_hold_currentness(self):
        value = self.value()
        contract = self.configure(value)
        run = self.assemble(contract)
        grant = Grant.objects.get(case=self.c, user=self.a, action='finance.read')
        grant.active = False
        grant.save()
        with self.assertRaises(PermissionDenied):
            analysis.ensure_current(run)
        grant.active = True
        grant.save()
        analysis.review(self.reviewer, self.c.pk, 'formula', contract.pk, 'Finance', 'return',
                        self.e['finance_review'].pk, 'Required inventory review withdrawn', rev(self.c))
        with self.assertRaises(ValidationError):
            analysis.ensure_current(run)
        analysis.review(self.reviewer, self.c.pk, 'formula', contract.pk, 'Finance', 'approve',
                        self.e['finance_review'].pk, 'New review cannot silently refresh old snapshot', rev(self.c))
        with self.assertRaises(ValidationError):
            analysis.ensure_current(run)
        transition(self.a, contract.pk, 'revoked')
        with self.assertRaises(ValidationError):
            self.assemble(contract)
        self.assertFalse(analysis.certification_findings(self.r))

    def test_legacy_selected_line_snapshot_remains_unchanged(self):
        run = self.assemble()
        snapshot = copy.deepcopy(run.snapshot)
        result = copy.deepcopy(run.result)
        self.assertNotIn('completeness', result)
        self.assertNotIn('completeness_contract', snapshot)
        statements.ensure_current(run)
        self.assertEqual(run.snapshot, snapshot)
        self.assertEqual(run.result, result)
        self.assertFalse(result['whole_statement_certified'])

    def test_v2_native_review_publication_receipt_remains_selected_scope(self):
        from apps.finance.documents import draft_report
        from apps.documents.controlled import reserve_publication, preflight
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        value = self.value()
        run = self.assemble(self.configure(value))
        analysis.review(self.reviewer, self.c.pk, 'output', run.pk, 'Finance', 'approve',
                        self.e['finance_review'].pk, 'Synthetic configured inventory only', rev(self.c))
        document = draft_report(self.a, self.c.pk, run.pk, self.template.pk, 'internal', rev(self.c))
        self.assertFalse(preflight(document))
        reserve_publication(self.a, self.c.pk, document.pk, rev(self.c))
        self.assertTrue(run_publication_once())
        receipt = PublicationReceipt.objects.get()
        payload = json.dumps(receipt.payload)
        self.assertIn('12.00', payload)
        self.assertIn('Selected statement lines only; full statement and balance-sheet oracle remain deferred.', payload)
        self.assertNotIn('SOCE!I17', payload)
        self.assertFalse(run.result['whole_statement_certified'])
        self.assertEqual(run.result['completeness']['scope'], 'configured_inventory_only')

    def test_inventory_evidence_is_immutable_case_bound_and_review_authority_current(self):
        from django.db import transaction, DatabaseError
        from apps.core.models import Evidence
        from tests.helpers import setup_case
        value = self.value()
        contract = self.configure(value)
        run = self.assemble(contract)
        evidence_id = value['completeness']['inventory_evidence_id']
        with self.assertRaises(DatabaseError), transaction.atomic():
            Evidence.objects.filter(pk=evidence_id).update(body='{}')
        statements.ensure_current(run)
        other_actor, other_case = setup_case(username='foreign-completeness-owner')
        foreign = add_evidence(other_actor, other_case.pk, 'policy_decision',
                               json.dumps(inventory(value)), 'synthetic:foreign-inventory')
        value['completeness']['inventory_evidence_id'] = foreign.pk
        with self.assertRaises(ValidationError):
            self.configure(value)
        grant = Grant.objects.get(case=self.c, user=self.reviewer, action='finance.review')
        grant.active = False
        grant.save()
        with self.assertRaises((ValidationError, PermissionDenied)):
            statements.ensure_current(run)

    def test_supersession_preserves_old_evidence_and_does_not_refresh_history(self):
        value = self.value()
        first = self.configure(value)
        run = self.assemble(first)
        original = copy.deepcopy(run.snapshot)
        second = self.configure(value)
        self.assertNotEqual(first.pk, second.pk)
        with self.assertRaises(ValidationError):
            statements.ensure_current(run)
        run.refresh_from_db()
        self.assertEqual(run.snapshot, original)
        fresh = self.assemble(second)
        self.assertEqual(fresh.result['completeness']['inventory_status'], 'covered')
        self.assertFalse(fresh.result['whole_statement_certified'])
