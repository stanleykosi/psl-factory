"""Native internal inbox only. No network endpoint, customer delivery or clock claim."""
from django.core.exceptions import ValidationError
class InternalSupportResponseAdapter:
 def lookup(self,job):
  from apps.baas.support_release import Receipt
  r=Receipt.objects.filter(job=job).first()
  if r:
   p=job.packet
   if r.operation_key!='support-response:'+str(p.case_id)+':'+str(p.pk) or r.recipient_id!=p.snapshot['recipient'] or r.payload!=p.payload or r.sha256!=p.sha256 or r.classification!='internal_storage_only':raise ValidationError('Receipt intent mismatch')
  return r
 def deliver(self,job_id,fence):
  from apps.baas.support_release_delivery import deliver_internal
  return deliver_internal(job_id,fence)
