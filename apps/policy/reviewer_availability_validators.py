"""Owner-evidenced availability is an operational constraint, never an authority grant."""
from django.core.exceptions import ValidationError
from jsonschema import Draft202012Validator
from adapters.forecast import obj
from .document_validators import typed
from .role_assignments import instant

COMPONENT='OPS.factory_review_availability'
SCHEMA='schema:psl/factory-review-availability/v1'
RECORD=obj({'principal_id':{'type':'integer','minimum':1},'status':{'enum':['available','unavailable',None]},
    'valid_from':{'type':'string'},'valid_until':{'type':'string'}})
VALUE=obj({'purpose':{'const':'finance.invoice.review'},'records':{'type':'array','maxItems':200,'items':RECORD}})

def validate_value(case,value,runtime=False):
    if list(Draft202012Validator(VALUE).iter_errors(value)):raise ValidationError('Closed typed reviewer availability records required')
    from apps.identity.models import Grant
    periods={}
    for record in value['records']:
        pk=record['principal_id']
        if type(pk) is not int:raise ValidationError('Exact integer reviewer identity required')
        left,right=instant(record['valid_from']),instant(record['valid_until'])
        if left>=right:raise ValidationError('Availability needs a finite increasing timezone-aware window')
        if not runtime and not Grant.objects.filter(case=case,user_id=pk,active=True,action='case.read').exists():
            raise ValidationError('Availability records require current same-workspace membership')
        if any(max(left,a)<min(right,b) for a,b in periods.get(pk,[])):
            raise ValidationError('Overlapping availability windows require explicit owner correction')
        periods.setdefault(pk,[]).append((left,right))
    return value

def validate_reference(component,target,case,runtime=False):
    return validate_value(case,typed(target,SCHEMA,VALUE),runtime)
