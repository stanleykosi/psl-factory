"""Manual F33 fallback: evidence and human review, never an accounting engine."""
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import validate,digest
from apps.documents.controlled import baseline_manifest
from apps.documents.validation import finite,source_current
from apps.documents.validation_models import DiscoverySource
from apps.pmo.services import subject
from apps.pmo.models import Milestone
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.recognition_validators import AUTHORITY,REVIEW,CATEGORIES,ID
from adapters.forecast import obj,KEY
from .recognition_models import ProgressPacket,RecognitionRecord
TEXT={'type':'string','minLength':1,'maxLength':4000}
IDS={'type':'array','maxItems':100,'uniqueItems':True,'items':ID}
PACKET=obj({'period_start':{'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'},'period_end':{'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'},'as_of':{'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'},'statement':TEXT,'access_context':TEXT,'contact_context':TEXT,'facts':{'type':'array','maxItems':100,'items':obj({'category':{'enum':CATEGORIES},'evidence_id':ID,'description':TEXT})},'source_ids':IDS,'milestone_ids':IDS,'gaps':{'type':'array','maxItems':100,'uniqueItems':True,'items':TEXT},'conflicts':{'type':'array','maxItems':100,'uniqueItems':True,'items':TEXT}})

def locked(actor,case_id,action,expected=None):
 case=lock_case(actor,case_id,action,expected)
 list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
 require(actor,case,action);require(actor,case,'case.read');require(actor,case,'recognition.read')
 if case.kind!='project':raise ValidationError('Project case required')
 return case

def manifest(case,payload):
 baseline=baseline_manifest(case)
 allowed={'estimate':['progress_estimate'],'completion':['completion'],'acceptance':['progress_acceptance','client_feedback'],'price':['progress_price','sow','costing','billing_coverage'],'cash':['cash_report']}
 for f in payload['facts']:
  e=subject(case,f['evidence_id'])
  if e.kind not in allowed[f['category']]:raise ValidationError('Fact category does not match evidence kind')
 evidence_ids={f['evidence_id'] for f in payload['facts']}|{v for v in baseline.values() if v}
 evidence={str(i):subject(case,i).sha256 for i in sorted(evidence_ids)}
 sources={}
 for i in payload['source_ids']:
  s=DiscoverySource.objects.filter(case=case,pk=i).first()
  if not s:raise ValidationError('Scoped discovery source required')
  source_current(s)
  if 'F33' not in s.metadata['process_ids']:raise ValidationError('Discovery source needs F33 scope')
  sources[str(i)]={'sha256':s.sha256,'version':s.version}
 milestones={}
 for i in payload['milestone_ids']:
  m=Milestone.objects.filter(case=case,pk=i).first()
  if not m:raise ValidationError('Scoped completed milestone required')
  milestones[str(i)]={'evidence_id':m.evidence_id,'sha256':m.evidence.sha256,'completed_by':m.completed_by_id,'completed_at':m.completed_at.isoformat()}
 return {'baseline':baseline,'evidence':evidence,'sources':sources,'milestones':milestones}

def packet_current(packet):
 if ProgressPacket.objects.filter(case=packet.case,reference=packet.reference,version__gt=packet.version).exists():raise ValidationError('Packet superseded; new attestation and review required')
 if manifest(packet.case,packet.payload)!=packet.manifest:raise ValidationError('Packet sources or signed baseline changed')
 for f in packet.payload['facts']:
  e=subject(packet.case,f['evidence_id'])
  if packet.case.evidence.filter(kind=e.kind,version__gt=e.version).exists():raise ValidationError('Fact evidence revised; prepare successor packet')
 return packet

def findings(packet):
 p=packet.payload;out=list(p['gaps'])+[f'Conflict: {s}' for s in p['conflicts']]
 if not packet.manifest['baseline'].get('signed_id'):out.append('Signed commercial baseline missing')
 cats={f['category'] for f in p['facts']}
 if 'price' not in cats:out.append('Price evidence missing; unknown is not zero')
 if not cats&{'estimate','completion','acceptance'}:out.append('PM progress evidence missing; cash is not progress')
 return out

def authority(actor,case,purpose):
 config=active_component(AUTHORITY,case);v=reference_values(config)[0]
 role={'attest':'PM','review':'Finance'}[purpose]
 if not any(r=={'user_id':actor.pk,'purpose':purpose,'role':role} for r in v['assignments']):raise PermissionDenied('No configured actual human for this responsibility')
 return {AUTHORITY:config.pk,**decision_authority(actor,case,role)}

def authority_current(record):
 purpose='attest' if record.kind=='attest' else 'review'
 require(record.actor,record.packet.case,'recognition.'+purpose)
 if authority(record.actor,record.packet.case,purpose)!=record.authority:raise ValidationError('Authority changed; new human review required')

def attested(packet):
 r=packet.records.filter(kind='attest').order_by('-pk').first()
 if not r:raise ValidationError('PM attestation required')
 authority_current(r);return r

@transaction.atomic
def prepare(actor,case_id,reference,payload,evidence_id,expected):
 case=locked(actor,case_id,'recognition.prepare',expected);validate(KEY,reference);finite(payload);validate(PACKET,payload)
 try:dates=[date.fromisoformat(payload[k]) for k in ['period_start','period_end','as_of']]
 except ValueError:raise ValidationError('Use valid ISO calendar dates')
 if dates[0]>dates[1] or dates[2]>timezone.localdate():raise ValidationError('Valid reporting period and non-future attestation date required')
 e=subject(case,evidence_id);m=manifest(case,payload)
 v=(ProgressPacket.objects.filter(case=case,reference=reference).order_by('-version').values_list('version',flat=True).first() or 0)+1
 r=ProgressPacket.objects.create(case=case,reference=reference,version=v,payload=payload,manifest=m,sha256=digest({'payload':payload,'manifest':m}),evidence=e,actor=actor)
 event(actor,case,'recognition.packet',packet=r.pk);bump(case);return r

def guard_record(actor,case,packet_id,kind,operation_key,evidence_id,note,verdict=None,decision_evidence_id=None):
 """Read-only native checks, including original replay before new-currentness."""
 if kind not in ['attest','request','receive','review']:raise ValidationError('Unknown F33 transition')
 require(actor,case,'recognition.'+kind);require(actor,case,'case.read');require(actor,case,'recognition.read')
 if case.kind!='project':raise ValidationError('Project case required')
 validate(KEY,operation_key);validate(TEXT,note)
 packet=ProgressPacket.objects.filter(case=case,pk=packet_id).first()
 if not packet:raise ValidationError('Scoped progress packet required')
 e=subject(case,evidence_id)
 intent={'note':note,'verdict':verdict,'decision_evidence_id':decision_evidence_id}
 if kind!='review' and (verdict is not None or decision_evidence_id is not None):raise ValidationError('Only Finance review can record a disposition')
 if decision_evidence_id:subject(case,decision_evidence_id,'recognition_decision')
 old=packet.records.filter(operation_key=operation_key).first()
 if old:
  if old.actor_id!=actor.pk or old.kind!=kind or old.evidence_id!=e.pk or old.payload['intent']!=intent:raise ValidationError('Operation key reused for changed intent')
  return packet,e,intent,old,{},{}
 packet_current(packet);auth={};snapshot={}
 if kind=='attest':auth=authority(actor,case,'attest')
 elif kind=='request':snapshot={'attestation_id':attested(packet).pk}
 elif kind=='receive':
  q=packet.records.filter(kind='request').order_by('-pk').first()
  if not q:raise ValidationError('Durable review request required before receipt')
  if q.payload['snapshot']['attestation_id']!=attested(packet).pk:raise ValidationError('New PM attestation needs a new review request')
  require(q.actor,case,'recognition.request')
  snapshot={'request_id':q.pk,'attestation_id':q.payload['snapshot']['attestation_id'],'receipt_only':True}
 elif kind=='review':
  if verdict not in ['reviewed','return','disputed']:raise ValidationError('Choose reviewed, return or disputed')
  auth=authority(actor,case,'review');a=attested(packet)
  receipt=packet.records.filter(kind='receive').order_by('-pk').first()
  if not receipt:raise ValidationError('Finance receipt required before review')
  if receipt.payload['snapshot'].get('attestation_id')!=a.pk:raise ValidationError('New PM attestation needs a new request and Finance receipt')
  snapshot={'attestation_id':a.pk,'receipt_id':receipt.pk,'request_id':receipt.payload['snapshot']['request_id']}
  if verdict=='reviewed':
   config=active_component(REVIEW,case);rules=reference_values(config)[0]
   if rules['independent_reviewer'] and actor.pk in [packet.actor_id,a.actor_id]:raise PermissionDenied('Independent Finance reviewer required')
   gaps=findings(packet);cats={f['category'] for f in packet.payload['facts']}
   if gaps or not set(rules['required_categories'])<=cats:raise ValidationError('Unresolved evidence gaps/conflicts or required categories: '+str(gaps))
   if rules['decision_reference_required'] and not decision_evidence_id:raise ValidationError('Finance decision evidence reference required')
   snapshot.update(review_policy_id=config.pk,policy_evidence_id=rules['policy_evidence_id'])
 return packet,e,intent,None,auth,snapshot

@transaction.atomic
def record(actor,case_id,packet_id,kind,operation_key,evidence_id,note,expected,verdict=None,decision_evidence_id=None):
 if kind not in ['attest','request','receive','review']:raise ValidationError('Unknown F33 transition')
 case=locked(actor,case_id,'recognition.'+kind,expected)
 packet,e,intent,old,auth,snapshot=guard_record(actor,case,packet_id,kind,operation_key,evidence_id,note,verdict,decision_evidence_id)
 if old:return old
 payload={'intent':intent,'snapshot':snapshot,'recognised_amount':None,'accounting_posted':False,'invoice_approved':False,'payment_approved':False}
 r=RecognitionRecord.objects.create(packet=packet,kind=kind,operation_key=operation_key,payload=payload,authority=auth,evidence=e,actor=actor)
 event(actor,case,'recognition.'+kind,record=r.pk,packet=packet.pk);bump(case);return r

def record_current(r):
 packet_current(r.packet)
 if r.kind in ['attest','review']:authority_current(r)
 if r.kind=='attest' and attested(r.packet).pk!=r.pk:raise ValidationError('Later PM attestation exists')
 if r.kind in ['request','receive'] and r.payload['snapshot'].get('attestation_id')!=attested(r.packet).pk:raise ValidationError('Attestation changed since request/receipt')
 if r.kind=='review':
  a=attested(r.packet)
  if a.pk!=r.payload['snapshot']['attestation_id']:raise ValidationError('PM attestation replaced')
  if r.payload['intent']['verdict']=='reviewed':
   c=active_component(REVIEW,r.packet.case)
   if c.pk!=r.payload['snapshot']['review_policy_id']:raise ValidationError('Recognition review policy changed')
  if r.packet.records.filter(kind='review',pk__gt=r.pk).exists():raise ValidationError('Later Finance disposition exists')
 return r

def position(packet):
 holds=findings(packet)
 try:packet_current(packet)
 except (ValidationError,PermissionDenied) as exc:holds.append(str(exc))
 reviews=[]
 for r in packet.records.select_related('actor').order_by('pk'):
  try:record_current(r);current=True
  except (ValidationError,PermissionDenied):current=False
  reviews.append({'id':r.pk,'kind':r.kind,'actor_id':r.actor_id,'current':current,'payload':r.payload})
 return {'packet_id':packet.pk,'reference':packet.reference,'version':packet.version,'sha256':packet.sha256,'holds':holds,'records':reviews,'recognised_amount':None,'accounting_posted':False}
