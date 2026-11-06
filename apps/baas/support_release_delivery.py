from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event
from apps.agents.boundary import lock_principals
from . import support_release as d

@transaction.atomic
def claim(case_id):
 now=timezone.now();q=d.Job.objects.select_for_update(of=('self',),skip_locked=True).filter(packet__case_id=case_id).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now)).order_by('pk')
 j=q.first()
 if not j:return
 # Lease uses the immutable prepared budget; receipt recovery does not resolve current policy.
 j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.packet.snapshot['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence

def check(j,fence):
 if j.status!='leased' or j.fence!=fence or j.lease_until<=timezone.now():raise ValidationError('Expired response worker fence')

@transaction.atomic
def finish(pk,fence,status):
 initial=d.Job.objects.get(pk=pk);Case.objects.select_for_update().get(pk=initial.packet.case_id);j=d.Job.objects.select_for_update().get(pk=pk);check(j,fence)
 j.status=status;j.error={'held':'Current source/release/destination/budget controls hold new delivery','unknown':'Outcome unknown; reconcile persisted receipt before retry'}.get(status,'');j.save(update_fields=['status','error']);event(j.decision.actor,j.packet.case,'agent.data.support_response_'+status,job=j.pk)

@transaction.atomic
def deliver_internal(pk,fence):
 initial=d.Job.objects.get(pk=pk);c=Case.objects.select_for_update().get(pk=initial.packet.case_id);lock_principals(c)
 j=d.Job.objects.select_for_update().select_related('packet__draft__owner','decision__actor').get(pk=pk);check(j,fence)
 from adapters.support_response import InternalSupportResponseAdapter
 existing=InternalSupportResponseAdapter().lookup(j)
 if existing:return existing
 from apps.workflows.readiness import gate
 gate(c,'supportresponse')
 v=d.releasable(j)
 if j.attempts>v['max_attempts']:raise ValidationError('Response attempt budget exhausted')
 return d.Receipt.objects.create(job=j,operation_key='support-response:'+str(c.pk)+':'+str(j.packet_id),recipient_id=j.packet.snapshot['recipient'],payload=j.packet.payload,sha256=j.packet.sha256,classification='internal_storage_only')

def run_once(case_id,adapter=None):
 from adapters.support_response import InternalSupportResponseAdapter
 lease=claim(case_id)
 if not lease:return False
 pk,fence=lease;j=d.Job.objects.select_related('packet__case').get(pk=pk);adapter=adapter or InternalSupportResponseAdapter()
 if type(adapter) is not InternalSupportResponseAdapter and not j.packet.case.synthetic:finish(pk,fence,'held');return True
 try:
  if not adapter.lookup(j):adapter.deliver(pk,fence)
  # Verify persisted native receipt independently of adapter-returned claims.
  if not InternalSupportResponseAdapter().lookup(j):raise ValidationError('No native verified receipt')
 except (TimeoutError,ConnectionError):finish(pk,fence,'unknown')
 except (ValidationError,PermissionDenied,ValueError,TypeError):finish(pk,fence,'held')
 else:finish(pk,fence,'confirmed')
 return True
