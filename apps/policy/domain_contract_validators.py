from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from adapters.forecast import obj
from .document_validators import typed,ROLES
from .application_recovery_validators import REF

COMPONENT='OPS.domain_contracts'
SCHEMA='schema:psl/domain-contract-criteria/v1'
VALUE=obj({
    **{p+'_id':{'type':'integer','minimum':1} for p in ['operator','reviewer']},
    **{p+'_role':{'enum':ROLES} for p in ['operator','reviewer']},
    'allowed_provider_refs':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':REF},
    'destination_ref':REF,
    'review_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'observation_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'allow_synthetic':{'type':'boolean'},
    'activation_mode':{'const':'reviewed_preflight_only'},
})

@transaction.atomic
def validate_reference(component,target,case,runtime=False):
    value=typed(target,SCHEMA,VALUE)
    if value['operator_id']==value['reviewer_id'] or value['allow_synthetic']!=case.synthetic:
        raise ValidationError('Distinct current principals and exact synthetic scope required')
    if not runtime:
        from django.contrib.auth import get_user_model
        from apps.workflows.reconstitution import access
        from .services import decision_authority
        try:
            for prefix,purpose in [('operator','capture'),('reviewer','review')]:
                actor=get_user_model().objects.get(pk=value[prefix+'_id'],is_active=True)
                access(actor,case,purpose);decision_authority(actor,case,value[prefix+'_role'])
        except (get_user_model().DoesNotExist,PermissionDenied):
            raise ValidationError('Fresh current recovery purposes and D05 roles required') from None
    return value
