from django.core.exceptions import ValidationError, PermissionDenied
from adapters.forecast import obj
from .document_validators import typed, ROLES

COMPONENT = 'OPS.application_recovery'
SCHEMA = 'schema:psl/application-recovery/v1'
REF = {'type': 'string', 'pattern': '^[a-zA-Z0-9:_-]{1,100}$'}
VALUE = obj({
    'source_ref': REF, 'target_ref': REF, 'key_ref': REF,
    'operator_id': {'type': 'integer', 'minimum': 1}, 'operator_role': {'enum': ROLES},
    'reviewer_id': {'type': 'integer', 'minimum': 1}, 'reviewer_role': {'enum': ROLES},
    'attachment_ids': {'type': 'array', 'uniqueItems': True, 'maxItems': 1000, 'items': {'type': 'integer', 'minimum': 1}},
    'max_archive_bytes': {'type': 'integer', 'minimum': 1024, 'maximum': 134217728},
    'max_attachment_bytes': {'type': 'integer', 'minimum': 0, 'maximum': 67108864},
    'max_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 300},
    'lease_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 1800},
    'max_attempts': {'type': 'integer', 'minimum': 1, 'maximum': 10},
    'retention_days': {'type': 'integer', 'minimum': 1, 'maximum': 36500},
    'authorization_valid_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 31536000},
    'archive_valid_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 31536000},
    'allow_synthetic': {'type': 'boolean'},
})


def validate_reference(component, target, case, runtime=False):
    v = typed(target, SCHEMA, VALUE)
    if v['operator_id'] == v['reviewer_id']:
        raise ValidationError('Independent archive operator and human reviewer required')
    if v['lease_seconds'] < v['max_seconds'] * 5:
        raise ValidationError('Lease must cover the bounded dump/restore/verification command stages')
    if case.synthetic != v['allow_synthetic']:
        raise ValidationError('Explicit synthetic/operational source scope required')
    if not runtime:
        from django.contrib.auth import get_user_model
        from apps.workflows.application_recovery import access
        from .services import decision_authority
        try:
            for key, action in [('operator', 'capture'), ('reviewer', 'review')]:
                actor = get_user_model().objects.get(pk=v[key + '_id'], is_active=True)
                access(actor, case, action)
                decision_authority(actor, case, v[key + '_role'])
        except (get_user_model().DoesNotExist, PermissionDenied):
            raise ValidationError('Actual active principals, database-wide source grants and current human roles required') from None
    return v
