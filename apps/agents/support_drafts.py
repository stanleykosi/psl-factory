"""Typed, bounded reviewed-result drafting tool. Domain services own all authority."""
def prepare(actor,case_id,receipt_id,reference,expected=None):
 from apps.baas.support_agent import reuse
 return reuse(actor,case_id,receipt_id,reference,expected)
