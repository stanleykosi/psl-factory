from decimal import Decimal,localcontext
import json
from django.core.exceptions import ValidationError
from apps.pmo.services import subject
from apps.finance.rules import decimal
from .document_validators import typed,ROLES
from adapters.forecast import obj,rows,MONEY

METHOD=obj({'implementation':{'const':'monthly_cash_chain_v1'},'decimal_places':{'type':'integer','minimum':0,'maximum':8},
    'opening_max_age_days':{'type':'integer','minimum':0,'maximum':365},'partial_publication':{'enum':['hold','label_partial']},
    'matching':{'enum':['exact_only','explicit_partial']},'match_reversal':{'const':'full_once'},'rollover':{'const':'explicit_dates_and_reasons'},
    'actual_roles':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}},'distinct_actual_reporter':{'type':'boolean'},
    'oracle_evidence_id':{'type':'integer','minimum':1},'oracles':rows(obj({'opening':MONEY,'inflow':MONEY,'outflow':MONEY,'expected':MONEY}),2)})
PROJECTION=obj({'forecast':rows(obj({'audience':{'enum':['internal','management']},'publisher_roles':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}},
    'columns':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['opening','inflow','outflow','closing']}},'disclosure':{'const':'aggregate_with_coverage'}}),1)})

def chain(opening,inflow,outflow):
    if any(v is None for v in [opening,inflow,outflow]):return None
    with localcontext() as ctx:
        ctx.prec=512
        value=decimal(opening)+decimal(inflow)-decimal(outflow)
        if abs(value)>=Decimal('1e24'):raise ValidationError('Forecast numeric budget exceeded')
        return format(value,'f')

def validate_method(target,case):
    v=typed(target,'schema:psl/forecast-method/v1',METHOD)
    source=subject(case,v['oracle_evidence_id'],'forecast_oracle')
    try:content=json.loads(source.body)
    except (ValueError,TypeError):raise ValidationError('Forecast oracles require structured evidence')
    if content!=v['oracles']:raise ValidationError('Forecast oracles differ from their exact cited evidence')
    known=unknown=False
    for o in v['oracles']:
        actual=chain(o['opening'],o['inflow'],o['outflow']);expected=o['expected']
        if (actual is None)!=(expected is None) or actual is not None and decimal(actual)!=decimal(expected):raise ValidationError('Forecast chain fails supplied golden oracle')
        known|=actual is not None;unknown|=actual is None
    if not known or not unknown:raise ValidationError('Supply known and unknown forecast oracle cases')

def validate_projection(target):
    import copy
    from .finance_validators import SCHEMAS
    schema=copy.deepcopy(PROJECTION);existing=copy.deepcopy(SCHEMAS['D10.audience_projection_rules'][1]['properties'])
    audience=existing['audiences']['items']
    audience['properties'].update(columns={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['actual','budget','prior','variance','prior_variance','ratio']}},charts={'type':'boolean'})
    schema['properties'].update(existing)
    from .group_forecast_validators import GROUP,validate_group
    schema['properties']['group']=GROUP
    v=typed(target,'schema:psl/forecast-projection/v1',schema)
    if 'group' in v:validate_group(v['group'])
    if len({r['audience'] for r in v['forecast']})!=len(v['forecast']):raise ValidationError('Duplicate forecast audience')
    audiences=v.get('audiences',[])
    if ('audiences' in v)!=('disclosure' in v) or len({r['audience'] for r in audiences})!=len(audiences):raise ValidationError('Preserve exact existing Finance projection and disclosure together')
    if any(not r['formula_keys'] or not r['include_company'] and not r['bu_keys'] or r.get('charts') and not set(r.get('columns',[])) & {'actual','budget','prior'} for r in audiences):raise ValidationError('Existing Finance projection needs valid aggregate/chart selection')
