"""Selected statement lines from exact reviewed native inputs; no workbook inference."""
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case
from apps.policy.services import active_component,reference_values
from .models import FinanceRun,FinanceReview,FinanceStatementInput
from . import analysis

COMPONENT='D06.statement_contract'

def contract_for(case,contract_id):
    contract=active_component(COMPONENT,case)
    if contract.pk!=contract_id:raise ValidationError('Select the exact active statement contract')
    review=analysis.current_review(case,'formula',configuration=contract)
    if not review['valid']:raise ValidationError('Statement contract needs current native rule review')
    return contract,reference_values(contract)[0],review

def snapshot(actor,parent,contract_id):
    from apps.identity.services import require
    for action in ['case.read','finance.read','finance.calculate']:require(actor,parent.case,action)
    analysis.ensure_current(parent)
    contract,value,review=contract_for(parent.case,contract_id)
    anchor={'entity':parent.result['entity'],'period':parent.result['period'],
        'currency':parent.result['currency'],'accounting_basis':parent.source.accounting_basis}
    if any(value[k]!=v for k,v in anchor.items()):raise ValidationError('Statement contract differs from anchor entity, period, currency or accounting basis')
    inputs=[];figures={};findings=[];sources={}
    for row in value['inputs']:
        if row['source_run'] not in sources:
            source=FinanceRun.objects.filter(pk=row['source_run'],case=parent.case,kind='formula').first()
            if source is None:raise ValidationError('Exact same-case native formula input required')
            problems=analysis.certification_findings(source)
            if problems:raise ValidationError(problems)
            sources[source.pk]=(source,analysis.current_review(parent.case,'output',run=source))
        source,decision=sources[row['source_run']]
        if any((source.source.accounting_basis if k=='accounting_basis' else source.result[k])!=v for k,v in anchor.items()):
            raise ValidationError('Statement inputs must share entity, period, currency and accounting basis; no conversion')
        if not decision['valid'] or decision['id']!=row['source_review']:
            raise ValidationError('Statement input requires its exact current output review')
        metric=source.result['company'].get(row['metric'])
        if metric is None:raise ValidationError('Exact source company metric required')
        if metric['unit']!=row['unit']:raise ValidationError('Statement unit mismatch; no silent scaling')
        converted=metric['value'];conversion=None
        if value.get('convention_mode')=='producer_verified':
            from .conventions import transfer
            converted,conversion,problems=transfer(parent.case,row,source,metric);findings.extend(problems)
        elif row['source_sign'] is None or row['destination_sign'] is None:
            findings.append('Explicit reviewed presentation-sign declaration is missing: '+row['destination'])
        elif row['source_sign']!=row['destination_sign']:
            findings.append('Convention conversion requires a separate typed reviewed contract: '+row['destination'])
        if metric['value'] is None:findings.append('Unknown statement input: '+row['destination'])
        figures[row['destination']]={'value':converted,'unit':metric['unit'],'rule_key':row['destination']}
        inputs.append({'declaration':row,'operation_key':source.operation_key,'result_hash':analysis.digest(source.result),'review':decision,'source_evidence_ids':source.result.get('source_evidence_ids',[])})
        if value.get('convention_mode')=='producer_verified':
            inputs[-1]['convention_transfer']=conversion
            if conversion:
                inputs[-1]['source_evidence_ids']=sorted(set(inputs[-1]['source_evidence_ids'])|{conversion['producer']['declaration']['evidence_id'],conversion['conversion']['declaration']['evidence_id'],conversion['conversion']['declaration']['oracle_evidence_id']})
    if value['oracle_evidence_id'] is None:findings.append('Owner-approved selected-line oracle is missing; whole-statement oracle remains deferred')
    else:
        from apps.pmo.services import subject
        oracle=json.loads(subject(parent.case,value['oracle_evidence_id'],'finance_oracle').body)
        from .rules import decimal
        for key,metric in figures.items():
            actual=metric['value'];expected=oracle[key]
            if (actual is None)!=(expected is None) or actual is not None and decimal(actual)!=decimal(expected):
                findings.append('Selected-line oracle differs: '+key)
    snap={'implementation':'finance-statement-inputs/v2' if value.get('convention_mode')=='producer_verified' else 'finance-statement-inputs/v1','parent':{'id':parent.pk,'key':parent.operation_key},
        'policies':{COMPONENT:{'id':contract.pk,'revision':contract.revision,'status':'ACTIVE'}},
        'reviews':{COMPONENT:review},'source_review':parent.snapshot['source_review'],'inputs':inputs}
    result={**anchor,'company':figures,'by_bu':{},'status':'needs_attention' if findings else 'complete','findings':findings,
        'scope':'selected_statement_lines','whole_statement_certified':False,'ledger_posted':False,
        'anchor_source_evidence_ids':parent.result.get('source_evidence_ids',[]),
        'source_evidence_ids':sorted({pk for item in inputs for pk in item['source_evidence_ids']}|({value['oracle_evidence_id']} if value['oracle_evidence_id'] else set()))}
    return snap,result

@transaction.atomic
def assemble(actor,case_id,parent_id,contract_id,expected):
    case=lock_case(actor,case_id,'finance.calculate',expected)
    parent=FinanceRun.objects.filter(case=case,pk=parent_id,kind='formula').first()
    if parent is None:raise ValidationError('Exact native formula anchor required')
    snap,result=snapshot(actor,parent,contract_id)
    run=analysis.store(actor,case,parent.source,'statement',parent,{'contract_id':contract_id},snap,result)
    for item in snap['inputs']:
        row=item['declaration']
        FinanceStatementInput.objects.get_or_create(statement=run,destination=row['destination'],defaults={
            'source_run_id':row['source_run'],'source_review_id':row['source_review'],'metric':row['metric'],
            'contract_id':contract_id,'declaration':row})
    return run

def ensure_current(run):
    snap,result=snapshot(run.actor,run.parent,run.request['contract_id'])
    if snap!=run.snapshot or result!=run.result:raise ValidationError('Statement input, rule, review or source changed; rebuild')
    actual=list(run.statement_inputs.order_by('destination').values('destination','source_run_id','source_review_id','metric','contract_id','declaration'))
    expected=sorted([{'destination':r['destination'],'source_run_id':r['source_run'],'source_review_id':r['source_review'],
        'metric':r['metric'],'contract_id':run.request['contract_id'],'declaration':r} for r in [i['declaration'] for i in snap['inputs']]],key=lambda r:r['destination'])
    if actual!=expected:raise ValidationError('Statement relational input inventory differs from reviewed snapshot')
    return run
