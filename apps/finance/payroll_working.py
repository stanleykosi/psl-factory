"""Private working-row presentation; readiness is never approval or publication."""
from collections import Counter,defaultdict

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator

MESSAGES={'unknown_amount':'Pay amount needs review','overlap_unresolved':'The two sources overlap for this pay item',
    'missing_hr_membership':'Not found in the authorised staff list','ambiguous_hr_membership':'More than one staff match',
    'unknown_bu':'Business unit needs confirmation','midperiod_transfer_requires_treatment':'A mid-month move needs an agreed treatment',
    'merge_policy_missing':'The source-combination rule needs configuration','match_policy_missing':'The staff-matching rule needs configuration',
    'duplicate_source_row_or_component':'Conflicting source rows need the source owner',
    'missing_row_currency':'Currency is missing from this source row','invalid_row_currency':'Currency needs confirmation',
    'row_currency_mismatch':'Currency differs from the agreed payroll currency',
    'row_currency_rule_unconfigured':'The source-currency rule needs a decision',
    'row_handling_rule_unconfigured':'The conflicting-row rule needs a decision',
    'duplicate_merge_rule_unconfigured':'The combination rule does not yet allow held duplicate rows'}

REJECTION_MESSAGES={
    'spreadsheet_columns':'Use only the columns agreed for this payroll source.',
    'spreadsheet_format':'Check the spreadsheet format and remove formulas before uploading.',
    'out_of_contract_fields':'The export contains fields outside its agreed source layout.',
    'json_schema':'The export contents could not be read. Check the file format.',
    'envelope_schema':'The export is missing required source details.',
    'source_or_period_scope':'Use the agreed payroll source, period and currency.',
    'source_freshness':'Ask the source owner for a current export with its actual preparation time.',
    'duplicate_source_row_or_component':'Ask the source owner to resolve duplicate staff or pay items.',
    'identity_schema':'Check staff, row and pay-item references with the source owner.',
    'amount_schema_or_precision':'Ask the source owner to check pay amounts and their decimal places.',
    'control_total_schema':'Ask the source owner to check the control total.',
}


def rejection_notice(codes):
    messages=list(dict.fromkeys(REJECTION_MESSAGES.get(code,'Check the export and its agreed source layout.') for code in codes))
    return 'The upload could not be accepted. '+' '.join(messages)+' No source values retained.'


def rows(value,kind,*,page=None,status='all'):
    source=value.get('rows',[])
    if not isinstance(source,list) or len(source)>1000:raise ValidationError('Narrow the payroll working set before viewing rows.')
    if status not in ['all','ready','held']:raise ValidationError('Choose all rows, ready rows or rows needing review.')
    issues=defaultdict(list)
    for issue in value.get('issues',[]):
        issues[(issue.get('employee_id'),issue.get('component'))].append(issue['code'])
    output=[]
    for index,row in enumerate(source):
        codes=list(row.get('quarantine_codes',[]))+list(issues[(row['employee_id'],row.get('component'))])+list(issues[(row['employee_id'],None)])
        if row['amount'] is None:codes.append('unknown_amount')
        if kind in ['match','aggregate'] and (row.get('bu') is None or row.get('match_status')!='matched'):
            codes.append('unknown_bu' if row.get('match_status')=='matched' else row.get('match_status') or 'missing_hr_membership')
        codes=sorted(set(codes))
        output.append({'position':index+1,'employee':row['employee_id'],'component':row['component'],
            'amount':row['amount'],'bu':row.get('bu'),'codes':codes,
            'findings':[MESSAGES.get(code,code.replace('_',' ').capitalize()) for code in codes],'ready':not codes,
            'row_ref':row.get('row_ref'),
            'data_row':row.get('data_row'),'quarantined':bool(row.get('quarantine_codes')),
            'has_source_amount':'source_amount' in row,'source_amount':row.get('source_amount'),
            'source_currency':row.get('source_currency'),
            'sources':[{'input_id':p['input_id'],'row_ref':p['row_ref'],'provider':p['provider'],'data_row':p.get('data_row')}
                       for p in row.get('provenance',[])]})
    counts=Counter('ready' if row['ready'] else 'held' for row in output)
    selected=[row for row in output if status=='all' or row['ready']==(status=='ready')]
    return {'page':Paginator(selected,25).get_page(page),'status':status,'total':len(output),
        'ready':counts['ready'],'held':counts['held'],'publication_ready':False,
        'item_label':'source rows' if kind=='input' else 'working pay items',
        'source_rows':len(source) if kind=='input' else sum(len(row.get('provenance',[])) or 1 for row in source)}
