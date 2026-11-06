from apps.core.evidence_access import public_evidence,restricted
"""Versioned migration evidence and AF13 readiness. No deployment or restore effects."""
from django.db import transaction,connection
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.migration_validators import COMPONENT,KINDS
from apps.policy.validation_validators import PROCESS_IDS,process_ids
from apps.pmo.services import subject
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from adapters.migration_evidence import SuppliedMigrationEvidenceAdapter,LocalEvidenceInventoryAdapter
from .contracts import digest,validate
from .migration_models import MigrationPlan,MigrationProof,MigrationObservation,MigrationAssessment,MigrationReadinessReview,MigrationAF13Binding
from . import validation as af
ID={'type':'integer','minimum':1};HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
PLAN=obj({'process_ids':PROCESS_IDS,'build_ref':KEY,'source_system':KEY,'source_ref':KEY,'source_version':KEY,'target_system':KEY,'target_ref':KEY,'target_version':KEY,'expected_record_count':{'anyOf':[{'type':'integer','minimum':0},{'type':'null'}]},'expected_manifest_sha256':{'anyOf':[HASH,{'type':'null'}]},'evidence_ids':{'type':'array','minItems':1,'maxItems':200,'uniqueItems':True,'items':ID}})
PROOF=obj({'plan_id':ID,'plan_sha256':HASH,'build_ref':KEY,'source_ref':KEY,'target_ref':KEY,'source_version':KEY,'target_version':KEY,'kind':{'enum':KINDS},'system':KEY,'external_ref':KEY,'receipt_version':KEY,'recorded_at':{'type':'string'},'performed_by_ref':KEY,'outcome':{'enum':['passed','failed','unknown']},'evidence_class':{'enum':['supplied_report','synthetic_report']},'record_count':{'anyOf':[{'type':'integer','minimum':0},{'type':'null'}]},'manifest_sha256':{'anyOf':[HASH,{'type':'null'}]}})

def readable(a,c):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active authenticated principal required')
 require(a,c,'case.read');require(a,c,'migration.read')
def locked(a,case_id,action,expected=None):
 c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c);return c
def config(c):
 p=active_component(COMPONENT,c);return p,reference_values(p)[0]
def plan_for(c,pk):
 p=MigrationPlan.objects.select_related('case','package__case','actor').filter(case=c,pk=pk).first()
 if not p:raise ValidationError('Exact case migration plan required')
 return p
def current_plan(p):
 if MigrationPlan.objects.filter(case=p.case,reference=p.reference,version__gt=p.version).exists():raise ValidationError('Migration plan was superseded; old evidence remains historical')
 if p.sha256!=digest({'payload':p.payload,'package':p.package_id}):raise ValidationError('Plan hash mismatch')

@transaction.atomic
def capture_plan(a,case_id,reference,payload,evidence_id,package_id=None,expected=None,predecessor=None):
 c=locked(a,case_id,'migration.capture',expected);validate(KEY,reference);validate(PLAN,payload);process_ids(payload['process_ids'])
 for pk in payload['evidence_ids']:
  e=subject(c,pk)
  if restricted(e):raise ValidationError('Restricted source evidence cannot enter a general inventory; use an authorised source contract')
 old=MigrationPlan.objects.filter(case=c,reference=reference).order_by('-version').first()
 if old and old.pk!=predecessor or not old and predecessor:raise ValidationError('Explicit current predecessor required for a plan revision')
 package=af.package_for(c,package_id) if package_id else None
 if package and (hasattr(package,'private_readiness_packet') or hasattr(package,'private_protection_packet')):raise ValidationError('Private readiness evidence needs its scoped native adapter')
 if package and (set(payload['process_ids'])!=set(package.payload['process_ids']) or package.payload['build_ref']!=payload['build_ref']):raise ValidationError('Exact AF13 build and process scope required')
 p=MigrationPlan.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,package=package,payload=payload,sha256=digest({'payload':payload,'package':package_id}),evidence=subject(c,evidence_id,'migration_plan'),actor=a)
 event(a,c,'migration.plan_captured',plan=p.pk,migration_executed=False);bump(c);return p

@transaction.atomic
def capture_proof(a,case_id,plan_id,evidence_id,expected=None):
 c=locked(a,case_id,'migration.capture',expected);p=plan_for(c,plan_id);e=subject(c,evidence_id);v=SuppliedMigrationEvidenceAdapter().read(e,PROOF,'migration_proof')
 if v['plan_id']!=p.pk or v['plan_sha256']!=p.sha256 or any(v[k]!=p.payload[k] for k in ['build_ref','source_ref','target_ref','source_version','target_version']):raise ValidationError('Proof must correlate exact plan/hash/build/source/target versions')
 if timestamp(v['recorded_at'])>timezone.now():raise ValidationError('Actual evidence cannot be future dated')
 if v['evidence_class']=='synthetic_report' and not c.synthetic:raise ValidationError('Synthetic reports cannot prove operational migration')
 key=digest({'tenant':c.tenant,**{k:v[k] for k in ['system','external_ref','receipt_version']}})
 with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[int(key[:15],16)])
 old=MigrationProof.objects.filter(tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],receipt_version=v['receipt_version']).first()
 if old:
  if old.plan_id!=p.pk or old.sha256!=digest(v):raise ValidationError('Source receipt identity already claimed or conflicting; retain history and investigate')
  return old
 r=MigrationProof.objects.create(plan=p,tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],receipt_version=v['receipt_version'],kind=v['kind'],payload=v,sha256=digest(v),evidence=e,actor=a)
 event(a,c,'migration.report_received',proof=r.pk,native_execution_verified=False);bump(c);return r

@transaction.atomic
def observe_inventory(a,case_id,plan_id,expected=None):
 c=locked(a,case_id,'migration.inventory',expected);p=plan_for(c,plan_id);current_plan(p)
 # Capture is independent of business policy; no target write or migration command is exposed.
 result=LocalEvidenceInventoryAdapter().read(a,p)
 o=MigrationObservation.objects.create(plan=p,payload=result,actor=a);event(a,c,'migration.inventory_read',observation=o.pk,migration_executed=False);bump(c);return o

def bounded_age(at,seconds):
 age=(timezone.now()-at).total_seconds();return 0<=age<=seconds
def snapshot(p):
 current_plan(p);policy,rules=config(p.case)
 if not set(p.payload['process_ids'])<=set(rules['process_ids']):raise ValidationError('Migration policy does not cover every selected process')
 proofs=[];findings=[]
 for kind in rules['required_kinds']:
  proof=MigrationProof.objects.filter(plan=p,kind=kind).order_by('-pk').first()
  proofs.append([kind,proof.pk if proof else None,proof.sha256 if proof else None])
  if not proof:findings.append('Missing '+kind+' evidence');continue
  readable(proof.actor,p.case);require(proof.actor,p.case,'migration.capture')
  if proof.system not in rules['proof_systems']:findings.append('Unconfigured '+kind+' source system')
  if proof.payload['outcome']!='passed':findings.append(kind+' report is failed or unknown')
  if not bounded_age(timestamp(proof.payload['recorded_at']),rules['max_age_seconds']):findings.append(kind+' evidence expired or future dated')
  if kind=='reconciliation' and (proof.payload['record_count'] is None or proof.payload['manifest_sha256'] is None or proof.payload['record_count']!=p.payload['expected_record_count'] or proof.payload['manifest_sha256']!=p.payload['expected_manifest_sha256']):findings.append('Reconciliation count/digest unknown or differs from declared inventory')
 o=MigrationObservation.objects.filter(plan=p).select_related('actor').order_by('-pk').first();inventory=None
 if rules['inventory_mode']!='local_evidence_manifest_v1':findings.append('Native inventory adapter unavailable for configured source mode')
 elif not o:findings.append('Current read-only inventory observation required')
 else:
  readable(o.actor,p.case);require(o.actor,p.case,'migration.inventory');inventory=o.pk
  if o.payload!=LocalEvidenceInventoryAdapter().read(o.actor,p):findings.append('Observed inventory changed')
  if not bounded_age(o.created_at,rules['max_age_seconds']):findings.append('Inventory observation expired')
  for field,observed in [('expected_record_count','record_count'),('expected_manifest_sha256','manifest_sha256')]:
   if p.payload[field] is None:findings.append(field+' remains unknown')
   elif p.payload[field]!=o.payload[observed]:findings.append(field+' differs from actual selected evidence')
 package=None
 if not p.package_id:findings.append('Exact AF13 operational-readiness package required')
 else:
  af.package_current(p.package)
  if p.package.payload['level']!='operational':findings.append('AF13 package must explicitly request operational scope')
  for field in ['manual_fallback','rollout_plan','migration_plan']:
   if not p.package.payload[field].strip():findings.append('AF13 '+field+' remains missing')
  if not p.package.payload['role_list']:findings.append('AF13 actual role list remains missing')
  if not p.package.payload['support_owner_id']:findings.append('AF13 support owner remains unknown')
  else:af.scoped_person(p.case,p.package.payload['support_owner_id'],'validation.support')
  if any(g['state']=='open' for g in p.package.payload['gaps']):findings.append('AF13 selected scope retains unresolved evidence gaps')
  if any(v['status']!='ACTIVE' for v in p.package.manifest['policies'].values()):findings.append('AF13 selected domain policies remain unavailable')
  package={'id':p.package_id,'sha256':p.package.sha256,'meaning':af.approved_review(p.package,'meaning').pk,'expectations':af.approved_review(p.package,'expectations').pk}
 return {'plan':p.pk,'plan_sha256':p.sha256,'policy':policy.pk,'proofs':proofs,'inventory':inventory,'package':package},rules,findings

@transaction.atomic
def assess(a,case_id,plan_id,expected=None):
 c=locked(a,case_id,'migration.assess',expected);p=plan_for(c,plan_id);pins,_,findings=snapshot(p)
 result={'documentary_complete':not findings,'findings':findings,'native_inventory_read':pins['inventory'] is not None,'native_migration_execution_verified':False,'native_restore_verified':False,'operational_ready':False,'deployment_authorized':False,'whole_product_accepted':False,'coverage':'Exact selected plan/processes/build and evidence metadata; supplied execution/restore reports remain unverified'}
 r=MigrationAssessment.objects.create(plan=p,snapshot=pins,result=result,actor=a);event(a,c,'migration.assessed',assessment=r.pk,operational_ready=False);bump(c);return r

def current_assessment(r):
 p=r.plan;readable(r.actor,p.case);require(r.actor,p.case,'migration.assess')
 latest=MigrationAssessment.objects.filter(plan=p).order_by('-pk').first()
 if not latest or latest.pk!=r.pk:raise ValidationError('A newer assessment is current')
 pins,rules,findings=snapshot(p)
 if pins!=r.snapshot or findings!=r.result['findings']:raise ValidationError('Plan, policy, evidence, inventory, source access or AF13 review changed; reassess')
 return rules

def authority(a,r,purpose):
 readable(a,r.plan.case);require(a,r.plan.case,'migration.review');require(a,r.plan.case,'migration.evidence.read');_,rules=config(r.plan.case)
 row=next((x for x in rules['assignments'] if x['purpose']==purpose and x['user_id']==a.pk),None)
 if not row:raise PermissionDenied('Configured exact readiness reviewer required; admin/source text confers no authority')
 preparers={r.plan.actor_id,r.actor_id};preparers.update(MigrationProof.objects.filter(plan=r.plan).values_list('actor_id',flat=True));preparers.update(MigrationObservation.objects.filter(plan=r.plan).values_list('actor_id',flat=True))
 if purpose=='independent' or not rules['allow_owner_preparer_review']:
  if a.pk in preparers:raise PermissionDenied('Independent readiness reviewer cannot prepare this plan/evidence/assessment')
 return decision_authority(a,r.plan.case,row['role'])
def latest_review(r,purpose):return MigrationReadinessReview.objects.filter(assessment=r,purpose=purpose).order_by('-pk').first()
def review_inputs(r,purpose):
 current_assessment(r)
 if not r.result['documentary_complete']:raise ValidationError('Documentary/inventory gaps require resolution before readiness review')
 v={'assessment':r.pk,'snapshot_sha256':digest(r.snapshot)}
 if purpose=='independent':v['owner_review']=approved_review(r,'owner').pk
 return v
def approved_review(r,purpose):
 row=latest_review(r,purpose)
 if not row or row.verdict!='approve':raise ValidationError('Current '+purpose+' migration-readiness review required')
 if row.authority!=authority(row.actor,r,purpose) or row.snapshot!=review_inputs(r,purpose):raise ValidationError('Readiness review authority or inputs changed')
 return row

@transaction.atomic
def review(a,case_id,assessment_id,purpose,verdict,operation_key,evidence_id,reason,expected=None):
 c=locked(a,case_id,'migration.review',expected);r=MigrationAssessment.objects.select_related('plan__case','plan__package__case').filter(plan__case=c,pk=assessment_id).first()
 if not r or purpose not in ['owner','independent'] or verdict not in ['approve','return','reject','withdraw']:raise ValidationError('Exact case assessment, review purpose and verdict required')
 validate(KEY,operation_key)
 if not isinstance(reason,str) or not 1<=len(reason.strip())<=1000:raise ValidationError('Bounded actual readiness rationale required')
 e=subject(c,evidence_id,'migration_review');old=MigrationReadinessReview.objects.filter(assessment=r,operation_key=operation_key).first()
 if old:
  if (old.actor_id,old.purpose,old.verdict,old.evidence_id,old.reason)!=(a.pk,purpose,verdict,e.pk,reason):raise ValidationError('Readiness operation key conflicts with recorded intent')
  return old
 auth=authority(a,r,purpose);pins=review_inputs(r,purpose) if verdict=='approve' else {'assessment':r.pk}
 row=MigrationReadinessReview.objects.create(assessment=r,purpose=purpose,verdict=verdict,operation_key=operation_key,snapshot=pins,authority=auth,evidence=e,reason=reason,actor=a)
 event(a,c,'migration.readiness_reviewed',review=row.pk,operational_acceptance=False);bump(c);return row

@transaction.atomic
def bind(a,case_id,assessment_id,expected=None):
 c=locked(a,case_id,'migration.bind',expected);r=MigrationAssessment.objects.select_related('plan__case','plan__package__case').filter(plan__case=c,pk=assessment_id).first()
 if not r or not r.plan.package_id:raise ValidationError('Exact case assessment with AF13 package required')
 af.owner_authority(a,r.plan.package,'acceptance')
 owner=approved_review(r,'owner');independent=approved_review(r,'independent');pins={'assessment':r.pk,'owner_review':owner.pk,'independent_review':independent.pk,'package_sha256':r.plan.package.sha256}
 old=MigrationAF13Binding.objects.filter(assessment=r,package=r.plan.package).first()
 if old:
  if old.snapshot!=pins:raise ValidationError('Binding inputs changed; reassess and bind a new assessment')
  return old
 b=MigrationAF13Binding.objects.create(assessment=r,package=r.plan.package,snapshot=pins,actor=a);event(a,c,'migration.af13_bound',binding=b.pk,operational_acceptance=False);bump(c);return b

@transaction.atomic
def report(a,case_id,assessment_id):
 c=locked(a,case_id,'migration.read');r=MigrationAssessment.objects.select_related('plan__case','plan__package__case').filter(plan__case=c,pk=assessment_id).first()
 if not r:raise ValidationError('Exact case readiness assessment required')
 holds=[];reviews={}
 try:current_assessment(r)
 except (ValidationError,PermissionDenied) as exc:holds.append(str(exc))
 for purpose in ['owner','independent']:
  try:reviews[purpose]={'current':True,'id':approved_review(r,purpose).pk}
  except (ValidationError,PermissionDenied):reviews[purpose]={'current':False,'id':None}
 return {'assessment':r.pk,'plan':r.plan_id,'result':r.result,'holds':holds,'reviews':reviews,'documentary_readiness_reviewed':not holds and all(v['current'] for v in reviews.values()),'operational_ready':False,'deployment_authorized':False,'native_migration_execution_verified':False}

def package_readiness(p,actor=None):
 b=p.migration_bindings.select_related('assessment__plan__case','assessment__plan__package__case').order_by('-pk').first()
 if not b:return {'status':'not_bound','operational_ready':False}
 if actor is None:return {'status':'scoped_read_required','operational_ready':False}
 try:readable(actor,p.case)
 except PermissionDenied:return {'status':'access_required','operational_ready':False}
 try:
  value=report(actor,p.case_id,b.assessment_id)
  af.owner_authority(b.actor,p,'acceptance')
  expected={'assessment':b.assessment_id,'owner_review':approved_review(b.assessment,'owner').pk,'independent_review':approved_review(b.assessment,'independent').pk,'package_sha256':p.sha256}
  if expected!=b.snapshot:raise ValidationError('Migration binding changed')
  return {'status':'documentary_reviewed' if value['documentary_readiness_reviewed'] else 'held','binding':b.pk,**value}
 except PermissionDenied:return {'status':'stale_or_held','operational_ready':False}
 except ValidationError:return {'status':'stale_or_held','operational_ready':False}
