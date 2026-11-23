from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj
from .document_validators import typed,ROLES
import copy
COMPONENT='D11.planning_alignment'
SCHEMA='schema:psl/planning-alignment/v1'
TEAMS=['Engineering','QA','Infra','Security']
STATES=['unresolved','resolved','deferred']
ACTION_STATES=['open','in_progress','paused','completed','cancelled']
ID={'type':'integer','minimum':1};NULL={'type':'null'}
VALUE=obj({'blocking_question_states':{'type':'array','uniqueItems':True,'items':{'enum':STATES}},
    'require_named_contacts':{'type':'array','uniqueItems':True,'items':{'enum':TEAMS}},
    'allowed_action_states':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ACTION_STATES}},
    'alignment_max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'comparison_reviewer_id':{'anyOf':[ID,NULL]},'comparison_reviewer_role':{'anyOf':[{'enum':ROLES},NULL]},
    'independent_comparison':{'type':'boolean'},'allow_synthetic':{'type':'boolean'}})
SCHEMA_V2='schema:psl/planning-alignment/v2'
DEPARTMENTS=['Engineering','QA','Security','Product','Infrastructure']
DEPARTMENT_RULES=obj({
    'required_departments':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':DEPARTMENTS}},
    'effort_required_for':{'type':'array','uniqueItems':True,'items':{'enum':DEPARTMENTS}},
    'recorder_roles':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}},
    'reviewer_roles':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}},
    'allow_recorder_review':{'type':'boolean'},
    'changed_effort_action':{'enum':['review_required','fresh_costing_required']}})
VALUE_V2=copy.deepcopy(VALUE)
VALUE_V2['properties']['department_inputs']=DEPARTMENT_RULES
VALUE_V2['required'].append('department_inputs')

def validate_reference(component,target,case,runtime=False):
    extended=target.schema_ref==SCHEMA_V2
    value=typed(target,SCHEMA_V2 if extended else SCHEMA,VALUE_V2 if extended else VALUE)
    if extended and set(value['department_inputs']['effort_required_for'])-set(value['department_inputs']['required_departments']):
        raise ValidationError('Effort requirements must refer to required departments.')
    if case.kind!='project' or value['allow_synthetic']!=case.synthetic:raise ValidationError('Exact project/classification planning criteria required')
    if (value['comparison_reviewer_id'] is None)!=(value['comparison_reviewer_role'] is None):raise ValidationError('Comparison principal and role must be configured together')
    if not runtime and value['comparison_reviewer_id'] is not None:
        from apps.identity.services import require
        from .services import decision_authority
        try:
            a=get_user_model().objects.get(pk=value['comparison_reviewer_id'],is_active=True)
            for action in ['case.read','planning.read','planning.compare']:require(a,case,action)
            decision_authority(a,case,value['comparison_reviewer_role'])
        except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Current actual comparison principal, role and case-purpose grants required') from None
    return value
