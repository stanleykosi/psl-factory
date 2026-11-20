"""Optional reasons approved by the business for recording customer losses."""

from django.core.exceptions import ValidationError

from adapters.forecast import obj
from .document_validators import typed


COMPONENT = 'OPS.rfp_loss_catalog'
SCHEMA = 'schema:psl/rfp-loss-catalog/v1'
VALUE = obj({'reasons': {'type': 'array', 'maxItems': 25, 'items': obj({
    'key': {'type': 'string', 'pattern': '^[a-z][a-z0-9_-]{0,49}$'},
    'label': {'type': 'string', 'minLength': 1, 'maxLength': 80},
})}})


def validate_reason_names(reasons):
    if len(reasons) > 25 or any(len(row['label']) > 80 for row in reasons):
        raise ValidationError('Use up to 25 loss reasons with at most 80 characters each.')
    if len({row['key'] for row in reasons}) != len(reasons) or len({row['label'].casefold() for row in reasons}) != len(reasons):
        raise ValidationError('Enter each loss reason once.')
    if any(label != label.strip() or not label.strip() or not label.isprintable() for label in (row['label'] for row in reasons)):
        raise ValidationError('Use a plain name for each loss reason.')


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project':
        raise ValidationError('Set customer loss reasons for a project workspace.')
    validate_reason_names(value['reasons'])
    return value
