from django.core.exceptions import ValidationError, PermissionDenied
from adapters.forecast import obj
from .document_validators import typed, ROLES
from .application_recovery_validators import REF

COMPONENT = 'OPS.cold_recovery'
SCHEMA = 'schema:psl/cold-recovery/v1'
VALUE = obj({
    **{k: REF for k in ['archive_ref', 'target_ref', 'key_ref']},
    **{k + '_id': {'type': 'integer', 'minimum': 1} for k in ['operator', 'reviewer']},
    **{k + '_role': {'enum': ROLES} for k in ['operator', 'reviewer']},
    'max_archive_bytes': {'type': 'integer', 'minimum': 1024, 'maximum': 134217728},
    'max_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 300},
    'lease_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 1800},
    'max_attempts': {'type': 'integer', 'minimum': 1, 'maximum': 10},
    'authorization_valid_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 31536000},
    'archive_valid_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 31536000},
    'allow_synthetic': {'type': 'boolean'},
})


def validate_reference(component, target, case, runtime=False):
    v = typed(target, SCHEMA, VALUE)
    if v['operator_id'] == v['reviewer_id'] or v['lease_seconds'] < 5 * v['max_seconds'] or v['allow_synthetic'] != case.synthetic:
        raise ValidationError('Independent principals, adequate command lease and explicit control scope required')
    if not runtime:
        from django.contrib.auth import get_user_model
        from apps.workflows.cold_recovery import access, provisioned
        from .services import decision_authority
        try:
            for key, purpose in [('operator', 'capture'), ('reviewer', 'review')]:
                a = get_user_model().objects.get(pk=v[key + '_id'], is_active=True)
                access(a, case, purpose)
                provisioned(a, purpose)
                decision_authority(a, case, v[key + '_role'])
        except (get_user_model().DoesNotExist, PermissionDenied):
            raise ValidationError('Fresh active deployment principals, purpose grants and D05 roles required') from None
    return v
