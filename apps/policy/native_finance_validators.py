from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj
from .document_validators import typed,ROLES
from .application_recovery_validators import REF
COMPONENT='OPS.native_finance_receipts'
SCHEMA='schema:psl/native-finance-receipts/v1'
VALUE=obj({
    **{p+'_id':{'type':'integer','minimum':1} for p in ['operator','reviewer']},
    **{p+'_role':{'enum':ROLES} for p in ['operator','reviewer']},
    'provider_ref':REF,'store_ref':REF,'destination_ref':REF,
    'max_payload_bytes':{'type':'integer','minimum':256,'maximum':1048576},
    'max_seconds':{'type':'integer','minimum':1,'maximum':60},
    'observation_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'review_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'lease_seconds':{'type':'integer','minimum':10,'maximum':1800},
    'max_attempts':{'type':'integer','minimum':1,'maximum':10},
    'allow_synthetic':{'type':'boolean'},'activation_mode':{'const':'inert_companion_only'},
})

@transaction.atomic
def validate_reference(component,target,case,runtime=False):
    v=typed(target,SCHEMA,VALUE)
    if v['operator_id']==v['reviewer_id'] or v['allow_synthetic']!=case.synthetic or v['lease_seconds']<v['max_seconds']*2:
        raise ValidationError('Distinct current principals, exact fixture scope and sufficient bounded lease required')
    if not runtime:
        from django.contrib.auth import get_user_model
        from apps.workflows.native_finance import access
        from .services import decision_authority
        try:
            for prefix,purpose in [('operator','capture'),('reviewer','review')]:
                actor=get_user_model().objects.get(pk=v[prefix+'_id'],is_active=True)
                access(actor,case,purpose);decision_authority(actor,case,v[prefix+'_role'])
        except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Fresh Finance purpose/role principals required') from None
    return v
