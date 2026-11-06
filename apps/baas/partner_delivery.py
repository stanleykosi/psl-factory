from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.core.services import event,bump
from apps.finance.analysis import digest,note
from adapters.partner_operations import InternalPartnerFinanceAdapter
from . import partner_operations as domain
from .partner_operations import locked
from .models import PartnerFinanceJob,PartnerFinanceReceipt

@transaction.atomic
def claim():
    now=timezone.now();j=PartnerFinanceJob.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now)).order_by('pk').first()
    if not j:return None
    j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence

def check(j,fence):
    if j.status!='leased' or j.fence!=fence or j.lease_until<=timezone.now():raise ValidationError('Expired partner Finance fence')

@transaction.atomic
def finish(pk,fence,status,error=''):
    initial=PartnerFinanceJob.objects.select_related('report__record').get(pk=pk);Case.objects.select_for_update().get(pk=initial.report.record.case_id)
    j=PartnerFinanceJob.objects.select_for_update().get(pk=pk);check(j,fence);j.status=status;j.error=error[:400];j.save(update_fields=['status','error']);event(j.actor,j.report.record.case,'partner.handoff_'+status,job=j.pk,error=j.error)

@transaction.atomic
def deliver_local(pk,fence):
    initial=PartnerFinanceJob.objects.select_related('report__record').get(pk=pk);case=Case.objects.select_for_update().get(pk=initial.report.record.case_id)
    j=PartnerFinanceJob.objects.select_for_update().select_related('report__record').get(pk=pk);check(j,fence);list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    from apps.workflows.readiness import gate
    gate(case,'partner')
    value=domain.finance_intent(j.actor,j.report,j.intent['role'])
    if value!=j.intent:raise ValidationError('Partner source, review, authority or recipient changed; reconcile reserved intent')
    r=PartnerFinanceReceipt.objects.create(report=j.report,job=j,recipient_id=value['recipient'],payload=value['public'],sha256=digest(value['public']))
    event(j.actor,case,'partner.finance_received',receipt=r.pk,invoice_created=False);return r.pk

def run_once(adapter=None):
    adapter=adapter or InternalPartnerFinanceAdapter();lease=claim()
    if not lease:return False
    pk,fence=lease;j=PartnerFinanceJob.objects.select_related('report__record__case').get(pk=pk)
    if type(adapter) is not InternalPartnerFinanceAdapter and not j.report.record.case.synthetic:finish(pk,fence,'held','Fault adapters require synthetic scope');return True
    try:
        if adapter.lookup(j):finish(pk,fence,'confirmed');return True
        if j.attempts>j.intent['max_attempts']:finish(pk,fence,'held','Attempt budget exhausted; operator reconciliation required');return True
        adapter.deliver(pk,fence)
    except (TimeoutError,ConnectionError):finish(pk,fence,'unknown','Outcome unknown; query actual Finance receipt before retry')
    except (ValidationError,PermissionDenied,ValueError) as exc:finish(pk,fence,'held',str(exc))
    else:finish(pk,fence,'confirmed')
    return True

@transaction.atomic
def operate(actor,case_id,job_id,operation,reason,expected):
    case=locked(actor,case_id,'partner.finance.operate',expected);note(reason)
    j=PartnerFinanceJob.objects.select_for_update().filter(pk=job_id,report__record__case=case).first()
    if not j or operation not in ['retry','cancel','replace_intent']:raise ValidationError('Choose this case job and recovery operation')
    if j.status in ['confirmed','cancelled','replaced'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Proven, terminal or leased delivery cannot be changed')
    if InternalPartnerFinanceAdapter().lookup(j):raise ValidationError('Actual receipt exists; let worker reconcile')
    if j.status=='unknown':raise ValidationError('Unknown outcome requires receipt lookup before operator changes')
    if operation=='cancel':j.status='cancelled'
    else:
        if j.status!='held':raise ValidationError('Only held work requires recovery')
        value=domain.finance_intent(actor,j.report,j.intent['role'])
        if operation=='retry':
            if value!=j.intent or j.actor_id!=actor.pk:raise ValidationError('Intent changed; explicitly replace it')
            j.status='pending';j.attempts=0
        else:
            j.status='replaced';j.save(update_fields=['status']);PartnerFinanceJob.objects.create(report=j.report,generation=j.generation+1,actor=actor,intent=value)
    j.error=reason[:400];j.save(update_fields=['status','error','attempts']);event(actor,case,'partner.handoff_operator',job=j.pk,operation=operation,reason=reason);bump(case);return j
