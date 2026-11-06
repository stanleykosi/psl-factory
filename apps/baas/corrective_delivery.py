from datetime import timedelta
from django.db import transaction,IntegrityError
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.finance.analysis import digest,note
from adapters.reconciliation import InternalEngineeringAdapter
from .models import CorrectiveJob,CorrectiveDelivery
from . import corrective,reconciliation as recon

@transaction.atomic
def claim():
    now=timezone.now();j=CorrectiveJob.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now)).order_by('pk').first()
    if not j:return None
    j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence

def check(j,fence):
    if j.status!='leased' or j.fence!=fence or j.lease_until<=timezone.now():raise ValidationError('Expired Engineering handoff worker fence')

@transaction.atomic
def finish(pk,fence,status,error=''):
    initial=CorrectiveJob.objects.select_related('request').get(pk=pk);Case.objects.select_for_update().get(pk=initial.request.case_id)
    j=CorrectiveJob.objects.select_for_update().get(pk=pk);check(j,fence);j.status=status;j.error=error[:400];j.save(update_fields=['status','error']);event(j.actor,j.request.case,'baas.handoff_'+status,job=j.pk,error=j.error)

@transaction.atomic
def deliver_local(pk,fence):
    initial=CorrectiveJob.objects.select_related('request').get(pk=pk);case=Case.objects.select_for_update().get(pk=initial.request.case_id)
    j=CorrectiveJob.objects.select_for_update().select_related('request').get(pk=pk);check(j,fence);list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    from apps.workflows.readiness import gate
    gate(case,'engineering')
    value=corrective.intent(j.actor,j.request,j.intent['sender_role'])
    if value!=j.intent:raise ValidationError('Source, decision, route or human authority changed; reconcile exact reserved request')
    r=CorrectiveDelivery.objects.create(request=j.request,job=j,tenant=case.tenant,operation_key=j.operation_key,subject_key=j.subject_key,recipient_id=value['recipient'],payload=value['public'],sha256=digest(value['public']))
    event(j.actor,case,'baas.engineering_request_received',receipt=r.pk,request=j.request_id,financial_execution=False);return r.pk

def run_once(adapter=None):
    adapter=adapter or InternalEngineeringAdapter();lease=claim()
    if not lease:return False
    pk,fence=lease;j=CorrectiveJob.objects.select_related('request__case').get(pk=pk)
    if type(adapter) is not InternalEngineeringAdapter and not j.request.case.synthetic:finish(pk,fence,'held','Fault adapters restricted to synthetic cases');return True
    try:
        if adapter.lookup(j):finish(pk,fence,'confirmed');return True
        if j.attempts>j.intent['max_attempts']:finish(pk,fence,'held','Attempt budget exhausted; operator reconciliation required');return True
        adapter.deliver(pk,fence)
    except (TimeoutError,ConnectionError):finish(pk,fence,'unknown','Outcome unknown; look up actual request receipt before retry')
    except IntegrityError:finish(pk,fence,'held','A matching Engineering receipt already exists; reconcile the logical operation')
    except (ValidationError,PermissionDenied,ValueError) as exc:finish(pk,fence,'held',str(exc))
    else:finish(pk,fence,'confirmed')
    return True

@transaction.atomic
def operate(actor,case_id,job_id,action,reason,expected):
    case=recon.locked(actor,case_id,'baas.corrective.operate',expected);note(reason);j=CorrectiveJob.objects.select_for_update().filter(pk=job_id,request__case=case).first()
    if not j or action not in ['cancel','retry','replace_intent']:raise ValidationError('Select this case job and recovery action')
    if j.status in ['confirmed','cancelled','replaced'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Proven, terminal or actively leased work cannot be changed')
    if InternalEngineeringAdapter().lookup(j):raise ValidationError('Actual receipt exists; let the worker reconcile it')
    if j.status=='unknown':raise ValidationError('Unknown handoff requires receipt lookup before cancellation/retry')
    if action=='cancel':j.status='cancelled'
    else:
        if j.status!='held':raise ValidationError('Only held work needs operator retry')
        value=corrective.intent(actor,j.request,j.intent['sender_role'])
        if action=='retry':
            if j.intent!=value or j.actor_id!=actor.pk:raise ValidationError('Intent changed; explicitly replace it')
            j.status='pending';j.attempts=0
        else:
            j.status='replaced';j.save(update_fields=['status'])
            CorrectiveJob.objects.create(request=j.request,generation=j.generation+1,intent=value,actor=actor,tenant=case.tenant,operation_key=j.operation_key,subject_key=j.subject_key)
    j.error=reason[:400];j.save(update_fields=['status','attempts','error']);event(actor,case,'baas.handoff_operator_'+action,job=j.pk,reason=reason);bump(case);return j
