"""Owner-supplied inventory, not an inferred whole-statement accounting engine."""
import json
from django.core.exceptions import ValidationError
from apps.pmo.services import subject
from .finance_validators import obj, rows, KEY, KEYS, DEC
from .statement_validators import ID, LINE

LAYOUT = obj({key: LINE['properties'][key] for key in
              ['destination', 'source_kind', 'unit', 'destination_sign']})
CHECK = obj({'key': KEY, 'method': KEY, 'destinations': dict(KEYS, minItems=1),
             'oracle_evidence_id': {'anyOf': [ID, {'type': 'null'}]}})
CONTRACT = obj({'inventory_evidence_id': ID, 'layout': rows(LAYOUT), 'checks': rows(CHECK)})
ANCHOR = ('entity', 'period', 'currency', 'accounting_basis')
METHOD = 'exact_line_oracle_v1'


def inventory(value):
    complete = value['completeness']
    return {**{key: value[key] for key in ANCHOR}, 'layout': complete['layout'],
            'checks': [{key: check[key] for key in ['key', 'method', 'destinations']}
                       for check in complete['checks']]}


def evidence_json(case, pk, kind):
    evidence = subject(case, pk, kind)
    try:
        return json.loads(evidence.body)
    except (ValueError, TypeError) as exc:
        raise ValidationError('Structured statement completeness evidence required') from exc


def validate(value, case):
    complete = value['completeness']
    if complete is None:
        return
    destinations = [row['destination'] for row in complete['layout']]
    if len(set(destinations)) != len(destinations):
        raise ValidationError('Required layout destinations must be unique')
    keys = [check['key'] for check in complete['checks']]
    if len(set(keys)) != len(keys):
        raise ValidationError('Required statement check keys must be unique')
    if evidence_json(case, complete['inventory_evidence_id'], 'policy_decision') != inventory(value):
        raise ValidationError('Independent owner inventory evidence must match the exact reporting basis, required layout and checks')
    for check in complete['checks']:
        if not set(check['destinations']) <= set(destinations):
            raise ValidationError('Required checks must reference required layout destinations')
        if check['oracle_evidence_id'] is None:
            continue
        oracle = evidence_json(case, check['oracle_evidence_id'], 'finance_oracle')
        expected_header = {**{key: value[key] for key in ANCHOR},
                           'check_key': check['key'], 'method': check['method']}
        if not isinstance(oracle, dict) or set(oracle) != set(expected_header) | {'values'} or any(
                oracle.get(key) != expected for key, expected in expected_header.items()):
            raise ValidationError('Check oracle must identify the exact reporting basis, key and method')
        # Unknown methods remain explicit runtime holds, never an executable user expression.
        if check['method'] != METHOD:
            continue
        from jsonschema import Draft202012Validator
        amount = obj({'value': DEC, 'unit': LINE['properties']['unit']})
        schema = obj({key: amount for key in check['destinations']})
        errors = list(Draft202012Validator(schema).iter_errors(oracle['values']))
        if errors:
            raise ValidationError('Check oracle must enumerate exact required destinations with known decimal values and units')
        units = {row['destination']: row['unit'] for row in complete['layout']}
        if any(row['unit'] != units[key] for key, row in oracle['values'].items()):
            raise ValidationError('Check oracle units differ from required layout; no implicit conversion')
