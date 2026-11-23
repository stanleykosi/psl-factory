"""Authority for reviewing a proposed calculator version."""
from django.core.exceptions import ValidationError
from adapters.forecast import obj
from .document_validators import ROLES, typed

COMPONENT = 'OPS.costing_version_review'
SCHEMA = 'schema:psl/costing-version-review/v1'
VALUE = obj({
    'reviewer_id': {'anyOf': [{'type': 'integer', 'minimum': 1}, {'type': 'null'}]},
    'reviewer_role': {'anyOf': [{'enum': ROLES}, {'type': 'null'}]},
    'independent_review': {'const': True},
})


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project':
        raise ValidationError('Calculator proposals require a project scope.')
    if (value['reviewer_id'] is None) != (value['reviewer_role'] is None):
        raise ValidationError('Set the reviewer and role together, or leave both unset.')
    return value
