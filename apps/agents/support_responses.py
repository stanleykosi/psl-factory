"""Bounded preparation tool only; human release remains a separate service/UI action."""
def prepare(actor,case_id,draft_id,reference,expected=None):
 from apps.baas.support_release import prepare as service
 return service(actor,case_id,draft_id,reference,expected)
