"""Synthetic F09 negative: period-policy succession rejects historical input.

Not a direct inner period-guard proof, F08 exercise or whole-statement oracle.
"""
import copy
import json
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.finance import analysis, statements
from apps.finance.models import (
    FinancialImport, FinanceReview, FinanceRun, FinanceSource, FinanceStatementInput,
)
from apps.finance.services import capture_import, validate_import
from apps.workflows.models import Outbox
from tests.finance_analysis_helpers import fixture, policy, declared_units
from tests.helpers import rev


class StatementPeriodCurrentnessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        (cls.actor, cls.case, cls.evidence, cls.data, _, _, _, _) = fixture(
            username='period776', recipient_username='period776-reader')
        # Keep the accepted identity arithmetic and sign conventions unchanged.
        mapping = copy.deepcopy(cls.data['mapping'][-1])
        rule = copy.deepcopy(cls.data['formulas'][-1])
        mapping['to_period'] = rule['to_period'] = '2026-11'
        rule['oracle_evidence_id'] = cls.evidence['oracle_asset_display'].pk
        for component, value, purpose in [
            ('D06.account_bu_maps', [mapping], 'mapping'),
            ('D06.rule_oracle_refs', [rule], 'formula'),
        ]:
            config = policy(cls.actor, cls.case, component, value, cls.evidence['policy_decision'])
            cls.review(purpose, config.pk)

    @classmethod
    def review(cls, purpose, target):
        return analysis.review(
            cls.actor, cls.case.pk, purpose, target, 'Finance', 'approve',
            cls.evidence['finance_review'].pk, 'Synthetic exact native input reviewed', rev(cls.case))

    def source_output(self, period, raw_amount='500'):
        evidence = add_evidence(
            self.actor, self.case.pk, 'financial_input',
            f'account,amount,currency,period\nasset,{raw_amount},NGN,{period}\n',
            'synthetic:period776-' + period)
        batch = capture_import(self.actor, self.case.pk, evidence.pk, rev(self.case))
        validate_import(self.actor, self.case.pk, batch.pk, rev(self.case))
        units = declared_units(self.actor, self.case, batch)
        source = analysis.capture_source(
            self.actor, self.case.pk, batch.pk, 'synthetic-company', 'accrual',
            timezone.now() - timedelta(hours=1), 'complete', '500',
            self.evidence['finance_source'].pk, rev(self.case), unit_declaration=units)
        self.review('source', source.pk)
        mapping = analysis.map_source(self.actor, self.case.pk, source.pk, [], rev(self.case))
        output = analysis.calculate(self.actor, self.case.pk, mapping.pk, rev(self.case))
        self.assertEqual(analysis.certification_findings(output), [])
        decision = self.review('output', output.pk)
        self.assertEqual(output.result['company']['asset_display']['value'], '0.50')
        return output, decision

    def contract(self, anchor, selections):
        rows = [dict(
            destination=destination, source_run=run.pk, source_review=review.pk,
            metric='asset_display', source_location='synthetic:asset', source_kind='note',
            unit='thousands_currency', source_sign='asset_positive',
            destination_sign='asset_positive', transfer='identity',
        ) for destination, run, review in selections]
        oracle = add_evidence(self.actor, self.case.pk, 'finance_oracle',
                              json.dumps({row['destination']: '0.50' for row in rows}),
                              'synthetic:period776-selected-lines-only')
        value = {**{key: anchor.result[key] for key in ['entity', 'period', 'currency']},
                 'accounting_basis': 'accrual', 'scope': 'selected_statement_lines',
                 'inputs': rows, 'oracle_evidence_id': oracle.pk}
        config = policy(self.actor, self.case, 'D06.statement_contract', value,
                        self.evidence['policy_decision'])
        self.review('formula', config.pk)
        return config

    @staticmethod
    def rows(models):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in models}

    def test_equal_totals_different_period_history_cannot_be_composed(self):
        self.assertEqual(connection.vendor, 'postgresql')
        old, old_review = self.source_output('2026-10')
        historical_models = [FinancialImport, FinanceSource, FinanceRun, FinanceReview, Evidence]
        history = self.rows(historical_models)
        # Native policy succession only: preserve the sign/unit/control metadata.
        convention = dict(self.data['conventions'], period='2026-11')
        policy(self.actor, self.case, 'D06.unit_sign_currency_period', convention,
               self.evidence['policy_decision'])
        current, current_review = self.source_output('2026-11')
        self.assertNotEqual(old.result['period'], current.result['period'])
        self.assertEqual(Decimal(old.result['company']['asset_display']['value']) -
                         Decimal(current.result['company']['asset_display']['value']), Decimal('0'))
        config = self.contract(current, [('left', current, current_review), ('right', old, old_review)])
        # Current anchor passes. Historical input is rejected by certification,
        # before the inner period comparison or any statement persistence.
        self.assertIs(analysis.ensure_current(current), current)
        observed = historical_models + [Case, Audit, FinanceStatementInput,
                                       Publication, PublicationJob, PublicationReceipt, Outbox]
        before = self.rows(observed)
        with self.assertRaisesMessage(
                ValidationError, 'Source, policy, review or authority changed; rebuild the exact Finance preview'):
            statements.assemble(self.actor, self.case.pk, current.pk, config.pk, rev(self.case))
        self.assertEqual(before, self.rows(observed))
        self.assertFalse(FinanceRun.objects.filter(kind='statement').exists())
        self.assertFalse(FinanceStatementInput.objects.exists())
        for model in historical_models:
            previous = history[model._meta.label]
            self.assertEqual(previous, list(model.objects.filter(
                pk__in=[row['id'] for row in previous]).order_by('pk').values()))

    def test_same_period_selected_line_identity_control(self):
        self.assertEqual(connection.vendor, 'postgresql')
        first, first_review = self.source_output('2026-10')
        # Distinct raw source bytes, same native decimal total; duplicate imports are forbidden.
        second, second_review = self.source_output('2026-10', raw_amount='500.00')
        config = self.contract(second, [('left', first, first_review), ('right', second, second_review)])
        before = self.rows([Publication, PublicationJob, PublicationReceipt, Outbox])
        result = statements.assemble(self.actor, self.case.pk, second.pk, config.pk, rev(self.case))
        self.assertEqual(result.result['status'], 'complete')
        self.assertEqual(result.statement_inputs.count(), 2)
        self.assertEqual({item['value'] for item in result.result['company'].values()}, {'0.50'})
        self.assertFalse(result.result['whole_statement_certified'])
        self.assertFalse(result.result['ledger_posted'])
        self.assertEqual(before, self.rows([Publication, PublicationJob, PublicationReceipt, Outbox]))
