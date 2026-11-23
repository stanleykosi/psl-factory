"""Explicit external-team choices and recorder roles supply no account grants."""
from django.core.exceptions import ValidationError
from copy import deepcopy

from adapters.forecast import KEY, obj
from .document_validators import ROLES, typed

COMPONENT = 'OPS.issue_team_controls'
SCHEMA = 'schema:psl/issue-team-controls/v1'
SCHEMA_V2 = 'schema:psl/issue-team-controls/v2'
CHANNELS = ['email', 'whatsapp', 'ticket', 'meeting', 'phone', 'document']
VALUE = obj({
    'recorder_roles': {'type': 'array', 'minItems': 1, 'maxItems': len(ROLES),
                       'uniqueItems': True, 'items': {'enum': ROLES}},
    'teams': {'type': 'array', 'minItems': 1, 'maxItems': 40, 'items': obj({
        'key': KEY, 'label': {'type': 'string', 'minLength': 1, 'maxLength': 100}})},
    'channels': {'type': 'array', 'minItems': 1, 'maxItems': len(CHANNELS),
                 'uniqueItems': True, 'items': {'enum': CHANNELS}},
    'clock_basis': {'const': 'human_attested_source_time'},
})
VALUE_V2 = deepcopy(VALUE)
VALUE_V2['properties'].update({
    'resolution_recorder_roles': {'type':'array','maxItems':len(ROLES),'uniqueItems':True,
                                'items':{'enum':ROLES}},
    'acknowledgement_clock': {'enum':[None,'recorded_at','human_attested_source_time']},
})
VALUE_V2['required'] += ['resolution_recorder_roles','acknowledgement_clock']


def validate_value(value, schema=SCHEMA):
    from apps.documents.contracts import validate
    schemas = {SCHEMA:VALUE, SCHEMA_V2:VALUE_V2}
    if schema not in schemas:
        raise ValidationError('Use a supported issue-team rule version.')
    validate(schemas[schema], value)
    if len({team['key'] for team in value['teams']}) != len(value['teams']):
        raise ValidationError('Use distinct external team identities for this project.')
    labels = [team['label'] for team in value['teams']]
    if any(label != label.strip() for label in labels) or len(set(labels)) != len(labels):
        raise ValidationError('Provide distinct team names without surrounding whitespace.')
    return value


def validate_reference(target, case):
    schema = target.schema_ref
    value = typed(target, schema, VALUE_V2 if schema == SCHEMA_V2 else VALUE)
    if case.kind != 'project':
        raise ValidationError('Issue-team rules belong to a project.')
    return validate_value(value, schema)
