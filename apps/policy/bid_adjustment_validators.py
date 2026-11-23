"""Bind bid adjustments to money inputs in a reviewed P14 rule."""
from django.core.exceptions import ValidationError

from adapters.costing import KEY, number
from adapters.forecast import obj, rows

from .document_validators import typed


COMPONENT = 'OPS.bid_cost_adjustments'
SCHEMA = 'schema:psl/bid-cost-adjustments/v1'
DECIMAL = {'type': 'string', 'pattern': r'^(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$'}
VALUE = obj({
    'rule_id': {'type': 'integer', 'minimum': 1},
    'targets': rows(obj({
        'input_key': KEY,
        'label': {'type': 'string', 'minLength': 1, 'maxLength': 80},
        'max_absolute_value': DECIMAL,
    })),
})


def validate_reference(target, case):
    from apps.pmo.costing_models import CostingRule

    value = typed(target, SCHEMA, VALUE)
    rule = CostingRule.objects.only('payload').filter(pk=value['rule_id'], case=case).first()
    if case.kind != 'project' or rule is None:
        raise ValidationError('Choose the exact calculator version for this project.')
    currency = rule.payload['currency']
    available = {entry['key'] for entry in rule.payload['inputs'] if entry['unit'] == currency}
    keys = {entry['input_key'] for entry in value['targets']}
    if len(keys) != len(value['targets']) or not keys <= available:
        raise ValidationError('Each adjustment must match a distinct declared currency input.')
    if any(number(entry['max_absolute_value']) <= 0 or not entry['label'].strip() for entry in value['targets']):
        raise ValidationError('Each target needs a name and a positive limit.')
    return value
