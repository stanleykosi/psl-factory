"""Exact current native Finance evidence; metadata-only storage, no publication/posting."""
from apps.documents.contracts import digest

class FinanceAcceptanceAdapter:
 def read(self,actor,draft):
  from apps.finance import ledger_agents as d
  d.projection_access(actor,draft.source.projection)
  packet=d.approved_evidence(draft.owner,draft.case_id,draft.pk)
  return {'draft':draft.pk,'version':draft.version,'owner':draft.owner_id,'draft_sha256':draft.sha256,'review':packet['review'],'packet_sha256':digest(packet),'source':packet['source'],'provider_binding_classification':packet['provider_binding_classification'],'native_authenticity_verified':False}
