"""Typed finite payroll choices and explicit synthetic/owner oracles; no uploaded code."""
from datetime import timedelta
from copy import deepcopy
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from adapters.forecast import obj,KEY
from adapters.payroll_spreadsheet import FIELDS
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
HEADER={'type':'string','minLength':1,'maxLength':100}
COLUMNS=obj({field:HEADER for field in FIELDS})
LAYOUT={'oneOf':[
 obj({'format':{'const':'csv'},'delimiter':{'enum':[',',';','\t']},'columns':COLUMNS}),
 obj({'format':{'const':'xlsx'},'sheet':{'type':'string','minLength':1,'maxLength':31},'columns':COLUMNS}),
]}
PROVIDER=obj({'provider':KEY,'owner_id':ID,'owner_role':{'enum':ROLES}})
PROVIDER['properties']['spreadsheet_layouts']={'type':'array','minItems':1,'maxItems':2,'items':LAYOUT}
SCHEMAS={
 ACCESS:('schema:psl/payroll-access/v1',obj({'human_only':{'const':True},'entity':KEY,'from_period':MONTH,'to_period':MONTH,'currency':KEY,'unit':{'const':'major_currency'},'providers':{'type':'array','minItems':2,'maxItems':2,'items':PROVIDER},'reader_ids':IDS,'allowed_components':KEYS,'source_decimal_places':{'type':'integer','minimum':0,'maximum':8},'max_age_seconds':{'type':'integer','minimum':1},'retention_seconds':{'type':'integer','minimum':1},'retention_mode':{'const':'restrict_after_expiry'},'source_contract_evidence_id':ID})),
 MERGE:('schema:psl/payroll-merge/v1',obj({'duplicate_within_source':{'const':'reject'},'adjustment_treatment':{'const':'source_revision_only'},'method':{'enum':['disjoint_union','prefer_provider','sum_explicit']},'provider_order':{'type':'array','minItems':2,'maxItems':2,'uniqueItems':True,'items':KEY},'unknown_amount':{'const':'hold'},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':obj({'left':DEC,'right':DEC,'expected':DEC,'overlap':{'type':'boolean'}})}})),
 MATCH:('schema:psl/payroll-match/v1',obj({'employee_key':{'const':'opaque_exact_case_sensitive'},'hr_purpose':{'const':'payroll_matching'},'membership':{'enum':['whole_period_only','as_of_snapshot']},'multiple_memberships':{'const':'hold'},'missing_membership':{'const':'hold'},'unknown_bu':{'const':'hold'},'hr_write':{'const':False}})),
 REPORT:('schema:psl/payroll-report/v1',obj({'components':{'type':'array','minItems':1,'maxItems':50,'items':obj({'component':KEY,'coefficient':{'type':'string'}})},'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']},'minimum_employees':{'type':'integer','minimum':1},'small_groups':{'const':'hold_all_publication'},'recipient_ids':IDS,'destination':KEY,'disclosure':{'const':'aggregate_only'},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':obj({'amounts':{'type':'array','minItems':1,'maxItems':50,'items':obj({'component':KEY,'amount':DEC})},'expected':DEC})}})),
 AUTH:('schema:psl/payroll-authority/v1',obj({'human_only':{'const':True},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'role':{'const':'Finance'},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['input','combine','match','aggregate','publish']}}})},'independent_reviewer':{'type':'boolean'}}))}

# Explicit successors. Existing reference IDs and v1 source behavior stay intact.
ACCESS_V2=deepcopy(SCHEMAS[ACCESS][1])
ACCESS_V2['properties'].update(format={'const':'psl.payroll-access/v2'},
 row_handling={'enum':[None,'reject_export','hold_conflicting_rows']},
 currency_mode={'enum':[None,'request_currency','row_currency']})
ACCESS_V2['required']+=['format','row_handling','currency_mode']
for layout in ACCESS_V2['properties']['providers']['items']['properties']['spreadsheet_layouts']['items']['oneOf']:
 layout['properties']['columns']['properties']['currency']=deepcopy(HEADER)
MERGE_V2=deepcopy(SCHEMAS[MERGE][1])
MERGE_V2['properties'].update(format={'const':'psl.payroll-merge/v2'},
 duplicate_within_source={'enum':[None,'reject','hold_conflicting_rows']})
MERGE_V2['required']+=['format']
SUCCESSOR_SCHEMAS={ACCESS:('schema:psl/payroll-access/v2',ACCESS_V2),
                   MERGE:('schema:psl/payroll-merge/v2',MERGE_V2)}


def schema_for(component,content):
 successor=SUCCESSOR_SCHEMAS.get(component)
 if successor and isinstance(content,dict) and content.get('format')==successor[1]['properties']['format']['const']:
  return successor
 return SCHEMAS[component]

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
 v=typed(target,*schema_for(component,target.content))
 if component==ACCESS:
  if v['from_period']>v['to_period'] or len({r['provider'] for r in v['providers']})!=2:raise ValidationError('Two distinct providers and ordered periods required')
  for provider in v['providers']:
   layouts=provider.get('spreadsheet_layouts',[])
   if len({layout['format'] for layout in layouts})!=len(layouts) or any(
    len(set(layout['columns'].values()))!=len(layout['columns']) for layout in layouts
   ):raise ValidationError('Each export format needs a distinct, exact payroll header mapping')
   if v.get('format')=='psl.payroll-access/v2':
    if v['currency_mode']=='row_currency' and any('currency' not in layout['columns'] for layout in layouts):
     raise ValidationError('Every mapped spreadsheet format needs its agreed row-currency header.')
    if v['currency_mode']=='request_currency' and any('currency' in layout['columns'] for layout in layouts):
     raise ValidationError('Choose a row-currency source contract before mapping a currency column.')
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
