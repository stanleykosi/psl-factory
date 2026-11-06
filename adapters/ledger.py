import json
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
class SuppliedQuickBooksReadAdapter:
 """Operator-supplied read response. No native authentication, posting or retries."""
 def source(self,evidence,schema):
  return self.read(evidence,schema,kind='ledger_source')
 def checked_observation(self,lineage,check,schema,rules):
  """Revalidate supplied immutable evidence; this never authenticates to or writes QuickBooks."""
  from django.utils import timezone
  from adapters.hrfinance import timestamp
  value=self.read(check.evidence,schema)
  if value!=check.payload:raise ValidationError('Recorded observation differs from exact supplied evidence')
  if any(value[k]!=lineage.payload[k] for k in ['provider','realm','entity','source_reference','transaction_date','accounting_period','treatment_evidence_id']):raise ValidationError('Exact source/economic observation correlation required')
  if value['state']!='found' or not value['target_reference'] or not value['incumbent_version']:raise ValidationError('Uncertain, multiple or absent outcomes cannot adjudicate a claim')
  if not 0<=(timezone.now()-timestamp(value['observed_at'])).total_seconds()<=rules['max_age_seconds']:raise ValidationError('Fresh incumbent evidence required')
  return value
 def read(self,evidence,schema,kind='quickbooks_verification'):
  if evidence.kind!=kind or len(evidence.body)>100000:raise ValidationError('Bounded QuickBooks verification evidence required')
  def pairs(items):
   out={}
   for k,v in items:
    if k in out:raise ValueError('Duplicate key')
    out[k]=v
   return out
  try:v=json.loads(evidence.body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
  except (ValueError,TypeError,RecursionError):raise ValidationError('Strict finite response JSON required')
  validate(schema,v);return v
