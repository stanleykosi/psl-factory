"""Closed metadata projection; never returns transaction quotations or draft bodies."""
from apps.finance import acceptance as h

class AcceptedFinanceMetadataAdapter:
 def read(self,actor,handoff,fields):
  h.access(actor,handoff);accepted=h.confirmed(handoff,'accept')
  values={'handoff':handoff.pk,'handoff_version':handoff.version,'handoff_sha256':handoff.sha256,'package':handoff.package_id,'package_sha256':handoff.package.sha256,'draft':handoff.draft_id,'draft_sha256':handoff.snapshot['finance']['draft_sha256'],'acceptance':accepted.pk,'af13_acceptance':accepted.snapshot['af13_acceptance'],'classification':'Accepted scoped metadata; native QuickBooks, whole-product and operational acceptance remain unverified'}
  from apps.policy.ledger_validators import METADATA_FIELDS
  from django.core.exceptions import ValidationError
  if not fields or set(fields)-set(METADATA_FIELDS):raise ValidationError('Closed accepted metadata fields required')
  return {key:values[key] for key in fields},accepted.pk
