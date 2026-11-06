from apps.identity.services import require
from apps.core.models import Case
from apps.pmo.engagement import report
from apps.identity.intake import investigate as duplicates

def investigate(actor,case_id):
    c=Case.objects.get(pk=case_id);require(actor,c,'agent.engagement')
    return {'capability':'A01 engagement identity triage and A04 planning dependencies','process_ids':['P03','P16'],
        **report(actor,case_id),'possible_duplicate_case_ids':duplicates(actor,case_id)['possible_duplicate_case_ids']}
