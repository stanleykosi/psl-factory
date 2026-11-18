"""Private working-row presentation; readiness is never approval or publication."""
from collections import Counter,defaultdict

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator

MESSAGES={'unknown_amount':'Pay amount needs review','overlap_unresolved':'The two sources overlap for this pay item',
    'missing_hr_membership':'Not found in the authorised staff list','ambiguous_hr_membership':'More than one staff match',
    'unknown_bu':'Business unit needs confirmation','midperiod_transfer_requires_treatment':'A mid-month move needs an agreed treatment',
    'merge_policy_missing':'The source-combination rule needs configuration','match_policy_missing':'The staff-matching rule needs configuration'}


def rows(value,kind,*,page=None,status='all'):
    source=value.get('rows',[])
    if not isinstance(source,list) or len(source)>1000:raise ValidationError('Narrow the payroll working set before viewing rows.')
    if status not in ['all','ready','held']:raise ValidationError('Choose all rows, ready rows or rows needing review.')
    issues=defaultdict(list)
    for issue in value.get('issues',[]):
        issues[(issue.get('employee_id'),issue.get('component'))].append(issue['code'])
    output=[]
    for index,row in enumerate(source):
        codes=list(issues[(row['employee_id'],row.get('component'))])+list(issues[(row['employee_id'],None)])
        if row['amount'] is None:codes.append('unknown_amount')
        if kind in ['match','aggregate'] and (row.get('bu') is None or row.get('match_status')!='matched'):
            codes.append('unknown_bu' if row.get('match_status')=='matched' else row.get('match_status') or 'missing_hr_membership')
        codes=sorted(set(codes))
        output.append({'position':index+1,'employee':row['employee_id'],'component':row['component'],
            'amount':row['amount'],'bu':row.get('bu'),'codes':codes,
            'findings':[MESSAGES.get(code,code.replace('_',' ').capitalize()) for code in codes],'ready':not codes,
            'row_ref':row.get('row_ref'),
            'sources':[{'input_id':p['input_id'],'row_ref':p['row_ref'],'provider':p['provider']}
                       for p in row.get('provenance',[])]})
    counts=Counter('ready' if row['ready'] else 'held' for row in output)
    selected=[row for row in output if status=='all' or row['ready']==(status=='ready')]
    return {'page':Paginator(selected,25).get_page(page),'status':status,'total':len(output),
        'ready':counts['ready'],'held':counts['held'],'publication_ready':False}
