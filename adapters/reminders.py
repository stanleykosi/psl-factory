"""Check human channel evidence against the reserved reminder."""
import json

from django.core.exceptions import ValidationError


def check_evidence(body, operation, digest, recipient, reference, delivered):
    if not isinstance(body, str) or len(body.encode()) > 8000:
        raise ValidationError('Use bounded channel receipt evidence.')
    try:
        supplied = json.loads(body)
    except ValueError:
        raise ValidationError('Use the typed reminder receipt evidence.') from None
    expected = {'operation': str(operation), 'draft_sha256': digest, 'recipient': recipient,
                'reference': reference, 'delivered': delivered}
    if (not isinstance(supplied, dict) or supplied.keys() != expected.keys() or
            type(supplied['delivered']) is not bool or supplied != expected):
        raise ValidationError('Receipt evidence does not identify this exact version, recipient and outcome.')
