"""Engineering contract for scoped, receipt-verified project file archives."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError

from adapters.forecast import obj
from apps.identity.services import require
from .document_validators import typed


COMPONENT = 'OPS.archive_file_transfer'
SCHEMA = 'schema:psl/archive-file-transfer/v1'
VALUE = obj({
    'adapter': {'enum': ['private_object_store/v1', 'synthetic_archive/v1']},
    'operator_id': {'type': 'integer', 'minimum': 1},
    'max_files': {'type': 'integer', 'minimum': 1, 'maximum': 500},
    'max_bytes': {'type': 'integer', 'minimum': 1, 'maximum': 52428800},
    'lease_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 300},
})


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project':
        raise ValidationError('Project file archives require a project.')
    if value['adapter'] == 'synthetic_archive/v1' and not case.synthetic:
        raise ValidationError('The sample archive store is restricted to synthetic projects.')
    operator = get_user_model().objects.filter(pk=value['operator_id'], is_active=True).first()
    if not operator:
        raise ValidationError('Select an active archive operator.')
    try:
        for action in ['case.read', 'delivery.read', 'delivery.manage', 'delivery.archive_files']:
            require(operator, case, action)
    except PermissionDenied:
        raise ValidationError('The archive operator needs current project archive permissions.') from None
    return value
