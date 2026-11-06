from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj
from .document_validators import typed,ROLES
VARIANTS='OPS.native_finance_variants'
FOLLOWUP='OPS.finance_receipt_followup'
SCHEMAS={
 VARIANTS:('schema:psl/native-finance-variants/v1',obj({'variants':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['issue','deliver','adjust','adjust_deliver']}},'identifier_contract':{'const':'exact_incumbent_ids_v1'}})),
 FOLLOWUP:('schema:psl/finance-receipt-followup/v1',obj({'owner_id':{'type':'integer','minimum':1},'owner_role':{'enum':ROLES},
    'resolutions':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['investigate','link_current_intent','decline']}},
    'request_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},'allow_synthetic':{'type':'boolean'}}))}

@transaction.atomic
def validate_reference(component,target,case,runtime=False):
    v=typed(target,*SCHEMAS[component])
    if component==FOLLOWUP:
        if v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact follow-up fixture scope required')
        if not runtime:
            from django.contrib.auth import get_user_model
            from apps.finance.receipt_followup import access
            from .services import decision_authority
            try:
                actor=get_user_model().objects.get(pk=v['owner_id'],is_active=True)
                access(actor,case,'decide');decision_authority(actor,case,v['owner_role'])
            except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Current Finance follow-up owner required') from None
    return v
