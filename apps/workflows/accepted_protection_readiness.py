"""Native accepted AF13 protection capability binding; shared readiness owns durable execution."""
from django.db import transaction
from apps.finance.acceptance_evaluation import evaluated
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from apps.identity.services import require
from apps.documents.contracts import digest
from adapters.accepted_protection_readiness import AcceptedProtectionReadinessAdapter as Adapter
from .readiness_models import AcceptedProtectionReadiness as Binding

FIELD='accepted_protection_job_ids'

def binding(contract):
 return Binding.objects.select_related('contract__case','job__plan__case').filter(contract=contract).first()

def access(actor,b):
 for old in Binding.objects.filter(contract__case=b.contract.case,contract__reference=b.contract.reference).select_related('job__plan__case'):
  Adapter().access(actor,old.job)

def prepare(actor,c,pk,payload):
 j=Adapter().job(c,pk);value=Adapter().describe(actor,j)
 if payload['kind']!='adapter' or payload['family']!='protection' or payload['implementation']!='internal_postgres_session_v1' or set(payload['capabilities'])!={'health','receipt_lookup'} or payload['target_key']!='internal:protection':raise ValidationError('AF13 protection requires exact internal health/receipt contract')
 return j,value

def bind(actor,contract,context):
 j,value=context
 return Binding.objects.create(contract=contract,job=j,actor=actor,snapshot=value,sha256=digest(value))

def check(actor,contract):
 b=binding(contract)
 if not b:return None
 access(actor,b)
 if b.snapshot!=Adapter().describe(actor,b.job) or b.sha256!=digest(b.snapshot):raise ValidationError('Exact AF13 protection provenance changed')
 return b

def validate_policy(c,v,runtime=False):
 for pk in v[FIELD]:
  j=Adapter().job(c,pk)
  if j.actor_id==v['reviewer_id']:raise ValidationError('Independent native reviewer cannot prepare the source operator intent')
 if not v['independent_review'] or not v['require_receipt_probe'] or v['probe_user_id']==v['reviewer_id']:raise ValidationError('AF13 protection requires independent humans and receipt probes')
 if not runtime:
  try:
   for key in ['probe_user_id','reviewer_id']:
    a=get_user_model().objects.filter(pk=v[key],is_active=True).first()
    if not a:raise ValidationError('Actual active private readiness principal required')
    for pk in v[FIELD]:Adapter().access(a,Adapter().job(c,pk))
    require(a,c,'integration.read');require(a,c,'integration.source.read')
  except PermissionDenied:raise ValidationError('Actual original private source/export grants required') from None

def policy(contract,v):
 b=binding(contract)
 if b and (b.job_id not in v.get(FIELD,[]) or not v['require_receipt_probe'] or not v['independent_review'] or v['probe_user_id']==v['reviewer_id']):raise ValidationError('Configure independent exact AF13 protection inventory and independent receipt review')
 return b

def intent(actor,contract,kind,source_id):
 b=check(actor,contract)
 if not b:return None
 if kind=='evaluation' or kind=='receipt' and source_id!=b.job_id:raise ValidationError('Exact enrolled AF13 protection source required')
 Adapter().current(actor,b.job)
 return {'binding':b.pk,'sha256':b.sha256,'source':b.snapshot}

def observation(contract,job,base):
 b=check(job.actor,contract)
 if not b:return None
 value=dict(base,native_accepted_protection={'binding':b.pk,'sha256':b.sha256,'source':b.snapshot})
 if job.intent['kind']=='receipt':value['accepted_protection_receipt']=Adapter().receipts(b.job)
 return value

def findings(contract,head):
 b=check(head.actor,contract)
 if not b:return []
 Adapter().current(head.actor,b.job)
 pin={'binding':b.pk,'sha256':b.sha256,'source':b.snapshot}
 if head.job.intent.get('native_accepted_protection')!=pin or head.payload.get('native_accepted_protection')!=pin:return ['AF13 protection observation provenance changed']
 if head.payload['kind']=='receipt' and head.payload.get('accepted_protection_receipt')!=Adapter().receipts(b.job):return ['AF13 protection receipt changed; fresh probe/review required']
 return []

def visible_jobs(actor,c):
 from .operator_models import RecoveryJob
 ids=[]
 for j in RecoveryJob.objects.filter(plan__case=c,kind__in=['export','backup','restore'],plan__payload__has_key='private_protection_packet_ids').select_related('plan__case'):
  try:Adapter().access(actor,j)
  except PermissionDenied:continue
  ids.append(j.pk)
 return RecoveryJob.objects.filter(pk__in=ids).select_related('plan')

def selection(c,source_job=None):
 from .readiness_models import IntegrationSelection
 if source_job is None:return None
 return IntegrationSelection.objects.select_related('contract__case').filter(case=c,family='protection',contract__accepted_protection_readiness__job_id=source_job).order_by('-version').first()

@transaction.atomic
@evaluated
def investigate(actor,c):
 from . import readiness as d
 from apps.policy.services import resolve
 from apps.policy.readiness_validators import ACCEPTED_COMPONENT as PRIVATE_COMPONENT
 d.locked(actor,c.pk,'agent.integrations');d.readable(actor,c,True);rows=[];status=resolve(PRIVATE_COMPONENT,c).status
 for b in Binding.objects.filter(contract__case=c).order_by('-pk')[:30]:
  try:
   access(actor,b);a=d.IntegrationAssessment.objects.filter(contract=b.contract).order_by('-pk').first();v=d.report(actor,c.pk,a.pk) if a else None
  except PermissionDenied:continue
  probes=list(d.IntegrationProbe.objects.filter(contract=b.contract).order_by('-pk').values('id','status','intent__kind')[:10])
  question='Refresh exact source/owner acceptance, health, receipt and independent review when held.'
  if status!='ACTIVE':question='Configure and validate the independent AF13 protection readiness inventory/principals/criteria.'
  if any(p['status']=='unknown' for p in probes):question='Reconcile the original committed observation before retry; preserve the original attempt budget.'
  try:receipt_state=Adapter().receipts(b.job)['receipt']['state']
  except (ValidationError,ConnectionError,OSError):receipt_state='unavailable_or_conflicting'
  recovery=receipt_state=='found' and b.job.status in ['pending','unknown','leased']
  if recovery:question='Reconcile the exact committed source metadata receipt through operator recovery before any new effect; preserve its original attempt budget.'
  elif receipt_state=='unavailable_or_conflicting':question='Inspect the reserved sealed bytes and receipt lineage; preserve history and do not overwrite conflicting evidence.'
  rows.append({'source_status':b.job.status,'receipt_state':receipt_state,'source_receipt_recovery_needed':recovery,'policy_status':status,'probes':probes,'contract':b.contract_id,'operator_job':b.job_id,'job_kind':b.job.kind,'review_current':bool(v and v['review_current']),'question':question,'current_authority_restored':False})
 return {'findings':rows,'effect_tools':[],'persisted_agent_run':False,'readiness_scope':'exact_job_native_health_and_receipt_only','operational_ready':False,'deployment_authorized':False}
