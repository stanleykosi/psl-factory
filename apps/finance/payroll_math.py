"""Pure bounded Decimal working-sheet transformations; parameters are owner configuration."""
from datetime import date
import calendar
from decimal import Decimal,localcontext
from adapters.payroll import sum_values
from apps.policy.payroll_validators import merge_amount,report_amount
from .rules import decimal,number
from functools import wraps

def exact_context(fn):
 @wraps(fn)
 def run(*args,**kwargs):
  with localcontext() as context:
   context.prec=512
   return fn(*args,**kwargs)
 return run

@exact_context
def combine(inputs,rules):
 buckets={};controls={};codes=[]
 for item,payload in inputs:
  calculated=sum_values(r['amount'] for r in payload['rows']);declared=payload['control_total']
  controls[str(item.pk)]={'declared':declared,'calculated':calculated,'difference':None if declared is None or calculated is None else number(decimal(declared)-decimal(calculated))}
  if declared is None or calculated is None or decimal(declared)!=decimal(calculated):codes.append('source_control_unresolved')
  if payload['completeness']!='complete':codes.append('source_inventory_incomplete')
  for r in payload['rows']:buckets.setdefault((r['employee_id'],r['component']),[]).append({**r,'input_id':item.pk,'provider':item.provider})
 rows=[];issues=[]
 for (employee,component),group in sorted(buckets.items()):
  provenance=[{'input_id':x['input_id'],'row_ref':x['row_ref'],'provider':x['provider'],'amount':x['amount']} for x in group]
  if not rules:amount=None;code='merge_policy_missing'
  else:
   group=sorted(group,key=lambda r:rules['provider_order'].index(r['provider']))
   amount=merge_amount(group[0]['amount'],group[1]['amount'] if len(group)>1 else None,len(group)>1,rules['method'])
   code='overlap_unresolved' if len(group)>1 and rules['method']=='disjoint_union' else 'unknown_amount' if amount is None else None
  if code:codes.append(code);issues.append({'employee_id':employee,'component':component,'code':code})
  rows.append({'employee_id':employee,'component':component,'amount':amount,'provenance':provenance})
 raw=sum_values(c['calculated'] for c in controls.values());combined=sum_values(r['amount'] for r in rows)
 return {'rows':rows,'issues':issues,'controls':controls,'raw_total':raw,'combined_total':combined,'intentional_overlap_difference':None if raw is None or combined is None else number(decimal(raw)-decimal(combined))},sorted(set(codes))

def match(rows,hr_rows,period,semantics,rules):
 memberships={}
 for r in hr_rows:memberships.setdefault(r['employee_id'],[]).append(r)
 year,month=map(int,period.split('-'));first=date(year,month,1);last=date(year,month,calendar.monthrange(year,month)[1]);out=[];issues=[]
 for row in rows:
  group=memberships.get(row['employee_id'],[]);code=None;bu=None
  if not rules:code='match_policy_missing'
  elif not group:code='missing_hr_membership'
  elif len(group)!=1:code='ambiguous_hr_membership'
  else:
   r=group[0];end=date.fromisoformat(r['effective_until']) if r['effective_until'] is not None else None
   if r['bu'] is None:code='unknown_bu'
   elif rules['membership']=='whole_period_only' and (date.fromisoformat(r['effective_from'])>first or end is not None and (end<last if semantics=='inclusive' else end<=last)):code='midperiod_transfer_requires_treatment'
   else:bu=r['bu']
  if code:issues.append({'employee_id':row['employee_id'],'code':code})
  out.append({**row,'bu':bu,'match_status':code or 'matched'})
 return {'rows':out,'issues':issues},sorted({r['code'] for r in issues})

@exact_context
def aggregate(rows,rules):
 included={r['component'] for r in rules['components']};eligible=[r for r in rows if r['component'] in included];excluded=[r for r in rows if r['component'] not in included];groups={};codes=[]
 for r in eligible:
  if r['bu'] is None or r['match_status']!='matched':codes.append('unresolved_membership');continue
  groups.setdefault(r['bu'],[]).append(r)
 output={};counts={}
 for bu,items in sorted(groups.items()):
  output[bu]=report_amount(items,rules);counts[bu]=len({r['employee_id'] for r in items})
  if output[bu] is None:codes.append('unknown_included_amount')
  if counts[bu]<rules['minimum_employees']:codes.append('small_group_disclosure_hold')
 if not eligible:codes.append('empty_eligible_population')
 eligible_total=report_amount(eligible,rules);grouped=sum_values(output.values());raw_eligible=sum_values(r['amount'] for r in eligible)
 if eligible_total is None or grouped is None or decimal(eligible_total)!=decimal(grouped):codes.append('group_rounding_or_unresolved_tieout')
 return {'by_bu':output,'employee_counts':counts,'eligible_total':eligible_total,'grouped_total':grouped,'excluded_total':sum_values(r['amount'] for r in excluded),'unweighted_eligible_total':raw_eligible,'coefficient_effect':None if raw_eligible is None or eligible_total is None else number(decimal(eligible_total)-decimal(raw_eligible)),'rows':rows},sorted(set(codes))
