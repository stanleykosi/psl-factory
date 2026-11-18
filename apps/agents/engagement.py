from apps.identity.services import require
from apps.core.models import Case
from apps.pmo.engagement import report
from apps.identity.intake import investigate as duplicates

def investigate(actor,case_id):
    c=Case.objects.get(pk=case_id);require(actor,c,'agent.engagement')
    from apps.pmo import engagement_details as details
    from django.core.exceptions import ValidationError,PermissionDenied
    saved=details.Details.objects.filter(case=c).order_by('-pk').first()
    facts={'status':'not_recorded','start_date':'unknown','client_contact':'unknown'}
    if saved:
        try:
            current,contact=details.current(c,saved.pk)
            facts={'status':'current','start_date':'recorded' if current.planned_start else 'unknown',
                   'client_contact':'recorded' if contact else 'unknown','details':current.pk}
        except (ValidationError,PermissionDenied):facts['status']='source_review_needed'
    return {'capability':'A01 engagement identity triage and A04 planning dependencies','process_ids':['P03','P16'],
        'project_details':facts,
        **report(actor,case_id),'possible_duplicate_case_ids':duplicates(actor,case_id)['possible_duplicate_case_ids']}
