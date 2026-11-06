"""Supplemental engineering contracts; no native workbook or financial policy defaults."""
from decimal import localcontext
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from apps.documents.contracts import validate
from apps.finance.rules import decimal,number
from .document_validators import typed
ID={'type':'integer','minimum':1}
DEC={'anyOf':[{'type':'string','maxLength':64},{'type':'null'}]}
INCOME='F12.detail_rules'
INVENTORY='F13.inventory_rules'
AUTH='SCHEDULES.review_authority'
ORACLE=obj({'input':DEC,'expected':DEC})
SCHEMAS={
 INCOME:('schema:psl/income-detail/v1',obj({'entity':KEY,'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'report_line':KEY,'source_unit':KEY,'target_unit':KEY,'factor':{'type':'string'},'child_tolerance':{'type':'string'},'allowed_relationships':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['disaggregation','reclassification','additive']}},'source_overlap':{'enum':['hold','reviewed_evidence_resolution']},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':ORACLE}})),
 INVENTORY:('schema:psl/schedule-inventory/v1',obj({'required_keys':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':KEY},'accepted_levels':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['definition','synthetic_implementation']}},'monthly_performance':{'enum':['separate','existing_output','undecided']},'decision_evidence_id':{'anyOf':[ID,{'type':'null'}]}})),
 AUTH:('schema:psl/schedule-authority/v1',obj({'independent_reviewer':{'type':'boolean'},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'role':{'const':'Finance'},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['income','inventory']}}})}}))}

def scale(amount,factor):
 if amount is None:return None
 with localcontext() as ctx:
  ctx.prec=512
  value=number(decimal(amount)*decimal(factor,positive=True))
  decimal(value) # the result must also fit the explicit numeric budget, without rounding
  return value

def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 if component==INCOME:
  decimal(v['factor'],positive=True);decimal(v['child_tolerance'],nonnegative=True)
  if v['source_unit']==v['target_unit'] and decimal(v['factor'])!=1:raise ValidationError('Same-unit conversion must be identity')
  known=unknown=False
  for o in v['oracles']:
   actual=scale(o['input'],v['factor'])
   if actual is None:
    unknown=True
    if o['expected'] is not None:raise ValidationError('Unknown conversion is not zero')
   else:
    known=True
    if o['expected'] is None or decimal(actual)!=decimal(o['expected']):raise ValidationError('Conversion differs from supplied exact oracle')
  if not known or not unknown:raise ValidationError('Known and unknown conversion oracles required')
 elif component==INVENTORY:
  if v['monthly_performance']!='undecided' and not v['decision_evidence_id']:raise ValidationError('Monthly output decision needs scoped evidence')
  if v['decision_evidence_id']:
   from apps.pmo.services import subject
   subject(case,v['decision_evidence_id'],'policy_decision')
 elif component==AUTH:
  keys=[]
  for a in v['assignments']:
   if not get_user_model().objects.filter(pk=a['user_id'],is_active=True).exists():raise ValidationError('Actual active Finance principal required')
   keys.extend((a['user_id'],p) for p in a['purposes'])
  if len(keys)!=len(set(keys)):raise ValidationError('Duplicate review assignment')
