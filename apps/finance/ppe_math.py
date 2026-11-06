"""Finite proposed implementations; parameters and actual accounting policy are supplied."""
from decimal import localcontext
from django.core.exceptions import ValidationError
from .rules import decimal,number,ROUNDING

def charge(rule,cost,accumulated,residual,life,fraction):
 if rule['method']=='unimplemented_method':return {'charge':None,'finding':'method_implementation_missing'}
 if any(x is None for x in [cost,accumulated,residual,life,fraction]):return {'charge':None,'finding':'asset_rule_inputs_unknown'}
 with localcontext() as ctx:
  ctx.prec=512
  c,a,r,l,f=decimal(cost,nonnegative=True),decimal(accumulated,nonnegative=True),decimal(residual,nonnegative=True),decimal(life,positive=True),decimal(fraction,nonnegative=True)
  if a>c or r>c:return {'charge':None,'finding':'asset_basis_invalid'}
  raw=(c-r)/l*f;remaining=max(c-a-r,decimal('0'))
  if raw>remaining:
   if rule['remaining_value']=='hold':return {'charge':None,'finding':'charge_exceeds_remaining_value'}
   raw=remaining
  value=raw.quantize(decimal('1').scaleb(-rule['decimal_places']),rounding=ROUNDING[rule['rounding']])
  if value>remaining:return {'charge':None,'finding':'rounding_exceeds_remaining_value'}
  result=number(value);decimal(result)
  return {'charge':result,'finding':None}
