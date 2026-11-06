from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.core.services import event
from apps.agents.boundary import lock_principals
from adapters.support_channel import SupportChannelAdapter
from apps.documents.contracts import digest
from . import support_channel as d

@transaction.atomic
def claim(case_id):
 now=timezone.now();j=d.Job.objects.select_for_update(of=('self',),skip_locked=True).filter(claim__case_id=case_id).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now)).order_by('pk').first()
 if not j:return
 j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence

def fence(j,f):
 if j.status!='leased' or j.fence!=f or j.lease_until<=timezone.now():raise ValidationError('Expired channel-check fence')
@transaction.atomic
def finish(pk,f,status):
 initial=d.Job.objects.get(pk=pk);Case.objects.select_for_update().get(pk=initial.claim.case_id);j=d.Job.objects.select_for_update().get(pk=pk);fence(j,f);j.status=status;j.save(update_fields=['status']);event(j.actor,j.claim.case,'agent.data.support_channel_check_'+status,job=j.pk)

@transaction.atomic
def execute(pk,f,adapter):
 initial=d.Job.objects.get(pk=pk);c=Case.objects.select_for_update().get(pk=initial.claim.case_id);lock_principals(c);j=d.Job.objects.select_for_update().select_related('claim__case','actor').get(pk=pk);fence(j,f)
 from apps.workflows.readiness import gate
 gate(c,'supportchannel')
 if j.attempts>j.intent['max_attempts']:raise ValidationError('Original channel check attempt budget exhausted')
 if d.intent(j.actor,j.claim)!=j.intent:raise ValidationError('Channel-check source/policy/principal/binding changed')
 value=adapter.verify(j);_,v=d.rules(c);d.validate_result(j.claim,value,v);fence(j,f)
 return d.Receipt.objects.create(job=j,payload=value,sha256=digest(value),binding=j.intent['binding'])

def run_once(case_id,adapter=None):
 adapter=adapter or SupportChannelAdapter();lease=claim(case_id)
 if not lease:return False
 pk,f=lease;j=d.Job.objects.select_related('claim__case').get(pk=pk)
 if type(adapter) is not SupportChannelAdapter and not j.claim.case.synthetic:finish(pk,f,'held');return True
 try:
  # Read-only GET has no remote business effect. Reconcile a committed local observation before re-querying.
  if not SupportChannelAdapter().lookup(j):execute(pk,f,adapter)
 except (ConnectionError,TimeoutError,UnicodeError):finish(pk,f,'unknown')
 except (ValidationError,PermissionDenied,ValueError,TypeError):finish(pk,f,'held')
 else:finish(pk,f,'confirmed')
 return True

@transaction.atomic
def operate(a,case_id,pk,action,reason,expected=None):
 c=d.locked(a,case_id,'operate',expected);j=d.Job.objects.select_for_update().filter(pk=pk,claim__case=c).first()
 if not j or action not in ['retry','cancel'] or not isinstance(reason,str) or not reason.strip() or len(reason)>400:raise ValidationError('Exact channel check/action/reason required')
 if SupportChannelAdapter().lookup(j) or j.status in ['confirmed','cancelled'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Committed or active observation cannot change')
 if j.status=='unknown':raise ValidationError('Unknown read requires original scoped worker reconciliation')
 if action=='retry':
  if j.status!='held' or j.intent!=d.intent(j.actor,j.claim) or j.attempts>=j.intent['max_attempts']:raise ValidationError('Original check intent/budget required')
 j.status='pending' if action=='retry' else 'cancelled';j.save(update_fields=['status']);event(a,c,'agent.data.support_channel_operator',job=j.pk,operation=action,reason=reason);return j
