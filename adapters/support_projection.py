"""Local projection of supplied intake claims; never dereference content_reference."""
from django.core.exceptions import ValidationError
from apps.policy.support_agent_validators import FIELDS
class SupportProjectionAdapter:
 def project(self,intake,fields):
  if not fields or len(set(fields))!=len(fields) or any(k not in FIELDS for k in fields):raise ValidationError('Explicit closed intake field inventory required')
  values={k:intake.payload[k] for k in fields}
  if any(not isinstance(v,str) or not v for v in values.values()):raise ValidationError('Selected unknown field cannot become empty or zero')
  return {'classification':'supplied_support_intake_claims','fields':values,'native_channel_verified':False,'content_reference_dereferenced':False}
