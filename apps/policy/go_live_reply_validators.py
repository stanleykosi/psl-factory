from adapters.forecast import obj
from .document_validators import ROLES, typed


SCHEMA = 'schema:psl/go-live-client-replies/v1'
CHANNELS = ['email', 'customer_portal', 'meeting', 'phone', 'other']
ROLE_LIST = {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'enum': ROLES}}
VALUE = obj({
    'kind': {'const': 'go_live_reply'},
    'key': {'const': 'client_responses'},
    'recording_roles': ROLE_LIST,
    'correction_roles': ROLE_LIST,
    'remediation_roles': ROLE_LIST,
    'allow_recorder_correction': {'type': 'boolean'},
    'channels': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'enum': CHANNELS}},
    'changes_handling': {'enum': ['reviewed_document_successor', 'owner_review']},
    'decline_handling': {'enum': ['new_release_candidate', 'owner_review']},
    'issue_states_for_new_release': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                                     'items': {'enum': ['Resolved', 'Closed']}},
})


def validate_reference(target, case):
    from django.core.exceptions import ValidationError
    if case.kind != 'project':
        raise ValidationError('Go-live responses belong to a project.')
    return typed(target, SCHEMA, VALUE)
