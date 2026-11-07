"""Explicit eligible native activity; never remote tools in the planner prompt."""
from apps.identity.services import require
from apps.core.models import Case
from apps.finance.ledger import readable
from apps.workflows import quickbooks_mcp as broker


def read(actor, case_id, lineage_id, contract_id, expected=None):
    case = Case.objects.get(pk=case_id)
    readable(actor, case)
    require(actor, case, 'agent.ledger')
    intent = broker.reserve(actor, case_id, lineage_id, contract_id, expected, caller_mode='agent')
    broker.execute(actor, case_id, intent.pk)
    # External content is not instructions and is not inserted into planning context.
    return broker.status(actor, case_id, intent.pk)
