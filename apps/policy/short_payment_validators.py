"""Scoped decision authority for an issued invoice with a verified shortfall."""
from django.core.exceptions import ValidationError

from adapters.forecast import obj

from .document_validators import typed


COMPONENT = 'OPS.invoice_short_payment_review'
SCHEMA = 'schema:psl/invoice-short-payment-review/v1'
TREATMENTS = {
    'request_proof': 'Keep the balance owed and request proof',
    'record_exception': 'Approve an exception',
    'reject_exception': 'Reject the exception',
}
VALUE = obj({
    'reviewer_id': {'anyOf': [{'type': 'integer', 'minimum': 1}, {'type': 'null'}]},
    'treatments': {'type': 'array', 'uniqueItems': True, 'items': {'enum': list(TREATMENTS)}},
})


def validate_reference(target, case, *, runtime=False):
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project':
        raise ValidationError('Short-payment decisions require a project scope.')
    if bool(value['reviewer_id']) != bool(value['treatments']):
        raise ValidationError('Set the Finance reviewer and permitted treatments together.')
    if not runtime and value['reviewer_id'] is not None:
        from apps.identity.models import Grant
        needed = {'case.read', 'finance.read', 'finance.short_payment.read', 'finance.short_payment.decide'}
        grants = Grant.objects.filter(case=case, user_id=value['reviewer_id'], active=True, user__is_active=True,
                                      action__in=needed).values_list('action', flat=True)
        if set(grants) != needed:
            raise ValidationError('Choose a reviewer with current access to this workspace and decision.')
    return value
