from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from .models import InvoiceJob,InvoiceIssue,InvoiceDelivery
from . import invoices

@transaction.atomic
def claim(case_id=None,job_id=None,*,lookup_only=False):
    if type(lookup_only) is not bool:raise ValidationError('Explicit receipt-only lookup flag required')
    now=timezone.now()
    query=InvoiceJob.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now))
    if lookup_only:query=query.exclude(status='pending')
    if case_id is not None:query=query.filter(invoice__case_id=case_id)
    if job_id is not None:query=query.filter(pk=job_id)
    job=query.order_by('pk').first()
    if not job:return None
    job.status='leased';job.fence+=1;job.attempts+=1;job.lease_until=now+timedelta(seconds=job.intent['identity']['lease_seconds'])
    job.save(update_fields=['status','fence','attempts','lease_until']);return job.pk,job.fence

def check(job,fence):
    if job.status!='leased' or job.fence!=fence or job.lease_until<=timezone.now():raise ValidationError('Expired invoice worker fence')

@transaction.atomic
def finish(pk,fence,status,error=''):
    initial=InvoiceJob.objects.get(pk=pk);case=Case.objects.select_for_update().get(pk=initial.invoice.case_id)
    job=InvoiceJob.objects.select_for_update().get(pk=pk);check(job,fence)
    job.status=status;job.error=error[:400];job.save(update_fields=['status','error'])
    event(job.actor,case,'invoice.effect_'+status,job=pk,kind=job.kind,error=job.error)

@transaction.atomic
def dispatch_context(pk,fence):
    initial=InvoiceJob.objects.get(pk=pk);case=Case.objects.select_for_update().get(pk=initial.invoice.case_id)
    job=InvoiceJob.objects.select_for_update().select_related('invoice').get(pk=pk);check(job,fence)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    from apps.workflows.readiness import gate
    gate(case,'invoice')
    require(job.actor,case,invoices.effect_action(job.kind))
    work_id=job.intent.get('factory_execution',{}).get('work')
    if work_id is None and invoices.legacy_factory_work_id(job) is not None:raise ValidationError('Legacy factory intent requires explicit operator revalidation before new dispatch')
    value=invoices.intent(job.actor,job.invoice,job.kind,job.intent.get('issuer_role'),job.intent.get('correction'),factory_work_id=work_id)
    if value!=job.intent:raise ValidationError('Invoice source/review/policy/destination changed; reconcile reserved intent')
    from apps.workflows.models import FactoryWork
    if FactoryWork.objects.filter(invoice=job.invoice,cancel_requested=True).exists():raise ValidationError('Factory cancellation prevents new invoice dispatch; existing effects require reconciliation')
    return job,value


@transaction.atomic
def deliver_local(pk,fence):
    job,value=dispatch_context(pk,fence)
    return _record_reserved_receipt(job,value)

def _record_reserved_receipt(job,value):
    """Internal helper; caller owns a transaction, fence and dispatch/proof validation."""
    if job.kind in ['adjust','adjust_deliver']:
        from .corrections import apply_local
        return apply_local(job)
    i=job.invoice
    if job.kind=='issue':
        existing=InvoiceIssue.objects.filter(obligation_key=i.obligation_key).first()
        if existing and existing.invoice_id!=i.pk:raise ValidationError('Canonical obligation was already issued with another document; correction required')
        receipt,created=InvoiceIssue.objects.get_or_create(invoice=i,defaults={'obligation_key':i.obligation_key,'job':job,'operation_key':'obligation:'+i.obligation_key,'payload':i.payload,'sha256':i.sha256})
    else:
        receipt,created=InvoiceDelivery.objects.get_or_create(invoice=i,defaults={'job':job,'recipient_id':value['recipient'],'payload':invoices.delivery_payload(i),'sha256':value['delivery_hash']})
        if receipt.recipient_id!=value['recipient']:raise ValidationError('Invoice already delivered to a different reserved principal')
    expected_payload=i.payload if job.kind=='issue' else invoices.delivery_payload(i)
    expected_hash=i.sha256 if job.kind=='issue' else value['delivery_hash']
    if receipt.payload!=expected_payload or receipt.sha256!=expected_hash:raise ValidationError('Existing invoice receipt differs; investigate')
    return receipt.pk

@transaction.atomic
def record_accepted_mock(pk,fence,observed):
    """Record an already accepted exact synthetic effect, never dispatch or renew authority."""
    initial=InvoiceJob.objects.get(pk=pk)
    case=Case.objects.select_for_update().get(pk=initial.invoice.case_id)
    job=InvoiceJob.objects.select_for_update().select_related('invoice').get(pk=pk);check(job,fence)
    if not case.synthetic or job.kind not in ['issue','deliver']:raise PermissionDenied('Only exact isolated synthetic provider proof is supported')
    payload=job.invoice.payload if job.kind=='issue' else invoices.delivery_payload(job.invoice)
    binding={'payload':payload,'destination':job.intent['adapter']['recipient_id'],'target':job.invoice_id,'intent':job.intent}
    expected={'environment':'synthetic_mock','operation_key':job.operation_key,'payload':payload,'destination':binding['destination'],'fingerprint':invoices.digest(binding)}
    if observed!=expected:raise ValidationError('Accepted effect proof differs from reserved identity/payload/destination')
    result=_record_reserved_receipt(job,job.intent)
    event(job.actor,case,'invoice.accepted_mock_observed',job=job.pk,proof_hash=invoices.digest(observed),environment='synthetic_mock',dispatch_authorized=False)
    return result

def run_once(adapter=None,case_id=None,job_id=None,*,lookup_only=False):
    if type(lookup_only) is not bool:raise ValidationError('Explicit receipt-only lookup flag required')
    from adapters.invoices import InternalInvoiceAdapter
    adapter=adapter or InternalInvoiceAdapter();lease=claim(case_id,job_id,lookup_only=lookup_only)
    if not lease:return False
    pk,fence=lease;job=InvoiceJob.objects.select_related('invoice__case').get(pk=pk)
    if type(adapter) is not InternalInvoiceAdapter and not job.invoice.case.synthetic:
        finish(pk,fence,'held','Fault adapters are restricted to synthetic cases');return True
    try:
        # Proven prior effects survive later source/authority changes; reconcile before new dispatch checks.
        if adapter.lookup(job):finish(pk,fence,'confirmed');return True
        if lookup_only:
            finish(pk,fence,'unknown','Original effect is not confirmed; receipt-only lookup authorises no send')
            return True
        if job.attempts>job.intent['identity']['max_attempts']:finish(pk,fence,'held','Attempt budget exhausted; operator reconciliation required');return True
        dispatch_context(pk,fence)
        adapter.deliver(pk,fence)
    except (TimeoutError,ConnectionError):finish(pk,fence,'unknown','Outcome unknown; reconcile before retry')
    except (ValidationError,PermissionDenied,ValueError) as exc:finish(pk,fence,'held',str(exc))
    else:finish(pk,fence,'confirmed')
    return True

@transaction.atomic
def operate(actor,case_id,job_id,action,reason,expected):
    from adapters.invoices import InternalInvoiceAdapter
    from .analysis import note
    case=lock_case(actor,case_id,'finance.invoice.operate',expected);note(reason)
    job=InvoiceJob.objects.select_for_update().filter(pk=job_id,invoice__case=case).first()
    if not job or action not in ['cancel','retry','replace_intent']:raise ValidationError('Choose exact invoice job and operator action')
    if job.status in ['confirmed','cancelled','replaced'] or job.status=='leased' and job.lease_until>timezone.now():raise ValidationError('Proven, cancelled, replaced or actively leased work cannot be changed')
    if InternalInvoiceAdapter().lookup(job):raise ValidationError('Effect already exists; let worker reconcile it')
    if job.status=='unknown':raise ValidationError('Unknown effects require worker lookup before operator retry/cancellation')
    if action=='cancel':job.status='cancelled'
    else:
        if job.status!='held':raise ValidationError('Only held work needs operator retry')
        require(actor,case,invoices.effect_action(job.kind))
        work_id=job.intent.get('factory_execution',{}).get('work') or invoices.legacy_factory_work_id(job)
        value=invoices.intent(actor,job.invoice,job.kind,job.intent.get('issuer_role'),job.intent.get('correction'),factory_work_id=work_id)
        if action=='retry':
            if value!=job.intent or actor.pk!=job.actor_id:raise ValidationError('Intent changed; explicitly replace held intent')
            job.status='pending';job.attempts=0
        else:
            if InvoiceJob.objects.filter(invoice=job.invoice,kind=job.kind,generation__gt=job.generation).exists():raise ValidationError('Newer reservation exists')
            new=InvoiceJob.objects.create(invoice=job.invoice,kind=job.kind,generation=job.generation+1,intent=value,
                operation_key=f'invoice:{job.invoice_id}:{job.kind}:g{job.generation+1}',actor=actor)
            job.status='replaced'
    job.error=reason[:400];job.save(update_fields=['status','attempts','error'])
    event(actor,case,'invoice.operator_'+action,job=job.pk,reason=reason);bump(case);return job
