"""Actual local invoice acceptance and recipient inbox. No external accounting/ledger/API authenticity."""
from django.core.exceptions import ValidationError
from apps.finance.models import InvoiceIssue,InvoiceDelivery

class InternalInvoiceAdapter:
    def lookup(self,job):
        if job.kind in ['adjust','adjust_deliver']:
            from .financial_corrections import lookup
            return lookup(job)
        model=InvoiceIssue if job.kind=='issue' else InvoiceDelivery
        receipt=model.objects.filter(invoice=job.invoice).first()
        from apps.finance.invoices import delivery_payload
        from apps.finance.billing import digest
        expected=job.invoice.payload if job.kind=='issue' else delivery_payload(job.invoice)
        if receipt and (receipt.payload!=expected or receipt.sha256!=digest(expected)):raise ValidationError('Invoice receipt payload/hash mismatch')
        return receipt
    def deliver(self,pk,fence):
        from apps.finance.invoice_delivery import deliver_local
        return deliver_local(pk,fence)

class TimeoutAfterInvoiceAccept(InternalInvoiceAdapter):
    def deliver(self,pk,fence):
        super().deliver(pk,fence);raise TimeoutError('Synthetic timeout after persisted local invoice acceptance')
