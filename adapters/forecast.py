"""Supplied JSON evidence adapter. It does not authenticate bank/accounting sources."""
import json,re
from datetime import date
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from apps.finance.rules import decimal

KEY={'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}
MONEY={'anyOf':[{'type':'string','pattern':r'^-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$'},{'type':'null'}]}
DAY={'type':['string','null']}
def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def rows(props,minimum=0):return {'type':'array','minItems':minimum,'maxItems':100,'items':props}
OPENING=obj({'account':KEY,'amount':MONEY,'observed_on':{'type':'string'},'cutoff':{'const':'start_of_day'},'evidence_id':{'type':'integer','minimum':1}})
ITEM=obj({'key':KEY,'kind':{'enum':['receivable','other_inflow','outflow']},'source_ref':KEY,'owner':KEY,'amount':MONEY,'expected_on':DAY,'original_due':DAY,'issue_id':{'type':['integer','null'],'minimum':1},'evidence_id':{'type':'integer','minimum':1},'commitment':{'enum':['forecast_only','reported_commitment']}})
SCENARIO=obj({'entity':KEY,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'basis':{'const':'gross_cash'},'as_of':{'type':'string'},
    'months':{'type':'array','minItems':1,'maxItems':24,'uniqueItems':True,'items':{'type':'string','pattern':'^[0-9]{4}-(0[1-9]|1[0-2])$'}},
    'coverage':obj({'accounts':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':KEY},'inflows':{'enum':['complete','partial','unknown']},'outflows':{'enum':['complete','partial','unknown']},'omissions':rows({'type':'string','minLength':1,'maxLength':500})}),
    'openings':rows(OPENING),'items':rows(ITEM),'rollover':rows(obj({'key':KEY,'disposition':{'enum':['carry','cancel']},'reason':{'type':'string','minLength':1,'maxLength':1000}}))})
ACTUAL=obj({'entity':KEY,'account':KEY,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'basis':{'const':'gross_cash'},'source':KEY,'transaction':KEY,'direction':{'enum':['inflow','outflow']},'amount':MONEY,'occurred_on':{'type':'string'}})

def parsed(body,schema):
    try:v=json.loads(body)
    except (ValueError,TypeError):raise ValidationError('Supply bounded structured forecast JSON')
    validate(schema,v);return v

def day(value):
    try:return date.fromisoformat(value)
    except (ValueError,TypeError):raise ValidationError('Use an exact actual calendar date YYYY-MM-DD')

def scenario(body):
    v=parsed(body,SCENARIO);day(v['as_of'])
    months=v['months'];numbers=[int(m[:4])*12+int(m[5:]) for m in months]
    if any(b!=a+1 for a,b in zip(numbers,numbers[1:])):raise ValidationError('Supply ordered contiguous forecast months')
    if any(len({r[k] for r in v[collection]})!=len(v[collection]) for collection,k in [('items','key'),('openings','account'),('rollover','key')]):raise ValidationError('Duplicate forecast item/account/rollover keys')
    if len({(i['kind'],i['source_ref'],i['original_due']) for i in v['items']})!=len(v['items']):raise ValidationError('Duplicate source occurrence across forecast assumptions')
    for o in v['openings']:
        day(o['observed_on'])
        if o['amount'] is not None:decimal(o['amount'])
    for i in v['items']:
        for k in ['expected_on','original_due']:
            if i[k] is not None:day(i[k])
        if i['amount'] is not None:decimal(i['amount'],nonnegative=True)
        if (i['kind']=='receivable')!=(i['issue_id'] is not None):raise ValidationError('Only receivable items identify a canonical issued invoice')
    return v

def actual(body):
    v=parsed(body,ACTUAL);day(v['occurred_on'])
    if v['amount'] is not None:decimal(v['amount'],positive=True)
    return v
