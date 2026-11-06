import math
from django.core.exceptions import ValidationError
from .document_validators import typed

SUPPORTED={'D11.hypercare_criteria_ref'}
METRIC={'type':'object','properties':{'key':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,39}$'},
    'unit':{'type':'string','minLength':1,'maxLength':40},'owner':{'enum':['Engineering','Infrastructure']},
    'operator':{'enum':['lte','gte','eq']},'threshold':{'type':'number'}},
    'required':['key','unit','owner','operator','threshold'],'additionalProperties':False}


def validate_reference(component,target,case):
    c=typed(target,'schema:psl/hypercare-criteria/v1',{'type':'object','properties':{
        'clock':{'const':'elapsed_hours_since_release'},'minimum_hours':{'type':'number','minimum':0,'maximum':87600},
        'confirmation_owners':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['Engineering','Infrastructure']}},
        'metrics':{'type':'array','minItems':1,'maxItems':20,'items':METRIC},'financial_controls':{'const':'independent'}},
        'required':['clock','minimum_hours','confirmation_owners','metrics','financial_controls'],'additionalProperties':False})
    if not math.isfinite(c['minimum_hours']) or any(not math.isfinite(m['threshold']) for m in c['metrics']):
        raise ValidationError('Hypercare numeric criteria must be finite')
    keys=[(m['owner'],m['key']) for m in c['metrics']]
    if len(keys)!=len(set(keys)) or any(m['owner'] not in c['confirmation_owners'] for m in c['metrics']):
        raise ValidationError('Metric owner/key must be unique and require an explicit confirmation owner')
