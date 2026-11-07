from collections import Counter
from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError
from apps.policy.services import reference_values
from .models import FinanceAdjustment
from .rules import decimal,number,total,evaluate,formula_order

def effective(values,entity,period):return [v for v in values if v['entity']==entity and v['from_period']<=period<=v['to_period']]

def map_rows(source,data,configs,adjustments):
    from .source_units import require_mapping
    require_mapping(source)
    convention=reference_values(configs['D06.unit_sign_currency_period'])[0];period=convention['period'];currency=convention['currency']
    maps=effective(reference_values(configs['D06.account_bu_maps']),source.entity,period)
    rows=[];findings=[];counts=Counter(x['account'] for x in data['rows']);seen=set()
    raw_total=total(x['amount'] if isinstance(x['amount'],str) and _valid(x['amount']) else None for x in data['rows'])
    inputs=[dict(x,origin='import',evidence_id=source.batch.evidence_id) for x in data['rows']]
    for pk in adjustments:
        a=FinanceAdjustment.objects.get(source=source,pk=pk)
        inputs.extend({'account':x['account'],'amount':x['amount'],'currency':currency,'period':period,'line':f'adjustment:{a.pk}:{i}',
            'origin':'reporting_adjustment','evidence_id':a.evidence_id} for i,x in enumerate(a.lines,1))
    for row in inputs:
        matches=[m for m in maps if m['account']==row['account']];reason=[]
        value=row['amount'] if row['amount'] is not None and _valid(row['amount']) else None
        if value is None:reason.append('Unknown or invalid exact source amount; not zero')
        if row['currency']!=currency or row['period']!=period:value=None;reason.append('Currency/period does not match the selected source convention; no conversion')
        mapping=matches[0] if len(matches)==1 else None
        if not mapping:reason.append('Unmapped account' if not matches else 'Multiply mapped account')
        if mapping:
            seen.add(mapping['key'])
            if row['origin']=='import' and counts[row['account']]>1 and mapping['source_rows']=='reject_duplicate_accounts':value=None;reason.append('Duplicate source account requires explicit row handling')
        result={'source_line':row['line'],'source_evidence':row['evidence_id'],'account':row['account'],'raw_amount':row['amount'],'amount':value,'origin':row['origin'],
            **{key:(mapping[key] if mapping else None) for key in ['report_line','metric','treatment','bu','pool']},'mapping_key':mapping['key'] if mapping else None,'findings':reason}
        rows.append(result);findings.extend(f"{row['line']}: {x}" for x in reason)
    for m in maps:
        if m['key'] not in seen:
            rows.append({'source_line':None,'source_evidence':source.batch.evidence_id,'account':m['account'],'raw_amount':None,'amount':None,'origin':'missing_source',
                **{k:m[k] for k in ['report_line','metric','treatment','bu','pool']},'mapping_key':m['key'],'findings':['Mapped source account is absent; fallback to zero is not configured']})
            findings.append('Missing source account: '+m['account'])
    if not maps:findings.append('No effective mapping for this entity/period')
    with localcontext() as context:
        context.prec=512
        difference=None if source.control_total is None or raw_total is None else number(raw_total-decimal(source.control_total))
    return {'status':'needs_attention' if findings else 'complete','rows':rows,'findings':findings,'entity':source.entity,'period':period,'currency':currency,'unit':'major_currency',
        'sign_convention':convention['sign_convention'],'source_control':{'actual':number(raw_total),'supplied':source.control_total,'difference':difference},
        'reporting_adjustment_ids':adjustments,'ledger_posted':False,'source_evidence_ids':sorted({source.evidence_id,source.batch.evidence_id}|{r['source_evidence'] for r in rows})}

def _valid(value):
    try:decimal(value);return True
    except ValidationError:return False

def calculate_formulas(parent,configuration):
    mapping=parent if parent.kind=='mapping' else parent.parent
    data=mapping.result;rules=effective(reference_values(configuration),data['entity'],data['period'])
    ordered=formula_order(rules);rows=data['rows']
    # Private source detail is kept out of company metrics and aggregate publications.
    lineage={'implementation':'finance-note-lineage/v1','mapping_run':mapping.pk,
        'mapping_operation_key':mapping.operation_key,'source_id':mapping.source_id,
        'source_hash':mapping.snapshot['source_hash'],'source_unit':data['unit'],
        'source_sign_convention':data['sign_convention'],'report_lines':{},'formulas':{}}
    for key in sorted({r['report_line'] for r in rows if r['report_line']}):
        selected=[(index,row) for index,row in enumerate(rows) if row['report_line']==key]
        original=[row['amount'] for _,row in selected if row['origin']!='reporting_adjustment']
        adjustments=[row['amount'] for _,row in selected if row['origin']=='reporting_adjustment']
        lineage['report_lines'][key]={'original_total':number(total(original)),
            'adjustment_total':number(total(adjustments)) if adjustments else '0',
            'adjusted_total':number(total(row['amount'] for _,row in selected)),
            'rows':[dict(row,mapping_row_index=index) for index,row in selected]}
    lineage['adjustments']=[{'id':a.pk,'reference':a.reference,'revision':a.number,'kind':a.kind,
        'evidence_id':a.evidence_id,'review':next(x['review'] for x in mapping.snapshot['adjustments'] if x['id']==a.pk)}
        for a in FinanceAdjustment.objects.filter(pk__in=data['reporting_adjustment_ids']).order_by('pk')]
    def group(items):
        keys={r['report_line'] for r in items if r['report_line']}
        return {key:number(total(r['amount'] for r in items if r['report_line']==key)) for key in keys}
    def calculate(lines,bu=False):
        results={}
        for rule in ordered:
            if bu and rule['scope']=='company_only':continue
            operands={}
            for term in rule['terms']:
                if term['kind']=='line':value=lines.get(term['key'])
                else:
                    dependency=results.get(term['key'],{})
                    value=dependency.get('unrounded' if term['value_stage']=='unrounded_formula' else 'value')
                operands[(term['kind'],term['key'])]=value
            output=evaluate(rule,operands,include_provenance=not bu)
            if not bu:
                provenance=output.pop('calculation_provenance')
                lineage['formulas'][rule['key']]={**provenance,'rule_key':rule['key'],
                    'configuration_id':configuration.pk,'implementation':rule['implementation'],
                    'oracle_evidence_id':rule['oracle_evidence_id'],
                    'unrounded':output['unrounded'],'display_value':output['value'],
                    'rounding_difference':output['rounding_difference'],
                    'operands':[dict(t,value=operands[(t['kind'],t['key'])]) for t in rule['terms']]}
            output['lineage']=[dict(t,value=operands[(t['kind'],t['key'])]) for t in rule['terms']]
            output['rule_key']=rule['key'];output['implementation']=rule['implementation'];results[rule['key']]=output
        return results
    company=calculate(group(rows));by_bu={}
    if parent.kind=='allocation':
        for bu in parent.result['bu_keys']:
            values=[]
            for row in parent.result['rows']:
                if row['report_line']:
                    # Explicit zero allocated by a known rule is zero; absent/held attribution stays unknown.
                    if row['status']=='allocated':value=row['allocations'].get(bu,'0')
                    elif row['status']=='company_only':continue
                    else:value=None
                    values.append({'report_line':row['report_line'],'amount':value})
            by_bu[bu]=calculate(group(values),bu=True)
    findings=[]
    if not ordered:findings.append('No effective formula rules for this entity/period')
    for scope,result in [('company',company)]+list(by_bu.items()):
        findings.extend(scope+': unknown operands for '+key for key,value in result.items() if value['value'] is None)
    comparison={}
    for key,value in company.items():
        if any(key in result for result in by_bu.values()):
            rollup=total(result.get(key,{}).get('value') for result in by_bu.values())
            with localcontext() as context:
                context.prec=512
                difference=None if rollup is None or value['value'] is None else number(Decimal(value['value'])-rollup)
            comparison[key]={'company':value['value'],'bu_total':number(rollup),'difference':difference,'unit':value['unit']}
    return {'note_lineage':lineage,'bu_comparison':comparison,'status':'complete' if not findings and parent.result['status']=='complete' else 'needs_attention','findings':findings,'company':company,'by_bu':by_bu,
        'entity':data['entity'],'period':data['period'],'currency':data['currency'],'base_unit':'major_currency','parent_run':parent.pk,
        'source_evidence_ids':data['source_evidence_ids'],'ledger_posted':False}
