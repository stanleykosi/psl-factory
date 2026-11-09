"""Explicit synthetic U1 controls. Not owner policy or provider-authenticated data."""
import copy
import json
from apps.finance import usage_intake as domain
from .helpers import setup_case, rev
from .billing_helpers import coverage, evidence, policy, FIXTURE


def fixture(username='human'):
    actor, case = setup_case(username=username)
    coverages = [coverage(actor, case, reference=customer + '-coverage', customer=customer, service='API', contract=customer + '-contract',
                         from_period='2026-09', to_period='2026-09', completeness='complete') for customer in ['C1', 'C2']]
    scope = {'case_id': str(case.pk), 'provider_namespace': 'synthetic:data-team', 'provider_ref': 'data-example'}
    source = {'schema': 'finance-collective-usage/v1', 'scope': scope, 'report_ref': 'U1', 'source_version': 'v1', 'period': '2026-09',
              'controls_version': 'approved-controls-v1', 'extracted_at': '2026-10-01T10:00:00+00:00', 'cutoff_at': '2026-09-30T23:59:59+00:00',
              'completeness': 'complete', 'rows': [
                  {'transaction_id': 'U1-' + cov.customer, 'customer': cov.customer, 'service': cov.service, 'contract': cov.contract,
                   'period': '2026-09', 'unit': 'request', 'quantity': quantity} for cov, quantity in zip(coverages, ['10', '20'])]}
    controls = {'schema': 'finance-collective-controls/v1', 'scope': scope, 'report_ref': 'U1', 'source_version': 'v1', 'period': '2026-09',
                'version': 'approved-controls-v1', 'approval_reference': 'synthetic-owner-approved-example',
                'population': [dict({key: row[key] for key in ['customer', 'service', 'contract', 'unit', 'quantity']},
                                    coverage_id=cov.pk, currency=cov.currency, row_count=1) for cov, row in zip(coverages, source['rows'])],
                'totals': [{'unit': 'request', 'row_count': 2, 'quantity': '30'}]}
    return actor, case, coverages, source, controls


def receive(actor, case, source, controls, delivery='delivery-1', operation='operation-1', predecessor=None, expected=None):
    e = evidence(actor, case, 'usage_intake_source', json.dumps(source))
    c = evidence(actor, case, 'usage_intake_controls', json.dumps(controls))
    return domain.receive(actor, case.pk, e.pk, c.pk, delivery, operation, rev(case) if expected is None else expected, predecessor)


def correction(source, controls, quantity='12'):
    source, controls = copy.deepcopy(source), copy.deepcopy(controls)
    source['source_version'] = controls['source_version'] = 'v2'
    source['controls_version'] = controls['version'] = 'approved-controls-v2'
    source['rows'][0]['quantity'] = controls['population'][0]['quantity'] = quantity
    controls['totals'][0]['quantity'] = str(int(quantity) + 20)
    return source, controls


def prices(actor, case, coverages):
    f = json.loads(FIXTURE.read_text())
    rules = [dict(f['rule'], key='rate-' + cov.customer, coverage_id=cov.pk, from_period='2026-09', to_period='2026-09',
                  unit='request', rate='2', currency=cov.currency, amount_basis=cov.amount_basis) for cov in coverages]
    arithmetic = {'implementation': 'net_exclusive_line_tax_v1', 'tax_rate': '0', 'decimal_places': 2, 'rounding': 'half_up',
                  'oracles': [{'quantity': '10', 'rate': '2', 'net': '20.00', 'tax': '0.00', 'total': '20.00'},
                              {'quantity': '0', 'rate': '2', 'net': '0.00', 'tax': '0.00', 'total': '0.00'},
                              {'quantity': None, 'rate': '2', 'net': None, 'tax': None, 'total': None}]}
    oracle = evidence(actor, case, 'billing_oracle', json.dumps(arithmetic['oracles']))
    arithmetic['oracle_evidence_id'] = oracle.pk
    return [policy(actor, case, 'D08.effective_price_rule_refs', rules), policy(actor, case, 'D08.tax_tier_rounding_rules', arithmetic)]
