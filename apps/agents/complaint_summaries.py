from apps.core.models import Case
from apps.identity.services import require
from apps.baas import summaries

def draft(actor,case_id,request_id,key):
    c=Case.objects.get(pk=case_id);require(actor,c,'agent.support.summary')
    version=summaries.prepare(actor,case_id,request_id,key)
    return {'capability':'A02 evidence synthesis and A06 bounded drafting','process_id':'B02','version_id':version.pk,'sha256':version.sha256,
        'included_cases':version.result['included_count'],'omitted_cases':version.result['omitted_count'],
        'coverage':version.result['coverage'],'human_review_required':True,'external_effect_tools':[]}
