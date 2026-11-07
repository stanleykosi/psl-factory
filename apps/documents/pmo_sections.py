"""Honest missing-coverage sections for native PMO client projections only.

Callers supply only their already-authorized public projection citations. This
never reads source bodies, infers absence of risk, or fills arbitrary user drafts.
"""
from django.core.exceptions import ValidationError
from .contracts import PMO_CLIENT_SECTIONS


def complete_native_client_sections(fields, audience, evidence_ids):
    if audience != 'client':
        return fields
    if not evidence_ids or any(type(pk) is not int or pk < 1 for pk in evidence_ids):
        raise ValidationError('Native client coverage statements require exact authorized source references')
    result = dict(fields)
    for key in PMO_CLIENT_SECTIONS:
        if key not in result:
            label = key.replace('_', ' ')
            result[key] = {'text': 'Unknown: ' + label + ' is not established by this selected local PMO packet. '
                                  'This is an explicit coverage gap for human review, not a statement that no ' + label + ' exists.',
                           'evidence_ids': sorted(set(evidence_ids))}
    return result
