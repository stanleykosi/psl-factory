"""F07 supplied-register -> human review -> finite schedule -> reviewed read-only note reference."""
import re,json
from datetime import date,timedelta
from decimal import localcontext
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.pmo.services import subject
from apps.policy.services import resolve,active_component,reference_values,decision_authority
from apps.policy.ppe_validators import SOURCE,CALC,AUTH
from apps.policy.schedule_validators import ID,DEC
from apps.documents.contracts import validate,digest
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from adapters.ppe import SuppliedPPEAdapter
from .models import ScheduleWork,ScheduleReview,FinanceRun
from .rules import decimal,number,total
from .ppe_math import charge
from . import analysis
DATE={'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'}
ASSET=obj(dict({'asset_id':KEY,'category':KEY,'capitalisation':{'enum':['capitalise','undecided']},'classification_evidence_id':ID},**{k:DEC for k in ['opening_cost','opening_accumulated','residual','life','fraction']}))
EVENT=obj({'event_id':KEY,'asset_id':KEY,'date':DATE,'kind':{'enum':['addition','disposal','reclassification']},'cost_delta':DEC,'accumulated_delta':DEC,'evidence_id':ID})
READ_ACTIONS = ('case.read', 'finance.read', 'ppe.read')
REGISTER=obj({'entity':KEY,'provider':KEY,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'unit':{'const':'major_currency'},'period_start':DATE,'period_end':DATE,'label_as_of':DATE,'extracted_at':{'type':'string'},'completeness':{'enum':['complete','partial','unknown']},'opening_evidence_id':ID,'assets':{'type':'array','minItems':1,'maxItems':100,'items':ASSET},'events':{'type':'array','maxItems':100,'items':EVENT},'closing_controls':obj({k:DEC for k in ['cost','accumulated','book_value']})})

def readable(actor,c):
 if not actor.is_authenticated or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Active human principal required')
 for key in READ_ACTIONS:require(actor,c,key)
def locked(actor,case_id,action,expected=None):
 c=lock_case(actor,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(actor,c);return c
def exact(c,pk,kind=None):
 q=ScheduleWork.objects.select_related('case','actor','parent').filter(case=c,pk=pk,kind__in=['ppe_register','ppe_schedule'])
 if kind:q=q.filter(kind=kind)
 w=q.first()
 if not w:raise ValidationError('Select this case exact PPE work type/version')
 return w
def config(c,key):return reference_values(active_component(key,c))[0]
def latest(w,purpose):return w.reviews.filter(authority__purpose=purpose).order_by('-pk').first()
def authority(actor,w,purpose):
 readable(actor,w.case);require(actor,w.case,'ppe.review');p=active_component(AUTH,w.case);v=reference_values(p)[0]
 if not any(a['user_id']==actor.pk and purpose in a['purposes'] for a in v['assignments']):raise PermissionDenied('Actual configured Finance purpose authority required')
 if v['independent_reviewer'] and actor.pk==w.actor_id:raise PermissionDenied('Independent Finance reviewer required')
 return dict(decision_authority(actor,w.case,'Finance'),**{AUTH:p.pk,'purpose':purpose})
def approved(w,purpose):
 r=latest(w,purpose)
 if not r or r.verdict!='approve':raise ValidationError('Current exact '+purpose+' human review required')
 if authority(r.actor,w,purpose)!=r.authority or r.snapshot!=w.snapshot:raise ValidationError('PPE human authority/context changed')
 return r
def current(w,depth=0):
 if depth>36:raise ValidationError('Prior-schedule chain budget exceeded')
 readable(w.actor,w.case);require(w.actor,w.case,'ppe.capture' if w.kind=='ppe_register' else 'ppe.prepare')
 if ScheduleWork.objects.filter(case=w.case,kind=w.kind,reference=w.reference,version__gt=w.version).exists():raise ValidationError('PPE source/output superseded; create a reviewed successor')
 if w.kind=='ppe_schedule' and snapshot(w.actor,w.case,w.payload,w.parent,depth)!=w.snapshot:raise ValidationError('PPE register/prior/policy/review/basis/ledger changed; rebuild')
 if w.kind=='ppe_schedule' and calculate(w.case,w.payload,w.snapshot,w.parent)!=w.result:raise ValidationError('PPE current calculation/freshness differs; preserve history and rebuild')
 return w
def store(a,c,kind,ref,payload,pins,result,e,parent=None):
 if not isinstance(ref,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',ref):raise ValidationError('Stable bounded PPE reference required')
 intent={'case':str(c.pk),'actor':a.pk,'kind':kind,'reference':ref,'payload':payload,'snapshot':pins,'evidence':e.pk,'parent':parent.pk if parent else None};key=digest(intent)
 old=ScheduleWork.objects.filter(operation_key=key).first()
 if old:current(old);return old
 previous=ScheduleWork.objects.filter(case=c,kind=kind,reference=ref).order_by('-version').first()
 if previous:
  old_scope=previous.payload if kind=='ppe_register' else exact(c,previous.payload['register_id']).payload
  new_scope=payload if kind=='ppe_register' else exact(c,payload['register_id']).payload
  if any(old_scope[k]!=new_scope[k] for k in ['entity','provider','period_start','period_end']):raise ValidationError('Different period/source population needs a distinct stable reference')
 w=ScheduleWork.objects.create(case=c,kind=kind,reference=ref,version=previous.version+1 if previous else 1,payload=payload,snapshot=pins,result=result,evidence=e,parent=parent,actor=a,operation_key=key,sha256=digest({'intent':intent,'result':result}))
 event(a,c,'finance.ppe_prepared',work=w.pk,kind=kind,status=result['status'],ledger_posted=False);bump(c);return w

@transaction.atomic
def capture(a,case_id,reference,evidence_id,expected=None):
 c=locked(a,case_id,'ppe.capture',expected);e=subject(c,evidence_id,'ppe_register');v=SuppliedPPEAdapter().read(e);validate(REGISTER,v)
 try:start,end,label=[date.fromisoformat(v[k]) for k in ['period_start','period_end','label_as_of']]
 except ValueError:raise ValidationError('Actual calendar dates required')
 if start>end or end>timezone.localdate() or label>timezone.localdate() or timestamp(v['extracted_at'])>timezone.now():raise ValidationError('Ordered actual period/as-of/extraction dates required')
 if len({r['asset_id'] for r in v['assets']})!=len(v['assets']) or len({r['event_id'] for r in v['events']})!=len(v['events']):raise ValidationError('Duplicate asset/event identity')
 subject(c,v['opening_evidence_id'],'ppe_opening')
 for r in v['assets']:
  subject(c,r['classification_evidence_id'],'ppe_classification')
  for k in ['opening_cost','opening_accumulated','residual','life','fraction']:
   if r[k] is not None:decimal(r[k],positive=k=='life',nonnegative=k!='life')
 for r in v['events']:
  try:event_date=date.fromisoformat(r['date'])
  except ValueError:raise ValidationError('Actual event calendar date required')
  if r['asset_id'] not in {x['asset_id'] for x in v['assets']} or not start<=event_date<=end:raise ValidationError('Event must identify a declared asset and current period')
  subject(c,r['evidence_id'],'ppe_event')
  for k in ['cost_delta','accumulated_delta']:
   if r[k] is not None:decimal(r[k])
  if r['kind']=='addition' and ((r['cost_delta'] is not None and decimal(r['cost_delta'])<0) or (r['accumulated_delta'] is not None and decimal(r['accumulated_delta'])!=0)):raise ValidationError('Addition contract uses nonnegative cost and explicit zero accumulated movement')
  if r['kind']=='disposal' and any(r[k] is not None and decimal(r[k])>0 for k in ['cost_delta','accumulated_delta']):raise ValidationError('Disposals use signed nonpositive supplied balances')
 for x in v['closing_controls'].values():
  if x is not None:decimal(x,nonnegative=True)
 return store(a,c,'ppe_register',reference,v,{'source_hash':e.sha256},{'status':'captured','asset_count':len(v['assets']),'event_count':len(v['events']),'date_basis_ambiguous':label!=end},e)

def snapshot(actor,c,payload,parent,depth=0):
 r=exact(c,payload['register_id'],'ppe_register');current(r,depth);readable(actor,c)
 decision=latest(r,'register');basis=latest(r,'basis');pins={'register':[r.pk,r.sha256],'register_review':decision.pk if decision else None,'basis_review':basis.pk if basis else None,'policies':{}}
 for key in [SOURCE,CALC]:
  p=resolve(key,c);pins['policies'][key]={'status':p.status,'id':p.configuration.pk if p.configuration else None}
 for purpose in ['register','basis']:
  try:approved(r,purpose);pins[purpose+'_approved']=True
  except (ValidationError,PermissionDenied):pins[purpose+'_approved']=False
 pins['owner_validation']=None
 if pins['policies'][SOURCE]['status']=='ACTIVE':
  source=config(c,SOURCE)
  if source['validation_package_id']:
   from apps.documents import validation as av
   p=av.package_for(c,source['validation_package_id']);state={'id':p.pk,'sha256':p.sha256,'valid':False,'reviews':[]}
   try:
    av.package_current(p)
    state['reviews']=[av.approved_review(p,k).pk for k in ['meaning','expectations','acceptance']]
    state['valid']='F07' in p.payload['process_ids'] and p.payload['level'] in ['definition','synthetic_implementation']
    ids=set(av.DiscoverySource.objects.filter(case=c,pk__in=p.payload['source_ids']).values_list('evidence_id',flat=True))
    if pins['policies'][CALC]['status']!='ACTIVE' or not {x['method_evidence_id'] for x in config(c,CALC)['rules']}<=ids:state['valid']=False
   except (ValidationError,PermissionDenied):pass
   pins['owner_validation']=state
 if payload['prior_id']:
  prior=exact(c,payload['prior_id'],'ppe_schedule');current(prior,depth+1);pr=approved(prior,'schedule');pins['prior']=[prior.pk,prior.sha256,pr.pk]
 if parent:
  if parent.case_id!=c.pk or parent.kind!='mapping':raise ValidationError('Select this case exact Finance mapping note')
  require(actor,c,'finance.calculate');analysis.ensure_current(parent);pins['ledger']=[parent.pk,parent.operation_key]
 return pins

def calculate(c,payload,pins,parent):
 r=exact(c,payload['register_id'],'ppe_register');v=r.payload;findings=[];rows=[]
 if not pins['register_approved']:findings.append('register_human_review_required')
 if v['label_as_of']!=v['period_end'] and not pins['basis_approved']:findings.append('date_basis_explanation_required')
 source=config(c,SOURCE) if pins['policies'][SOURCE]['status']=='ACTIVE' else None
 calc=config(c,CALC)['rules'] if pins['policies'][CALC]['status']=='ACTIVE' else []
 if not source:findings.append('source_rules_missing')
 if not calc:findings.append('calculation_rules_missing')
 if source:
  if source['validation_requirement']=='af13_required' and not (pins['owner_validation'] and pins['owner_validation']['valid']):findings.append('af13_owner_definition_acceptance_required')
  if any(source[k]!=v[k] for k in ['entity','provider','currency','unit']) or not source['from_period']<=v['period_end'][:7]<=source['to_period']:findings.append('source_scope_mismatch')
  if (timezone.now()-timestamp(v['extracted_at'])).total_seconds()>source['max_age_seconds']:findings.append('source_stale')
  if source['opening_mode']=='prior_required' and not payload['prior_id'] and source['external_opening_period']!=v['period_end'][:7]:findings.append('prior_approved_schedule_required')
 if v['completeness']!='complete':findings.append('register_population_incomplete')
 prior_rows=None
 if payload['prior_id']:
  prior=exact(c,payload['prior_id'],'ppe_schedule');pv=exact(c,prior.payload['register_id']).payload
  if any(pv[k]!=v[k] for k in ['entity','provider','currency','unit']) or date.fromisoformat(pv['period_end'])+timedelta(days=1)!=date.fromisoformat(v['period_start']):findings.append('prior_period_scope_or_continuity_mismatch')
  prior_rows={x['asset_id']:x for x in prior.result['rows']}
  if set(prior_rows)-{x['asset_id'] for x in v['assets']}:findings.append('prior_assets_omitted')
 with localcontext() as ctx:
  ctx.prec=512
  reclasses=[e for e in v['events'] if e['kind']=='reclassification']
  if reclasses and any(total(e[k] for e in reclasses)!=0 for k in ['cost_delta','accumulated_delta']):findings.append('reclassification_population_not_zero')
  for asset in v['assets']:
   codes=[];events=[e for e in v['events'] if e['asset_id']==asset['asset_id']];rules=[x for x in calc if x['category']==asset['category']];rule=rules[0] if len(rules)==1 else None
   delta=total(e['cost_delta'] for e in events) if events else decimal('0');ad=total(e['accumulated_delta'] for e in events) if events else decimal('0')
   cost=None if asset['opening_cost'] is None or delta is None else decimal(asset['opening_cost'])+delta
   accum=None if asset['opening_accumulated'] is None or ad is None else decimal(asset['opening_accumulated'])+ad
   if not rule:codes.append('category_rule_missing')
   if asset['capitalisation']!='capitalise':codes.append('capitalisation_undecided')
   additions=[e for e in events if e['kind']=='addition']
   if rule and rule['below_threshold']=='hold' and any(e['cost_delta'] is not None and decimal(e['cost_delta'])<decimal(rule['capitalisation_threshold']) for e in additions):codes.append('capitalisation_below_threshold')
   if prior_rows is not None:
    old=prior_rows.get(asset['asset_id'])
    if old:
     if any(asset[k] is None or old[f] is None or decimal(asset[k])!=decimal(old[f]) for k,f in [('opening_cost','closing_cost'),('opening_accumulated','closing_accumulated')]):codes.append('opening_does_not_match_prior')
    elif any(asset[k] is None or decimal(asset[k])!=0 for k in ['opening_cost','opening_accumulated']) or not additions:codes.append('new_asset_opening_or_addition_evidence_missing')
   if cost is None or accum is None:codes.append('movement_or_opening_unknown')
   elif cost<0 or accum<0 or accum>cost:codes.append('closing_asset_basis_invalid');cost=None;accum=None
   amount=None
   if rule and not codes:
    got=charge(rule,asset['opening_cost'] if rule['cost_basis']=='opening' else number(cost),number(accum),asset['residual'],asset['life'],asset['fraction']);amount=got['charge']
    if got['finding']:codes.append(got['finding'])
   if amount is not None and cost-accum-decimal(amount)<0:codes.append('charge_exceeds_closing_book');amount=None
   closing=None if amount is None or accum is None else accum+decimal(amount);book=None if closing is None or cost is None else cost-closing
   for value in [cost,closing,book]:
    if value is not None:decimal(number(value),nonnegative=True)
   rows.append({'asset_id':asset['asset_id'],'category':asset['category'],'closing_cost':number(cost),'charge':amount,'closing_accumulated':number(closing),'book_value':number(book),'event_refs':[e['event_id'] for e in events],'findings':codes})
  totals={k:number(total(row[f] for row in rows)) for k,f in [('cost','closing_cost'),('accumulated','closing_accumulated'),('book_value','book_value'),('charge','charge')]}
  for key in ['cost','accumulated','book_value']:
   actual,control=totals[key],v['closing_controls'][key]
   if actual is None or control is None or not source or abs(decimal(actual)-decimal(control))>decimal(source['tolerance']):findings.append('closing_control_unreconciled:'+key)
  if parent:
   data=parent.result
   if any(data[k]!=v[k] for k in ['entity','currency','unit']) or data['period']!=v['period_end'][:7] or analysis.certification_findings(parent):findings.append('ledger_scope_or_review_mismatch')
   values=[x['amount'] for x in data['rows'] if source and x['report_line']==source['ledger_line']];value=total(values)
   if not source or value is None or totals['book_value'] is None or abs(value*decimal(source['ledger_coefficient'])-decimal(totals['book_value']))>decimal(source['tolerance']):findings.append('ledger_note_difference')
  elif source and source['ledger_comparison']=='required':findings.append('ledger_note_required')
 if any(x['findings'] for x in rows):findings.append('asset_rows_held')
 return {'status':'held' if findings else 'ready','findings':findings,'rows':rows,'totals':totals,'scope':{k:v[k] for k in ['entity','currency','unit','period_start','period_end','label_as_of']},'coverage':'selected_supplied_population','native_source_verified':False,'ledger_posted':False}

@transaction.atomic
def prepare(a,case_id,reference,register_id,prior_id=None,ledger_id=None,expected=None):
 c=locked(a,case_id,'ppe.prepare',expected);r=exact(c,register_id,'ppe_register');payload={'register_id':r.pk,'prior_id':prior_id};parent=FinanceRun.objects.filter(case=c,pk=ledger_id).first() if ledger_id else None
 if ledger_id and not parent:raise ValidationError('Ledger note outside case')
 pins=snapshot(a,c,payload,parent);result=calculate(c,payload,pins,parent)
 return store(a,c,'ppe_schedule',reference,payload,pins,result,r.evidence,parent)

@transaction.atomic
def review(a,case_id,work_id,purpose,verdict,evidence_id,note,expected=None):
 c=locked(a,case_id,'ppe.review',expected);w=exact(c,work_id);analysis.note(note)
 if purpose not in (['register','basis'] if w.kind=='ppe_register' else ['schedule']) or verdict not in ['approve','return','reject','revoke']:raise ValidationError('Exact typed PPE purpose/verdict required')
 auth=authority(a,w,purpose);e=subject(c,evidence_id,'ppe_basis_explanation' if purpose=='basis' else 'finance_review')
 if verdict=='approve':
  current(w)
  if purpose=='schedule' and (w.result['status']!='ready' or calculate(c,w.payload,w.snapshot,w.parent)!=w.result):raise ValidationError('Current reconciled PPE schedule required')
 if verdict=='revoke' and (not latest(w,purpose) or latest(w,purpose).verdict!='approve'):raise ValidationError('A prior approval must exist to revoke')
 result=ScheduleReview.objects.create(work=w,verdict=verdict,authority=auth,snapshot=w.snapshot,evidence=e,note=note,actor=a)
 event(a,c,'finance.ppe_review',work=w.pk,purpose=purpose,review=result.pk,verdict=verdict);bump(c);return result
