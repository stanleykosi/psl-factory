"""Bounded supplied payroll reader and local reviewed-aggregate adapter. No payroll/source writes."""
import json,re
from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError
from django.utils import timezone
from adapters.hrfinance import timestamp
from apps.finance.rules import decimal,number
class PayrollExportError(ValidationError):
 def __init__(self,code):super().__init__('Payroll export rejected: '+code+'; no values retained',code=code)

def sum_values(values):
 values=list(values)
 if any(v is None for v in values):return None
 with localcontext() as c:c.prec=512;return number(sum((decimal(v) for v in values),Decimal(0)))

class SuppliedPayrollAdapter:
 def read(self,body,request,provider,rules):
  if not isinstance(body,str) or len(body.encode('utf-8'))>256000:raise PayrollExportError('payload_budget')
  try:v=json.loads(body,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
  except (TypeError,ValueError):raise PayrollExportError('json_schema')
  keys={'provider','source_version','entity','period','currency','unit','extracted_at','completeness','control_total','rows'}
  if not isinstance(v,dict) or set(v)!=keys:raise PayrollExportError('envelope_schema')
  if v['provider']!=provider or any(v[k]!=request.metadata[k] for k in ['entity','period','currency']) or v['unit']!='major_currency':raise PayrollExportError('source_or_period_scope')
  if not isinstance(v['source_version'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',v['source_version']):raise PayrollExportError('source_version_schema')
  try:at=timestamp(v['extracted_at'])
  except ValidationError:raise PayrollExportError('timestamp_schema')
  if at>timezone.now() or (timezone.now()-at).total_seconds()>rules['max_age_seconds']:raise PayrollExportError('source_freshness')
  if v['completeness'] not in ['complete','partial','unknown'] or not isinstance(v['rows'],list) or len(v['rows'])>500:raise PayrollExportError('inventory_schema')
  refs=set();pairs=set()
  for r in v['rows']:
   if not isinstance(r,dict) or set(r)!={'row_ref','employee_id','component','amount'}:raise PayrollExportError('out_of_contract_fields')
   if any(not isinstance(r[k],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',r[k]) for k in ['row_ref','employee_id','component']):raise PayrollExportError('identity_schema')
   if r['component'] not in rules['allowed_components']:raise PayrollExportError('component_scope')
   if r['row_ref'] in refs or (r['employee_id'],r['component']) in pairs:raise PayrollExportError('duplicate_source_row_or_component')
   refs.add(r['row_ref']);pairs.add((r['employee_id'],r['component']))
   if r['amount'] is not None:
    try:
     n=decimal(r['amount'])
     with localcontext() as ctx:
      ctx.prec=512
      rounded=n.quantize(Decimal(1).scaleb(-rules['source_decimal_places']))
     if n!=rounded:raise ValueError
    except (ValidationError,ValueError,ArithmeticError):raise PayrollExportError('amount_schema_or_precision')
  if v['control_total'] is not None:
   try:decimal(v['control_total'])
   except ValidationError:raise PayrollExportError('control_total_schema')
  return v

class LocalPayrollReportAdapter:
 def read(self,actor,publication_id):
  from apps.finance.payroll import read_publication
  return read_publication(actor,publication_id)
