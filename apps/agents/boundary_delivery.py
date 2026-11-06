from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.models import Grant
from apps.documents.contracts import digest
from adapters.private_evidence import PrivateEvidenceAdapter
from . import boundary as d

@transaction.atomic
def claim(case_id=None):
 now=timezone.now();q=d.Job.objects.select_for_update(of=('self',),skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now))
 if case_id is not None:q=q.filter(projection__case_id=case_id)
 j=q.order_by('pk').first()
 if not j:return None
 j.status='leased';j.attempts+=1;j.fence+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','attempts','fence','lease_until']);return j.pk,j.fence

def fenced(j,f):
 if j.status!='leased' or j.fence!=f or j.lease_until<=timezone.now():raise ValidationError('Expired data worker fence')

@transaction.atomic
def execute(pk,f):
 initial=d.Job.objects.select_related('projection').get(pk=pk);d.lock_scope(initial.projection.case_id);c=Case.objects.select_for_update().get(pk=initial.projection.case_id);d.lock_principals(c)
 j=d.Job.objects.select_for_update().select_related('projection__case','projection__evidence','actor').get(pk=pk);fenced(j,f)
 r=d.Receipt.objects.filter(job=j).first()
 if r:return finish(j,c,r)
 adapter=PrivateEvidenceAdapter()
 # Receipt lookup contains no new private input. Recover before current sender/budget checks.
 try:value=adapter.lookup(j)
 except ValidationError as exc:raise ConnectionError('Receipt reconciliation unavailable') from None
 if value is None:
  if j.attempts>j.intent['max_attempts']:raise ValidationError('Configured attempt budget exhausted')
  if d.context(j.actor,j.projection)!=j.intent:raise ValidationError('Private send context changed; new reviewed intent required')
  if j.projection.evidence.kind=='agent_private_ledger':
   from apps.workflows.readiness import gate
   gate(c,'ledgerdata')
  try:value=adapter.extract(j)
  except ValidationError:raise ConnectionError('Uncertain provider response; reconcile before retry') from None
 fenced(j,f)
 try:result=d.output(j.projection,value,j.intent['max_output_chars']);valid=True
 except ValidationError:result={};valid=False
 r=d.Receipt.objects.create(job=j,valid=valid,result=result,output_sha256=digest(value));return finish(j,c,r)

def finish(j,c,r):
 j.status='confirmed' if r.valid else 'rejected';j.lease_until=None;j.save(update_fields=['status','lease_until']);event(j.actor,c,'agent.data.received',job=j.pk,receipt=r.pk,valid=r.valid);bump(c);return r

@transaction.atomic
def failure(pk,f,status):
 j=d.Job.objects.select_for_update().get(pk=pk)
 if j.status=='leased' and j.fence==f and j.lease_until>timezone.now():j.status=status;j.lease_until=None;j.save(update_fields=['status','lease_until'])

def run_once(case_id=None):
 item=claim(case_id)
 if not item:return False
 try:execute(*item)
 except (TimeoutError,ConnectionError):failure(*item,'unknown')
 except (ValidationError,PermissionDenied):failure(*item,'held')
 return True

@transaction.atomic
def operate(a,case_id,pk,operation,expected=None):
 c=d.locked(a,case_id,'agent.data.operate',expected);j=d.Job.objects.select_for_update().select_related('projection__case','projection__evidence','actor').filter(projection__case=c,pk=pk).first()
 if not j:raise ValidationError('Exact case extraction required')
 d.source_access(a,j.projection)
 # Uncertain jobs remain lookup-first; cannot cancel/rekey away an uncertain effect.
 if j.status!='held' or operation!='retry':raise ValidationError('Held work supports receipt-first retry only')
 if d.Receipt.objects.filter(job=j).exists():raise ValidationError('Committed receipt cannot be changed')
 if j.projection.evidence.kind=='agent_private_ledger' and j.attempts>=j.intent['max_attempts']:raise ValidationError('Original private Finance attempt budget exhausted')
 if operation=='retry' and d.context(j.actor,j.projection)!=j.intent:raise ValidationError('Original reviewed context required')
 j.status='pending';j.save(update_fields=['status']);event(a,c,'agent.data.operated',job=j.pk,operation=operation);bump(c);return j
