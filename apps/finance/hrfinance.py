"""F35 private minimal HR snapshots and read-only Finance receipts."""
import json,hashlib
from datetime import date,timedelta
from uuid import uuid4
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,bump,event
from apps.identity.services import require
from apps.identity.models import Grant
from apps.pmo.services import subject
from apps.documents.contracts import validate,digest
from apps.documents.validation import finite
from apps.policy.services import active_component,reference_values,decision_authority,register_reference,save_draft
from apps.policy.registry import components
from apps.policy.hrfinance_validators import AUTHORITY,DISCLOSURE,REQUIRED,FIELD_LIST,IDS,MONTH,TEXT,BASIS_SCHEMAS
from adapters.forecast import obj,KEY
from adapters.hrfinance import SuppliedHRExportAdapter,HRExportError,day,timestamp
from .hrfinance_models import HRFinanceNeed,HRDisclosure,HRReadSnapshot,HRHandoffRecord
NEED=obj({'purpose':KEY,'entity':KEY,'period':MONTH,'as_of':{'type':'string'},'fields':FIELD_LIST,'justification':{'type':'object','additionalProperties':TEXT},'recipient_ids':IDS})

def locked(actor,case_id,action,expected=None):
 c=lock_case(actor,case_id,action,expected)
 list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
 for k in [action,'case.read','hrfinance.read']:require(actor,c,k)
 return c

def exact(case,model,pk):
 path='case' if model==HRFinanceNeed else 'need__case' if model==HRDisclosure else 'contract__need__case'
 q=model.objects.defer('payload') if model==HRReadSnapshot else model.objects
 r=q.filter(pk=pk,**{path:case}).first()
 if not r:raise ValidationError('Select an exact scoped HR/Finance record')
 return r

def authority(actor,case,purpose):
 config=active_component(AUTHORITY,case);v=reference_values(config)[0];role='Finance' if purpose=='receive' else 'HR'
 if not any(r=={'user_id':actor.pk,'purpose':purpose,'role':role} for r in v['assignments']):raise PermissionDenied('No configured human for this HR/Finance responsibility')
 return {AUTHORITY:config.pk,**decision_authority(actor,case,role)}

def latest_need(need):
 if HRFinanceNeed.objects.filter(case=need.case,reference=need.reference,version__gt=need.version).exists():raise ValidationError('Finance need superseded; request a new disclosure')

def current_contract(c):
 latest_need(c.need)
 for key,pk in c.policy_ids.items():
  if active_component(key,c.need.case).pk!=pk:raise ValidationError('HR/Finance policy changed; prepare a new exact disclosure')
 if HRDisclosure.objects.filter(need=c.need,pk__gt=c.pk).exists():raise ValidationError('Disclosure replaced')
 rules=reference_values(active_component(DISCLOSURE,c.need.case))[0]
 e=subject(c.need.case,rules['source_evidence_id'],'hr_contract_source')
 if c.need.case.evidence.filter(kind=e.kind,version__gt=e.version).exists():raise ValidationError('HR source-view contract evidence revised')
 return c

def authorized(c):
 current_contract(c);r=c.records.filter(kind__in=['approve','return','revoke']).order_by('-pk').first()
 if not r or r.kind!='approve':raise ValidationError('Current HR disclosure approval required')
 require(r.actor,c.need.case,'hrfinance.authorize')
 if authority(r.actor,c.need.case,'authorize')!=r.authority:raise ValidationError('HR authorising principal or role changed')
 return r

@transaction.atomic
def need(actor,case_id,reference,payload,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.need',expected);validate(KEY,reference);finite(payload);validate(NEED,payload)
 if set(payload['justification'])!=set(payload['fields']) or not set(REQUIRED)<=set(payload['fields']):raise ValidationError('Every requested field needs its own purpose justification and exact identity/date fields')
 at=day(payload['as_of'])
 if at.strftime('%Y-%m')!=payload['period'] or at>timezone.localdate():raise ValidationError('As-of date must be actual and within requested period')
 if ('monthly_pay' in payload['fields'])!=('currency' in payload['fields']):raise ValidationError('Monthly pay requires currency')
 e=subject(c,evidence_id,'hr_finance_need');v=(HRFinanceNeed.objects.filter(case=c,reference=reference).order_by('-version').values_list('version',flat=True).first() or 0)+1
 r=HRFinanceNeed.objects.create(case=c,reference=reference,version=v,payload=payload,evidence=e,actor=actor)
 event(actor,c,'hrfinance.need',need=r.pk,version=v);bump(c);return r

@transaction.atomic
def contract(actor,case_id,need_id,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.contract',expected);validate(KEY,operation_key);n=exact(c,HRFinanceNeed,need_id);e=subject(c,evidence_id,'hr_contract_source')
 old=HRDisclosure.objects.filter(need=n,operation_key=operation_key).first()
 if old:
  if old.actor_id!=actor.pk or old.evidence_id!=e.pk:raise ValidationError('Disclosure operation intent changed')
  return old
 latest_need(n);policy=active_component(DISCLOSURE,c);rules=reference_values(policy)[0];p=n.payload
 if not set(p['fields'])<=set(rules['allowed_fields']) or not set(p['recipient_ids'])<=set(rules['recipient_ids']) or p['purpose'] not in rules['purposes'] or not rules['from_period']<=p['period']<=rules['to_period']:raise ValidationError('Need exceeds exact configured fields, recipients, purpose or periods')
 if e.pk!=rules['source_evidence_id']:raise ValidationError('Use the exact configured source-view contract evidence')
 for uid in p['recipient_ids']:
  from django.contrib.auth import get_user_model
  u=get_user_model().objects.get(pk=uid)
  for k in ['case.read','hrfinance.read','hrfinance.snapshot.read','hrfinance.receive']:require(u,c,k)
  authority(u,c,'receive')
 auth=active_component(AUTHORITY,c)
 payload={**p,**{k:rules[k] for k in ['source_view','employee_key_semantics','effective_until_semantics','route','max_age_seconds','retention_seconds','retention_mode','correction_route']}}
 pins={DISCLOSURE:policy.pk,AUTHORITY:auth.pk}
 r=HRDisclosure.objects.create(need=n,operation_key=operation_key,payload=payload,policy_ids=pins,sha256=digest({'need':n.pk,'payload':payload,'policies':pins}),evidence=e,actor=actor)
 event(actor,c,'hrfinance.contract',contract=r.pk,need=n.pk);bump(c);return r

@transaction.atomic
def decide(actor,case_id,contract_id,verdict,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.authorize',expected);d=exact(c,HRDisclosure,contract_id);validate(KEY,operation_key)
 if verdict not in ['approve','return','revoke']:raise ValidationError('Choose approve, return or revoke')
 e=subject(c,evidence_id,'hr_disclosure_decision');intent={'verdict':verdict}
 old=d.records.filter(operation_key=operation_key).first()
 if old:
  if old.actor_id!=actor.pk or old.kind!=verdict or old.evidence_id!=e.pk:raise ValidationError('Decision key reused with changed intent')
  return old
 a=authority(actor,c,'authorize')
 if verdict!='revoke':current_contract(d)
 r=HRHandoffRecord.objects.create(contract=d,kind=verdict,operation_key=operation_key,payload=intent,authority=a,evidence=e,actor=actor)
 event(actor,c,'hrfinance.disclosure_decision',record=r.pk,verdict=verdict);bump(c);return r

def current_snapshot(s,for_use=False):
 if s.status!='accepted':raise ValidationError('Rejected snapshot has no readable rows')
 a=authorized(s.contract)
 if s.manifest['authorization_id']!=a.pk:raise ValidationError('HR approval changed since capture')
 if timezone.now()>=s.retain_until:raise ValidationError('Retained snapshot access expired')
 extracted_at,completeness=HRReadSnapshot.objects.filter(pk=s.pk).values_list('payload__extracted_at','payload__completeness').get()
 if (timezone.now()-timestamp(extracted_at)).total_seconds()>s.contract.payload['max_age_seconds']:raise ValidationError('HR source snapshot stale')
 if s.contract.snapshots.filter(status='accepted',pk__gt=s.pk).exists():raise ValidationError('HR snapshot replaced; no silent historical restatement')
 if for_use and completeness!='complete':raise ValidationError('HR inventory is partial or unknown')
 return s

def snapshot_access(actor,s):
 # Pure currentness/authority checks shared by observations and locked readers.
 c=s.contract.need.case
 for k in ['case.read','hrfinance.read','hrfinance.snapshot.read']:require(actor,c,k)
 current_snapshot(s)
 if actor.pk not in s.contract.payload['recipient_ids']:raise PermissionDenied('Not an exact HR-authorised Finance recipient')
 authority(actor,c,'receive')
 return s

@transaction.atomic
def check_snapshot_access(actor,s):
 locked(actor,s.contract.need.case_id,'hrfinance.snapshot.read')
 return snapshot_access(actor,s)

@transaction.atomic
def read_snapshot(actor,s):
 check_snapshot_access(actor,s)
 return s.payload

@transaction.atomic
def capture(actor,case_id,contract_id,operation_key,body,expected):
 c=locked(actor,case_id,'hrfinance.capture',expected);d=exact(c,HRDisclosure,contract_id);validate(KEY,operation_key)
 if not isinstance(body,str) or len(body.encode('utf-8'))>256000:raise ValidationError('Supplied export exceeds bounded input budget')
 h=hashlib.sha256(body.encode('utf-8')).hexdigest();old=d.snapshots.defer('payload').filter(operation_key=operation_key).first()
 if old:
  if old.actor_id!=actor.pk or old.source_sha256!=h:raise ValidationError('Snapshot operation intent changed')
  authority(actor,c,'authorize')
  if old.status=='accepted':current_snapshot(old)
  # Historical retry returns only the record; callers must re-check access before rows.
  return old
 a=authorized(d);authority(actor,c,'authorize')
 try:payload=SuppliedHRExportAdapter().read(body,d);status='accepted';findings=[]
 except HRExportError as exc:payload={};status='rejected';findings=[exc.code]
 manifest={'authorization_id':a.pk,'contract_hash':d.sha256,'policy_ids':d.policy_ids,'findings':findings,'native_authenticity_verified':False}
 r=HRReadSnapshot.objects.create(contract=d,operation_key=operation_key,status=status,source_sha256=h,sha256=digest({'payload':payload,'manifest':manifest,'source_sha256':h}),payload=payload,manifest=manifest,retain_until=timezone.now()+timedelta(seconds=d.payload['retention_seconds']),actor=actor)
 event(actor,c,'hrfinance.snapshot',snapshot=r.pk,status=status,findings=findings);bump(c);return r

@transaction.atomic
def receive(actor,case_id,snapshot_id,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.receive',expected);s=exact(c,HRReadSnapshot,snapshot_id);validate(KEY,operation_key);e=subject(c,evidence_id,'hr_disclosure_decision')
 old=s.contract.records.filter(operation_key=operation_key).first()
 if old:
  if old.kind!='receipt' or old.snapshot_id!=s.pk or old.actor_id!=actor.pk or old.evidence_id!=e.pk:raise ValidationError('Receipt intent changed')
  return old
 read_snapshot(actor,s);a=authority(actor,c,'receive')
 r=HRHandoffRecord.objects.create(contract=s.contract,snapshot=s,kind='receipt',operation_key=operation_key,payload={'sha256':s.sha256,'receipt_only':True,'hr_write':False},authority=a,evidence=e,actor=actor)
 event(actor,c,'hrfinance.receipt',receipt=r.pk,snapshot=s.pk);bump(c);return r

@transaction.atomic
def correction(actor,case_id,snapshot_id,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.correction',expected);s=exact(c,HRReadSnapshot,snapshot_id);read_snapshot(actor,s);validate(KEY,operation_key);e=subject(c,evidence_id,'hr_correction_request')
 old=s.contract.records.filter(operation_key=operation_key).first()
 if old:
  if old.kind!='correction' or old.snapshot_id!=s.pk or old.actor_id!=actor.pk or old.evidence_id!=e.pk:raise ValidationError('Correction intent changed')
  return old
 r=HRHandoffRecord.objects.create(contract=s.contract,snapshot=s,kind='correction',operation_key=operation_key,payload={'route':s.contract.payload['correction_route'],'source_write':False},authority=authority(actor,c,'receive'),evidence=e,actor=actor)
 event(actor,c,'hrfinance.correction_requested',record=r.pk,snapshot=s.pk);bump(c);return r

@transaction.atomic
def respond(actor,case_id,request_id,successor_id,operation_key,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.respond',expected);q=exact(c,HRHandoffRecord,request_id);validate(KEY,operation_key);e=subject(c,evidence_id,'hr_correction_response')
 if q.kind!='correction':raise ValidationError('Choose an actual Finance correction request')
 successor=exact(c,HRReadSnapshot,successor_id)
 if successor.contract_id!=q.contract_id or successor.pk<=q.snapshot_id:raise ValidationError('HR response needs an exact later snapshot of this disclosure')
 current_snapshot(successor);auth=authority(actor,c,'respond')
 old=q.contract.records.filter(operation_key=operation_key).first()
 if old:
  if old.kind!='response' or old.snapshot_id!=successor.pk or old.payload['request_id']!=q.pk or old.actor_id!=actor.pk or old.evidence_id!=e.pk:raise ValidationError('Response intent changed')
  return old
 r=HRHandoffRecord.objects.create(contract=q.contract,snapshot=successor,kind='response',operation_key=operation_key,payload={'request_id':q.pk,'source_write':False,'new_finance_receipt_required':True},authority=auth,evidence=e,actor=actor)
 event(actor,c,'hrfinance.correction_response',record=r.pk);bump(c);return r

def basis_snapshot(case,value):
 s=exact(case,HRReadSnapshot,value['snapshot_id'])
 if s.sha256!=value['sha256'] or s.contract.payload['entity']!=value['entity'] or s.contract.payload['period']!=value['period']:raise ValidationError('Exact HR snapshot/hash/entity/period required')
 if s.contract.payload['purpose']!='bu_attribution' or set(s.contract.payload['fields'])!=set(REQUIRED):raise ValidationError('Allocation interface accepts only minimal staff/BU/date fields for bu_attribution')
 return s

def allocation_basis(actor,case,value):
 s=basis_snapshot(case,value);payload=read_snapshot(actor,s);current_snapshot(s,for_use=True)
 receipt=s.contract.records.filter(kind='receipt',snapshot=s,actor=actor).order_by('-pk').first()
 if not receipt or authority(actor,case,'receive')!=receipt.authority:raise ValidationError('Current recipient-specific Finance receipt required')
 return {'entity':value['entity'],'period':value['period'],'as_of':payload['as_of'],'completeness':payload['completeness'],'snapshot_id':s.pk,'receipt_id':receipt.pk,'rows':[{'subject_ref':r['employee_id'],'bu':r['bu'],'weight':'1'} for r in payload['rows']]}

@transaction.atomic
def draft_basis(actor,case_id,snapshot_id,evidence_id,expected):
 c=locked(actor,case_id,'hrfinance.bind',expected);require(actor,c,'policy.configure');s=exact(c,HRReadSnapshot,snapshot_id)
 v={'snapshot_id':s.pk,'sha256':s.sha256,'entity':s.contract.payload['entity'],'period':s.contract.payload['period']};allocation_basis(actor,c,v)
 e=subject(c,evidence_id,'policy_decision');drafts=[]
 for component,schema in BASIS_SCHEMAS.items():
  ref=register_reference(actor,c.pk,'hr-basis:'+str(uuid4()),schema,v,e.pk)
  value=ref.ref if component=='D07.effective_membership_ref' else [ref.ref]
  drafts.append(save_draft(actor,c.pk,{'slot_id':'D07','component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if c.kind=='project' else 'service','ref':str(c.pk)},'effective_from':timezone.now().isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(e.pk)],'human_decision_ref':'evidence:'+str(e.pk),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if c.synthetic else 'operational','value':value}))
 event(actor,c,'hrfinance.basis_drafted',snapshot=s.pk,drafts=[r.pk for r in drafts]);bump(c);return drafts
