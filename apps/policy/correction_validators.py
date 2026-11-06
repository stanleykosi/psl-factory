from django.core.exceptions import ValidationError
from .document_validators import typed
from .finance_validators import obj
from .settlement_validators import ROLE_LIST

TARGETS=['invoice_credit','invoice_debit','invoice_void','cash_successor']
KINDS={'invoice_credit':'invoice_credit_note','invoice_debit':'invoice_debit_note','invoice_void':'invoice_void_note','cash_successor':'cash_correction'}
METHOD=obj({'implementation':{'const':'canonical_adjustments_v1'},'allowed_kinds':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,'items':{'enum':['credit','debit','void']}},
    'decimal_places':{'type':'integer','minimum':0,'maximum':8},'credit_allocation_conflict':{'enum':['hold','reverse_all_live_allocations']},
    'void_allocations':{'enum':['hold','reverse_all_live_allocations']},'void_amount':{'const':'current_adjusted_face'},'void_terminal':{'const':True}})

def schema_for(component,value,base):
    if component=='D08.duplicate_correction_rules' and isinstance(value,dict) and 'correction' in value:return 'schema:psl/invoice-identity/v2'
    if component=='D14.adjustment_correction_rule_refs' and isinstance(value,dict) and value.get('target') in TARGETS:return 'schema:psl/financial-correction/v1'
    if component=='D14.legal_document_requirements' and isinstance(value,dict) and value.get('target') in TARGETS:return 'schema:psl/financial-legal-evidence/v1'
    return base

def validate_reference(component,target,case):
    allowed={'schema:psl/invoice-identity/v2':'D08.duplicate_correction_rules','schema:psl/financial-correction/v1':'D14.adjustment_correction_rule_refs','schema:psl/financial-legal-evidence/v1':'D14.legal_document_requirements'}
    if allowed.get(target.schema_ref)!=component:raise ValidationError('Correction schema cannot configure another policy component')
    if target.schema_ref=='schema:psl/invoice-identity/v2':
        import copy
        from .settlement_validators import SCHEMAS
        schema=copy.deepcopy(SCHEMAS['D08.duplicate_correction_rules'][1]);schema['properties']['correction']=METHOD;schema['required']+=['correction']
        typed(target,'schema:psl/invoice-identity/v2',schema)
    elif target.schema_ref=='schema:psl/financial-correction/v1':
        name=target.content.get('target')
        if name not in TARGETS:raise ValidationError('Unknown financial correction target')
        props={'target':{'const':name},'roles':ROLE_LIST,'require_distinct_preparer':{'type':'boolean'}}
        if name=='cash_successor':props.update(implementation={'const':'successor_after_full_reversal_v1'},assignment={'enum':['preserve_current_contract','unmatched']})
        else:props['implementation']={'const':'canonical_adjustment_v1'}
        typed(target,'schema:psl/financial-correction/v1',obj(props))
    else:
        name=target.content.get('target')
        if name not in KINDS:raise ValidationError('Unknown legal correction target')
        typed(target,'schema:psl/financial-legal-evidence/v1',obj({'target':{'const':name},'evidence_kind':{'const':KINDS[name]},'reason_required':{'const':True}}))
