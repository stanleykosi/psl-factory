"""Bounded investigation uses current domain services; no execution tool."""
from apps.identity.services import require
from apps.finance import receipt_followup as d

def investigate(actor,case_id,request_id):
    from apps.core.models import Case
    c=Case.objects.get(pk=case_id);require(actor,c,'agent.receipt_followup')
    r=d.report(actor,case_id,request_id)
    from apps.finance.followup_successors import report
    r['successors']=report(actor,case_id,request_id)['lineage']
    r['effect_tools']=[]
    focus={'issue':'canonical obligation and issued document','deliver':'public invoice projection and exact recipient',
        'adjust':'legal credit/debit/void note, signed delta and prior face','adjust_deliver':'accepted legal note projection and exact recipient'}[r['variant']]
    r['next_steps']=['Ask the current Finance owner to investigate the exact source invoice and correction.',
        'Use normal current invoice/correction reviews and operator reconciliation before any effect.',
        'Unknown remains unresolved; a follow-up link neither proves a receipt nor authorises execution.']
    if not r['decision_current']:r['next_steps'].insert(0,'Obtain a current configured Finance owner disposition.')
    if r['successors']:
        r['next_steps'].append('Inspect proposed/current/stale successor lineage and its separate receipt status; lineage review never releases a financial action.')
    r['next_steps'].insert(0,'Investigate '+focus+'; supplied outcome is '+r['supplied_outcome']+'.')
    return r
