"""Accountability nominations are not business-role assignments or approval grants."""
from django.core.exceptions import ValidationError
from adapters.forecast import obj
from .document_validators import typed
from .factory_validators import ID

COMPONENT='OPS.factory_finance_responsibility'
SCHEMA='schema:psl/factory-finance-responsibility/v1'
SCHEMA_V2='schema:psl/factory-finance-responsibility/v2'
METHOD_V2='native_finance_single_review/v2'
SCHEMA_V3='schema:psl/factory-finance-responsibility/v3'
METHOD_V3='native_finance_single_review/v3'
OWNERS=('process_owner_id','activity_owner_id','policy_owner_id')
VALUE=obj({'definition':{'const':'pmo-finance/v1'},'process_id':{'const':'F30'},
    'activity':{'const':'ACT10'},'method':{'const':'native_finance_single_review/v1'},
    **{name:ID for name in (*OWNERS,'governance_resolver_id')}})
VALUE_V2=obj({**VALUE['properties'],'method':{'const':METHOD_V2},
    'authority_mode':{'enum':[None,'direct_only','direct_or_configured_delegate']}})
VALUE_V3=obj({**VALUE_V2['properties'],'method':{'const':METHOD_V3},
    'availability_mode':{'enum':[None,'not_applied','current_window_required']}})

def principal(case,pk,governance=False):
    from django.contrib.auth import get_user_model
    from apps.identity.services import require
    from django.core.exceptions import PermissionDenied
    user=get_user_model().objects.filter(pk=pk,is_active=True).first() if pk is not None else None
    if not user:return None
    try:
        for action in ['case.read','finance.read','factory.read']+(['policy.configure'] if governance else []):require(user,case,action)
    except PermissionDenied:return None
    return user

def validate_reference(component,target,case,runtime=False):
    value=(typed(target,SCHEMA_V3,VALUE_V3) if target.schema_ref==SCHEMA_V3 else
        typed(target,SCHEMA_V2,VALUE_V2) if target.schema_ref==SCHEMA_V2 else typed(target,SCHEMA,VALUE))
    if any(value[name] is not None and type(value[name]) is not int for name in (*OWNERS,'governance_resolver_id')):
        raise ValidationError('Nominee identities must be positive integers or explicitly unknown')
    if not runtime:
        for name in (*OWNERS,'governance_resolver_id'):
            if value[name] is not None and principal(case,value[name],name=='governance_resolver_id') is None:
                raise ValidationError('Responsibility nominations require an active principal with current same-project access; the governance resolver also needs configuration permission')
    return value
