"""Versioned historical-fact interchange; no RFP approval becomes Planning approval."""
from adapters.forecast import obj
from apps.documents.contracts import validate

PROTOCOL='psl.won-planning-sources/v1'
ID={'type':'integer','minimum':1}
INPUTS=['prd_id','scope_id','engineering_estimate_id','security_estimate_id']
SOURCE=obj({'id':ID,'kind':{'type':'string'},'source':{'type':'string'},
            'version':{'type':'integer','minimum':1},'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}})
QUOTE=obj({'amount':{'type':'string','pattern':r'^[0-9]+(?:\.[0-9]+)?$'},
           'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'basis':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,79}$'}})
VALUE=obj({'format':{'const':PROTOCOL},'capture':ID,'disposition':ID,'submission':ID,'response':ID,
    'reference':{'type':'string','minLength':1,'maxLength':160},'response_number':{'type':'integer','minimum':1},
    'inputs':obj({key:SOURCE for key in INPUTS}),'response_source':SOURCE,'terms_source':SOURCE,
    'quoted_price':{'anyOf':[QUOTE,{'type':'null'}]},
    'requirements':{'type':'integer','minimum':1,'maximum':100},'addressed':{'type':'integer','minimum':0,'maximum':100},
    'historical_authority_reused':{'const':False},'planning_approval_granted':{'const':False}})


def checked(value):
    validate(VALUE,value)
    return value
