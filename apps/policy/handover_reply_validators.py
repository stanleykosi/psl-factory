"""Configured human capture of an evidenced Support or Operations reply."""
from adapters.forecast import obj
from .document_validators import ROLES, typed

COMPONENT = 'OPS.handover_reply_capture'
SCHEMA = 'schema:psl/handover-reply-capture/v1'
CHANNELS = ['email', 'whatsapp', 'client_portal', 'signed_document', 'meeting']
VALUE = obj({
    'recorder_roles': {'type': 'array', 'minItems': 1, 'maxItems': len(ROLES),
                       'uniqueItems': True, 'items': {'enum': ROLES}},
    'channels': {'type': 'array', 'minItems': 1, 'maxItems': len(CHANNELS),
                 'uniqueItems': True, 'items': {'enum': CHANNELS}},
})


def validate_reference(target, case):
    from django.core.exceptions import ValidationError

    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project':
        raise ValidationError('Support handover replies require a project.')
    return value
