"""Bounded declared decimal graphs; supplied contracts are not native workbook verification."""
import json
from decimal import Decimal,localcontext,ROUND_HALF_EVEN,ROUND_HALF_UP,ROUND_DOWN,DecimalException
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY,MONEY
ID={'type':'integer','minimum':1};HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
UNIT={'type':'string','minLength':1,'maxLength':60}
ARRAY=lambda item,minimum=0:{'type':'array','minItems':minimum,'maxItems':60,'items':item}
INPUT=obj({'key':KEY,'unit':UNIT})
VALUE=obj({'key':KEY,'unit':UNIT,'value':MONEY})
NODE=obj({'key':KEY,'unit':UNIT,'operation':{'enum':['add','subtract','multiply','divide']},'operands':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'string','pattern':'^(input|parameter|node):[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}},'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']}})
RULE=obj({'implementation':{'const':'declared_decimal_graph_v1'},'implementation_version':{'const':'1'},'calculator_ref':KEY,'calculator_version':KEY,'calculator_sha256':HASH,'contract_basis':KEY,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'source_class':{'enum':['synthetic_fixture','supplied_contract']},'source_locator':{'type':'string','minLength':1,'maxLength':500},'owner_id':{'anyOf':[ID,{'type':'null'}]},'owner_role':{'anyOf':[KEY,{'type':'null'}]},'oracle_owner_id':{'anyOf':[ID,{'type':'null'}]},'oracle_role':{'anyOf':[KEY,{'type':'null'}]},'override_mode':{'const':'new_rule_version'},'inputs':ARRAY(INPUT,1),'parameters':ARRAY(obj({'key':KEY,'unit':UNIT,'value':MONEY,'evidence_id':ID})),'nodes':ARRAY(NODE,1),'outputs':{'type':'array','minItems':1,'maxItems':30,'uniqueItems':True,'items':KEY}})
EXPECTED=obj({'status':{'enum':['known','held']},'values':ARRAY(VALUE,1),'findings':{'type':'array','maxItems':120,'uniqueItems':True,'items':{'type':'string','maxLength':220}}})
SCENARIO=obj({'key':KEY,'scenario':{'enum':['normal','exception']},'inputs':ARRAY(VALUE,1),'expected':EXPECTED})
ORACLE=obj({'rule_sha256':HASH,'calculator_ref':KEY,'calculator_version':KEY,'source_class':{'enum':['synthetic_fixture','independent_owner_examples']},'source_locator':{'type':'string','minLength':1,'maxLength':500},'scenarios':{'type':'array','minItems':2,'maxItems':30,'items':SCENARIO}})

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON property')
        result[key]=value
    return result

def read(body,schema):
    try:v=json.loads(body,object_pairs_hook=unique_object)
    except (ValueError,TypeError,RecursionError):raise ValidationError('Exact structured costing evidence required')
    validate(schema,v);return v

def number(value):
    if value is None:return None
    n=Decimal(value)
    if not n.is_finite() or abs(n)>=Decimal('1e24'):raise ValidationError('Decimal magnitude budget exceeded')
    return n

def graph(rule):
    validate(RULE,rule);units={}
    for kind,rows in [('input',rule['inputs']),('parameter',rule['parameters'])]:
        if len({r['key'] for r in rows})!=len(rows):raise ValidationError('Distinct declared input/parameter keys required')
        for r in rows:
            units[kind+':'+r['key']]=r['unit']
            if kind=='parameter':number(r['value'])
    keys=[]
    for n in rule['nodes']:
        if n['key'] in keys or any(ref not in units for ref in n['operands']):raise ValidationError('Unique topologically ordered nodes and exact references required; no cycles or uploaded code')
        if n['operation'] in ['add','subtract'] and any(units[ref]!=n['unit'] for ref in n['operands']):raise ValidationError('Addition/subtraction units must agree')
        units['node:'+n['key']]=n['unit'];keys.append(n['key'])
    if not set(rule['outputs'])<=set(keys):raise ValidationError('Outputs must select declared graph nodes')

def calculate(rule,inputs):
    graph(rule);validate(ARRAY(VALUE,1),inputs)
    if len({r['key'] for r in inputs})!=len(inputs) or {r['key']:r['unit'] for r in inputs}!={r['key']:r['unit'] for r in rule['inputs']}:raise ValidationError('Every exact input/unit is required once; unknown is null')
    vals={'input:'+r['key']:number(r['value']) for r in inputs};vals.update({'parameter:'+r['key']:number(r['value']) for r in rule['parameters']});findings=[];lineage=[]
    try:
        with localcontext() as ctx:
            ctx.prec=64
            for n in rule['nodes']:
                left,right=[vals[k] for k in n['operands']];value=None
                if left is None or right is None:findings.extend('unknown:'+k for k in n['operands'] if vals[k] is None)
                elif n['operation']=='divide' and right==0:findings.append('division_by_zero:'+n['key'])
                else:
                    op=n['operation'];value=left+right if op=='add' else left-right if op=='subtract' else left*right if op=='multiply' else left/right
                    if abs(value)>=Decimal('1e24'):raise ValidationError('Calculation magnitude budget exceeded')
                    value=value.quantize(Decimal(1).scaleb(-n['decimal_places']),rounding={'half_even':ROUND_HALF_EVEN,'half_up':ROUND_HALF_UP,'down':ROUND_DOWN}[n['rounding']])
                vals['node:'+n['key']]=value;lineage.append({'node':n['key'],'operands':n['operands'],'value':format(value,'f') if value is not None else None,'unit':n['unit'],'rounding':n['rounding'],'decimal_places':n['decimal_places']})
    except DecimalException:raise ValidationError('Declared decimal operation cannot be represented within budget')
    values=[{'key':key,'unit':next(n['unit'] for n in rule['nodes'] if n['key']==key),'value':format(vals['node:'+key],'f') if vals['node:'+key] is not None else None} for key in rule['outputs']]
    return {'status':'held' if findings else 'known','values':values,'findings':list(dict.fromkeys(findings)),'lineage':lineage,'implementation':'declared_decimal_graph_v1','native_workbook_verified':False,'invoice_created':False}

def compare(actual,expected):
    validate(EXPECTED,expected)
    if actual['status']!=expected['status'] or actual['findings']!=expected['findings'] or [(v['key'],v['unit']) for v in actual['values']]!=[(v['key'],v['unit']) for v in expected['values']]:return False
    return all(number(a['value'])==number(b['value']) for a,b in zip(actual['values'],expected['values']))

class SuppliedCostingContractAdapter:
    def read_rule(self,evidence):return read(evidence.body,RULE)
    def read_oracle(self,evidence):return read(evidence.body,ORACLE)

class LocalCostingReportAdapter:
    def read(self,actor,case_id,run_id):
        from apps.pmo.costing import report
        return report(actor,case_id,run_id)
