from datetime import datetime
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.pmo.services import subject
from apps.finance.rules import decimal,evaluate,formula_order
from .document_validators import typed,ROLES

SUPPORTED={'D06.statement_contract','D06.account_bu_maps','D06.rule_oracle_refs','D07.authorized_input_refs','D07.join_overlap_rule_id',
    'D07.effective_membership_ref','D07.allocation_pool_rules','D07.rounding_residual_rule_id',
    'D10.report_category_effective_dates','D10.audience_projection_rules','D10.restatement_rule_id','D10.forecast_inclusion_rule_id'}
KEY={'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}
ACCOUNT={'type':'string','minLength':1,'maxLength':160,'pattern':r'^[^\x00-\x1f\x7f]+$'}
DEC={'type':'string','pattern':'^-?(0|[1-9][0-9]{0,23})(\\.[0-9]{1,8})?$'}
PERIOD={'type':'string','pattern':'^[0-9]{4}-(0[1-9]|1[0-2])$'}
KEYS={'type':'array','maxItems':100,'uniqueItems':True,'items':KEY}
BASE={'key':KEY,'entity':KEY,'from_period':PERIOD,'to_period':PERIOD}

def obj(props,required=None):return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
def rows(item,minimum=1):return {'type':'array','minItems':minimum,'maxItems':100,'items':item}

SCHEMAS={
'D06.account_bu_maps':('finance-account-map',obj(dict(BASE,account=ACCOUNT,report_line=KEY,
    metric={'enum':['revenue','direct_cost','staff_cost','opex','asset','liability','equity','other']},
    treatment={'enum':['company','direct','pool']},bu={'anyOf':[KEY,{'type':'null'}]},pool={'anyOf':[KEY,{'type':'null'}]},
    source_rows={'enum':['reject_duplicate_accounts','preserve_explicit_rows']}))),
'D06.rule_oracle_refs':('finance-formula',obj(dict(BASE,implementation={'const':'linear_decimal_v1'},scope={'enum':['company_only','company_and_bu']},
    terms=rows(obj({'kind':{'enum':['line','formula']},'key':KEY,'coefficient':DEC,'value_stage':{'enum':['base_value','rounded_formula','unrounded_formula']}})),divisor=DEC,
    output_unit={'enum':['major_currency','thousands_currency','millions_currency']},decimal_places={'type':'integer','minimum':0,'maximum':8},rounding={'enum':['half_even','half_up','down']},
    oracle_evidence_id={'type':'integer','minimum':1},oracles=rows(obj({'key':KEY,'inputs':rows(obj({'kind':{'enum':['line','formula']},'key':KEY,'value':{'anyOf':[DEC,{'type':'null'}]}})),
        'expected':{'anyOf':[DEC,{'type':'null'}]}}),2)))),
'D10.report_category_effective_dates':('finance-bu',obj(dict(BASE,name={'type':'string','minLength':1,'maxLength':160}))),
'D07.allocation_pool_rules':('finance-pool',obj(dict(BASE,pool=KEY,metric={'enum':['revenue','direct_cost','staff_cost','opex','other']},method={'enum':['fixed_weights','headcount_weighted']},
    weights=rows(obj({'bu':KEY,'weight':DEC}),0),excluded_bu_keys=KEYS,excluded_accounts={'type':'array','maxItems':100,'uniqueItems':True,'items':ACCOUNT}))),
'D07.rounding_residual_rule_id':('finance-rounding',obj({'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']},
    'residual':{'enum':['hold','assign_to_configured_bu']},'residual_bu':{'anyOf':[KEY,{'type':'null'}]},'source_precision':{'const':'reject_excess_precision'}})),
'D07.authorized_input_refs':('finance-authorized-basis',obj({'entity':KEY,'period':PERIOD,'provider':{'enum':['HR','Finance']},'evidence_id':{'type':'integer','minimum':1},'purpose':{'const':'allocation_basis'}})),
'D07.join_overlap_rule_id':('finance-basis-join',obj({'implementation':{'const':'single_effective_snapshot_v1'},'match_key':{'const':'subject_ref'},'duplicate_subjects':{'const':'reject'},
    'period_basis':{'const':'snapshot_at_as_of'},'weight_semantics':{'enum':['unit_per_subject','explicit_fte']}})),
'D07.effective_membership_ref':('finance-membership',obj({'entity':KEY,'period':PERIOD,'as_of':{'type':'string'},'evidence_id':{'type':'integer','minimum':1},
    'completeness':{'enum':['complete','partial','unknown']},'rows':rows(obj({'subject_ref':KEY,'bu':KEY,'weight':{'anyOf':[DEC,{'type':'null'}]}}))})),
'D10.audience_projection_rules':('finance-projection',obj({'disclosure':{'const':'aggregate_only'},'audiences':rows(obj({'audience':{'enum':['internal','management']},
    'formula_keys':KEYS,'bu_keys':KEYS,'include_company':{'type':'boolean'},'publisher_roles':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}}}))}))}

def validate_reference(component,target,case,runtime=False):
    if component=='D10.forecast_inclusion_rule_id':
        from .forecast_validators import validate_method
        validate_method(target,case);return
    if component=='D10.audience_projection_rules' and target.schema_ref=='schema:psl/forecast-projection/v1':
        from .forecast_validators import validate_projection
        validate_projection(target);return
    if component=='D10.restatement_rule_id':
        from .performance_validators import validate_restatement
        validate_restatement(target,case);return
    if component=='D06.unit_sign_currency_period':
        from .performance_validators import METHOD,validate_method
        v3=target.schema_ref=='schema:psl/source-conventions/v3'
        extra={'performance':METHOD} if v3 else {}
        v=typed(target,'schema:psl/source-conventions/v3' if v3 else 'schema:psl/source-conventions/v2',obj(dict({'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'unit':{'const':'major_currency'},
            'period':PERIOD,'sign_convention':{'enum':['debit_positive','credit_positive']},'report_controls':obj({'require_source_total':{'type':'boolean'},'tolerance':DEC,'bu_tolerance':DEC},required=['require_source_total','tolerance'])},**extra)))
        decimal(v['report_controls']['tolerance'],nonnegative=True)
        if 'bu_tolerance' in v['report_controls']:decimal(v['report_controls']['bu_tolerance'],nonnegative=True)
        if v3:validate_method(v['performance'],case)
        return
    if component=='D06.statement_contract':
        from .statement_validators import validate_reference as validate_statement
        return validate_statement(target,case)
    name,schema=SCHEMAS[component]
    projection_v2=component=='D10.audience_projection_rules' and target.schema_ref=='schema:psl/finance-projection/v2'
    if projection_v2:
        import copy
        schema=copy.deepcopy(schema);audience=schema['properties']['audiences']['items']
        audience['properties'].update(columns={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['actual','budget','prior','variance','prior_variance','ratio']}},charts={'type':'boolean'})
        audience['required']+=['columns','charts']
    v=typed(target,'schema:psl/'+name+('/v2' if projection_v2 else '/v1'),schema)
    if 'from_period' in v and v['to_period']<v['from_period']:raise ValidationError('Effective periods are reversed')
    if component=='D06.account_bu_maps':
        if v['account']!=v['account'].strip():raise ValidationError('Account identifier must match the supplied trimmed source exactly')
        valid={'company':(False,False),'direct':(True,False),'pool':(False,True)}[v['treatment']]
        if (v['bu'] is not None,v['pool'] is not None)!=valid:raise ValidationError('Select only the BU or pool required by the mapping treatment')
    elif component=='D06.rule_oracle_refs':
        for t in v['terms']:
            decimal(t['coefficient'])
            if (t['kind']=='line')!=(t['value_stage']=='base_value'):raise ValidationError('Select explicit base-line or rounded/unrounded formula operand stage')
        if len({(t['kind'],t['key']) for t in v['terms']})!=len(v['terms']):raise ValidationError('Repeated formula operands must be expressed as one explicit coefficient')
        divisor=decimal(v['divisor'],positive=True)
        if divisor!={'major_currency':1,'thousands_currency':1000,'millions_currency':1000000}[v['output_unit']]:raise ValidationError('Presentation unit and explicit divisor disagree')
        oracle_source=subject(case,v['oracle_evidence_id'],'finance_oracle')
        import json
        try: actual_oracles=json.loads(oracle_source.body)
        except (ValueError,TypeError):raise ValidationError('Oracle evidence must contain the exact structured scenarios')
        if actual_oracles!=v['oracles']:raise ValidationError('Formula scenarios differ from their cited oracle evidence')
        known=False;unknown=False
        if len({x['key'] for x in v['oracles']})!=len(v['oracles']):raise ValidationError('Oracle scenario keys must be unique')
        for oracle in v['oracles']:
            inputs={(x['kind'],x['key']):x['value'] for x in oracle['inputs']}
            if len(inputs)!=len(oracle['inputs']) or set(inputs)!={(t['kind'],t['key']) for t in v['terms']}:raise ValidationError('Oracle must supply each exact operand once')
            for value in inputs.values():
                if value is not None:decimal(value)
            actual=evaluate(v,inputs)['value'];expected=oracle['expected']
            if (actual is None)!=(expected is None) or actual is not None and decimal(actual)!=decimal(expected):raise ValidationError('Registered formula does not match its supplied oracle: '+oracle['key'])
            known|=actual is not None;unknown|=actual is None
        if not known or not unknown:raise ValidationError('Supply known-value and unknown-propagation oracle scenarios')
    elif component=='D07.allocation_pool_rules':
        if any(x!=x.strip() for x in v['excluded_accounts']):raise ValidationError('Excluded accounts must match exact supplied identifiers')
        if v['method']=='headcount_weighted' and v['weights'] or v['method']=='fixed_weights' and not v['weights']:raise ValidationError('Only fixed-weight rules supply explicit weights')
        if len({x['bu'] for x in v['weights']})!=len(v['weights']):raise ValidationError('Duplicate BU weight')
        for x in v['weights']:decimal(x['weight'],nonnegative=True)
        if v['weights'] and sum(decimal(x['weight']) for x in v['weights'])<=0:raise ValidationError('Fixed-weight denominator must be positive')
    elif component=='D07.rounding_residual_rule_id':
        if (v['residual']=='hold')!=(v['residual_bu'] is None):raise ValidationError('Explicit residual destination required only for assignment')
    elif component in ['D07.authorized_input_refs','D07.effective_membership_ref']:
        subject(case,v['evidence_id'],'finance_basis')
        if component=='D07.effective_membership_ref':
            try:
                at=datetime.fromisoformat(v['as_of'])
                if at.utcoffset() is None or at.strftime('%Y-%m')!=v['period'] or at>timezone.now():raise ValueError
            except (ValueError,TypeError):raise ValidationError('Basis as-of must be actual, aware and within the stated period')
            import json
            try:source=json.loads(subject(case,v['evidence_id'],'finance_basis').body)
            except (ValueError,TypeError):raise ValidationError('Allocation basis evidence needs its exact structured snapshot')
            if source!={k:x for k,x in v.items() if k!='evidence_id'}:raise ValidationError('Membership configuration differs from its cited immutable source')
            if len({x['subject_ref'] for x in v['rows']})!=len(v['rows']):raise ValidationError('Duplicate or conflicting basis subject')
            for x in v['rows']:
                if x['weight'] is not None:decimal(x['weight'],nonnegative=True)
    elif component=='D10.audience_projection_rules':
        if projection_v2 and any(x['charts'] and not set(x['columns']) & {'actual','budget','prior'} for x in v['audiences']):raise ValidationError('Charts require explicit actual/budget/prior data columns')
        if len({x['audience'] for x in v['audiences']})!=len(v['audiences']):raise ValidationError('Duplicate Finance audience projection')
        if any(not x['formula_keys'] or not x['include_company'] and not x['bu_keys'] for x in v['audiences']):raise ValidationError('Select actual aggregate outputs for each audience')

def validate_collection(component,values):
    if len(values)>100:raise ValidationError('Finance configuration exceeds 100-entry budget')
    if component in ['D06.account_bu_maps','D06.rule_oracle_refs','D10.report_category_effective_dates','D07.allocation_pool_rules']:
        if len({v['key'] for v in values})!=len(values):raise ValidationError('Finance configuration keys must be unique')
        for i,a in enumerate(values):
            for b in values[i+1:]:
                dimension='account' if component=='D06.account_bu_maps' else 'pool' if component=='D07.allocation_pool_rules' else 'key'
                if a['entity']==b['entity'] and a[dimension]==b[dimension] and max(a['from_period'],b['from_period'])<=min(a['to_period'],b['to_period']):raise ValidationError('Overlapping effective Finance mappings/rules')
    if component=='D06.rule_oracle_refs':formula_order(values)
