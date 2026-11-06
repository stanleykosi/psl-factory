"""Receipt-only transport recovery; no provider activation or new planning permission."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from adapters.forecast import obj
from apps.identity.services import require
from .document_validators import typed,ROLES
from .factory_validators import ID
from .role_assignments import instant

COMPONENT='OPS.factory_receipt_recovery'
SCHEMA='schema:psl/factory-receipt-recovery/v1'
METHOD='same_provider_receipt_lookup_v1'
TIME={'anyOf':[{'type':'string','format':'date-time'},{'type':'null'}]}
VALUE=obj({'method':{'enum':[None,METHOD]},'reviewer_id':ID,'review_role':{'enum':[None,*ROLES]},
           'independent_of_requester':{'type':['boolean','null']},'valid_from':TIME,'valid_until':TIME})

def validate_reference(component,target,case,runtime=False):
    value=typed(target,SCHEMA,VALUE)
    if value['reviewer_id'] is not None and type(value['reviewer_id']) is not int:raise ValidationError('Exact receipt reviewer identity required')
    for key in ['valid_from','valid_until']:
        if value[key] is not None:instant(value[key])
    if all(value[k] is not None for k in ['valid_from','valid_until']) and instant(value['valid_from'])>=instant(value['valid_until']):
        raise ValidationError('Receipt recovery requires an ordered validity window')
    if not runtime and value['reviewer_id'] is not None:
        user=get_user_model().objects.filter(pk=value['reviewer_id'],is_active=True).first()
        if not user:raise ValidationError('Current receipt reviewer required')
        try:
            for action in ['case.read','factory.read','factory.manage','integration.read','integration.source.read','integration.review']:require(user,case,action)
            if value['review_role'] is not None:
                from .services import decision_authority
                decision_authority(user,case,value['review_role'])
        except (PermissionDenied,ValidationError):raise ValidationError('Reviewer nomination requires existing scoped grants and native responsibility') from None
    return value
