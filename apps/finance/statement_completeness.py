"""Read-only, bounded inventory coverage; never whole-statement certification."""
from typing import TypedDict
from apps.policy.statement_completeness import ANCHOR, METHOD, evidence_json
from .rules import decimal


class Coverage(TypedDict):
    scope: str
    inventory_status: str
    check_status: str
    whole_statement_certified: bool
    required_destinations: list[str]
    selected_destinations: list[str]
    missing_destinations: list[str]
    unexpected_destinations: list[str]
    checks: list[dict]
    findings: list[str]
    evidence_ids: list[int]


def assess(case, value, figures) -> Coverage:
    selected = {row['destination']: row for row in value['inputs']}
    result: Coverage = {'scope': 'configured_inventory_only', 'inventory_status': 'held',
        'check_status': 'held', 'whole_statement_certified': False,
        'required_destinations': [], 'selected_destinations': sorted(selected),
        'missing_destinations': [], 'unexpected_destinations': [], 'checks': [],
        'findings': [], 'evidence_ids': []}
    complete = value.get('completeness')
    if complete is None:
        result['findings'].append('Owner required-layout and approved-check inventory is missing')
        return result
    required = {row['destination']: row for row in complete['layout']}
    result['evidence_ids'].append(complete['inventory_evidence_id'])
    result['required_destinations'] = sorted(required)
    result['missing_destinations'] = sorted(set(required) - set(selected))
    result['unexpected_destinations'] = sorted(set(selected) - set(required))
    for key in result['missing_destinations']:
        result['findings'].append('Required layout input missing: ' + key)
    for key in result['unexpected_destinations']:
        result['findings'].append('Selected destination outside required layout: ' + key)
    for key in sorted(set(selected) & set(required)):
        for field in ['source_kind', 'unit', 'destination_sign']:
            if selected[key][field] != required[key][field] or required[key][field] is None:
                result['findings'].append('Required layout declaration differs or is unknown: ' + key + ' / ' + field)
    if not result['findings']:
        result['inventory_status'] = 'covered'
    covered = set()
    for check in complete['checks']:
        row = {'key': check['key'], 'method': check['method'],
               'destinations': check['destinations'], 'oracle_evidence_id': check['oracle_evidence_id'],
               'status': 'held', 'findings': []}
        if check['oracle_evidence_id'] is not None:
            result['evidence_ids'].append(check['oracle_evidence_id'])
        if check['method'] != METHOD:
            row['findings'].append('Unsupported statement check method: ' + check['method'])
        elif check['oracle_evidence_id'] is None:
            row['findings'].append('Approved check oracle evidence is missing')
        else:
            oracle = evidence_json(case, check['oracle_evidence_id'], 'finance_oracle')
            for key in check['destinations']:
                actual = figures.get(key)
                expected = oracle['values'][key]
                if actual is None or actual['value'] is None:
                    row['findings'].append('Required check input missing or unknown: ' + key)
                elif actual['unit'] != expected['unit'] or decimal(actual['value']) != decimal(expected['value']):
                    row['findings'].append('Approved check oracle differs: ' + key)
            if not row['findings']:
                row['status'] = 'matched'
                covered.update(check['destinations'])
        result['checks'].append(row)
        result['findings'].extend(check['key'] + ': ' + finding for finding in row['findings'])
    uncovered = sorted(set(required) - covered)
    if uncovered:
        result['findings'].append('Required layout lacks matched supported check coverage: ' + ', '.join(uncovered))
    if not uncovered and all(check['status'] == 'matched' for check in result['checks']):
        result['check_status'] = 'matched'
    result['evidence_ids'] = sorted(set(result['evidence_ids']))
    return result
