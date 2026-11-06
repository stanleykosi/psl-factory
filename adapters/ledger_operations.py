"""Local receipt capability only; never calls QuickBooks or the private provider."""
class FinanceReceiptAdapter:
 def lookup(self,job):
  from apps.agents.boundary_models import EvidenceExtractionReceipt
  from apps.finance.ledger_agents import binding
  from django.core.exceptions import ValidationError
  binding(job.projection)
  if job.projection.process_id!='F01' or job.projection.evidence.kind!='agent_private_ledger':raise ValidationError('Native Finance extraction required')
  row=EvidenceExtractionReceipt.objects.filter(job=job).first()
  # A rejected output is still a committed receipt. Return metadata only.
  return {'receipt':row.pk,'valid':row.valid} if row else None
