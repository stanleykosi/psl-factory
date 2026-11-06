from django.core.exceptions import ValidationError
from adapters.forecast import obj
from .document_validators import typed,ROLES
COMPONENT='D11.engagement_identity_resolution'
SCHEMA='schema:psl/engagement-identity-resolution/v1'
VALUE=obj({'resolution_roles':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}},
    'max_decisions':{'type':'integer','minimum':1,'maximum':10000},'allow_synthetic':{'type':'boolean'}})
def validate_reference(component,target,case,runtime=False):
    v=typed(target,SCHEMA,VALUE)
    if case.kind!='project' or v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact project/classification identity criteria required')
    return v
