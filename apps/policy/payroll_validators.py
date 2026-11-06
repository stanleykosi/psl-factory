"""Typed finite payroll choices and explicit synthetic/owner oracles; no uploaded code."""
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from adapters.forecast import obj,KEY
from apps.documents.contracts import validate
from apps.finance.rules import decimal
from .document_validators import typed,ROLES
from .hrfinance_validators import ID,IDS,MONTH
ACCESS='F16.input_access_rules'
MERGE='F16.merge_rules'
MATCH='F17.match_rules'
REPORT='F18.reporting_rules'
AUTH='F18.review_authority'
DEC={'anyOf':[{'type':'string','pattern':r'^-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$'},{'type':'null'}]}
KEYS={'type':'array','minItems':1,'maxItems':50,'uniqueItems':True,'items':KEY}
SCHEMAS={
 ACCESS:('schema:psl/payroll-access/v1',obj({'human_only':{'const':True},'entity':KEY,'from_period':MONTH,'to_period':MONTH,'currency':KEY,'unit':{'const':'major_currency'},'providers':{'type':'array','minItems':2,'maxItems':2,'items':obj({'provider':KEY,'owner_id':ID,'owner_role':{'enum':ROLES}})},'reader_ids':IDS,'allowed_components':KEYS,'source_decimal_places':{'type':'integer','minimum':0,'maximum':8},'max_age_seconds':{'type':'integer','minimum':1},'retention_seconds':{'type':'integer','minimum':1},'retention_mode':{'const':'restrict_after_expiry'},'source_contract_evidence_id':ID})),
 MERGE:('schema:psl/payroll-merge/v1',obj({'duplicate_within_source':{'const':'reject'},'adjustment_treatment':{'const':'source_revision_only'},'method':{'enum':['disjoint_union','prefer_provider','sum_explicit']},'provider_order':{'type':'array','minItems':2,'maxItems':2,'uniqueItems':True,'items':KEY},'unknown_amount':{'const':'hold'},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':obj({'left':DEC,'right':DEC,'expected':DEC,'overlap':{'type':'boolean'}})}})),
 MATCH:('schema:psl/payroll-match/v1',obj({'employee_key':{'const':'opaque_exact_case_sensitive'},'hr_purpose':{'const':'payroll_matching'},'membership':{'enum':['whole_period_only','as_of_snapshot']},'multiple_memberships':{'const':'hold'},'missing_membership':{'const':'hold'},'unknown_bu':{'const':'hold'},'hr_write':{'const':False}})),
 REPORT:('schema:psl/payroll-report/v1',obj({'components':{'type':'array','minItems':1,'maxItems':50,'items':obj({'component':KEY,'coefficient':{'type':'string'}})},'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']},'minimum_employees':{'type':'integer','minimum':1},'small_groups':{'const':'hold_all_publication'},'recipient_ids':IDS,'destination':KEY,'disclosure':{'const':'aggregate_only'},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':obj({'amounts':{'type':'array','minItems':1,'maxItems':50,'items':obj({'component':KEY,'amount':DEC})},'expected':DEC})}})),
 AUTH:('schema:psl/payroll-authority/v1',obj({'human_only':{'const':True},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'role':{'const':'Finance'},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['input','combine','match','aggregate','publish']}}})},'independent_reviewer':{'type':'boolean'}}))}

def merge_amount(left,right,overlap,method):
 from decimal import localcontext
 if left is None or overlap and right is None:return None
 if not overlap:return left
 if method=='disjoint_union':return None
 if method=='prefer_provider':return left
 with localcontext() as c:c.prec=512;return format(decimal(left)+decimal(right),'f')

def report_amount(rows,rules):
 from decimal import Decimal,localcontext
 from apps.finance.rules import ROUNDING
 mapping={r['component']:decimal(r['coefficient']) for r in rules['components']}
 with localcontext() as c:
  c.prec=512;values=[None if r['amount'] is None else decimal(r['amount'])*mapping[r['component']] for r in rows if r['component'] in mapping]
  if not values or any(v is None for v in values):return None
  return format(sum(values,Decimal(0)).quantize(Decimal(1).scaleb(-rules['decimal_places']),rounding=ROUNDING[rules['rounding']]),'f')

def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 if component==ACCESS:
  if v['from_period']>v['to_period'] or len({r['provider'] for r in v['providers']})!=2:raise ValidationError('Two distinct providers and ordered periods required')
  ids=v['reader_ids']+[r['owner_id'] for r in v['providers']]
  if get_user_model().objects.filter(pk__in=set(ids),is_active=True).count()!=len(set(ids)):raise ValidationError('Active actual principals required')
  from apps.pmo.services import subject
  e=subject(case,v['source_contract_evidence_id'],'payroll_source_contract')
  if case.evidence.filter(kind=e.kind,version__gt=e.version).exists():raise ValidationError('Payroll source contract superseded')
  try:timezone.now()+timedelta(seconds=v['retention_seconds'])
  except (OverflowError,ValueError):raise ValidationError('Retention exceeds supported datetime range')
 elif component==MERGE:
  known=unknown=overlap=False
  for r in v['oracles']:
   for k in ['left','right','expected']:
    if r[k] is not None:decimal(r[k])
   actual=merge_amount(r['left'],r['right'],r['overlap'],v['method'])
   if (actual is None)!=(r['expected'] is None) or actual is not None and decimal(actual)!=decimal(r['expected']):raise ValidationError('Merge implementation differs from supplied oracle')
   known|=actual is not None;unknown|=r['left'] is None;overlap|=r['overlap']
  if not known or not unknown or not overlap:raise ValidationError('Known, overlap and unknown-propagation merge oracles required')
 elif component==REPORT:
  if len({r['component'] for r in v['components']})!=len(v['components']):raise ValidationError('Duplicate pay-component inclusion')
  for r in v['components']:decimal(r['coefficient'])
  if get_user_model().objects.filter(pk__in=v['recipient_ids'],is_active=True).count()!=len(v['recipient_ids']):raise ValidationError('Actual active report recipients required')
  known=unknown=False
  for r in v['oracles']:
   if any(x['component'] not in {x['component'] for x in v['components']} for x in r['amounts']):raise ValidationError('Oracle uses unknown component')
   actual=report_amount(r['amounts'],v)
   if (actual is None)!=(r['expected'] is None) or actual is not None and decimal(actual)!=decimal(r['expected']):raise ValidationError('Staff-cost sum/rounding differs from supplied oracle')
   known|=actual is not None;unknown|=actual is None
  if not known or not unknown:raise ValidationError('Known and unknown payroll report oracles required')
 elif component==AUTH:
  keys=[]
  for r in v['assignments']:
   if not get_user_model().objects.filter(pk=r['user_id'],is_active=True).exists():raise ValidationError('Actual active Finance human required')
   keys.extend((r['user_id'],k) for k in r['purposes'])
  if len(keys)!=len(set(keys)):raise ValidationError('Duplicate Finance authority')
