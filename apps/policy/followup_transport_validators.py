from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj,KEY
from .document_validators import typed,ROLES
OUTBOUND='OPS.finance_followup_transport';INBOUND='OPS.finance_followup_intake'
SCHEMAS={
 OUTBOUND:('schema:psl/finance-followup-transport/v1',obj({'sender_ref':KEY,'destination_ref':KEY,'endpoint_ref':KEY,'credential_ref':KEY,'credential_revision':KEY,
    'lease_seconds':{'type':'integer','minimum':30,'maximum':1800},'max_attempts':{'type':'integer','minimum':1,'maximum':10},'allow_synthetic':{'type':'boolean'}})),
 INBOUND:('schema:psl/finance-followup-intake/v1',obj({'sender_ref':KEY,'destination_ref':KEY,'principal_id':{'type':'integer','minimum':1},'principal_role':{'enum':ROLES},
    'evidence_id':{'type':'integer','minimum':1},'signature_window_seconds':{'type':'integer','minimum':1,'maximum':300},
    'variants':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['issue','deliver','adjust','adjust_deliver']}},'allow_synthetic':{'type':'boolean'}}))}

def validate_reference(component,target,case,runtime=False):
    v=typed(target,*SCHEMAS[component])
    if v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact transport fixture classification required')
    if component==INBOUND:
        if not case.evidence.filter(pk=v['evidence_id'],kind='integration_contract').exists():raise ValidationError('Current source-owned same-case intake contract evidence required')
        if not runtime:
            from django.contrib.auth import get_user_model
            from apps.finance.receipt_followup import access
            from apps.identity.services import require
            from .services import decision_authority
            try:
                actor=get_user_model().objects.get(pk=v['principal_id'],is_active=True)
                access(actor,case,'receive');access(actor,case);require(actor,case,'finance.receipt_followup.transport_receive')
                decision_authority(actor,case,v['principal_role'])
            except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Current source intake principal, purpose grants and D05 role required') from None
    return v
