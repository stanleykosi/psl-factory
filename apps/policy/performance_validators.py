import json
from datetime import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.pmo.services import subject
from apps.finance.rules import decimal
from apps.finance.performance_math import compare
from .document_validators import typed
from .finance_validators import obj,rows,KEY,KEYS,PERIOD,DEC

METRIC=obj({'key':KEY,'label':{'type':'string','minLength':1,'maxLength':100},'aggregation':{'enum':['sum','last_period']},
            'unit':{'enum':['major_currency','thousands_currency','millions_currency']}})
NULL_DEC={'anyOf':[DEC,{'type':'null'}]}
METHOD=obj({'implementation':{'const':'explicit_periods_v1'},'year_key':KEY,'entity':KEY,
    'periods':{'type':'array','minItems':12,'maxItems':12,'uniqueItems':True,'items':PERIOD},
    'bu_keys':KEYS,'include_company':{'type':'boolean'},'metrics':rows(METRIC),
    'budget_method':{'enum':['monthly_exact','annual_explicit_weights']},'annual_weights':rows(obj({'period':PERIOD,'weight':DEC}),0),
    'difference':{'const':'actual_minus_comparator'},'ratio':{'enum':['actual_over_budget','variance_over_absolute_budget']},
    'multiplier':{'enum':['1','100']},'zero_denominator':{'const':'unknown'},'decimal_places':{'type':'integer','minimum':0,'maximum':8},
    'rounding':{'enum':['half_even','half_up','down']},'prior_required':{'type':'boolean'},
    'oracle_evidence_id':{'type':'integer','minimum':1},'oracles':rows(obj({'key':KEY,'actual':NULL_DEC,'budget':NULL_DEC,'prior':NULL_DEC,
        'expected':obj({'variance':NULL_DEC,'prior_variance':NULL_DEC,'ratio':NULL_DEC})}),2)})

RESTATEMENT=obj({'implementation':{'const':'explicit_replacement_v1'},'written_request_required':{'const':True},
    'preserve_original':{'const':True},'allow_bu_scope_change':{'type':'boolean'},
    'historical_selection':{'enum':['current_only','explicit_original_or_current']}})


def validate_method(value,case):
    from jsonschema import Draft202012Validator
    errors=list(Draft202012Validator(METHOD).iter_errors(value))
    if errors:raise ValidationError([e.message for e in errors])
    try:months=[datetime.strptime(p,'%Y-%m').year*12+datetime.strptime(p,'%Y-%m').month for p in value['periods']]
    except ValueError:raise ValidationError('Fiscal periods must be actual monthly calendar dates')
    if months!=list(range(months[0],months[0]+12)):raise ValidationError('Supply twelve ordered consecutive fiscal months; January is not assumed')
    if len({x['key'] for x in value['metrics']})!=len(value['metrics']):raise ValidationError('Metric keys must be unique')
    if not value['include_company'] and not value['bu_keys']:raise ValidationError('Select company and/or explicit BU reporting scope')
    weights=value['annual_weights']
    if value['budget_method']=='monthly_exact' and weights:raise ValidationError('Monthly budgets must not be prorated')
    if value['budget_method']=='annual_explicit_weights':
        if len(weights)!=12 or {x['period'] for x in weights}!=set(value['periods']) or len({x['period'] for x in weights})!=12:raise ValidationError('Annual budget needs one explicit weight per fiscal month')
        if sum((decimal(x['weight'],nonnegative=True) for x in weights),Decimal(0))!=1:raise ValidationError('Annual weights must sum exactly to one')
    oracles=value['oracles'];source=subject(case,value['oracle_evidence_id'],'finance_oracle')
    try:cited=json.loads(source.body)
    except ValueError:raise ValidationError('Comparison oracle evidence needs exact structured scenarios')
    if cited!=oracles or len({x['key'] for x in oracles})!=len(oracles):raise ValidationError('Oracle source/scenario keys do not match')
    known=False;unknown=False
    for oracle in oracles:
        result=compare(oracle['actual'],oracle['budget'],oracle['prior'],value)
        for key,expected in oracle['expected'].items():
            actual=result[key]
            if (actual is None)!=(expected is None) or actual is not None and decimal(actual)!=decimal(expected):raise ValidationError('Comparison formula disagrees with supplied oracle '+oracle['key'])
        known|=result['ratio'] is not None;unknown|=result['ratio'] is None
    if not known or not unknown:raise ValidationError('Supply known and undefined/unknown ratio scenarios')


def validate_restatement(target,case):typed(target,'schema:psl/finance-restatement/v1',RESTATEMENT)
