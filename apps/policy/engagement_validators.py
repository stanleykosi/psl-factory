from django.core.exceptions import ValidationError
from adapters.forecast import obj,KEY
from .document_validators import typed,ROLES
ASSIGN='D11.engagement_assignment';REGISTER='D11.project_identifiers'
roles={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}}
SCHEMAS={
 ASSIGN:('schema:psl/engagement-assignment/v1',obj({'assignment_roles':roles,'allow_synthetic':{'type':'boolean'}})),
 REGISTER:('schema:psl/project-identifiers/v1',obj({'registration_roles':roles,'namespace':KEY,'format':{'enum':['ascii_token','bounded_text']},
    'max_length':{'type':'integer','minimum':1,'maximum':120},'case_sensitive':{'type':'boolean'},'allow_synthetic':{'type':'boolean'}}))}

def validate_reference(component,target,case,runtime=False):
    v=typed(target,*SCHEMAS[component])
    if case.kind!='project' or v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact project/classification engagement criteria required')
    return v
