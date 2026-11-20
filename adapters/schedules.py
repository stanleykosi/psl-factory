"""Bounded supplied inventory and local report adapters. No workbook execution or writes."""
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.identity.services import require
class SuppliedScheduleAdapter:
 def read(self,evidence,kind='schedule_inventory'):
  if kind not in ('schedule_inventory','income_detail') or evidence.kind!=kind or len(evidence.body)>128000:
   raise ValidationError('Choose the exact supplied schedule evidence for this work.')
  def pairs(items):
   result={}
   for key,value in items:
    if key in result:raise ValidationError('Duplicate JSON field')
    result[key]=value
   return result
  try:return json.loads(evidence.body,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError()))
  except (ValueError,TypeError,RecursionError):raise ValidationError('The supplied schedule evidence is not valid structured data.')

class LocalScheduleReportAdapter:
 @transaction.atomic
 def read(self,actor,work):
  from apps.finance.schedules import approved,locked
  locked(actor,work.case_id,'schedules.report');review=approved(work)
  return {'work_id':work.pk,'sha256':work.sha256,'review_id':review.pk,'result':work.result,'native_workbook_verified':False,'ledger_posted':False}
