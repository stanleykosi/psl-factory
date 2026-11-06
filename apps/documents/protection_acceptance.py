"""Private protection capability evidence attached to separately reviewed AF13 scope."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.documents import validation as af
from apps.documents.contracts import digest,validate
from apps.core.services import event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values
from apps.policy.protection_acceptance_validators import COMPONENT as ACCEPTANCE,OWNER
from apps.workflows.readiness_models import IntegrationAssessment
from adapters.forecast import KEY
from adapters.protection_acceptance import ProtectionAcceptanceAdapter as Adapter
from .protection_models import PrivateProtectionPacket as Packet
from apps.finance import acceptance_evaluation as evaluation

def binding(p):return Packet.objects.select_related('case','package','actor','assessment__contract__case').filter(package=p).first()

def package_access(a,p):
 b=binding(p)
 if not b:return
 # Every historical reference participant remains private after succession.
 for old in Packet.objects.filter(case=b.case,reference=b.reference).select_related('assessment__contract__case'):
  Adapter().access(a,old.assessment)

def scope(p):
 if p.finance_handoffs.exists() or hasattr(p,'private_readiness_packet') or set([OWNER,ACCEPTANCE])&set(p.payload['policy_components']) or 'F01' not in p.payload['process_ids'] or not set(p.payload['process_ids'])<=set(['F01','B13','P13','P15']):raise ValidationError('Separate nonrecursive native F01/AF13 validation scope required')
 if p.payload['level']=='operational':raise ValidationError('Capability evidence cannot establish operational acceptance')

def assessment_for(c,pk):
 row=IntegrationAssessment.objects.select_related('contract__case','actor').filter(pk=pk,contract__case=c).first()
 if row is None:raise ValidationError('Exact case private protection assessment required')
 return row

@transaction.atomic
@evaluation.evaluated
def prepare(a,case_id,assessment_id,package_id,reference,predecessor=None,expected=None,native_kind="restore"):
 c=af.locked(a,case_id,'validation.package.prepare',expected);require(a,c,'integration.source.read');validate(KEY,reference)
 p=af.package_for(c,package_id);scope(p);af.package_current(p);assessment=assessment_for(c,assessment_id)
 source=Adapter().access(a,assessment)
 if native_kind not in ['restore','export','backup'] or source.job.kind!=native_kind:raise ValidationError('Explicit matching native evidence kind required; file evidence is not restore proof')
 value={'package':p.pk,'package_sha256':p.sha256,'evidence':Adapter().read(a,assessment)}
 old=Packet.objects.filter(case=c,reference=reference).order_by('-version').first()
 if old:
  package_access(a,old.package)
  if old.snapshot==value and predecessor in [None,old.parent_id]:return old
 if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit latest private packet predecessor required')
 if p.reviews.exists() or Packet.objects.filter(package=p).exists():raise ValidationError('Use a fresh unreviewed package for private evidence binding')
 # A package with private proof cannot later be relabelled a Finance source handoff.
 b=Packet.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,parent=old,package=p,assessment=assessment,actor=a,snapshot=value,sha256=digest(value))
 evaluation.changed();event(a,c,'agent.data.protection_acceptance_packet',packet=b.pk);bump(c);return b

def validate_inventory(c,v,runtime=False):
 from django.contrib.auth import get_user_model
 pairs=v['private_protection']['inventory'];owners=reference_values(active_component(OWNER,c))[0]
 for pair in pairs:
  p=af.package_for(c,pair['package_id']);scope(p);assessment=assessment_for(c,pair['assessment_id'])
  existing=binding(p)
  if existing and existing.assessment_id!=assessment.pk:raise ValidationError('Acceptance inventory must match the bound private protection assessment')
  if p.actor is None:raise ValidationError('Actual package preparer required')
  for purpose in ['meaning','expectations','acceptance']:
   covered={pid for row in owners['assignments'] if purpose in row['purposes'] for pid in row['process_ids']}
   if not set(p.payload['process_ids'])<=covered:raise ValidationError('Protection owner authority must cover every selected process and purpose')
  try:source=Adapter().access(p.actor,assessment)
  except PermissionDenied:raise ValidationError('Actual private source grants required for package preparer') from None
  if pair.get('native_kind','restore')!=source.job.kind:raise ValidationError('Acceptance inventory requires exact explicit native kind; v1 is restore only')
  if not runtime:
   try:
    Adapter().access(p.actor,assessment)
    for row in owners['assignments']:
     if set(row['process_ids'])&set(p.payload['process_ids']):Adapter().access(get_user_model().objects.get(pk=row['user_id']),assessment)
   except PermissionDenied:raise ValidationError('Actual private source grants required for configured owners') from None
 keys=[x['package_id'] for x in pairs]
 if len(keys)!=len(set(keys)):raise ValidationError('One exact assessment per configured package required')

def current(b,a):
 return evaluation.confirmed(b.case_id,('private_protection',b.pk,a.pk),lambda:_current(b,a))

def _current(b,a):
 package_access(a,b.package);scope(b.package);af.package_current(b.package)
 if Packet.objects.filter(case=b.case,reference=b.reference,version__gt=b.version).exists():raise ValidationError('Private protection packet superseded')
 require(b.actor,b.case,'validation.package.prepare');Adapter().access(b.actor,b.assessment)
 value={'package':b.package_id,'package_sha256':b.package.sha256,'evidence':Adapter().read(a,b.assessment)}
 if value!=b.snapshot or b.sha256!=digest(b.snapshot):raise ValidationError('Private protection evidence changed; prepare a reviewed successor')
 config=active_component(ACCEPTANCE,b.case);v=reference_values(config)[0];rules=v.get('private_protection')
 kind=value['evidence'].get('job_kind','restore')
 if not rules or not any(pair['package_id']==b.package_id and pair['assessment_id']==b.assessment_id and pair.get('native_kind','restore')==kind for pair in rules['inventory']):raise ValidationError('Configure exact independent private protection acceptance inventory and native kind')
 if not 0<=(timezone.now()-b.created_at).total_seconds()<=rules['freshness_seconds']:raise ValidationError('Private protection packet expired')
 if rules['receipt_requirement']=='found' and value['evidence']['receipt_state']!='found':raise ValidationError('Configured committed native receipt evidence required')
 return {'packet':b.pk,'sha256':b.sha256,'acceptance_policy':config.pk,'assessment':b.assessment_id}

def review_pins(p,a,kind):
 b=binding(p)
 if b is None:return None
 value=current(b,a)
 if kind=='acceptance':
  evidence=b.snapshot['evidence'];preparers={b.actor_id,b.assessment.actor_id,b.assessment.contract.actor_id,evidence['transport_reviewer']}
  from apps.workflows.readiness_models import IntegrationObservation
  preparers.update(IntegrationObservation.objects.filter(pk__in=[x['observation'] for x in evidence['observations']]).values_list('actor_id',flat=True))
  if a.pk in preparers:raise PermissionDenied('AF13 acceptor must be independent of packet and transport evidence preparation/review')
 return value

def visible(a,c):
 ids=[]
 for b in Packet.objects.filter(case=c).select_related('package'):
  try:package_access(a,b.package)
  except PermissionDenied:continue
  ids.append(b.pk)
 return Packet.objects.filter(pk__in=ids)

@transaction.atomic
@evaluation.evaluated
def report(a,case_id,pk):
 c=af.locked(a,case_id,'validation.read');b=Packet.objects.select_related('package__case','assessment__contract__case','actor').filter(case=c,pk=pk).first()
 if b is None:raise ValidationError('Exact case private protection packet required')
 package_access(a,b.package)
 try:current(b,a);ready=True
 except (ValidationError,PermissionDenied,ConnectionError):ready=False
 return {'packet':b.pk,'version':b.version,'parent':b.parent_id,'package':b.package_id,'assessment':b.assessment_id,'sha256':b.sha256,'metadata':b.snapshot,'evidence_current':ready,'status':af.position(b.package,a),'whole_product_accepted':False,'operational_accepted':False,'deployment_authorized':False}

@transaction.atomic
@evaluation.evaluated
def investigate(a,case_id):
 c=af.locked(a,case_id,'agent.validation');rows=[]
 for b in visible(a,c).order_by('-pk')[:30]:
  value=report(a,c.pk,b.pk);rows.append({'packet':b.pk,'native_kind':b.snapshot['evidence'].get('job_kind','restore'),'receipt_state':b.snapshot['evidence']['receipt_state'],'evidence_current':value['evidence_current'],'reviews':value['status']['reviews'],'question':'Confirm exact capability scope and receipt criteria with configured owners; refresh superseded proof through a new package. Operational acceptance needs separate evidence.'})
 return {'findings':rows,'business_effect_tools':[],'persisted_agent_run':False}

@transaction.atomic
@evaluation.evaluated
def export(a,case_id,pk):
 c=af.locked(a,case_id,'validation.export');b=Packet.objects.select_related('package__case','assessment__contract__case','actor').filter(case=c,pk=pk).first()
 if b is None:raise ValidationError('Exact case private protection packet required')
 package_access(a,b.package);pins=current(b,a);acceptance=af.approved_review(b.package,'acceptance')
 return {'full_database_backup':False,'full_database_export':False,'packet':b.pk,'sha256':b.sha256,'package':b.package_id,'process_ids':b.package.payload['process_ids'],'level':b.package.payload['level'],'acceptance_review':acceptance.pk,'acceptor':acceptance.actor_id,'pins':pins,'evidence':b.snapshot['evidence'],'scope':'selected AF13 evidence only','payload_bodies_included':False,'current_authority_restored':False,'full_database_restore':False,'native_quickbooks_verified':False,'operational_acceptance':False,'whole_product_accepted':False,'deployment_authorized':False}
