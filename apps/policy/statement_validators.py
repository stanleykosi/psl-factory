"""Explicit identity-transfer contract. Arithmetic is not a sign declaration."""
from django.core.exceptions import ValidationError
from .document_validators import typed
from .finance_validators import obj, rows, KEY, PERIOD
from apps.pmo.services import subject

ID={'type':'integer','minimum':1}
SIGN={'anyOf':[KEY,{'type':'null'}]}
LINE=obj({'destination':KEY,'source_run':ID,'source_review':ID,'metric':KEY,
    'source_location':{'type':'string','minLength':1,'maxLength':160},
    'source_kind':{'enum':['note','soce']},'unit':{'enum':['major_currency','thousands_currency','millions_currency']},
    'source_sign':SIGN,'destination_sign':SIGN,'transfer':{'const':'identity'}})
VALUE=obj({'entity':KEY,'period':PERIOD,'accounting_basis':{'type':'string','minLength':1,'maxLength':100},
    'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'scope':{'const':'selected_statement_lines'},
    'inputs':rows(LINE),'oracle_evidence_id':{'anyOf':[ID,{'type':'null'}]}})

def validate_reference(target,case):
    v3=target.schema_ref=='schema:psl/finance-statement/v3'
    v2=v3 or target.schema_ref=='schema:psl/finance-statement/v2'
    if v2:
        from .statement_completeness import CONTRACT
        schema=obj(dict(VALUE['properties'],completeness={'anyOf':[CONTRACT,{'type':'null'}]}))
    else:schema=VALUE
    if v3:
        from .statement_ppe import PPE_LINE
        schema=obj(dict(schema['properties'],inputs=rows({'anyOf':[LINE,PPE_LINE]})))
    value=typed(target,'schema:psl/finance-statement/v3' if v3 else 'schema:psl/finance-statement/v2' if v2 else 'schema:psl/finance-statement/v1',schema)
    if v2:
        from .statement_completeness import validate
        validate(value,case)
    if len({r['destination'] for r in value['inputs']})!=len(value['inputs']):
        raise ValidationError('Statement destinations must be unique')
    from apps.finance.models import FinanceRun,FinanceReview
    for row in value['inputs']:
        if row.get('source_type')=='ppe_schedule':
            from .statement_ppe import validate_binding
            validate_binding(row,case,value)
            continue
        if not FinanceRun.objects.filter(pk=row['source_run'],case=case,kind='formula').exists():
            raise ValidationError('Statement inputs must identify exact same-case native formula outputs')
        if not FinanceReview.objects.filter(pk=row['source_review'],case=case,run_id=row['source_run'],purpose='output').exists():
            raise ValidationError('Statement input review must identify its exact native output')
    if value['oracle_evidence_id'] is not None:
        import json
        evidence=subject(case,value['oracle_evidence_id'],'finance_oracle')
        try: oracle=json.loads(evidence.body)
        except (ValueError,TypeError):raise ValidationError('Structured selected-line oracle required')
        if not isinstance(oracle,dict) or set(oracle)!={r['destination'] for r in value['inputs']}:
            raise ValidationError('Oracle must enumerate exactly the selected statement destinations')
        from apps.finance.rules import decimal
        for amount in oracle.values():
            if amount is not None:decimal(amount)
    return value
