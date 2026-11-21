"""An explicit human stop of one exact draft before any invoice effect."""
from dataclasses import dataclass

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.agents import factory_coordinator
from apps.core.services import lock_case
from apps.finance import invoices
from apps.finance.fixed_charge import preparation_access
from apps.finance.models import InvoiceDelivery, InvoiceIssue, InvoiceJob


@dataclass(frozen=True)
class DraftStop:
    case_revision: int
    reason: str
    existing_invoice: int | None


class DraftStopForm(forms.Form):
    case_revision = forms.IntegerField(min_value=1)
    reason = forms.CharField(max_length=2000)
    existing_invoice = forms.IntegerField(min_value=1, required=False)


def exact_identity(actor, work, invoice):
    if invoice.case_id != work.case_id or invoice.preparation.case_id != work.case_id:
        return False
    preparation_access(actor, invoice.preparation)
    return (invoice.obligation_key == invoices.obligation(invoice.preparation) == work.business_key
            and invoice.sha256 == invoices.digest(invoice.payload))


def eligible(actor, work, *, jobs=None):
    if (work.definition != 'pmo-finance/v1' or not work.invoice_id or work.cancel_requested
            or work.status in {'verified', 'cancelled', 'waiting_effect', 'followup_needed'}
            or work.lease_until and work.lease_until > timezone.now()):
        return False
    invoice = work.invoice
    if (work.preparation_id != invoice.preparation_id or not exact_identity(actor, work, invoice)
            or InvoiceJob.objects.filter(invoice=invoice).exists()
            or InvoiceIssue.objects.filter(invoice=invoice).exists()
            or InvoiceDelivery.objects.filter(invoice=invoice).exists()):
        return False

    original = factory_coordinator.pending(work)
    if original and not factory_coordinator.has_receipt(original):
        return False
    if jobs is None:
        from .factory import invoice_jobs
        jobs = invoice_jobs(work)
    return not jobs


def existing_issue(actor, work, invoice_id=None):
    issued = InvoiceIssue.objects.filter(
        obligation_key=work.business_key, invoice__case_id=work.case_id,
    ).exclude(invoice_id=work.invoice_id)
    if invoice_id is not None:
        issued = issued.filter(invoice_id=invoice_id)
    issue = issued.select_related('invoice__preparation', 'job').first()
    if not issue:
        return None
    invoice = issue.invoice
    if (issue.job.invoice_id != invoice.pk or issue.job.kind != 'issue'
            or issue.job.status != 'confirmed' or issue.sha256 != invoice.sha256
            or not exact_identity(actor, work, invoice)):
        return None
    return issue


def validate(actor, work, command):
    if (not isinstance(command, DraftStop) or type(command.case_revision) is not int
            or command.case_revision < 1 or not isinstance(command.reason, str)
            or not command.reason.strip() or len(command.reason) > 2000
            or command.existing_invoice is not None
            and (type(command.existing_invoice) is not int or command.existing_invoice < 1)):
        raise ValidationError('Enter a reason of up to 2,000 characters and choose the exact invoice if needed.')
    case = lock_case(actor, work.case_id, 'factory.manage', command.case_revision)
    if not eligible(actor, work):
        raise ValidationError('This draft cannot be stopped here. Refresh the work and check its original operations.')
    issue = None
    if command.existing_invoice is not None:
        try:
            issue = existing_issue(actor, work, command.existing_invoice)
        except (PermissionDenied, ValidationError):
            pass
        if not issue:
            raise ValidationError('Choose the recorded issued invoice for this billing obligation in this workspace.')
    invoice = work.invoice
    return case, {'schema': invoices.DRAFT_STOP_SCHEMA, 'invoice': invoice.pk,
                  'invoice_sha256': invoice.sha256, 'reason': command.reason.strip(),
                  'existing_invoice': issue.invoice_id if issue else None,
                  'existing_issue': issue.pk if issue else None}


def readback(actor, work):
    if work.status != 'cancelled' or not work.invoice_id:
        return None
    record = (invoices.draft_stop_history(work.invoice).filter(data__work=work.pk)
              .select_related('actor').order_by('-pk').first())
    if not record or not exact_identity(actor, work, work.invoice):
        return None
    issue = None
    invoice_id = record.data.get('existing_invoice')
    if type(invoice_id) is int:
        try:
            issue = existing_issue(actor, work, invoice_id)
        except (PermissionDenied, ValidationError):
            pass
        if issue and issue.pk != record.data.get('existing_issue'):
            issue = None
    return {'reason': record.data['reason'], 'at': record.created_at, 'actor': record.actor,
            'existing_invoice': issue.invoice if issue else None,
            'issued_at': issue.created_at if issue else None}
