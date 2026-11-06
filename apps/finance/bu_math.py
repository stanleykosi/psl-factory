from decimal import Decimal
from django.core.exceptions import ValidationError
from .rules import decimal,number,proportional
from .payroll_math import exact_context
from adapters.payroll import sum_values
from apps.policy.bu_validators import weights

@exact_context
def staff(rows,declared,rules,financial,bus):
 codes=[];out=[];counts={};included=[r for r in rows if r['component'] in financial['components']];selected={tuple(x) for x in declared}
 if not included:codes.append('empty_staff_population')
 if len(selected)!=len(declared):codes.append('duplicate_exception_subject')
 pairs={(r['employee_id'],r['component']) for r in included}
 if selected-pairs:codes.append('exception_subject_not_in_source')
 by={}
 for r in rules:by.setdefault((r['employee_id'],r['component']),[]).append(r)
 if set(by)-selected:codes.append('rule_not_declared_as_exception')
 for row in included:
  pair=(row['employee_id'],row['component']);exception=pair in selected;code=None;parts={};residual=None
  try:
   if row['amount'] is None:raise ValidationError('unknown_staff_cost')
   if exception:
    if len(by.get(pair,[]))!=1:raise ValidationError('missing_or_ambiguous_exception_rule')
    rule=by[pair][0]
    if rule['standard_pool_ref']!=financial['standard_pool_ref']:raise ValidationError('exception_pool_exclusion_mismatch')
    w=weights(rule['weights'])
   else:w={row['bu']:Decimal(1)} if financial['standard_method']=='matched_bu' else weights(financial['standard_weights'])
   if not set(w)<=set(bus):raise ValidationError('unknown_or_ineligible_bu')
   parts,residual,_=proportional(decimal(row['amount']),w,financial['rounding'])
   if residual:code='allocation_residual_held'
   for bu,amount in parts.items():
    if w[bu]>0:counts.setdefault(bu,set()).add(row['employee_id'])
  except ValidationError as e:code=e.messages[0]
  if code:codes.append(code)
  out.append({**row,'allocations':{k:number(v) for k,v in parts.items()},'residual':number(residual),'exception':exception,'standard_pool_ref':financial['standard_pool_ref'],'excluded_from_standard_pool':exception,'code':code})
 by_bu={bu:sum_values(r['allocations'].get(bu,'0') for r in out) for bu in sorted({b for r in out for b in r['allocations']})}
 source=sum_values(r['amount'] for r in included) if included else None;allocated=sum_values(by_bu.values()) if included else None;residual=sum_values(r['residual'] for r in out) if included else None
 conserved=source is not None and allocated is not None and residual is not None and decimal(source)==decimal(allocated)+decimal(residual)
 if not conserved:codes.append('staff_conservation_unresolved')
 return {'rows':out,'by_bu':by_bu,'staff_counts':{k:len(v) for k,v in counts.items()},'source_total':source,'allocated_total':allocated,'residual':residual,'conserved':conserved,'excluded_components_total':sum_values(r['amount'] for r in rows if r['component'] not in financial['components'])},sorted(set(codes))

@exact_context
def events(rows,rules,bus):
 mapping={m['tag']:m for m in rules['mappings']};out=[];codes=[]
 for row in rows:
  code=None;parts={};residual=None;company=None
  try:
   if row['amount'] is None:raise ValidationError('unknown_event_amount')
   if len(row['tags'])!=1:raise ValidationError('ambiguous_event_tags')
   rule=mapping.get(row['tags'][0])
   if not rule:raise ValidationError('unmapped_event')
   if rule['treatment']=='company':company=row['amount'];residual=Decimal(0)
   else:
    w={rule['bu']:Decimal(1)} if rule['treatment']=='direct' else weights(rule['weights'])
    if not set(w)<=set(bus):raise ValidationError('unknown_event_bu')
    parts,residual,_=proportional(decimal(row['amount']),w,rules['rounding'])
    if residual:code='event_residual_held'
  except ValidationError as e:code=e.messages[0]
  if code:codes.append(code)
  out.append({**row,'allocations':{k:number(v) for k,v in parts.items()},'company_only':company,'residual':number(residual),'code':code})
 by_bu={bu:sum_values(r['allocations'].get(bu,'0') for r in out) for bu in sorted({b for r in out for b in r['allocations']})}
 source=sum_values(r['amount'] for r in out);allocated=sum_values(by_bu.values()) if by_bu else '0';company=sum_values(r['company_only'] or '0' for r in out);residual=sum_values(r['residual'] for r in out)
 conserved=source is not None and residual is not None and decimal(source)==decimal(allocated)+decimal(company)+decimal(residual)
 if not conserved:codes.append('event_conservation_unresolved')
 return {'rows':out,'by_bu':by_bu,'source_total':source,'allocated_total':allocated,'company_only':company,'residual':residual,'conserved':conserved},sorted(set(codes))
