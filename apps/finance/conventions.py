"""Explicit producer-to-presentation contracts. Never infer signs from arithmetic."""
from django.core.exceptions import ValidationError
from apps.policy.services import active_component,reference_values
from . import analysis
from .rules import decimal,number

PRODUCER='D06.producer_conventions'
CONVERSION='D06.statement_conversions'

def apply_conversion(amount,conversion):
    """Exact finite operation, shared by golden validation and runtime. No scaling."""
    pair=(conversion['operation'],conversion['factor'])
    if pair not in {('identity','1'),('reverse_sign','-1')}:
        raise ValidationError('Only explicit identity/1 or reverse_sign/-1 is supported')
    if amount is None:return None
    value=decimal(amount)
    # copy_negate is exact even at the largest supported decimal precision.
    converted=value if pair[0]=='identity' else value.copy_negate()
    return number(converted.copy_abs() if converted.is_zero() else converted)


def reviewed(case,component,pk):
    config=active_component(component,case)
    if config.pk!=pk:raise ValidationError('Select exact active '+component)
    review=analysis.current_review(case,'formula',configuration=config)
    if not review['valid']:raise ValidationError('Current native formula-purpose review required: '+component)
    return config,reference_values(config)[0],review

def selected(value,key):
    found=[r for r in value['declarations'] if r['key']==key]
    if len(found)!=1:raise ValidationError('Exact convention declaration required: '+str(key))
    return found[0]

def transfer(case,row,source,metric):
    """Only formula sources enter here; outputs are never accepted as new sources."""
    if source.kind!='formula':raise ValidationError('Convention conversion accepts native formula producers only')
    if any(row[k] is None for k in ['producer_contract_id','producer_key','conversion_contract_id','conversion_key']):
        return metric['value'],None,['Reviewed producer and conversion declaration missing: '+row['destination']]
    pc,pv,pr=reviewed(case,PRODUCER,row['producer_contract_id'])
    cc,cv,cr=reviewed(case,CONVERSION,row['conversion_contract_id'])
    producer=selected(pv,row['producer_key']);conversion=selected(cv,row['conversion_key'])
    expected={'source_run':source.pk,'operation_key':source.operation_key,'source_review':row['source_review'],
        'metric':row['metric'],'unit':metric['unit'],'convention':row['source_sign']}
    if any(producer[k]!=v for k,v in expected.items()):raise ValidationError('Producer convention differs from exact native source, review, metric, unit or convention')
    if (conversion['from_convention'],conversion['to_convention'],conversion['unit'],conversion['operation'])!=(row['source_sign'],row['destination_sign'],metric['unit'],row['transfer']):
        raise ValidationError('Conversion from/to convention, unit or operation mismatch')
    amount=metric['value']
    # This sole declared operation is at the statement boundary, not rules.evaluate.
    result=apply_conversion(amount,conversion)
    pin={'producer':{'id':pc.pk,'revision':pc.revision,'review':pr,'declaration':producer},
        'conversion':{'id':cc.pk,'revision':cc.revision,'review':cr,'declaration':conversion},
        'source_value':amount,'destination_value':result,'applications':1}
    return result,pin,[]
