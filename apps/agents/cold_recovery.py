"""Live, private, bounded investigation; no approval/effect tools or generic logs."""
from django.db import transaction
from apps.core.models import Case
from apps.workflows import cold_recovery as d


@transaction.atomic
def prepare(actor, case_id, reference, **payload):
    d.access(actor, Case.objects.get(pk=case_id), 'agent')
    return d.capture(actor, case_id, reference, payload)


@transaction.atomic
def investigate(actor, case_id, plan_id):
    d.access(actor, Case.objects.get(pk=case_id), 'agent')
    result = d.report(actor, case_id, plan_id)
    result.update(effect_tools=[], next_steps=[])
    if not result['authorization_current']:
        result['next_steps'].append('Configure fresh scoped criteria and obtain an independent human decision for this exact archive/target/build')
    elif result['status'] in ['held', 'leased']:
        result['next_steps'].append('Reconcile the original target receipt before considering any further effect; do not reset the target')
    elif result['physical_receipt_current'] and not result['human_recovered_review_current']:
        result['next_steps'].append('Request an independent human review of the verified isolated recovery')
    result['next_steps'].append('Recovered authentication and outbound startup remain prohibited; operational activation requires separate work')
    return result
