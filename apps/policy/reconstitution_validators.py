from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from adapters.forecast import obj
from .application_recovery_validators import REF
from .document_validators import typed, ROLES

COMPONENT='OPS.reconstitution'
SCHEMA='schema:psl/reconstitution/v1'
DISPOSITIONS=['unresolved','retain_quarantine','receipt_confirmed','replacement_required']
VALUE=obj({
 'profile_ref':REF,'destination_ref':REF,
 **{p+'_id':{'type':'integer','minimum':1} for p in ['operator','reviewer']},
 **{p+'_role':{'enum':ROLES} for p in ['operator','reviewer']},
 'allowed_dispositions':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':DISPOSITIONS}},
 'max_records':{'type':'integer','minimum':1,'maximum':5000},
 'receipt_max_bytes':{'type':'integer','minimum':256,'maximum':1048576},
 'receipt_freshness_seconds':{'type':'integer','minimum':1,'maximum':31536000},
 'review_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},
 'lease_seconds':{'type':'integer','minimum':10,'maximum':1800},
 'max_attempts':{'type':'integer','minimum':1,'maximum':10},
 'activation_mode':{'const':'reviewed_plan_only'},'allow_synthetic':{'type':'boolean'},
})


@transaction.atomic
def validate_reference(component,target,case,runtime=False):
    v=typed(target,SCHEMA,VALUE)
    if v['operator_id']==v['reviewer_id'] or v['allow_synthetic']!=case.synthetic:
        raise ValidationError('Distinct fresh human principals and explicit synthetic/operational scope required')
    if not runtime:
        from django.contrib.auth import get_user_model
        from apps.workflows.reconstitution import access
        from .services import decision_authority
        try:
            for prefix,purpose in [('operator','capture'),('reviewer','review')]:
                a=get_user_model().objects.get(pk=v[prefix+'_id'],is_active=True)
                access(a,case,purpose)
                decision_authority(a,case,v[prefix+'_role'])
        except (get_user_model().DoesNotExist,PermissionDenied):
            raise ValidationError('Fresh deployed principals, archive-scope purpose grants and current D05 roles required') from None
    return v
