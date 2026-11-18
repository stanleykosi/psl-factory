"""Closed, source-free command shape for a human-reviewed account departure."""
import re
from django.core.exceptions import ValidationError


def checked(person_id,fingerprint,replacements,evidence):
    positive=lambda v:type(v) is int and v>0
    if not positive(person_id) or not isinstance(fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',fingerprint):
        raise ValidationError('An exact current staff account review is required.')
    if (type(replacements) is not dict or len(replacements)>10000 or
            any(not positive(k) or v is not None and not positive(v) for k,v in replacements.items())):
        raise ValidationError('Use exact action and successor references, or an explicit unassigned owner.')
    if (type(evidence) is not dict or len(evidence)>100 or
            any(not isinstance(k,str) or not positive(v) for k,v in evidence.items())):
        raise ValidationError('Use each workspace’s own handover evidence.')
