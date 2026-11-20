"""Reobserve a confirmed original invoice reservation without opening a new effect."""

from django.core.exceptions import ValidationError

from adapters.invoices import InternalInvoiceAdapter
from apps.agents.factory_coordinator import pending
from apps.core.models import Audit
from apps.core.services import event, lock_case
from apps.finance import invoices
from apps.finance.models import InvoiceJob
from apps.identity.models import Grant
from apps.identity.services import require

from .factory_execution import require_control
from .models import FactoryAttempt


def confirmed_waiting_job(work, jobs):
    if (work.definition != 'pmo-finance/v1' or work.status != 'waiting_effect' or work.cancel_requested
            or not work.invoice_id
            or any(job.status in ('pending', 'leased', 'unknown', 'held') for job in jobs)):
        return None
    confirmed = {job.pk: job for job in jobs if job.status == 'confirmed' and job.invoice_id == work.invoice_id}
    if not confirmed or pending(work) is not None:
        return None

    manual = Audit.objects.filter(case_id=work.case_id, action='factory.reconciliation_requested', data__work=work.pk
                                  ).order_by('-pk').values_list('created_at', 'data__job').first()
    automated = FactoryAttempt.objects.filter(activity__work=work, activity__kind='ACT12', phase='observed',
                                               result__lookup_only=True).order_by('-pk').values_list(
        'created_at', 'result__dispatch_job').first()
    latest = max((lookup for lookup in (manual, automated) if lookup), key=lambda lookup: lookup[0], default=None)
    return confirmed.get(latest[1]) if latest else None


def reconcile_confirmed(actor, work, original):
    """The caller holds the work lock. Keep any durable operator pause intact."""
    from .factory import invoice_jobs

    work.case = lock_case(actor, work.case_id, 'factory.execute')
    list(Grant.objects.select_for_update().filter(case=work.case).order_by('pk'))
    require_control(actor, work)
    job = InvoiceJob.objects.select_for_update(of=('self',)).select_related('invoice__case', 'actor').get(pk=original.pk)
    if confirmed_waiting_job(work, invoice_jobs(work)) != job:
        raise ValidationError('Open the current invoice work and check the original receipt again.')
    receipt = current_receipt(work, job)
    return record_reconciliation(actor, work, job, receipt)


def current_receipt(work, job):
    """Check the native proof and current intent under the caller's case and job locks."""
    if job.status != 'confirmed' or job.invoice_id != work.invoice_id or job.invoice.case_id != work.case_id:
        raise ValidationError('The confirmed receipt must belong to the current invoice work.')
    receipt = InternalInvoiceAdapter().lookup(job)
    if receipt is None or receipt.job_id != job.pk or job.intent['sha256'] != job.invoice.sha256:
        raise ValidationError('The confirmed receipt must match the original invoice and reservation.')
    if job.kind == 'issue':
        if receipt.obligation_key != work.business_key or receipt.operation_key != f'obligation:{work.business_key}':
            raise ValidationError('The original receipt belongs to a different invoice obligation.')
    elif receipt.recipient_id != job.intent['recipient'] or receipt.sha256 != job.intent['delivery_hash']:
        raise ValidationError('The receipt must match the original reviewed destination and document.')

    require(job.actor, work.case, invoices.effect_action(job.kind))
    bound = job.intent.get('factory_execution') is not None
    if not bound:
        # Legacy operations still require exact original attempt ownership and current source access.
        if invoices.legacy_factory_work_id(job) != work.pk:
            raise ValidationError('Current ownership of the original invoice operation is required.')
        invoices.factory_binding(job.actor, job.invoice, work.pk)
    current = invoices.intent(job.actor, job.invoice, job.kind, job.intent.get('issuer_role'),
                              factory_work_id=work.pk if bound else None)
    if current != job.intent:
        raise ValidationError('The original receipt is recorded. Review the changed invoice scope before continuing.')
    return receipt


def record_reconciliation(actor, work, job, receipt):
    """Record confirmed coordinator progress without enrolling or waking a request."""
    work.status = 'ready'
    work.finding = ''
    work.observation_hash = ''
    work.revision += 1
    work.save(update_fields=['status', 'finding', 'observation_hash', 'revision', 'updated_at'])
    event(actor, work.case, 'factory.invoice_receipt_reconciled', work=work.pk, job=job.pk,
          receipt=receipt.pk, operation=job.operation_key)
    return work
