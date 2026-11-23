"""Reviewed contact and channel choices for an exact Security estimate request."""
import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from adapters.forecast import obj

from .document_validators import typed


COMPONENT = 'OPS.rfp_security_estimate_routes'
SCHEMA = 'schema:psl/rfp-security-estimate-routes/v1'
VALUE = obj({
    'routes': {'type': 'array', 'maxItems': 2, 'items': obj({
        'channel': {'enum': ['email', 'whatsapp']},
        'contact': {'type': 'string', 'minLength': 1, 'maxLength': 160},
        'destination': {'type': 'string', 'minLength': 1, 'maxLength': 240},
        'method': {'enum': ['manual_receipt', 'synthetic_mailbox']},
        'allow_attachment': {'type': 'boolean'},
    })},
})


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    routes = value['routes']
    if case.kind != 'project' or len({route['channel'] for route in routes}) != len(routes):
        raise ValidationError('Choose one route per channel for this project.')
    for route in routes:
        destination = route['destination']
        for text in (route['contact'], destination):
            if not text or text.strip() != text or any(ord(c) < 32 for c in text):
                raise ValidationError('Use a named contact and a plain destination.')
        if route['method'] == 'synthetic_mailbox':
            if not case.synthetic or not (destination.endswith('.invalid') or destination.startswith('synthetic:')):
                raise ValidationError('The sample mailbox requires an isolated project and fictional contact.')
        if route['channel'] == 'email':
            validate_email(destination)
        elif route['method'] == 'manual_receipt' and not re.fullmatch(r'\+[1-9][0-9]{7,14}', destination):
            raise ValidationError('Use the confirmed international WhatsApp number.')
    return value
