"""Explicit external-team choices and recorder roles supply no account grants."""
from django.core.exceptions import ValidationError

from adapters.forecast import KEY, obj
from .document_validators import ROLES, typed

COMPONENT = 'OPS.issue_team_controls'
SCHEMA = 'schema:psl/issue-team-controls/v1'
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


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project' or len({team['key'] for team in value['teams']}) != len(value['teams']):
        raise ValidationError('Use distinct external team identities for this project.')
    if any(team['label'] != team['label'].strip() for team in value['teams']):
        raise ValidationError('Provide each team name without surrounding whitespace.')
    return value
