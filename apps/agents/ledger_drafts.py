"""Typed reviewed-result Finance drafting tool. No posting, approval or publication tools."""
def prepare(actor,case_id,receipt_id,reference,expected=None):
 from apps.finance.ledger_agents import reuse
 return reuse(actor,case_id,receipt_id,reference,expected)
