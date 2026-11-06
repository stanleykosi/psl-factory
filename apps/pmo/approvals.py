"""P02 references source-owned decisions. Routing/contract consent never grants approval."""
from django.db import transaction,connection
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import validate,digest
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.approval_validators import ROUTES,CONTRACTS
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from adapters.approvals import SuppliedApprovalReadAdapter
from .services import subject
from .gates import GATE_OWNERS
from .models import DeliveryCandidate,ApprovalRequest,ApprovalContractReview,ApprovalSourceReceipt,ApprovalObservation,ApprovalGateBinding,GateVerification,GateRecord
ID={'type':'integer','minimum':1};HASH={'type':'string','pattern':'^[a-f0-9]{64}$'};NULLKEY={'anyOf':[KEY,{'type':'null'}]}
SUBJECT=obj({'case_id':{'type':'string'},'candidate_ref':{'type':'string','minLength':1,'maxLength':160},'requirements_sha256':HASH,'build_ref':NULLKEY,'release_ref':NULLKEY})
SOURCE=obj({'request_id':ID,'kind':KEY,'subject':SUBJECT,'system':KEY,'source_owner':{'type':'string','minLength':1,'maxLength':100},'source_actor_ref':KEY,'external_ref':KEY,'source_version':KEY,'decision':{'enum':['accepted','rejected','withdrawn','unknown']},'decided_at':{'type':'string'},'signature_ref':KEY,'critical_defects':{'anyOf':[{'type':'integer','minimum':0},{'type':'null'}]}})
READ=obj({'receipt_id':ID,'system':KEY,'external_ref':KEY,'source_version':KEY,'observed_at':{'type':'string'},'outcome':{'enum':['available','unavailable','not_found','unknown']},'payload_sha256':{'anyOf':[HASH,{'type':'null'}]},'decision':{'enum':[None,'accepted','rejected','withdrawn','unknown']}})
def readable(a,c):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active authenticated principal required')
 require(a,c,'case.read');require(a,c,'approval.read')
def locked(a,case_id,action,expected=None):
 c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c)
 if c.kind!='project':raise ValidationError('Project coordination case required')
 return c
def exact(c,pk):
 r=ApprovalRequest.objects.select_related('case','candidate__requirements','actor').filter(case=c,pk=pk).first()
 if not r:raise ValidationError('Exact case prerequisite request required')
 return r
def current_request(r):
 if ApprovalRequest.objects.filter(case=r.case,reference=r.reference,version__gt=r.version).exists():raise ValidationError('Request subject was superseded; preserve older receipts')
 if r.subject['requirements_sha256']!=r.candidate.requirements.sha256:raise ValidationError('Candidate requirements changed')
def rules(c,kind):
 p=active_component(ROUTES,c);q=active_component(CONTRACTS,c);routes=reference_values(p)[0];contracts=reference_values(q)[0]
 route=next((x for x in routes['routes'] if x['kind']==kind),None);contract=next((x for x in contracts['contracts'] if x['kind']==kind),None)
 if not route or not contract:raise ValidationError('Configure this exact prerequisite owner and evidence contract')
 return p,q,route,contract,routes
def owner_authority(a,c,route,action):
 readable(a,c);require(a,c,action)
 if a.pk!=route['owner_id']:raise PermissionDenied('Exact department source owner required; coordinator cannot impersonate that owner')
 return decision_authority(a,c,route['owner_role'])
def contract_snapshot(c,kind):
 p,q,route,contract,_=rules(c,kind);e=subject(c,contract['contract_evidence_id']);return {ROUTES:p.pk,CONTRACTS:q.pk,'contract_evidence_sha256':e.sha256,'kind':kind}
@transaction.atomic
def review_contract(a,case_id,kind,evidence_id,verdict='accept',expected=None):
 c=locked(a,case_id,'approval.contract',expected);p,q,route,contract,_=rules(c,kind)
 if verdict not in ['accept','withdraw']:raise ValidationError('Choose contract acceptance or withdrawal; this is not a prerequisite approval')
 authority=owner_authority(a,c,route,'approval.contract');r=ApprovalContractReview.objects.create(case=c,kind=kind,verdict=verdict,snapshot=contract_snapshot(c,kind),authority=authority,evidence=subject(c,evidence_id,'approval_contract_review'),actor=a)
 event(a,c,'approval.contract_'+verdict,review=r.pk,kind=kind,approval_granted=False);bump(c);return r
def approved_contract(c,kind):
 p,q,route,contract,_=rules(c,kind);r=ApprovalContractReview.objects.filter(case=c,kind=kind).order_by('-pk').first()
 if not r or r.verdict!='accept' or r.snapshot!=contract_snapshot(c,kind) or r.authority!=owner_authority(r.actor,c,route,'approval.contract'):raise ValidationError('Current department-owned evidence-contract acceptance required')
 return r
@transaction.atomic
def create_request(a,case_id,reference,candidate_id,kind,build_ref,release_ref,evidence_id,expected=None,predecessor=None):
 c=locked(a,case_id,'approval.request',expected);candidate=DeliveryCandidate.objects.filter(case=c,pk=candidate_id).first();validate(KEY,kind);validate(KEY,reference)
 validate(NULLKEY,build_ref);validate(NULLKEY,release_ref)
 if not candidate:raise ValidationError('Exact project candidate required')
 old=ApprovalRequest.objects.filter(case=c,reference=reference).order_by('-version').first()
 if old and (old.pk!=predecessor or old.kind!=kind):raise ValidationError('Explicit current predecessor of the same prerequisite kind required')
 if predecessor and not old:raise ValidationError('No matching predecessor')
 r=ApprovalRequest.objects.create(case=c,candidate=candidate,reference=reference,version=old.version+1 if old else 1,kind=kind,gate_kind=kind if kind in GATE_OWNERS else None,subject={'case_id':str(c.pk),'candidate_ref':candidate.reference,'requirements_sha256':candidate.requirements.sha256,'build_ref':build_ref,'release_ref':release_ref},evidence=subject(c,evidence_id,'approval_request'),actor=a)
 event(a,c,'approval.request',request=r.pk,version=r.version,approval_granted=False);bump(c);return r
@transaction.atomic
def capture(a,case_id,request_id,evidence_id,expected=None):
 c=locked(a,case_id,'approval.capture',expected);r=exact(c,request_id);e=subject(c,evidence_id);v=SuppliedApprovalReadAdapter().read(e,SOURCE,'approval_source')
 if v['request_id']!=r.pk or v['kind']!=r.kind or v['subject']!=r.subject:raise ValidationError('Exact request/candidate/requirements/build/release correlation required')
 if timestamp(v['decided_at'])>timezone.now():raise ValidationError('Actual source decision time cannot be future-dated')
 key=digest({'tenant':c.tenant,**{k:v[k] for k in ['system','external_ref','source_version']}})
 with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[int(key[:15],16)])
 old=ApprovalSourceReceipt.objects.filter(tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],source_version=v['source_version']).first()
 if old:
  if old.request_id!=r.pk or old.sha256!=digest(v):raise ValidationError('Incumbent source identity is already claimed or conflicts; investigate without another approval instance')
  return old
 s=ApprovalSourceReceipt.objects.create(request=r,tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],source_version=v['source_version'],payload=v,sha256=digest(v),evidence=e,actor=a)
 event(a,c,'approval.source_received',receipt=s.pk,source_decision=v['decision'],verified=False);bump(c);return s

def context(receipt):
 r=receipt.request;current_request(r);p,q,route,contract,_=rules(r.case,r.kind);accepted=approved_contract(r.case,r.kind)
 if route['gate_kind']!=r.gate_kind:raise ValidationError('Preserve this exact source gate kind')
 if any(receipt.payload[k]!=route[k] for k in ['system','source_owner','source_actor_ref']):raise ValidationError('Receipt differs from configured owner/system/actor contract')
 if any(r.subject[k] is None for k in contract['required_subject_fields']):raise ValidationError('Required source subject fields remain unknown')
 return {ROUTES:p.pk,CONTRACTS:q.pk,'contract_review':accepted.pk},route,contract
@transaction.atomic
def observe(a,case_id,receipt_id,evidence_id,expected=None):
 c=locked(a,case_id,'approval.verify',expected);s=ApprovalSourceReceipt.objects.select_related('request__case','request__candidate').filter(pk=receipt_id,request__case=c).first()
 if not s:raise ValidationError('Exact case receipt required')
 e=subject(c,evidence_id);v=SuppliedApprovalReadAdapter().read(e,READ,'approval_observation');pins,route,contract=context(s)
 if (v['receipt_id'],v['system'],v['external_ref'],v['source_version'])!=(s.pk,s.system,s.external_ref,s.source_version):raise ValidationError('Exact source observation identity required')
 age=(timezone.now()-timestamp(v['observed_at'])).total_seconds()
 if age<0 or age>contract['max_age_seconds']:raise ValidationError('Current bounded observation required')
 auth={};status='unavailable'
 if v['outcome']=='available':
  auth=owner_authority(a,c,route,'approval.verify');require(a,c,'approval.source.read:'+route['system'])
  if contract['mode']!='owner_supplied_reference_v1' or contract['ordering']!='decided_at_monotonic_v1':raise ValidationError('Native provider/order implementation remains unavailable; supplied reference mode is explicit')
  status='referenced' if v['payload_sha256']==s.sha256 and v['decision']==s.payload['decision'] and timestamp(v['observed_at'])>=timestamp(s.payload['decided_at']) else 'conflicting'
  if any(timestamp(x)>timestamp(s.payload['decided_at']) for x in s.request.source_receipts.values_list('payload__decided_at',flat=True)):status='conflicting'
 pins['source_authority']=auth
 o=ApprovalObservation.objects.create(receipt=s,actor=a,evidence=e,payload=v,snapshot=pins,status=status)
 event(a,c,'approval.source_observed',observation=o.pk,receipt=s.pk,status=status,native_verified=False,approval_granted=False);bump(c);return o

def current_observation(o):
 s=o.receipt;r=s.request;readable(o.actor,r.case);require(o.actor,r.case,'approval.verify');pins,route,contract=context(s)
 if r.source_receipts.order_by('-pk').first().pk!=s.pk or s.observations.order_by('-pk').first().pk!=o.pk:raise ValidationError('Source receipt or observation was superseded')
 if o.status!='referenced':raise ValidationError('Source verification unavailable or conflicting; original receipt retained')
 auth=owner_authority(o.actor,r.case,route,'approval.verify');require(o.actor,r.case,'approval.source.read:'+route['system']);pins['source_authority']=auth
 if pins!=o.snapshot:raise ValidationError('Owner/contract/source authority changed; current re-observation required')
 age=(timezone.now()-timestamp(o.payload['observed_at'])).total_seconds()
 if not 0<=age<=contract['max_age_seconds']:raise ValidationError('Source observation expired; no checkbox fallback')
 return o

def visibility(a,r):
 readable(a,r.case);value={'request_id':r.pk,'reference':r.reference,'version':r.version,'kind':r.kind,'subject':r.subject,'status':'awaiting_source','source_decision':None,'source_owner':None,'receipt_id':None,'observation_id':None,'native_verified':False,'approval_granted_by_hub':False}
 s=r.source_receipts.order_by('-pk').first()
 try:
  current_request(r);_,_,route,_,_=rules(r.case,r.kind);value['source_owner']=route['source_owner']
  if not s:
   value['status_label']='Awaiting source receipt';return value
  require(a,r.case,'approval.source.read:'+s.system);value.update(receipt_id=s.pk,external_ref=s.external_ref,source_version=s.source_version,source_decision=s.payload['decision'],status='received_unverified')
  o=s.observations.order_by('-pk').first()
  if o:
   value['observation_id']=o.pk;current_observation(o);value['status']='referenced_'+s.payload['decision']
 except PermissionDenied:value['status']='unavailable';value.pop('external_ref',None);value.pop('source_version',None);value['source_decision']=None;value['receipt_id']=None;value['observation_id']=None
 except ValidationError:value['status']='unavailable' if s else 'configuration_required'
 value['status_label']={'awaiting_source':'Awaiting source receipt','received_unverified':'Received; unverified','configuration_required':'Owner configuration required','unavailable':'Verification unavailable','referenced_accepted':'Owner acceptance referenced','referenced_rejected':'Owner rejection referenced','referenced_withdrawn':'Owner withdrawal referenced','referenced_unknown':'Owner decision unknown'}.get(value['status'],value['status'])
 return value
@transaction.atomic
def export_gate(a,case_id,observation_id,expected=None):
 c=locked(a,case_id,'approval.export_gate',expected);o=ApprovalObservation.objects.select_related('receipt__request__case','receipt__request__candidate').filter(pk=observation_id,receipt__request__case=c).first()
 if not o:raise ValidationError('Exact case observation required')
 current_observation(o);r=o.receipt.request;_,_,route,_,_=rules(c,r.kind);owner_authority(a,c,route,'approval.export_gate')
 if not c.synthetic:raise ValidationError('Native authoritative source adapter required for operational release-gate use; referenced evidence remains visible')
 if not r.gate_kind:raise ValidationError('This prerequisite has no legacy delivery gate bridge')
 old=ApprovalGateBinding.objects.filter(observation=o).first()
 if old:return old
 require(a,c,'pmo.gate_record');require(a,c,'pmo.gate_verify')
 from .gates import record_gate
 g=GateRecord.objects.filter(candidate=r.candidate,kind=r.gate_kind,external_ref=o.receipt.external_ref,evidence=o.receipt.evidence).first()
 if not g:g=record_gate(a,c.pk,r.candidate_id,r.gate_kind,o.receipt.external_ref,o.receipt.evidence_id,None)
 decision=o.receipt.payload['decision'];defects=o.receipt.payload['critical_defects']
 if r.gate_kind=='qa_exit' and decision=='accepted' and defects!=0:decision='unknown' if defects is None else 'rejected'
 if decision=='withdrawn':decision='rejected'
 v=GateVerification.objects.create(record=g,adapter='owner-referenced-prerequisite-v1',result={'candidate_ref':r.candidate.reference,'requirements_sha256':r.candidate.requirements.sha256,'external_ref':g.external_ref,'source_owner':g.source_owner,'evidence_sha256':g.evidence.sha256,'decision':decision,'critical_defects':defects,'source_receipt':'p02:'+str(o.receipt_id)},actor=a)
 b=ApprovalGateBinding.objects.create(observation=o,verification=v);event(a,c,'approval.gate_reference_bound',binding=b.pk,approval_granted=False,native_verified=False);return b

def candidate_requests(candidate,kind):
 rows=ApprovalRequest.objects.filter(candidate=candidate,gate_kind=kind).select_related('case','candidate')
 return [r for r in rows if not ApprovalRequest.objects.filter(candidate=candidate,reference=r.reference,version__gt=r.version).exists()]
def gate_current(candidate,kind,verification):
 requests=candidate_requests(candidate,kind)
 if not requests:return
 if len(requests)!=1:raise ValidationError('Conflicting prerequisite requests require owner investigation')
 b=ApprovalGateBinding.objects.select_related('observation__receipt__request__case','observation__receipt__request__candidate').filter(verification=verification).first()
 if not b or b.observation.receipt.request_id!=requests[0].pk:raise ValidationError('Current source-owned P02 gate reference required; legacy verification is not a fallback')
 current_observation(b.observation)
def gate_context(candidate,kind):
 requests=candidate_requests(candidate,kind)
 if not requests:return None
 context=[]
 for r in requests:
  s=r.source_receipts.order_by('-pk').first();o=s.observations.order_by('-pk').first() if s else None;status='missing'
  if o:
   try:current_observation(o);status='current'
   except (ValidationError,PermissionDenied):status='unavailable'
  context.append({'request':r.pk,'receipt':s.pk if s else None,'observation':o.pk if o else None,'status':status})
 return context
