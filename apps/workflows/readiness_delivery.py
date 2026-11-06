from datetime import timedelta
from apps.finance.acceptance_evaluation import evaluated
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from adapters.forecast import KEY
from adapters.readiness import ReadinessAdapter,binding
from . import readiness as d
from .readiness_models import IntegrationProbe,IntegrationObservation

@evaluated
def intent(a,r,kind,source_id):
 d.current_contract(r);auth=d.authority(a,r,'probe');p,v=d.rules(r);b,_=binding(r)
 if kind not in ['health','receipt','evaluation'] or {'health':'health','receipt':'receipt_lookup','evaluation':'evaluation'}[kind] not in r.payload['capabilities']:raise ValidationError('Declared reviewed probe capability required')
 if b['classification']=='synthetic_authenticated_http' and not v['allow_synthetic_target']:raise ValidationError('Synthetic target is not permitted')
 if kind=='receipt':d.source_job(a,r.case,r.payload['family'],source_id,r)
 elif source_id is not None:raise ValidationError('Only receipt probes take a scoped source job')
 if r.payload['kind']=='adapter':
  from .operator_inventory import ROUTES
  from apps.identity.services import require
  require(a,r.case,ROUTES[r.payload['family']][2])
 if kind=='evaluation' and r.payload['kind']!='provider':raise ValidationError('Provider canary only')
 from apps.finance.publication_readiness import intent as native_intent,binding as native_binding
 native=native_intent(a,r,kind,source_id)
 if kind=='receipt' and r.payload['family']=='publication' and not native_binding(r):
  from apps.finance.accepted_documents import binding as document_binding
  if document_binding(d.source_job(a,r.case,'publication',source_id).publication.version):raise ValidationError('Native Finance receipt requires exact native contract enrollment')
 value={'contract':r.sha256,'kind':kind,'source_job':source_id,'authority':auth,'binding':b,'lease_seconds':v['lease_seconds'],'max_attempts':v['max_attempts']}
 if native:value['native_publication']=native
 from .private_protection_readiness import intent as private_intent
 private=private_intent(a,r,kind,source_id)
 if private:value['native_protection']=private
 from .private_file_readiness import intent as file_intent
 file=file_intent(a,r,kind,source_id)
 if file:value['native_file']=file
 from .accepted_protection_readiness import intent as accepted_intent
 accepted=accepted_intent(a,r,kind,source_id)
 if accepted:value['native_accepted_protection']=accepted
 return value
@transaction.atomic
def reserve(a,case_id,contract_id,key,kind,source_id=None,expected=None):
 c=d.locked(a,case_id,'integration.probe',expected);r=d.contract_for(c,contract_id);validate(KEY,key);v=intent(a,r,kind,source_id);old=IntegrationProbe.objects.filter(contract=r,intent_key=key).first()
 if old:
  if old.actor_id!=a.pk or old.intent!=v:raise ValidationError('Probe intent changed; use a new reviewed key')
  return old
 j=IntegrationProbe.objects.create(contract=r,intent_key=key,operation_key=digest({'case':str(c.pk),'contract':r.pk,'key':key}),intent=v,actor=a);d.audit(a,c,'integration.probe_reserved',r,job=j.pk);bump(c);return j
@transaction.atomic
def claim(case_id=None):
 now=timezone.now();query=IntegrationProbe.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now))
 if case_id is not None:query=query.filter(contract__case_id=case_id)
 j=query.order_by('pk').first()
 if not j:return None
 j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence
def fence(j,f):
 if j.status!='leased' or j.fence!=f or j.lease_until<=timezone.now():raise ValidationError('Expired readiness worker fence')
@transaction.atomic
@evaluated
def execute(pk,f,adapter):
 initial=IntegrationProbe.objects.select_related('contract').get(pk=pk);d.lock_scope(initial.contract.case_id);c=Case.objects.select_for_update().get(pk=initial.contract.case_id);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));j=IntegrationProbe.objects.select_for_update().select_related('contract__case','actor').get(pk=pk);fence(j,f)
 if intent(j.actor,j.contract,j.intent['kind'],j.intent['source_job'])!=j.intent:raise ValidationError('Readiness context changed')
 value=adapter.probe(j);fence(j,f);return persist(j,value)
def persist(j,value):
 value=dict(value,observed_at=value.get('observed_at',timezone.now().isoformat()));old=IntegrationObservation.objects.filter(job=j).first()
 if old:return old.payload
 IntegrationObservation.objects.create(contract=j.contract,job=j,external_key='native:'+j.operation_key,payload=value,sha256=digest(value),actor=j.actor);return value
@transaction.atomic
def finish(pk,f,status,value=None):
 initial=IntegrationProbe.objects.select_related('contract').get(pk=pk);Case.objects.select_for_update().get(pk=initial.contract.case_id);j=IntegrationProbe.objects.select_for_update().get(pk=pk);fence(j,f)
 if status=='confirmed':persist(j,value)
 j.status=status;j.save(update_fields=['status']);d.audit(j.actor,j.contract.case,'integration.probe_'+status,j.contract,job=j.pk)
def complete(pk,f,status,value=None):
 try:finish(pk,f,status,value)
 except ValidationError:
  j=IntegrationProbe.objects.get(pk=pk)
  if j.status=='leased' and j.fence==f and j.lease_until>timezone.now():raise

def run_once(adapter=None,case_id=None):
 adapter=adapter or ReadinessAdapter();lease=claim(case_id)
 if not lease:return False
 pk,f=lease;j=IntegrationProbe.objects.select_related('contract__case','actor').get(pk=pk)
 if type(adapter) is not ReadinessAdapter and not j.contract.case.synthetic:complete(pk,f,'held');return True
 try:
  old=adapter.lookup(j)
  if old:complete(pk,f,'confirmed',old);return True
  if j.attempts>j.intent['max_attempts']:complete(pk,f,'held');return True
  value=execute(pk,f,adapter)
 except (ConnectionError,TimeoutError):complete(pk,f,'unknown')
 except (ValidationError,PermissionDenied,ValueError,OSError):complete(pk,f,'held')
 else:complete(pk,f,'confirmed',value)
 return True
@transaction.atomic
def operate(a,case_id,pk,operation,reason,expected=None):
 c=d.locked(a,case_id,'integration.operate',expected);j=IntegrationProbe.objects.select_for_update().select_related('contract__case').filter(pk=pk,contract__case=c).first()
 if not j or operation not in ['retry','cancel'] or not isinstance(reason,str) or not 1<=len(reason.strip())<=400:raise ValidationError('Exact job/action and bounded reason required')
 d.authority(a,j.contract,'probe')
 if j.status in ['confirmed','cancelled'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Proven/terminal/active work cannot change')
 if ReadinessAdapter().lookup(j):raise ValidationError('Committed probe receipt exists; worker must reconcile')
 if j.status=='unknown':raise ValidationError('Unknown provider outcomes require receipt-first worker lookup')
 if operation=='retry':
  if j.status!='held' or j.actor_id!=a.pk or intent(a,j.contract,j.intent['kind'],j.intent['source_job'])!=j.intent:raise ValidationError('Changed intent requires a new key, preserving old history')
  from apps.finance.publication_readiness import binding as native_binding
  from .private_protection_readiness import binding as private_binding
  from .private_file_readiness import binding as file_binding
  from .accepted_protection_readiness import binding as accepted_binding
  if native_binding(j.contract) or private_binding(j.contract) or file_binding(j.contract) or accepted_binding(j.contract):
   if j.attempts>=j.intent['max_attempts']:raise ValidationError('Native readiness original attempt budget exhausted')
   j.status='pending'
  else:j.status='pending';j.attempts=0
 else:j.status='cancelled'
 j.save(update_fields=['status','attempts']);d.audit(a,c,'integration.operator_'+operation,j.contract,job=j.pk,reason=reason);bump(c);return j
