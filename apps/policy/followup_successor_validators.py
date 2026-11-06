from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj
from .document_validators import typed,ROLES
COMPONENT='OPS.finance_followup_successors'
SCHEMA='schema:psl/finance-followup-successors/v1'
KINDS=['intent_generation','legal_correction']
EVIDENCE=['integration_contract','financial_correction_review']
VALUE=obj({'relations':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':KINDS}},
    'reviewer_id':{'type':'integer','minimum':1},'reviewer_role':{'enum':ROLES},
    'evidence_kinds':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':EVIDENCE}},
    'valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},'allow_synthetic':{'type':'boolean'}})

def validate_reference(component,target,case,runtime=False):
    v=typed(target,SCHEMA,VALUE)
    if v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact successor policy classification required')
    if not runtime:
        from django.contrib.auth import get_user_model
        from apps.finance.receipt_followup import access
        from .services import decision_authority
        try:
            actor=get_user_model().objects.get(pk=v['reviewer_id'],is_active=True)
            access(actor,case,'review_successor');decision_authority(actor,case,v['reviewer_role'])
        except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Current independent Finance lineage reviewer required') from None
    return v
