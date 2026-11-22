"""Versioned human-reviewed revision intent, with unknown source slots retained."""
from apps.documents.contracts import validate
from .commercial_client_response import ID, HASH, obj

KIND = 'agent_private_commercial_rework'
PROTOCOL = 'commercial-rework/v1'
PREFIX = 'psl:' + PROTOCOL + ':'
SOURCE_KINDS = ('requirements', 'engineering_estimate', 'security_estimate', 'plan', 'costing')
PIN = obj({'id': ID, 'version': ID, 'sha256': HASH})
VALUE = obj({'protocol': {'const': PROTOCOL}, 'operation_key': {'type': 'string', 'format': 'uuid'},
    'command_sha256': HASH, 'predecessor': {'anyOf': [ID, {'type': 'null'}]},
    'witness': PIN, 'revision': ID, 'job': ID, 'review': PIN, 'draft_sha256': HASH,
    'sources': obj({kind: {'anyOf': [PIN, {'type': 'null'}]} for kind in SOURCE_KINDS}),
    'scope': {'type': 'string', 'minLength': 1, 'maxLength': 20000, 'pattern': r'\S'},
    'note': {'type': 'string', 'minLength': 1, 'maxLength': 4000, 'pattern': r'\S'},
    'human_confirmed': {'const': True}, 'cost_or_approval_inferred': {'const': False}})


def read(value):
    validate(VALUE, value)
    return value
