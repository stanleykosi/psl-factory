"""Restricted F16/F17/F18 working sheets, source-bound reviews and aggregate-only handoff."""
import hashlib
from datetime import timedelta
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.contracts import validate,digest
from apps.documents.validation import finite
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.payroll_validators import ACCESS,MERGE,MATCH,REPORT,AUTH
from apps.policy.hrfinance_validators import REQUIRED
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from adapters.payroll import SuppliedPayrollAdapter,PayrollExportError,sum_values
from .rules import decimal
from . import hrfinance as hr,payroll_math as maths
from .payroll_models import PayrollRequest,PayrollInput,PayrollRun,PayrollReview,PayrollPublication,PayrollReportReceipt,PayrollHRFollowup
from .hrfinance_models import HRReadSnapshot
REQUEST=obj({'entity':KEY,'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},'currency':KEY,'providers':{'type':'array','minItems':2,'maxItems':2,'uniqueItems':True,'items':KEY},'purpose':{'const':'bu_staff_cost'}})
STAGE_POLICY={'combine':MERGE,'match':MATCH,'aggregate':REPORT}

def locked(actor,case_id,action,expected=None):
 c=lock_case(actor,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
 for k in [action,'case.read','payroll.read']:require(actor,c,k)
 return c

def exact(case,model,pk):
 path='case' if model==PayrollRequest else 'request__case'
 q=model.objects.defer('payload') if model in [PayrollInput,PayrollPublication] else model.objects.defer('result') if model==PayrollRun else model.objects
 r=q.filter(pk=pk,**{path:case}).first()
 if not r:raise ValidationError('Select an exact scoped payroll record')
 return r

def latest_request(q):
 if PayrollRequest.objects.filter(case=q.case,reference=q.reference,version__gt=q.version).exists():raise ValidationError('Payroll request superseded')

def access(q,actor=None,private=False):
 latest_request(q);config=active_component(ACCESS,q.case);v=reference_values(config)[0]
 if v['entity']!=q.metadata['entity'] or v['currency']!=q.metadata['currency'] or not v['from_period']<=q.metadata['period']<=v['to_period'] or set(q.metadata['providers'])!={r['provider'] for r in v['providers']}:raise ValidationError('Payroll request exceeds current source/entity/period/currency contract')
 if private:
  for k in ['case.read','payroll.read','payroll.private.read']:require(actor,q.case,k)
  if actor.pk not in v['reader_ids']:raise PermissionDenied('Not a nominated restricted payroll reader')
 return config,v

def input_current(i):
 config,v=access(i.request)
 if config.pk!=i.metadata['access_policy_id']:raise ValidationError('Payroll access contract changed; obtain current source version')
 if not i.metadata['accepted']:raise ValidationError('Rejected input has no readable source rows')
 if timezone.now()>=i.retain_until or (timezone.now()-timestamp(i.metadata['extracted_at'])).total_seconds()>v['max_age_seconds']:raise ValidationError('Payroll input freshness/retained access expired')
 if i.request.inputs.filter(provider=i.provider,metadata__accepted=True,version__gt=i.version).exists():raise ValidationError('Payroll input replaced; rebuild instead of restating history')
 owner=next(r for r in v['providers'] if r['provider']==i.provider)
 require(i.actor,i.request.case,'payroll.capture')
 if owner['owner_id']!=i.actor_id or decision_authority(i.actor,i.request.case,owner['owner_role'])!=i.metadata['owner_authority']:raise ValidationError('Payroll source-owner authority changed')
 return i

def run_current(r):
 access(r.request)
 for key,pk in r.metadata['policy_ids'].items():
  if active_component(key,r.request.case).pk!=pk:raise ValidationError('Payroll working rule changed')
 if STAGE_POLICY[r.kind] not in r.metadata['policy_ids'] and resolve(STAGE_POLICY[r.kind],r.request.case).status=='ACTIVE':raise ValidationError('A working rule is now configured; prepare a new version')
 if timezone.now()>=r.retain_until:raise ValidationError('Restricted working copy retained access expired')
 require(r.actor,r.request.case,'payroll.'+r.kind);access(r.request,r.actor,True)
 if r.parent_id:run_current(exact(r.request.case,PayrollRun,r.parent_id))
 for pk in r.metadata.get('input_ids',[]):input_current(exact(r.request.case,PayrollInput,pk))
 if r.hr_snapshot_id:
  h=hr.exact(r.request.case,HRReadSnapshot,r.hr_snapshot_id)
  hr.snapshot_access(r.actor,h)
  if h.sha256!=r.metadata['hr_sha256']:raise ValidationError('HR source changed')
 return r

@transaction.atomic
def private_input(actor,case_id,pk):
 c=locked(actor,case_id,'payroll.private.read');i=exact(c,PayrollInput,pk);access(i.request,actor,True);input_current(i);return i.payload

def run_access(actor,r):
 # Pure authority/currentness validation; payload readers retain native locks.
 for action in ['case.read','payroll.read','payroll.private.read']:require(actor,r.request.case,action)
 access(r.request,actor,True);run_current(r)
 cursor=r
 while cursor:
  if cursor.hr_snapshot_id:hr.snapshot_access(actor,hr.exact(r.request.case,HRReadSnapshot,cursor.hr_snapshot_id))
  cursor=exact(r.request.case,PayrollRun,cursor.parent_id) if cursor.parent_id else None
 return r

@transaction.atomic
def check_run_access(actor,r):
 locked(actor,r.request.case_id,'payroll.private.read')
 return run_access(actor,r)

@transaction.atomic
def private_run(actor,case_id,pk):
 c=locked(actor,case_id,'payroll.private.read');r=exact(c,PayrollRun,pk);check_run_access(actor,r);return r.result

@transaction.atomic
def request(actor,case_id,reference,metadata,evidence_id,expected):
 c=locked(actor,case_id,'payroll.request',expected);validate(KEY,reference);finite(metadata);validate(REQUEST,metadata);e=subject(c,evidence_id,'payroll_need')
 v=(PayrollRequest.objects.filter(case=c,reference=reference).order_by('-version').values_list('version',flat=True).first() or 0)+1
 r=PayrollRequest.objects.create(case=c,reference=reference,version=v,metadata=metadata,evidence=e,actor=actor)
 event(actor,c,'payroll.request',request=r.pk,version=v);bump(c);return r

@transaction.atomic
def capture(actor,case_id,request_id,provider,operation_key,body,expected):
 c=locked(actor,case_id,'payroll.capture',expected);q=exact(c,PayrollRequest,request_id);validate(KEY,operation_key)
 config,v=access(q);owner=next((r for r in v['providers'] if r['provider']==provider),None)
 if not owner or owner['owner_id']!=actor.pk:raise PermissionDenied('This provider requires its actual nominated owner')
 authority=decision_authority(actor,c,owner['owner_role'])
 if not isinstance(body,str) or len(body.encode('utf-8'))>256000:raise ValidationError('Bounded supplied payroll export required')
 source_hash=hashlib.sha256(body.encode('utf-8')).hexdigest();old=q.inputs.defer('payload').filter(operation_key=operation_key).first()
 if old:
  if old.actor_id!=actor.pk or old.provider!=provider or old.source_sha256!=source_hash:raise ValidationError('Input retry key used for changed intent')
  return old
 try:
  p=SuppliedPayrollAdapter().read(body,q,provider,v);accepted=True;codes=[]
  calculated=sum_values(r['amount'] for r in p['rows'])
  if p['control_total'] is None or calculated is None or decimal(p['control_total'])!=decimal(calculated):codes.append('source_control_unresolved')
  if p['completeness']!='complete':codes.append('source_inventory_incomplete')
 except PayrollExportError as exc:p={};accepted=False;codes=[exc.code]
 version=(q.inputs.filter(provider=provider).order_by('-version').values_list('version',flat=True).first() or 0)+1
 meta={'accepted':accepted,'status':'complete' if accepted and not codes else 'held','codes':codes,'access_policy_id':config.pk,'owner_authority':authority,'extracted_at':p.get('extracted_at'),'source_version':p.get('source_version'),'native_authenticity_verified':False}
 i=PayrollInput.objects.create(request=q,provider=provider,version=version,operation_key=operation_key,source_sha256=source_hash,sha256=digest({'payload':p,'metadata':meta,'source_sha256':source_hash}),metadata=meta,payload=p,retain_until=timezone.now()+timedelta(seconds=v['retention_seconds']),actor=actor)
 event(actor,c,'payroll.input',input=i.pk,accepted=accepted,codes=codes);bump(c);return i

def run_old(q,key,actor,kind,intent):
 old=q.runs.defer('result').filter(operation_key=key).first()
 if old and (old.actor_id!=actor.pk or old.kind!=kind or old.metadata['intent']!=intent):raise ValidationError('Working retry key used for changed intent')
 return old

def store(actor,q,kind,key,intent,result,codes,pins,inputs,retention,parent=None,hr_source=None):
 meta={'status':'complete' if not codes else 'held','codes':sorted(set(codes)),'intent':intent,'policy_ids':pins,'input_ids':inputs,'hr_sha256':hr_source.sha256 if hr_source else None,'source_write':False,'accounting_posted':False}
 r=PayrollRun.objects.create(request=q,parent=parent,hr_snapshot=hr_source,kind=kind,operation_key=key,sha256=digest({'result':result,'metadata':meta,'parent':parent.sha256 if parent else None}),metadata=meta,result=result,retain_until=retention,actor=actor)
 event(actor,q.case,'payroll.'+kind,run=r.pk,status=meta['status'],codes=meta['codes']);bump(q.case);return r

@transaction.atomic
def combine(actor,case_id,request_id,input_ids,operation_key,expected):
 c=locked(actor,case_id,'payroll.combine',expected);q=exact(c,PayrollRequest,request_id);config,v=access(q,actor,True);validate(KEY,operation_key)
 if not isinstance(input_ids,list) or len(input_ids)!=2 or any(type(i) is not int for i in input_ids) or len(set(input_ids))!=2:raise ValidationError('Select two distinct exact payroll inputs')
 intent={'input_ids':sorted(input_ids)};old=run_old(q,operation_key,actor,'combine',intent)
 if old:return old
 inputs=[exact(c,PayrollInput,pk) for pk in input_ids]
 if any(i.request_id!=q.pk for i in inputs) or {i.provider for i in inputs}!=set(q.metadata['providers']):raise ValidationError('Two expected providers for the same request required')
 for i in inputs:input_current(i)
 policy=resolve(MERGE,c);rule=reference_values(policy.configuration)[0] if policy.status=='ACTIVE' else None
 if rule and set(rule['provider_order'])!=set(q.metadata['providers']):raise ValidationError('Merge provider order differs from the source contract')
 result,codes=maths.combine([(i,i.payload) for i in inputs],rule)
 pins={ACCESS:config.pk,**({MERGE:policy.configuration.pk} if rule else {})}
 if not rule:codes.append('merge_policy_missing')
 return store(actor,q,'combine',operation_key,intent,result,codes,pins,input_ids,min(i.retain_until for i in inputs))

@transaction.atomic
def match(actor,case_id,parent_id,hr_snapshot_id,operation_key,expected):
 c=locked(actor,case_id,'payroll.match',expected);p=exact(c,PayrollRun,parent_id)
 if p.kind!='combine':raise ValidationError('F17 requires an exact combined working sheet')
 check_run_access(actor,p);validate(KEY,operation_key);intent={'parent_id':p.pk,'hr_snapshot_id':hr_snapshot_id};old=run_old(p.request,operation_key,actor,'match',intent)
 if old:return old
 h=hr.exact(c,HRReadSnapshot,hr_snapshot_id);hr.authorized(h.contract)
 for k in ['hrfinance.read','hrfinance.snapshot.read']:require(actor,c,k)
 if actor.pk not in h.contract.payload['recipient_ids']:raise PermissionDenied('HR did not nominate this payroll matcher')
 if h.contract.payload['purpose']!='payroll_matching' or set(h.contract.payload['fields'])!=set(REQUIRED) or any(h.contract.payload[k]!=p.request.metadata[k] for k in ['entity','period']):raise ValidationError('Exact minimal payroll-matching HR contract/entity/period required; no inherited salary access')
 hr.authority(actor,c,'receive');codes=[];hr_rows=[]
 try:
  payload=hr.read_snapshot(actor,h);hr.current_snapshot(h,for_use=True);hr_rows=payload['rows']
  if not h.contract.records.filter(kind='receipt',snapshot=h,actor=actor).exists():codes.append('hr_receipt_missing')
 except ValidationError:
  codes.append('hr_source_unavailable')
  if 'duplicate_or_overlapping_employee' in h.manifest.get('findings',[]):codes.append('ambiguous_hr_source')
 resolved=resolve(MATCH,c);rule=reference_values(resolved.configuration)[0] if resolved.status=='ACTIVE' else None
 result,issues=maths.match(p.result['rows'],hr_rows,p.request.metadata['period'],h.contract.payload['effective_until_semantics'],rule)
 codes+=issues
 if p.metadata['status']!='complete':codes.append('parent_working_set_held')
 pins={**p.metadata['policy_ids'],**({MATCH:resolved.configuration.pk} if rule else {})}
 if not rule:codes.append('match_policy_missing')
 return store(actor,p.request,'match',operation_key,intent,result,codes,pins,p.metadata['input_ids'],min(p.retain_until,h.retain_until),parent=p,hr_source=h)

@transaction.atomic
def aggregate(actor,case_id,parent_id,operation_key,expected):
 c=locked(actor,case_id,'payroll.aggregate',expected);p=exact(c,PayrollRun,parent_id)
 if p.kind!='match':raise ValidationError('F18 requires an exact HR-matched working sheet')
 check_run_access(actor,p);validate(KEY,operation_key);intent={'parent_id':p.pk};old=run_old(p.request,operation_key,actor,'aggregate',intent)
 if old:return old
 policy=active_component(REPORT,c);rules=reference_values(policy)[0];_,access_rules=access(p.request)
 if not {r['component'] for r in rules['components']}<=set(access_rules['allowed_components']):raise ValidationError('Reporting includes components outside source disclosure')
 result,codes=maths.aggregate(p.result['rows'],rules)
 if p.metadata['status']!='complete':codes.append('parent_working_set_held')
 return store(actor,p.request,'aggregate',operation_key,intent,result,codes,{**p.metadata['policy_ids'],REPORT:policy.pk},p.metadata['input_ids'],p.retain_until,parent=p)

def authority(actor,q,purpose,preparer=None):
 config=active_component(AUTH,q.case);v=reference_values(config)[0]
 if not any(r['user_id']==actor.pk and purpose in r['purposes'] for r in v['assignments']):raise PermissionDenied('No actual configured Finance authority for this payroll decision')
 if purpose!='publish' and v['independent_reviewer'] and preparer==actor.pk:raise PermissionDenied('Independent configured Finance reviewer required')
 return {AUTH:config.pk,**decision_authority(actor,q.case,'Finance')}

def current_review(item):
 r=item.reviews.order_by('-pk').first()
 if not r or r.verdict!='approve' or r.subject_sha256!=item.sha256:raise ValidationError('Current exact payroll review required')
 q=item.request;require(r.actor,q.case,'payroll.review');access(q,r.actor,True)
 if isinstance(item,PayrollRun):run_access(r.actor,item);purpose=item.kind
 else:input_current(item);purpose='input'
 if authority(r.actor,q,purpose,item.actor_id)!=r.authority:raise ValidationError('Payroll review authority changed')
 if isinstance(item,PayrollRun):
  if item.parent_id:current_review(exact(q.case,PayrollRun,item.parent_id))
  else:
   for pk in item.metadata['input_ids']:current_review(exact(q.case,PayrollInput,pk))
 return r

@transaction.atomic
def review(actor,case_id,kind,subject_id,verdict,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'payroll.review',expected)
 if kind not in ['input','run'] or verdict not in ['approve','return','revoke']:raise ValidationError('Select an exact input/run and approve/return/revoke')
 item=exact(c,PayrollInput if kind=='input' else PayrollRun,subject_id);q=item.request;validate(KEY,operation_key);e=subject(c,evidence_id,'payroll_review')
 old=PayrollReview.objects.filter(request=q,operation_key=operation_key).first()
 if old:
  if old.actor_id!=actor.pk or old.verdict!=verdict or old.input_id!=(item.pk if kind=='input' else None) or old.run_id!=(item.pk if kind=='run' else None) or old.evidence_id!=e.pk:raise ValidationError('Review operation intent changed')
  return old
 access(q,actor,True);purpose='input' if kind=='input' else item.kind;a=authority(actor,q,purpose,item.actor_id)
 if verdict!='revoke':
  if kind=='input':input_current(item)
  else:check_run_access(actor,item)
 if verdict=='approve':
  if item.metadata['status']!='complete':raise ValidationError('Unresolved payroll source/control/matching/disclosure exceptions prevent approval')
  if kind=='run':
   if item.parent_id:current_review(exact(q.case,PayrollRun,item.parent_id))
   else:
    for pk in item.metadata['input_ids']:current_review(exact(c,PayrollInput,pk))
 r=PayrollReview.objects.create(request=q,input=item if kind=='input' else None,run=item if kind=='run' else None,operation_key=operation_key,verdict=verdict,authority=a,subject_sha256=item.sha256,evidence=e,actor=actor)
 event(actor,c,'payroll.review',review=r.pk,verdict=verdict);bump(c);return r

@transaction.atomic
def publish(actor,case_id,run_id,operation_key,expected):
 c=locked(actor,case_id,'payroll.publish',expected);r=exact(c,PayrollRun,run_id);validate(KEY,operation_key)
 if r.kind!='aggregate':raise ValidationError('Only an aggregate can enter a BU report')
 old=PayrollPublication.objects.filter(request=r.request,operation_key=operation_key).first()
 if old:
  if old.run_id!=r.pk or old.actor_id!=actor.pk:raise ValidationError('Publication retry intent changed')
  return old
 check_run_access(actor,r);decision=current_review(r);auth=authority(actor,r.request,'publish');policy=active_component(REPORT,c);rules=reference_values(policy)[0]
 if r.metadata['status']!='complete':raise ValidationError('All aggregate disclosure/reconciliation holds must be resolved')
 version=(PayrollPublication.objects.filter(request=r.request).order_by('-version').values_list('version',flat=True).first() or 0)+1
 payload={**{k:r.request.metadata[k] for k in ['entity','period','currency']},'unit':'major_currency','by_bu':r.result['by_bu'],'eligible_total':r.result['eligible_total'],'source_run':r.pk,'report_version':version,'destination':rules['destination'],'disclosure':'aggregate_only','hr_written':False,'ledger_posted':False}
 p=PayrollPublication.objects.create(request=r.request,run=r,review=decision,version=version,operation_key=operation_key,payload=payload,policy_ids={**auth,REPORT:policy.pk},actor=actor)
 event(actor,c,'payroll.aggregate_published',publication=p.pk,version=version,destination=rules['destination']);bump(c);return p

@transaction.atomic
def read_publication(actor,publication_id):
 p=PayrollPublication.objects.defer('payload').select_related('request__case').get(pk=publication_id);c=locked(actor,p.request.case_id,'payroll.report.read')
 policy=active_component(REPORT,c);rules=reference_values(policy)[0]
 if actor.pk not in rules['recipient_ids']:raise PermissionDenied('Not a configured aggregate report recipient')
 source=exact(c,PayrollRun,p.run_id);run_current(source)
 require(p.actor,c,'payroll.publish')
 if current_review(source).pk!=p.review_id or policy.pk!=p.policy_ids[REPORT] or authority(p.actor,p.request,'publish')!={k:v for k,v in p.policy_ids.items() if k!=REPORT}:raise ValidationError('BU staff-cost report stale; prepare a reviewed versioned replacement')
 if PayrollPublication.objects.filter(request=p.request,version__gt=p.version).exists():raise ValidationError('BU report version replaced')
 return p.payload

@transaction.atomic
def receive_report(actor,case_id,publication_id,expected):
 c=locked(actor,case_id,'payroll.report.receive',expected);p=exact(c,PayrollPublication,publication_id);read_publication(actor,p.pk)
 r,created=PayrollReportReceipt.objects.get_or_create(publication=p,actor=actor)
 if created:event(actor,c,'payroll.report_receipt',publication=p.pk,receipt=r.pk);bump(c)
 return r

@transaction.atomic
def hr_correction(actor,case_id,run_id,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'payroll.hr_correction',expected);r=exact(c,PayrollRun,run_id)
 if r.kind!='match':raise ValidationError('Use an exact F17 matching working sheet')
 check_run_access(actor,r);validate(KEY,operation_key)
 key='payroll:'+digest({'run':r.pk,'key':operation_key})
 q=hr.correction(actor,c.pk,r.hr_snapshot_id,key,evidence_id,None)
 link,_=PayrollHRFollowup.objects.get_or_create(record=q,defaults={'run':r,'actor':actor})
 if link.run_id!=r.pk or link.actor_id!=actor.pk:raise ValidationError('Correction link intent changed')
 event(actor,c,'payroll.hr_correction_linked',run=r.pk,record=q.pk);bump(c);return link
