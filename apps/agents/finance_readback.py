from django.db import transaction
from apps.workflows import finance_readback as d

@transaction.atomic
def investigate(actor,case_id,observation_id):
    o=d.Observation.objects.select_related('packet__mapping__plan__case').get(pk=observation_id,packet__mapping__plan__case_id=case_id)
    d.d.get(actor,case_id,o.packet.mapping_id,'agent')
    r=d.report(actor,case_id,observation_id);r['effect_tools']=[]
    r['next_steps']=recommendations(r)
    return r

def recommendations(r):
    """Recorded currentness is historical until the live observation is current."""
    recorded=r['recorded'];steps=list(r['holds'])
    if not r['observation_current']:
        steps.append('Recorded source state is historical; collect and review successor evidence before treating the disposition as current.')
    elif recorded['outcome']=='unknown':steps.append('No exact request observed. Confirm source-owner intake; absence is not proof of a failed financial effect.')
    elif recorded['outcome']=='conflict':steps.append('Investigate the exact request/publication digest conflict; preserve both histories.')
    elif recorded['disposition']!='current':steps.append('Historical request acknowledged; obtain a current source-owned disposition. Hold: '+str(recorded['hold_code']))
    else:steps.append('Current source authority verified for this disposition; any financial action still requires its normal independent controls.')
    steps.append('A request acknowledgement and intent link neither prove a financial receipt nor authorise execution.')
    if recorded.get('successors'):
        steps.append('Successor lineage and its separate receipt statuses are historical unless this live observation and independent review remain current; source lineage approval cannot release a financial effect.')
    return steps
