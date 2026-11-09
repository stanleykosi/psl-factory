"""Explicit fixed-weight coverage. v1 callers retain their relative-weight contract.

This validates owner-supplied meaning; it never chooses a denominator or expands
membership to the global BU catalogue. No payroll subjects belong in this data.
"""
import json
import re
from decimal import localcontext
from django.core.exceptions import ValidationError
from adapters.forecast import obj, KEY
from apps.documents.contracts import validate
from apps.finance.rules import decimal

DECIMAL = {'type': 'string', 'pattern': r'^-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$'}
COVERAGE = obj({
    'version': {'const': 'allocation-coverage/v1'},
    'mode': {'enum': ['relative_weights', 'declared_shares']},
    'population': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'uniqueItems': True, 'items': KEY},
    'completeness': {'const': 'complete'},
    'denominator': {'anyOf': [DECIMAL, {'type': 'null'}]},
    'basis': KEY,
    'evidence_id': {'type': 'integer', 'minimum': 1},
})
NULLABLE_COVERAGE = {'anyOf': [COVERAGE, {'type': 'null'}]}


def checked_weights(rows, coverage):
    validate(COVERAGE, coverage)
    if not rows or len({r['bu'] for r in rows}) != len(rows):
        raise ValidationError('allocation_coverage_duplicate_or_missing_weights')
    for row in rows:
        validate(DECIMAL, row['weight'])
    weights = {r['bu']: decimal(r['weight'], nonnegative=True) for r in rows}
    if set(weights) != set(coverage['population']):
        raise ValidationError('allocation_coverage_population_incomplete')
    with localcontext() as context:
        context.prec = 512
        total = sum(weights.values())
    if total <= 0:
        raise ValidationError('allocation_coverage_positive_total_required')
    if coverage['mode'] == 'declared_shares':
        if coverage['denominator'] is None:
            raise ValidationError('allocation_coverage_denominator_required')
        if total != decimal(coverage['denominator'], positive=True):
            raise ValidationError('allocation_coverage_share_total_incomplete')
    elif coverage['denominator'] is not None:
        raise ValidationError('allocation_coverage_relative_denominator_must_be_null')
    return weights


def evidence_payload(value, staff=False):
    coverage = value['weight_contract']
    return {
        'entity': value['entity'], 'from_period': value['from_period'], 'to_period': value['to_period'],
        'pool': value['standard_pool_ref'] if staff else value['pool'],
        'weights': value['standard_weights'] if staff else value['weights'],
        'excluded_bu_keys': [] if staff else value['excluded_bu_keys'],
        'coverage': {k: v for k, v in coverage.items() if k != 'evidence_id'},
    }


def validate_contract(value, case, staff=False):
    coverage = value['weight_contract']
    fixed = value['standard_method' if staff else 'method'] == 'fixed_weights'
    if not fixed:
        if coverage is not None:
            raise ValidationError('Fixed-weight coverage is not applicable to this method')
        return
    if coverage is None:
        raise ValidationError('Explicit fixed-weight coverage contract required')
    checked_weights(value['standard_weights' if staff else 'weights'], coverage)
    if not staff and set(coverage['population']) & set(value['excluded_bu_keys']):
        raise ValidationError('Declared eligible population includes excluded BUs')
    if staff and coverage['evidence_id'] != value['pool_contract_evidence_id']:
        raise ValidationError('Coverage and standard pool must cite the same contract')
    from apps.pmo.services import subject
    evidence = subject(case, coverage['evidence_id'], 'bu_pool_contract' if staff else 'finance_pool_contract')
    try:
        actual = json.loads(evidence.body)
    except (ValueError, TypeError):
        raise ValidationError('Allocation coverage requires exact structured pool evidence')
    expected = evidence_payload(value, staff)
    if actual != expected:
        raise ValidationError('Allocation coverage differs from its cited pool evidence')
    # Evidence kind is not a pool identity. Independently supplied pools and
    # disjoint effective windows must not revoke each other's configurations.
    for newer in case.evidence.filter(kind=evidence.kind, version__gt=evidence.version).only('body'):
        try:
            candidate = json.loads(newer.body)
        except (ValueError, TypeError):
            continue
        if not isinstance(candidate, dict):
            continue
        if candidate.get('entity') != expected['entity'] or candidate.get('pool') != expected['pool']:
            continue
        start, end = candidate.get('from_period'), candidate.get('to_period')
        if isinstance(start, str) and isinstance(end, str) and re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', start) and re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', end) and max(start, expected['from_period']) <= min(end, expected['to_period']):
            raise ValidationError('Allocation coverage contract replaced for this pool and period')
