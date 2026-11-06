import json
from django.core.exceptions import ValidationError
from django.db import transaction
class SuppliedPPEAdapter:
 def read(self,evidence):
  if evidence.kind!='ppe_register' or len(evidence.body)>100000:raise ValidationError('Bounded supplied PPE register evidence required')
  def pairs(items):
   out={}
   for k,v in items:
    if k in out:raise ValidationError('Duplicate JSON fields')
    out[k]=v
   return out
  try:return json.loads(evidence.body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
  except (ValueError,TypeError,RecursionError):raise ValidationError('Finite register JSON required')
class LocalPPEReportAdapter:
 @transaction.atomic
 def read(self,actor,work):
  from apps.finance import ppe
  ppe.locked(actor,work.case_id,'ppe.report');ppe.current(work);r=ppe.approved(work,'schedule')
  return {'work_id':work.pk,'review_id':r.pk,'sha256':work.sha256,'result':work.result,'native_source_verified':False,'ledger_posted':False}
