"""Closed selected-field projection; never dereference source evidence or call QuickBooks."""
from django.core.exceptions import ValidationError
from apps.policy.ledger_validators import FIELDS
class LedgerProjectionAdapter:
 def project(self,report,fields):
  if not fields or len(set(fields))!=len(fields) or any(k not in FIELDS for k in fields):raise ValidationError('Explicit closed Finance field inventory required')
  if report['verification_mode']!='supplied_read_only' or report['posting_performed'] or report['incumbent']['state']!='found':raise ValidationError('Reviewed read-only incumbent evidence required')
  value={k:report['incumbent'][k] for k in fields}
  if any(not isinstance(v,str) or not v for v in value.values()):raise ValidationError('Unknown selected field cannot become empty or zero')
  return {'classification':'supplied_finance_read_evidence','fields':value,'native_authenticity_verified':False,'posting_performed':False,'source_body_dereferenced':False}
