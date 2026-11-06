from apps.identity.services import require
from apps.core.models import Case
from apps.pmo.project_view import projection

def investigate(actor,case_id,audience):
    case=Case.objects.get(pk=case_id);require(actor,case,'agent.project_view')
    value=projection(actor,case_id,audience)
    return {'capability':'A04 configured project metadata investigation','process_ids':['P05'],'projection':value,
        'findings':[{'group':g,'coverage':v['coverage'],'truncated':v['truncated'],'outside_age_ids':[x['id'] for x in v['items'] if x['freshness']=='outside_recorded_age']} for g,v in value['groups'].items()],
        'actions_with_unknown_deadline':[x['id'] for x in value['groups'].get('actions',{}).get('items',[]) if x['due_at'] is None],
        'effect_tools':[],'provider':'deterministic_internal_no_external_model'}
