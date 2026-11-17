from apps.core.models import Case
from apps.identity.services import require
from apps.pmo.planning import report

def investigate(actor,case_id):
    case=Case.objects.get(pk=case_id);require(actor,case,'agent.planning')
    value=report(actor,case_id)
    department_questions=[]
    for row in (value.get('department_inputs') or {}).get('rows',[]):
        if row['record'] is None:
            department_questions.append({'department':row['department'],'question':'What input has this department supplied?','source_ids':[]})
        elif row['record']['effort_state']=='unknown':
            department_questions.append({'department':row['department'],'question':'What effort did this department confirm, or is it not applicable?',
                                         'source_ids':[row['record']['source']]})
    return {'capability':'A04 requirements and alignment dependency investigation','provider':'deterministic_internal_no_external_model',
        **value,'unknown_source_fields':[k for k,v in value.get('payload',{}).items() if k.endswith('_id') and v is None],
        'department_input_questions':department_questions,
        'source_clarification_questions':[{'key':f['key'],'question':f['detail'],'source_ids':f['source_ids'],'approval_granted':False} for f in value.get('source_correlation',{}).get('findings',[])],
        'unresolved_question_keys':[q['key'] for q in value.get('payload',{}).get('questions',[]) if q['state']=='unresolved']}
