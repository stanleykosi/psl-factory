"""Supplied export reader. No network discovery, HR writes or native authenticity claim."""
import json,hashlib,re
from datetime import date,datetime
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone

class HRExportError(ValidationError):
 def __init__(self,code):super().__init__('HR export exception: '+code+'; no source row values retained',code=code)

def timestamp(value):
 try:
  v=datetime.fromisoformat(value)
  if v.utcoffset() is None:raise ValueError
  return v
 except (ValueError,TypeError):raise HRExportError('timestamp_schema')

def day(value):
 try:
  if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError
  return date.fromisoformat(value)
 except (ValueError,TypeError):raise HRExportError('effective_date_schema')

class SuppliedHRExportAdapter:
 def read(self,body,contract,now=None):
  now=now or timezone.now()
  if not isinstance(body,str) or len(body.encode('utf-8'))>256000:raise HRExportError('payload_budget')
  try:v=json.loads(body,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
  except (TypeError,ValueError):raise HRExportError('json_schema')
  keys={'view_ref','source_version','as_of','extracted_at','entity','period','completeness','rows'}
  if not isinstance(v,dict) or set(v)!=keys:raise HRExportError('envelope_schema')
  p=contract.payload
  if any(v[k]!=p[k] for k in ['entity','period','as_of']) or v['view_ref']!=p['source_view']:raise HRExportError('source_view_or_period_scope')
  if not isinstance(v['source_version'],str) or not 1<=len(v['source_version'])<=100:raise HRExportError('source_version_unknown')
  at=timestamp(v['extracted_at'])
  if at>now or (now-at).total_seconds()>p['max_age_seconds']:raise HRExportError('source_freshness')
  if v['completeness'] not in ['complete','partial','unknown']:raise HRExportError('completeness_schema')
  if not isinstance(v['rows'],list) or len(v['rows'])>500:raise HRExportError('row_budget')
  fields=set(p['fields']);seen=set();as_of=day(v['as_of'])
  for r in v['rows']:
   if not isinstance(r,dict) or set(r)!=fields:raise HRExportError('out_of_contract_fields')
   if not isinstance(r['employee_id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',r['employee_id']):raise HRExportError('employee_identity_schema')
   if r['employee_id'] in seen:raise HRExportError('duplicate_or_overlapping_employee')
   seen.add(r['employee_id'])
   if r['bu'] is not None and (not isinstance(r['bu'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',r['bu'])):raise HRExportError('bu_identity_schema')
   start=day(r['effective_from']);end=day(r['effective_until']) if r['effective_until'] is not None else None
   if start>as_of or end is not None and (end<start or (as_of>end if p['effective_until_semantics']=='inclusive' else as_of>=end)):raise HRExportError('employee_not_effective_at_snapshot')
   if 'role' in r and r['role'] is not None and (not isinstance(r['role'],str) or not 1<=len(r['role'])<=100):raise HRExportError('role_schema')
   if 'monthly_pay' in r and r['monthly_pay'] is not None and (not isinstance(r['monthly_pay'],str) or not re.fullmatch(r'-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?',r['monthly_pay'])):raise HRExportError('pay_schema')
   if 'currency' in r and (not isinstance(r['currency'],str) or not re.fullmatch(r'[A-Z]{3}',r['currency'])):raise HRExportError('currency_schema')
  return v

class LocalHRFinanceInbox:
 def read(self,actor,case):
  from apps.finance.hrfinance import check_snapshot_access
  from apps.finance.hrfinance_models import HRReadSnapshot
  result=[]
  for s in HRReadSnapshot.objects.defer('payload').filter(contract__need__case=case,status='accepted').order_by('-pk')[:100]:
   try:check_snapshot_access(actor,s);result.append(s)
   except (ValidationError,PermissionDenied):pass
  return result
