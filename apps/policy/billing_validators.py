from datetime import date
import json
from django.core.exceptions import ValidationError
from apps.pmo.services import subject
from apps.finance.rules import decimal
from apps.finance.billing_math import price
from .document_validators import typed
from .finance_validators import obj,KEY,PERIOD,DEC,rows

NULLDEC={'anyOf':[DEC,{'type':'null'}]}
ID={'type':'integer','minimum':1}
SCHEMAS={
'D08.effective_price_rule_refs':('billing-price',obj({'key':KEY,'coverage_id':ID,'from_period':PERIOD,'to_period':PERIOD,
    'unit':KEY,'rate':DEC,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount_basis':{'const':'net_exclusive'},'implementation':{'const':'quantity_times_rate_v1'}})),
'D08.tax_tier_rounding_rules':('billing-arithmetic',obj({'implementation':{'const':'net_exclusive_line_tax_v1'},'tax_rate':DEC,
    'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']},
    'oracle_evidence_id':ID,'oracles':rows(obj({'quantity':NULLDEC,'rate':DEC,'net':NULLDEC,'tax':NULLDEC,'total':NULLDEC}),2)})),
'D12.contract_version_ref':('billing-contract',obj({'coverage_id':ID,'signed_evidence_id':ID,'signed_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}})),
'D12.currency_amount_basis':('billing-amount-basis',obj({'coverage_id':ID,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount_basis':KEY,
    'contract_value':NULLDEC,'decimal_places':{'type':'integer','minimum':0,'maximum':8}})),
'D12.stage_terms':('billing-stage',obj({'coverage_id':ID,'stage':{'enum':['signed_sow','uat','completion']},'amount':NULLDEC,
    'due_date':{'anyOf':[{'type':'string','format':'date'},{'type':'null'}]}})),
'D12.uat_billing_predicate_ref':('billing-predicate',obj({'coverage_id':ID,'stage':{'const':'uat'},'milestone_name':{'type':'string','minLength':1,'maxLength':200}})),
'D12.completion_billing_predicate_ref':('billing-predicate',obj({'coverage_id':ID,'stage':{'const':'completion'},'milestone_name':{'type':'string','minLength':1,'maxLength':200}})),
}
SUPPORTED=set(SCHEMAS)
ARRAYS={'D08.effective_price_rule_refs','D12.stage_terms'}
STRINGS={'D12.contract_version_ref','D12.uat_billing_predicate_ref','D12.completion_billing_predicate_ref'}

def coverage_for(case,pk):
    from apps.finance.models import BillingCoverage
    cov=BillingCoverage.objects.filter(case=case,pk=pk).first()
    if not cov:raise ValidationError('Configuration must reference exact case billing coverage')
    return cov

def validate_reference(component,target,case,runtime=False):
    name,schema=SCHEMAS[component];v=typed(target,'schema:psl/'+name+'/v1',schema)
    cov=coverage_for(case,v['coverage_id']) if 'coverage_id' in v else None
    if cov and 'currency' in v and (v['currency'],v['amount_basis'])!=(cov.currency,cov.amount_basis):raise ValidationError('Billing amount dimensions differ from exact coverage')
    if component=='D08.effective_price_rule_refs':
        decimal(v['rate'],nonnegative=True)
        if not cov.from_period<=v['from_period']<=v['to_period']<=cov.to_period:raise ValidationError('Price effective interval falls outside coverage')
    elif component=='D08.tax_tier_rounding_rules':
        decimal(v['tax_rate'],nonnegative=True)
        source=subject(case,v['oracle_evidence_id'],'billing_oracle')
        try:oracle=json.loads(source.body)
        except ValueError:raise ValidationError('Pricing oracle evidence requires structured scenarios')
        if oracle!=v['oracles']:raise ValidationError('Pricing scenarios differ from cited oracle evidence')
        known=unknown=False
        for o in oracle:
            got=price(o['quantity'],o['rate'],v)
            for field in ['net','tax','total']:
                expected=o[field];actual=got[field]
                if (actual is None)!=(expected is None) or actual is not None and decimal(actual)!=decimal(expected):raise ValidationError('Pricing algorithm differs from supplied oracle')
            known|=o['quantity'] is not None;unknown|=o['quantity'] is None
        if not known or not unknown:raise ValidationError('Provide known and unknown pricing oracles')
    elif component=='D12.contract_version_ref':
        from apps.pmo.models import Baseline
        signed=subject(case,v['signed_evidence_id'],'signature')
        if signed.sha256!=v['signed_sha256'] or not Baseline.objects.filter(case=case,signed=signed).exists():raise ValidationError('Contract must bind the exact current signed baseline')
    elif component=='D12.currency_amount_basis':
        if v['contract_value'] is not None:decimal(v['contract_value'],nonnegative=True)
    elif component=='D12.stage_terms':
        if v['amount'] is not None:decimal(v['amount'],nonnegative=True)
        if v['due_date'] is not None:
            try:date.fromisoformat(v['due_date'])
            except ValueError:raise ValidationError('Invalid explicit stage due date')

def validate_collection(component,values):
    if len(values)>100:raise ValidationError('Billing policy exceeds 100 records')
    if component=='D12.stage_terms':
        pairs=[(v['coverage_id'],v['stage']) for v in values]
        if len(set(pairs))!=len(pairs):raise ValidationError('Duplicate contract stage terms')
        # Partial configuration is allowed: another stage never supplies a missing term.
    if component=='D08.effective_price_rule_refs':
        if len({v['key'] for v in values})!=len(values):raise ValidationError('Duplicate price rule key')
        for i,a in enumerate(values):
            for b in values[i+1:]:
                if (a['coverage_id'],a['unit'])==(b['coverage_id'],b['unit']) and max(a['from_period'],b['from_period'])<=min(a['to_period'],b['to_period']):raise ValidationError('Overlapping effective price rules')
