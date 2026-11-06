"""F43 owner choices. No defaults for eligibility, membership or arithmetic."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj
from .document_validators import ROLES

def selections(values):
    return {'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'enum':values}}

FIELDS=['kind','amount','expected_on','original_due','commitment','residual','matched']
METADATA=['entity','currency','basis','as_of']
GROUP=obj({
    'implementation':{'enum':['native_selected_items_v1','owner_aggregate_pending']},
    'run_id':{'type':'integer','minimum':1},
    'run_hash':{'type':'string','pattern':'^[a-f0-9]{64}$'},
    'rows':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'string','minLength':1,'maxLength':100}},
    'fields':selections(FIELDS), 'metadata':selections(METADATA),
    'recipient_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
    'reviewer_roles':selections(ROLES),'publisher_roles':selections(ROLES),
    'allow_preparer_review':{'type':'boolean'},
    'oracle_evidence_id':{'type':'integer','minimum':1},
})

def validate_group(value):
    validate(GROUP,value)
    if not {'currency','basis','as_of'}.issubset(value['metadata']):
        raise ValidationError('Explicit source currency, accounting basis and as-of date must accompany selected cash rows')
