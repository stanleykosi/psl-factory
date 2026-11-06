"""Restricted F21 rules and F44 reference attribution; never a second ledger."""
import hashlib
from datetime import timedelta
from django.db import transaction,connection
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.contracts import validate,digest
from apps.documents.validation import finite
from apps.policy.services import resolve,active_component,reference_values,decision_authority
from apps.policy.bu_validators import STAFF,SOURCE,MAPPING,AUTH,DISCLOSE,WEIGHTS,weights
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from adapters.bu import SuppliedBUEventAdapter,EventExportError
from . import payroll as pr,bu_math as maths
from .payroll_models import PayrollRun
from .bu_models import BUWork,BUReview,BUReport,BUReceipt,BUEventClaim
from .allocation import CATALOG
from .mapping import effective
RULE=obj({'employee_id':KEY,'component':KEY,'entity':KEY,'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},'standard_pool_ref':KEY,'weights':WEIGHTS,'rationale_evidence_id':{'type':'integer','minimum':1}})
PAIR={'type':'array','minItems':2,'maxItems':2,'items':KEY}

def locked(actor,case_id,action,expected=None):
 c=lock_case(actor,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
 for k in [action,'case.read','bu.read']:require(actor,c,k)
 return c

def exact(c,pk):
 w=BUWork.objects.defer('payload').filter(case=c,pk=pk).first()
 if not w:raise ValidationError('Select an exact scoped BU work version')
 return w

def config(key,c,scope=None):
 p=active_component(key,c);v=reference_values(p)[0]
 if scope and 'entity' in v and (v['entity']!=scope['entity'] or not v['from_period']<=scope['period']<=v['to_period']):raise ValidationError('Rule entity/effective period does not match')
 return p,v

def catalog(c,scope):
 p=active_component(CATALOG,c);rows=effective(reference_values(p),scope['entity'],scope['period']);bus=[r['key'] for r in rows]
 if not bus:raise ValidationError('Effective BU catalogue required')
 return p,bus

def private_access(actor,w):
 for k in ['case.read','bu.read','bu.private.read']:require(actor,w.case,k)
 if w.payroll_id:
  pr.check_run_access(actor,pr.exact(w.case,PayrollRun,w.payroll_id))
 else:
  _,v=config(SOURCE,w.case,w.metadata['scope'])
  if actor.pk not in v['reader_ids']:raise PermissionDenied('Not an exact event-source reader')
 return w


def exception_inventory(c,payroll_id,components,at=None):
 # PostgreSQL selects only a component subkey; no employee/ratio payload is read.
 q=BUWork.objects.defer('payload').filter(case=c,payroll_id=payroll_id,kind='rule',metadata__accepted=True,payload__component__in=components)
 if at:q=q.filter(created_at__lte=at)
 rows=list(q.order_by('reference','-version').distinct('reference')[:101])
 if len(rows)>100:raise ValidationError('Restricted exception inventory exceeds the reviewed work budget')
 result=[]
 for r in rows:
  decisions=r.reviews.filter(purpose='rule')
  if at:decisions=decisions.filter(created_at__lte=at)
  last=decisions.order_by('-pk').values('id','verdict').first()
  result.append({'rule_id':r.pk,'review_id':last['id'] if last else None,'verdict':last['verdict'] if last else 'pending'})
 return sorted(result,key=lambda r:r['rule_id'])

def current(w,check_comparison=True):
 for key,pk in w.metadata['policy_ids'].items():
  if active_component(key,w.case).pk!=pk:raise ValidationError('BU source/rule context changed')
 if w.metadata.get('retain_until') and timezone.now()>=timestamp(w.metadata['retain_until']):raise ValidationError('BU retained access expired')
 if BUWork.objects.filter(case=w.case,kind=w.kind,reference=w.reference,version__gt=w.version,metadata__accepted=True).exists():raise ValidationError('BU work version replaced')
 require(w.actor,w.case,'bu.capture' if w.kind=='source' else 'bu.'+w.kind)
 if w.kind!='source':private_access(w.actor,w)
 if w.payroll_id:
  p=pr.exact(w.case,PayrollRun,w.payroll_id);pr.run_current(p)
  if p.sha256!=w.metadata['payroll_sha256']:raise ValidationError('Payroll source differs')
  for pk in w.metadata.get('rule_ids',[]):current(exact(w.case,pk),check_comparison=check_comparison)
  if w.kind=='staff':
   _,financial=config(STAFF,w.case,w.metadata['scope']);live=exception_inventory(w.case,w.payroll_id,financial['components'])
   # Older immutable work reconstructs its original ID/review inventory by creation time.
   expected=w.metadata.get('exception_inventory')
   if expected is None:expected=exception_inventory(w.case,w.payroll_id,financial['components'],w.created_at)
   if live!=expected:raise ValidationError('Private exception inventory or decision changed; rebuild and review')
   if any(r['verdict']!='revoke' and r['rule_id'] not in w.metadata.get('rule_ids',[]) for r in live):raise ValidationError('Known exception omitted from staff treatment')
 if w.parent_id:current(exact(w.case,w.parent_id),check_comparison=check_comparison)
 if check_comparison and w.metadata.get('comparison'):
  finance_comparison(w.actor,w.case,w.metadata['scope'],w.metadata['comparison'],w.metadata.get('comparison_hash'))
 if w.kind=='source':
  _,v=config(SOURCE,w.case,w.metadata['scope'])
  if not w.metadata['accepted'] or (timezone.now()-timestamp(w.metadata['extracted_at'])).total_seconds()>v['max_age_seconds']:raise ValidationError('Source rejected/stale')
  if w.actor_id!=v['owner_id'] or decision_authority(w.actor,w.case,'Finance')!=w.metadata['owner_authority']:raise ValidationError('Source-owner authority changed')
 return w

def old(c,key,kind,actor,intent):
 validate(KEY,key);w=BUWork.objects.defer('payload').filter(case=c,operation_key=key).first()
 if w and (w.kind!=kind or w.actor_id!=actor.pk or w.metadata['intent']!=intent):raise ValidationError('BU retry intent changed')
 return w

def save(actor,c,kind,reference,key,intent,payload,codes,pins,scope,retention,parent=None,payroll=None,extra=None):
 validate(KEY,reference);finite(payload)
 version=(BUWork.objects.filter(case=c,reference=reference,kind=kind).order_by('-version').values_list('version',flat=True).first() or 0)+1
 meta={'scope':scope,'status':'complete' if not codes else 'held','codes':sorted(set(codes)),'accepted':True,'policy_ids':pins,'intent':intent,'retain_until':retention.isoformat(),'payroll_sha256':payroll.sha256 if payroll else None,**(extra or {})}
 w=BUWork.objects.create(case=c,reference=reference,kind=kind,version=version,operation_key=key,parent=parent,payroll=payroll,payload=payload,metadata=meta,sha256=digest({'payload':payload,'metadata':meta}),actor=actor)
 event(actor,c,'bu.'+kind,work=w.pk,status=meta['status'],codes=meta['codes']);bump(c);return w

def authority(actor,w,purpose):
 p,v=config(AUTH,w.case)
 if not any(a['user_id']==actor.pk and purpose in a['purposes'] for a in v['assignments']):raise PermissionDenied('No actual configured Finance authority for this decision')
 if purpose!='publish' and v['independent_reviewer'] and w.actor_id==actor.pk:raise PermissionDenied('Independent actual reviewer required')
 return {AUTH:p.pk,**decision_authority(actor,w.case,'Finance')}

@transaction.atomic
def rule(actor,case_id,payroll_id,reference,key,payload,expected):
 c=locked(actor,case_id,'bu.rule',expected);p=pr.exact(c,PayrollRun,payroll_id)
 if p.kind!='match':raise ValidationError('F21 requires exact F17 matched payroll')
 pr.check_run_access(actor,p);require(actor,c,'bu.private.read');validate(RULE,payload);weights(payload['weights']);subject(c,payload['rationale_evidence_id'],'bu_review')
 if not any(row['employee_id']==payload['employee_id'] and row['component']==payload['component'] for row in p.result['rows']):raise ValidationError('Exact exception subject/component must exist in the authorised payroll source')
 scope={k:p.request.metadata[k] for k in ['entity','period','currency']}
 if any(payload[k]!=scope[k] for k in ['entity','period']):raise ValidationError('Exact subject/component period required; no previous-month fallback')
 intent={'payroll':p.pk,'reference':reference,'payload_sha256':digest(payload)};existing=old(c,key,'rule',actor,intent)
 if existing:return existing
 policy=resolve(STAFF,c);pins={STAFF:policy.configuration.pk} if policy.status=='ACTIVE' else {};codes=[] if pins else ['staff_policy_missing']
 if pins:
  _,v=config(STAFF,c,scope)
  if payload['standard_pool_ref']!=v['standard_pool_ref']:raise ValidationError('Exact standard-pool exclusion link required')
 return save(actor,c,'rule',reference,key,intent,payload,codes,pins,scope,p.retain_until,payroll=p)

def parents_reviewed(w):
 if w.payroll_id:pr.current_review(pr.exact(w.case,PayrollRun,w.payroll_id))
 for pk in w.metadata.get('rule_ids',[]):review_current(exact(w.case,pk))
 if w.parent_id:review_current(exact(w.case,w.parent_id))

def review_current(w,purpose=None):
 purpose=purpose or w.kind;r=w.reviews.filter(purpose=purpose).order_by('-pk').first()
 if not r or r.verdict!='approve' or r.subject_sha256!=w.sha256:raise ValidationError('Exact current BU approval required')
 current(w);private_access(r.actor,w);require(r.actor,w.case,'bu.review')
 if authority(r.actor,w,purpose)!=r.authority:raise ValidationError('Review authority changed')
 parents_reviewed(w);return r

@transaction.atomic
def staff(actor,case_id,payroll_id,reference,key,declared,rule_ids,expected):
 c=locked(actor,case_id,'bu.staff',expected);p=pr.exact(c,PayrollRun,payroll_id)
 if p.kind!='match':raise ValidationError('Exact HR-matched payroll required')
 pr.check_run_access(actor,p);require(actor,c,'bu.private.read');validate({'type':'array','maxItems':500,'items':PAIR},declared)
 if not isinstance(rule_ids,list) or any(type(i) is not int for i in rule_ids) or len(rule_ids)>100 or len(set(rule_ids))!=len(rule_ids):raise ValidationError('Distinct rule references required')
 intent={'payroll':p.pk,'reference':reference,'declared_sha256':digest(declared),'rule_ids':sorted(rule_ids)};existing=old(c,key,'staff',actor,intent)
 if existing:return existing
 scope={k:p.request.metadata[k] for k in ['entity','period','currency']};policy,v=config(STAFF,c,scope);cat,bus=catalog(c,scope);rules=[];codes=[];inventory=exception_inventory(c,p.pk,v['components'])
 if any(r['verdict']!='revoke' and r['rule_id'] not in rule_ids for r in inventory):codes.append('known_exception_omitted')
 for pk in rule_ids:
  r=exact(c,pk)
  if r.kind!='rule' or r.payroll_id!=p.pk:raise ValidationError('Exact payroll/version-bound private rules required')
  private_access(actor,r);current(r)
  try:review_current(r)
  except ValidationError:codes.append('exception_rule_unapproved')
  rules.append(r.payload)
 result,findings=maths.staff(p.result['rows'],declared,rules,v,bus);codes+=findings
 if p.metadata['status']!='complete':codes.append('parent_payroll_held')
 historical=BUReport.objects.filter(work__case=c,work__kind='staff',work__metadata__scope=scope).exists()
 if historical and v['historical_treatment']!='reviewed_replacement':codes.append('historical_rework_policy_hold')
 return save(actor,c,'staff',reference,key,intent,result,codes,{STAFF:policy.pk,CATALOG:cat.pk},scope,p.retain_until,payroll=p,extra={'rule_ids':rule_ids,'historical':historical,'exception_inventory':inventory})

@transaction.atomic
def capture(actor,case_id,reference,key,scope,body,expected):
 c=locked(actor,case_id,'bu.capture',expected);validate(obj({'entity':KEY,'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},'currency':KEY}),scope)
 policy,v=config(SOURCE,c,scope)
 if actor.pk!=v['owner_id']:raise PermissionDenied('Actual configured event-source owner required')
 owner=decision_authority(actor,c,'Finance')
 if not isinstance(body,str) or len(body.encode('utf-8'))>256000:raise ValidationError('Bounded supplied export required')
 intent={'reference':reference,'scope':scope,'body_sha256':hashlib.sha256(body.encode('utf-8')).hexdigest()};existing=old(c,key,'source',actor,intent)
 if existing:return existing
 try:
  payload,codes=SuppliedBUEventAdapter().read(body,scope,v)
  with transaction.atomic():
   for row in sorted(payload['rows'],key=lambda r:r['event_id']):
    identity={'tenant':c.tenant,'source':v['source'],'event_id':row['event_id']}
    with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(%s)',[int(digest(identity)[:15],16)])
    claim,_=BUEventClaim.objects.get_or_create(**identity,defaults={'case':c,'reference':reference})
    if claim.case_id!=c.pk or claim.reference!=reference:raise EventExportError('event_identity_owned_elsewhere')
  accepted=True
 except EventExportError as exc:payload={};codes=[exc.code];accepted=False
 return save(actor,c,'source',reference,key,intent,payload,codes,{SOURCE:policy.pk},scope,timezone.now()+timedelta(seconds=v['retention_seconds']),extra={'accepted':accepted,'owner_authority':owner,'extracted_at':payload.get('extracted_at'),'source_sha256':intent['body_sha256'],'native_authenticity_verified':False})


def finance_comparison(actor,c,scope,ref,expected_hash=None):
 from .analysis_models import FinanceRun
 from .analysis import ensure_current
 validate(obj({'run_id':{'type':'integer','minimum':1},'metric':{'type':'string','enum':['revenue','direct_cost','staff_cost','opex','other']}}),ref)
 require(actor,c,'finance.calculate');r=FinanceRun.objects.filter(case=c,pk=ref['run_id'],kind='allocation').first()
 if not r:raise ValidationError('Exact same-case Finance allocation comparison required')
 ensure_current(r)
 if any(r.result[k]!=scope[k] for k in ['entity','period','currency']):raise ValidationError('Finance company comparison scope differs')
 values=r.result.get('conservation',{}).get(ref['metric'])
 if r.result['status']!='complete' or not values or not values['conserved']:raise ValidationError('Current conserved Finance metric required')
 h=digest({'snapshot':r.snapshot,'result':r.result})
 if expected_hash and expected_hash!=h:raise ValidationError('Finance comparison changed')
 return values['source'],h

@transaction.atomic
def attribute(actor,case_id,source_id,reference,key,expected,comparison=None):
 c=locked(actor,case_id,'bu.event',expected);s=exact(c,source_id)
 if s.kind!='source':raise ValidationError('Exact supplied event source required')
 private_access(actor,s);current(s);intent={'parent':s.pk,'reference':reference,'comparison':comparison};existing=old(c,key,'event',actor,intent)
 if existing:return existing
 scope=s.metadata['scope'];policy,v=config(MAPPING,c,scope);cat,bus=catalog(c,scope);source_policy,source_rules=config(SOURCE,c,scope)
 result,codes=maths.events(s.payload['rows'],v,bus);codes+=s.metadata['codes'];comparison_hash=None
 if comparison:
  total,comparison_hash=finance_comparison(actor,c,scope,comparison)
  result['finance_company_comparison']={'reference':comparison,'company_total':total,'matches':result['source_total'] is not None and total is not None and pr.decimal(result['source_total'])==pr.decimal(total)}
  if not result['finance_company_comparison']['matches']:codes.append('finance_company_comparison_mismatch')
 elif source_rules['company_comparison']=='finance_allocation_required':codes.append('finance_company_comparison_missing')
 closed=scope['period'] in source_rules['closed_periods'];historical=closed or BUReport.objects.filter(work__case=c,work__kind='event',work__metadata__scope=scope).exists()
 if closed and source_rules['closed_period_treatment']=='hold':codes.append('closed_period_reference_hold')
 if historical and v['historical_treatment']!='reviewed_replacement':codes.append('historical_rework_policy_hold')
 return save(actor,c,'event',reference,key,intent,result,codes,{SOURCE:source_policy.pk,MAPPING:policy.pk,CATALOG:cat.pk},scope,timestamp(s.metadata['retain_until']),parent=s,extra={'historical':historical,'source_write':False,'comparison':comparison,'comparison_hash':comparison_hash})

@transaction.atomic
def review(actor,case_id,work_id,purpose,verdict,key,evidence_id,expected):
 c=locked(actor,case_id,'bu.review',expected);w=exact(c,work_id);private_access(actor,w);validate(KEY,key)
 if purpose not in [w.kind,'historical'] or verdict not in ['approve','return','revoke']:raise ValidationError('Select exact work purpose and decision')
 e=subject(c,evidence_id,'bu_review');a=authority(actor,w,purpose);r=w.reviews.filter(operation_key=key).first()
 if r:
  if r.actor_id!=actor.pk or r.purpose!=purpose or r.verdict!=verdict or r.evidence_id!=e.pk:raise ValidationError('Review retry intent changed')
  return r
 if verdict!='revoke':current(w)
 if verdict=='approve':
  if w.metadata['status']!='complete':raise ValidationError('Resolve BU work holds before approval')
  parents_reviewed(w)
  if w.kind=='rule':
   _,v=config(STAFF,c,w.metadata['scope']);_,bus=catalog(c,w.metadata['scope'])
   if not set(weights(w.payload['weights']))<=set(bus):raise ValidationError('Exception names unknown BU')
   p=pr.exact(c,PayrollRun,w.payroll_id)
   if w.payload['component'] not in v['components'] or not any(row['employee_id']==w.payload['employee_id'] and row['component']==w.payload['component'] for row in p.result['rows']):raise ValidationError('Exception subject/component absent from exact payroll population')
 r=BUReview.objects.create(work=w,purpose=purpose,verdict=verdict,operation_key=key,authority=a,subject_sha256=w.sha256,evidence=e,actor=actor)
 event(actor,c,'bu.review',work=w.pk,review=r.pk,verdict=verdict);bump(c);return r

@transaction.atomic
def read_private(actor,case_id,work_id):
 c=locked(actor,case_id,'bu.private.read');w=exact(c,work_id);private_access(actor,w);current(w);return w.payload

@transaction.atomic
def publish(actor,case_id,work_id,key,expected):
 c=locked(actor,case_id,'bu.publish',expected);w=exact(c,work_id);validate(KEY,key)
 if w.kind not in ['staff','event']:raise ValidationError('Only reconciled staff/event aggregates can be published')
 existing=BUReport.objects.defer('payload').filter(work=w,operation_key=key).first()
 if existing:
  if existing.actor_id!=actor.pk:raise ValidationError('Publication retry actor changed')
  return existing
 private_access(actor,w);current(w);r=review_current(w);a=authority(actor,w,'publish');policy,v=config(DISCLOSE,c)
 if w.metadata.get('historical'):review_current(w,'historical')
 if w.metadata['status']!='complete' or not w.payload['conserved']:raise ValidationError('Reconciled source population required')
 if w.kind=='staff' and any(n<v['minimum_staff'] for n in w.payload['staff_counts'].values()):raise ValidationError('Small-group protection holds whole report publication')
 payload={**w.metadata['scope'],'unit':'major_currency','by_bu':w.payload['by_bu'],'company_source_total':w.payload['source_total'],'allocated_total':w.payload['allocated_total'],'company_only':w.payload.get('company_only','0'),'residual':w.payload['residual'],'conserved':True,'source_work':w.pk,'coverage':'selected_supplied_population_only','native_authenticity_verified':False,'destination':v['destination'],'ledger_posted':False,'source_written':False,'disclosure':'aggregate_only'}
 version=(BUReport.objects.filter(work=w).order_by('-version').values_list('version',flat=True).first() or 0)+1
 report=BUReport.objects.create(work=w,review=r,version=version,operation_key=key,payload=payload,policy_ids={**a,DISCLOSE:policy.pk},actor=actor)
 event(actor,c,'bu.published',report=report.pk,work=w.pk);bump(c);return report

@transaction.atomic
def read_report(actor,report_id):
 r=BUReport.objects.defer('payload').select_related('work__case').get(pk=report_id);c=locked(actor,r.work.case_id,'bu.report.read');policy,v=config(DISCLOSE,c)
 if actor.pk not in v['recipient_ids']:raise PermissionDenied('Not a configured aggregate recipient')
 w=exact(c,r.work_id);current(w);require(r.actor,c,'bu.publish');private_access(r.actor,w)
 if review_current(w).pk!=r.review_id or authority(r.actor,w,'publish')!={k:pk for k,pk in r.policy_ids.items() if k!=DISCLOSE} or policy.pk!=r.policy_ids[DISCLOSE]:raise ValidationError('Report review/authority/disclosure changed')
 if w.metadata.get('historical'):review_current(w,'historical')
 if BUReport.objects.filter(work__case=c,work__kind=w.kind,work__metadata__scope=w.metadata['scope'],pk__gt=r.pk).exists():raise ValidationError('Aggregate report replaced by a reviewed successor')
 return r.payload

@transaction.atomic
def receive(actor,case_id,report_id,expected):
 c=locked(actor,case_id,'bu.receive',expected);r=BUReport.objects.defer('payload').filter(pk=report_id,work__case=c).first()
 if not r:raise ValidationError('Exact scoped report required')
 read_report(actor,r.pk);receipt,created=BUReceipt.objects.get_or_create(report=r,actor=actor)
 if created:event(actor,c,'bu.receipt',receipt=receipt.pk,report=r.pk);bump(c)
 return receipt
