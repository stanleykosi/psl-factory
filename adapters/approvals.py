import json
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
class SuppliedApprovalReadAdapter:
 """Strict supplied reference/read evidence; no cryptographic/native authenticity claim."""
 def read(self,evidence,schema,kind):
  if evidence.kind!=kind or len(evidence.body)>100000:raise ValidationError('Bounded typed prerequisite evidence required')
  def pairs(items):
   out={}
   for k,v in items:
    if k in out:raise ValueError('Duplicate fields')
    out[k]=v
   return out
  try:v=json.loads(evidence.body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
  except (ValueError,TypeError,RecursionError):raise ValidationError('Strict finite JSON required')
  validate(schema,v);return v
class InternalApprovalRoutingAdapter:
 def lookup(self,job):
  from apps.pmo.models import ApprovalRouteReceipt
  from apps.documents.contracts import digest
  receipt=ApprovalRouteReceipt.objects.filter(operation_key=job.operation_key).first()
  if receipt and (receipt.job_id!=job.pk or digest(receipt.payload)!=digest(job.intent['public']) or receipt.recipient_id!=job.intent['recipient']):raise ValidationError('Routing receipt identity/payload conflict')
  return receipt
 def deliver(self,pk,fence):
  from apps.pmo.approval_routing import deliver_local
  return deliver_local(pk,fence)
