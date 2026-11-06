"""Reviewed replacement execution authority; no appointments, roles or windows inferred."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from adapters.forecast import obj
from apps.identity.services import require
from apps.workflows.factory_definitions import DEFINITIONS
from .document_validators import typed,ROLES
from .factory_validators import ID
from .role_assignments import instant

COMPONENT='OPS.factory_recovery_authority'
SCHEMA='schema:psl/factory-recovery-authority/v1'
METHOD='reviewed_execution_principal_v1'
TIME={'anyOf':[{'type':'string','format':'date-time'},{'type':'null'}]}
RULE=obj({'definition':{'enum':list(DEFINITIONS)},'method':{'enum':[None,METHOD]},
    'principal_id':ID,'reviewer_id':ID,'review_role':{'enum':[None,*ROLES]},
    'independent_of_worker':{'type':['boolean','null']},'valid_from':TIME,'valid_until':TIME})
VALUE=obj({'rules':{'type':'array','minItems':1,'maxItems':len(DEFINITIONS),'items':RULE}})

def validate_reference(component,target,case,runtime=False):
    value=typed(target,SCHEMA,VALUE);seen=set()
    for rule in value['rules']:
        name=rule['definition']
        if name in seen:raise ValidationError('Only one recovery authority rule per work type is permitted')
        seen.add(name)
        for key in ['principal_id','reviewer_id']:
            if rule[key] is not None and type(rule[key]) is not int:raise ValidationError('Exact recovery principal identities required')
        for key in ['valid_from','valid_until']:
            if rule[key] is not None:instant(rule[key])
        if rule['valid_from'] is not None and rule['valid_until'] is not None and instant(rule['valid_from'])>=instant(rule['valid_until']):
            raise ValidationError('Recovery authority needs an ordered explicit validity window')
        if rule['independent_of_worker'] is True and rule['principal_id'] is not None and rule['principal_id']==rule['reviewer_id']:
            raise ValidationError('The configured independent reviewer must differ from the replacement worker')
        if runtime:continue
        for key,actions in [('principal_id',['factory.execute']),('reviewer_id',['factory.manage'])]:
            if rule[key] is None:continue
            user=get_user_model().objects.filter(pk=rule[key],is_active=True).first()
            if not user:raise ValidationError('Recovery nominees must be current active people')
            try:
                for action in ['case.read','factory.read',DEFINITIONS[name]['read'],*actions]:require(user,case,action)
                if key=='reviewer_id' and rule['review_role'] is not None:
                    from .services import decision_authority
                    decision_authority(user,case,rule['review_role'])
            except (PermissionDenied,ValidationError):raise ValidationError('Recovery nomination needs current scoped permissions and the configured native review role') from None
    return value
