"""Finite reviewed allocation/reference policies; no private subjects in policy artifacts."""
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.documents.contracts import validate
from apps.finance.rules import decimal,proportional,number
from adapters.forecast import obj,KEY
from .document_validators import typed
from .hrfinance_validators import ID,IDS,MONTH
from .payroll_validators import DEC
STAFF='F21.allocation_rules'
SOURCE='F44.source_rules'
MAPPING='F44.attribution_rules'
AUTH='BU.review_authority'
DISCLOSE='BU.disclosure_rules'
WEIGHTS={'type':'array','minItems':1,'maxItems':50,'items':obj({'bu':KEY,'weight':{'type':'string'}})}
ROUND=obj({'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']},'residual':{'enum':['hold','assign_to_configured_bu']},'residual_bu':{'anyOf':[KEY,{'type':'null'}]}})
ORACLES={'type':'array','minItems':2,'maxItems':20,'items':obj({'amount':DEC,'weights':WEIGHTS,'expected':{'anyOf':[{'type':'object','additionalProperties':{'type':'string'}},{'type':'null'}]},'residual':DEC})}
SCOPE={'entity':KEY,'from_period':MONTH,'to_period':MONTH}
SCHEMAS={
 STAFF:('schema:psl/bu-staff/v1',obj(dict(SCOPE,components={'type':'array','minItems':1,'uniqueItems':True,'items':KEY},standard_pool_ref=KEY,pool_contract_evidence_id=ID,standard_method={'enum':['matched_bu','fixed_weights']},standard_weights=dict(WEIGHTS,minItems=0),rounding=ROUND,historical_treatment={'enum':['prospective_only','reviewed_replacement']},oracles=ORACLES))),
 SOURCE:('schema:psl/bu-events-source/v1',obj(dict(SCOPE,currency=KEY,source=KEY,owner_id=ID,reader_ids=IDS,source_contract_evidence_id=ID,design_decision_evidence_id=ID,max_age_seconds={'type':'integer','minimum':1},retention_seconds={'type':'integer','minimum':1,'maximum':315360000},retention_mode={'const':'restrict_after_expiry'},closed_periods={'type':'array','uniqueItems':True,'items':MONTH},closed_period_treatment={'enum':['hold','reviewed_reference_only']},company_comparison={'enum':['declared_control_only','finance_allocation_required']},source_write={'const':False}))),
 MAPPING:('schema:psl/bu-events-mapping/v1',obj(dict(SCOPE,mappings={'type':'array','minItems':1,'maxItems':100,'items':obj({'tag':KEY,'treatment':{'enum':['direct','shared','company']},'bu':{'anyOf':[KEY,{'type':'null'}]},'pool':{'anyOf':[KEY,{'type':'null'}]},'weights':{'type':'array','maxItems':50,'items':obj({'bu':KEY,'weight':{'type':'string'}})}})},conflicting_tags={'const':'hold'},unknown_tags={'const':'hold'},rounding=ROUND,historical_treatment={'enum':['prospective_only','reviewed_replacement']},oracles=ORACLES))),
 AUTH:('schema:psl/bu-authority/v1',obj({'human_only':{'const':True},'independent_reviewer':{'type':'boolean'},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'role':{'const':'Finance'},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['rule','staff','source','event','publish','historical']}}})}})),
 DISCLOSE:('schema:psl/bu-disclosure/v1',obj({'recipient_ids':IDS,'minimum_staff':{'type':'integer','minimum':1},'small_groups':{'const':'hold_all_publication'},'destination':KEY,'disclosure':{'const':'aggregate_only'}}))}

def weights(v):
 if len({r['bu'] for r in v})!=len(v) or not v:raise ValidationError('Distinct nonempty BU weights required')
 result={r['bu']:decimal(r['weight'],nonnegative=True) for r in v}
 if not any(result.values()):raise ValidationError('Positive allocation denominator required')
 return result

def validate_reference(component,target,case,runtime=False):
 schema_id,schema=SCHEMAS[component]
 if component==STAFF and target.schema_ref=='schema:psl/bu-staff/v2':
  from copy import deepcopy
  from .allocation_coverage import NULLABLE_COVERAGE
  schema=deepcopy(schema);schema['properties']['weight_contract']=NULLABLE_COVERAGE;schema['required'].append('weight_contract');schema_id=target.schema_ref
 v=typed(target,schema_id,schema)
 if 'from_period' in v and v['from_period']>v['to_period']:raise ValidationError('Ordered effective periods required')
 if component in [STAFF,MAPPING]:
  rule=v['rounding']
  if (rule['residual']=='assign_to_configured_bu')!=(rule['residual_bu'] is not None):raise ValidationError('Residual destination must be explicit only for assignment')
  known=unknown=False
  for o in v['oracles']:
   w=weights(o['weights'])
   if o['amount'] is None:
    unknown=True
    if o['expected'] is not None or o['residual'] is not None:raise ValidationError('Unknown is not zero')
   else:
    a,r,_=proportional(decimal(o['amount']),w,rule);known=True
    if o['expected'] is None or set(a)!=set(o['expected']) or any(a[k]!=decimal(o['expected'][k]) for k in a) or o['residual'] is None or r!=decimal(o['residual']):raise ValidationError('Allocation differs from exact supplied oracle')
  if not known or not unknown:raise ValidationError('Known and unknown oracles required')
  if component==STAFF:
   if v['standard_method']=='fixed_weights' or v['standard_weights']:weights(v['standard_weights'])
   if schema_id=='schema:psl/bu-staff/v2':
    from .allocation_coverage import validate_contract
    validate_contract(v,case,staff=True)
   from apps.pmo.services import subject
   e=subject(case,v['pool_contract_evidence_id'],'bu_pool_contract')
   if (schema_id!='schema:psl/bu-staff/v2' or v['standard_method']!='fixed_weights') and case.evidence.filter(kind=e.kind,version__gt=e.version).exists():raise ValidationError('Standard pool contract replaced')
  else:
   if len({r['tag'] for r in v['mappings']})!=len(v['mappings']):raise ValidationError('Duplicate mapping tags')
   for m in v['mappings']:
    if m['treatment']=='direct' and (m['bu'] is None or m['pool'] is not None or m['weights']):raise ValidationError('Direct mapping requires only an exact BU')
    if m['treatment']=='shared':
     if m['pool'] is None or m['bu'] is not None:raise ValidationError('Shared treatment requires only pool/weights')
     weights(m['weights'])
    if m['treatment']=='company' and (m['bu'] is not None or m['pool'] is not None or m['weights']):raise ValidationError('Company-only is not a BU allocation')
 elif component==SOURCE:
  from apps.pmo.services import subject
  for field,kind in [('source_contract_evidence_id','bu_source_contract'),('design_decision_evidence_id','bu_design_decision')]:
   e=subject(case,v[field],kind)
   if case.evidence.filter(kind=kind,version__gt=e.version).exists():raise ValidationError('Source contract or design decision replaced')
  ids=set(v['reader_ids']+[v['owner_id']])
  if get_user_model().objects.filter(pk__in=ids,is_active=True).count()!=len(ids):raise ValidationError('Actual active source owner/readers required')
 elif component==AUTH:
  keys=[]
  for a in v['assignments']:
   if not get_user_model().objects.filter(pk=a['user_id'],is_active=True).exists():raise ValidationError('Actual active Finance human required')
   keys += [(a['user_id'],p) for p in a['purposes']]
  if len(keys)!=len(set(keys)):raise ValidationError('Duplicate decision assignment')
 elif component==DISCLOSE:
  if get_user_model().objects.filter(pk__in=v['recipient_ids'],is_active=True).count()!=len(v['recipient_ids']):raise ValidationError('Actual report recipients required')
