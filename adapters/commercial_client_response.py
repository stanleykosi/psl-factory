"""Versioned human witness evidence for a delivered commercial document."""
from apps.documents.contracts import validate

KIND = 'agent_private_commercial_response'
PROTOCOL = 'commercial-client-response/v1'
PREFIX = 'psl:' + PROTOCOL + ':'
ID = {'type': 'integer', 'minimum': 1}
HASH = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


PROOF = obj({'id': ID, 'actor': ID, 'sha256': HASH, 'size': {'type': 'integer', 'minimum': 1},
             'name': {'type': 'string', 'minLength': 1, 'maxLength': 160}})
VALUE = obj({'protocol': {'const': PROTOCOL}, 'operation_key': {'type': 'string', 'format': 'uuid'},
    'command_sha256': HASH, 'predecessor': {'anyOf': [ID, {'type': 'null'}]}, 'revision': ID,
    'receipt': ID, 'document_version': ID, 'document_sha256': HASH, 'response': ID, 'evidence': ID,
    'client_name': {'type': 'string', 'minLength': 1, 'maxLength': 160, 'pattern': r'\S'},
    'responded_at': {'type': 'string', 'format': 'date-time'},
    'outcome': {'enum': ['signed', 'changes_requested', 'declined']}, 'genuine': {'const': True},
    'party_ref': {'anyOf': [{'type': 'string', 'minLength': 1, 'maxLength': 200}, {'type': 'null'}]},
    'party_identity_evidence': {'anyOf': [ID, {'type': 'null'}]},
    'signature_policy': {'anyOf': [ID, {'type': 'null'}]},
    'proofs': {'type': 'array', 'minItems': 1, 'maxItems': 12, 'items': PROOF},
    'authority': obj({'D05.role_principal_assignments': ID}),
    'assurance': {'const': 'human_witness_only_not_signature_provider_authentication'}})


def read(value):
    validate(VALUE, value)
    if len({proof['id'] for proof in value['proofs']}) != len(value['proofs']):
        from django.core.exceptions import ValidationError
        raise ValidationError('Use each proof file once.')
    return value
