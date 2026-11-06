"""Bounded supplied events and read-only local reporting; no native ledger write."""
import json
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from apps.policy.bu_validators import DEC
from apps.policy.hrfinance_validators import MONTH
from apps.finance.rules import decimal
from adapters.payroll import sum_values
EVENT=obj({'event_id':KEY,'amount':DEC,'tags':{'type':'array','maxItems':20,'uniqueItems':True,'items':KEY}})
EXPORT=obj({'source':KEY,'source_version':KEY,'entity':KEY,'period':MONTH,'currency':KEY,'unit':{'const':'major_currency'},'extracted_at':{'type':'string'},'completeness':{'enum':['complete','partial','unknown']},'control_total':DEC,'rows':{'type':'array','minItems':1,'maxItems':500,'items':EVENT}})
class EventExportError(ValidationError):
 def __init__(self,code):super().__init__('Supplied event export rejected',code=code)
class SuppliedBUEventAdapter:
 def read(self,body,scope,rules):
  try:
   data=json.loads(body);validate(EXPORT,data)
  except (ValueError,TypeError,ValidationError):raise EventExportError('event_schema_rejected')
  if any(data[k]!=scope[k] for k in ['entity','period','currency']) or data['source']!=rules['source']:raise EventExportError('event_scope_mismatch')
  try:t=timestamp(data['extracted_at'])
  except (ValidationError,ValueError,TypeError):raise EventExportError('event_extract_invalid')
  age=(timezone.now()-t).total_seconds()
  if age<0 or age>rules['max_age_seconds']:raise EventExportError('event_extract_stale')
  if len({r['event_id'] for r in data['rows']})!=len(data['rows']):raise EventExportError('duplicate_event_identity')
  try:
   for row in data['rows']:
    if row['amount'] is not None:decimal(row['amount'])
   if data['control_total'] is not None:decimal(data['control_total'])
  except ValidationError:raise EventExportError('event_numeric_invalid')
  total=sum_values(r['amount'] for r in data['rows']);codes=[]
  if total is None or data['control_total'] is None or decimal(total)!=decimal(data['control_total']):codes.append('event_control_unresolved')
  if data['completeness']!='complete':codes.append('event_inventory_incomplete')
  return data,codes
class LocalBUReportAdapter:
 def read(self,actor,report_id):
  from apps.finance.bu import read_report
  return read_report(actor,report_id)
