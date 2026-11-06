from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from apps.finance.rules import decimal
from apps.finance.ppe_math import charge
from .document_validators import typed
from .schedule_validators import ID,DEC
SOURCE='F07.source_rules'
CALC='F07.calculation_rules'
AUTH='F07.review_authority'
MONTH={'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'}
PARAMS={k:DEC for k in ['cost','accumulated','residual','life','fraction']}
RULE=obj({'category':KEY,'method':{'enum':['straight_line_explicit_fraction_v1','unimplemented_method']},'method_evidence_id':ID,'cost_basis':{'enum':['opening','closing']},'capitalisation_threshold':{'type':'string'},'below_threshold':{'enum':['hold','reviewed_exception']},'fraction_basis':{'const':'explicit_supplied_fraction'},'remaining_value':{'enum':['hold','cap_at_residual']},'decimal_places':{'type':'integer','minimum':0,'maximum':8},'rounding':{'enum':['half_even','half_up','down']},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':obj(dict(PARAMS,expected_charge=DEC,expected_finding={'anyOf':[KEY,{'type':'null'}]}))}})
SCHEMAS={SOURCE:('schema:psl/ppe-source/v1',obj({'entity':KEY,'provider':KEY,'max_age_seconds':{'type':'integer','minimum':1},'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'unit':{'const':'major_currency'},'from_period':MONTH,'to_period':MONTH,'validation_requirement':{'enum':['finance_reviewed_local','af13_required']},'validation_package_id':{'anyOf':[ID,{'type':'null'}]},'opening_mode':{'enum':['reviewed_external','prior_required']},'external_opening_period':{'anyOf':[MONTH,{'type':'null'}]},'ledger_comparison':{'enum':['required','not_required']},'ledger_line':KEY,'ledger_coefficient':{'enum':['1','-1']},'tolerance':{'type':'string'}})),CALC:('schema:psl/ppe-calculation/v1',obj({'rules':{'type':'array','minItems':1,'maxItems':50,'items':RULE}})),AUTH:('schema:psl/ppe-authority/v1',obj({'independent_reviewer':{'type':'boolean'},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'role':{'const':'Finance'},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['register','basis','schedule']}}})}}))}

def validate_reference(component,target,case,runtime=False):
 from apps.pmo.services import subject
 v=typed(target,*SCHEMAS[component])
 if component==SOURCE:
  if v['from_period']>v['to_period']:raise ValidationError('Ordered effective periods required')
  decimal(v['tolerance'],nonnegative=True)
  if v['validation_package_id']:
   from apps.documents.validation import package_for
   p=package_for(case,v['validation_package_id'])
   if 'F07' not in p.payload['process_ids']:raise ValidationError('Owner validation package must cover F07')
  if v['external_opening_period'] and not v['from_period']<=v['external_opening_period']<=v['to_period']:raise ValidationError('External opening exception period must be inside the source-policy window')
 elif component==CALC:
  if len({r['category'] for r in v['rules']})!=len(v['rules']):raise ValidationError('Distinct asset categories required')
  for r in v['rules']:
   subject(case,r['method_evidence_id'],'ppe_policy');decimal(r['capitalisation_threshold'],nonnegative=True)
   known=unknown=False
   for o in r['oracles']:
    for k in PARAMS:
     if o[k] is not None:decimal(o[k],positive=k=='life',nonnegative=k!='life')
    got=charge(r,**{k:o[k] for k in PARAMS})
    if got['finding']!=o['expected_finding'] or (got['charge'] is None)!=(o['expected_charge'] is None) or (got['charge'] is not None and decimal(got['charge'])!=decimal(o['expected_charge'])):raise ValidationError('PPE calculation differs from supplied exact oracle')
    known|=got['charge'] is not None;unknown|=got['charge'] is None
   if not unknown or (r['method']!='unimplemented_method' and not known):raise ValidationError('Known and held/unknown oracles required for implemented methods')
 else:
  keys=[]
  for r in v['assignments']:
   if not get_user_model().objects.filter(pk=r['user_id'],is_active=True).exists():raise ValidationError('Actual active Finance principal required')
   keys.extend((r['user_id'],p) for p in r['purposes'])
  if len(keys)!=len(set(keys)):raise ValidationError('Duplicate human purpose assignment')
