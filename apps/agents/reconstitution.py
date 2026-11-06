from django.db import transaction
from apps.core.models import Case
from apps.workflows import reconstitution as d


@transaction.atomic
def prepare(actor,case_id,recovery_id,reference,profile_ref):
    d.access(actor,Case.objects.get(pk=case_id),'agent')
    return d.capture(actor,case_id,recovery_id,reference,profile_ref)


@transaction.atomic
def investigate(actor,case_id,plan_id):
    d.access(actor,Case.objects.get(pk=case_id),'agent')
    result=d.report(actor,case_id,plan_id)
    result['effect_tools']=[]
    result['next_steps']=[]
    if result['policy_status']!='ACTIVE':result['next_steps'].append('Configure OPS.reconstitution with fresh independent purposes/roles and exact deployment references')
    for row in result.get('manifest',{}).get('effects',[]):
        if row['verdict']=='unresolved':result['next_steps'].append('Investigate exact effect '+row['effect_key']+'; missing receipts remain unknown and cannot authorize retry')
        if row['verdict']=='replacement_required':result['next_steps'].append('Create a new source-owned intent and obtain its current business approvals for '+row['effect_key']+'; this plan cannot dispatch it')
    result['next_steps'].append('Independent review/publication records an inert plan; authentication, debt, release controls and archived queues remain unchanged')
    return result
