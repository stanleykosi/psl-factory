"""O01 scoped restoration triage; it cannot enable accounts or allocate access."""
from adapters.staff_accounts import restoration_packet
from apps.identity import staff_reactivation


def investigate_restoration(actor,person_id):
    prepared=staff_reactivation.prepare(actor,person_id)
    packet=restoration_packet(prepared)
    prepared['assistance']={'agent_role':'O01','packet':packet,'next_action':
        'Resolve the recorded role or source findings, then request a fresh account review.' if packet['findings'] else
        'A person must confirm restoration. Review and allocate fresh workspace access afterwards.'}
    return prepared
