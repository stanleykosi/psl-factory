"""Native private restore capability binding; shared readiness owns durable execution."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from apps.identity.services import require
from apps.documents.contracts import digest
from adapters.private_protection_readiness import PrivateProtectionReadinessAdapter as Adapter
from .readiness_models import PrivateProtectionReadiness as Binding

FIELD='private_protection_job_ids'

def binding(contract):
 return Binding.objects.select_related('contract__case','job__plan__case').filter(contract=contract).first()

def access(actor,b):
 for old in Binding.objects.filter(contract__case=b.contract.case,contract__reference=b.contract.reference).select_related('job__plan__case'):
  Adapter().access(actor,old.job)

def prepare(actor,c,pk,payload):
 j=Adapter().job(c,pk);value=Adapter().describe(actor,j)
 if payload['kind']!='adapter' or payload['family']!='protection' or payload['implementation']!='internal_postgres_session_v1' or set(payload['capabilities'])!={'health','receipt_lookup'} or payload['target_key']!='internal:protection':raise ValidationError('Private protection requires exact internal health/receipt contract')
 return j,value

def bind(actor,contract,context):
 j,value=context
 return Binding.objects.create(contract=contract,job=j,actor=actor,snapshot=value,sha256=digest(value))

def check(actor,contract):
 b=binding(contract)
 if not b:return None
 access(actor,b)
 if b.snapshot!=Adapter().describe(actor,b.job) or b.sha256!=digest(b.snapshot):raise ValidationError('Exact private protection provenance changed')
 return b

def validate_policy(c,v,runtime=False):
 for pk in v[FIELD]:Adapter().job(c,pk)
 if not v['independent_review'] or not v['require_receipt_probe'] or v['probe_user_id']==v['reviewer_id']:raise ValidationError('Private protection requires independent humans and receipt probes')
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
 if b and (b.job_id not in v.get(FIELD,[]) or not v['require_receipt_probe'] or not v['independent_review'] or v['probe_user_id']==v['reviewer_id']):raise ValidationError('Configure independent exact private protection inventory and independent receipt review')
 return b

def intent(actor,contract,kind,source_id):
 b=check(actor,contract)
 if not b:return None
 if kind=='evaluation' or kind=='receipt' and source_id!=b.job_id:raise ValidationError('Exact enrolled private protection source required')
 Adapter().current(actor,b.job)
 return {'binding':b.pk,'sha256':b.sha256,'source':b.snapshot}

def observation(contract,job,base):
 b=check(job.actor,contract)
 if not b:return None
 value=dict(base,native_protection={'binding':b.pk,'sha256':b.sha256,'source':b.snapshot})
 if job.intent['kind']=='receipt':value['receipt_provenance']=Adapter().receipts(b.job)
 return value

def findings(contract,head):
 b=check(head.actor,contract)
 if not b:return []
 Adapter().current(head.actor,b.job)
 pin={'binding':b.pk,'sha256':b.sha256,'source':b.snapshot}
 if head.job.intent.get('native_protection')!=pin or head.payload.get('native_protection')!=pin:return ['Private protection observation provenance changed']
 if head.payload['kind']=='receipt' and head.payload.get('receipt_provenance')!=Adapter().receipts(b.job):return ['Private protection receipt changed; fresh probe/review required']
 return []

def visible_jobs(actor,c):
 from .operator_models import RecoveryJob
 ids=[]
 for j in RecoveryJob.objects.filter(plan__case=c,kind='restore',plan__payload__has_key='private_readiness_packet_ids').exclude(plan__payload__has_key='private_protection_packet_ids').select_related('plan__case'):
  try:Adapter().access(actor,j)
  except PermissionDenied:continue
  ids.append(j.pk)
 return RecoveryJob.objects.filter(pk__in=ids)

def selection(c,source_job=None):
 from .readiness_models import IntegrationSelection
 q=IntegrationSelection.objects.select_related('contract__case').filter(case=c,family='protection')
 from .private_readiness_operations import private_job
 if source_job is None or not private_job(c,source_job):return q.filter(contract__private_protection_readiness__isnull=True,contract__private_file_readiness__isnull=True,contract__accepted_protection_readiness__isnull=True).order_by('-version').first()
 return q.filter(contract__private_protection_readiness__job_id=source_job).order_by('-version').first()

def investigate(actor,c):
 from . import readiness as d
 from apps.policy.services import resolve
 from apps.policy.readiness_validators import PRIVATE_COMPONENT
 require(actor,c,'agent.integrations');d.readable(actor,c,True);rows=[];status=resolve(PRIVATE_COMPONENT,c).status
 for b in Binding.objects.filter(contract__case=c).order_by('-pk')[:30]:
  try:
   access(actor,b);a=d.IntegrationAssessment.objects.filter(contract=b.contract).order_by('-pk').first();v=d.report(actor,c.pk,a.pk) if a else None
  except PermissionDenied:continue
  probes=list(d.IntegrationProbe.objects.filter(contract=b.contract).order_by('-pk').values('id','status','intent__kind')[:10])
  question='Refresh exact source/owner acceptance, health, receipt and independent review when held.'
  if status!='ACTIVE':question='Configure and validate the independent private protection readiness inventory/principals/criteria.'
  if any(p['status']=='unknown' for p in probes):question='Reconcile the original committed observation before retry; preserve the original attempt budget.'
  rows.append({'policy_status':status,'probes':probes,'contract':b.contract_id,'restore_job':b.job_id,'review_current':bool(v and v['review_current']),'question':question,'current_authority_restored':False})
 return {'findings':rows,'effect_tools':[],'persisted_agent_run':False}
