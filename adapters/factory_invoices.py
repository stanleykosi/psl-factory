"""Durable file-backed mock provider, restricted to synthetic cases and explicit test directories."""
import json,os
from pathlib import Path
from django.core.exceptions import ValidationError,PermissionDenied
from apps.finance.billing import digest
from .invoices import InternalInvoiceAdapter

class MockFactoryInvoiceAdapter(InternalInvoiceAdapter):
    def __init__(self,directory,lose_response=False,uncertain_lookup=False,delayed_reads=0):
        self.directory=Path(directory);self.lose_response=lose_response;self.uncertain_lookup=uncertain_lookup;self.delayed_reads=delayed_reads
        self.directory.mkdir(parents=True,exist_ok=True)

    def path(self,job):
        if not job.invoice.case.synthetic:raise PermissionDenied('Mock provider accepts synthetic cases only')
        return self.directory/(digest([job.invoice.case.tenant,job.invoice.case_id.hex,job.operation_key])+'.json')

    def intended(self,job):
        from apps.finance.invoices import delivery_payload
        payload=job.invoice.payload if job.kind=='issue' else delivery_payload(job.invoice)
        binding={'payload':payload,'destination':job.intent['adapter']['recipient_id'],'target':job.invoice_id,'intent':job.intent}
        return {'environment':'synthetic_mock','operation_key':job.operation_key,'payload':payload,'destination':binding['destination'],'fingerprint':digest(binding)}

    def lookup(self,job):
        existing=super().lookup(job)
        if existing:return existing
        path=self.path(job)
        if not path.exists():
            if self.uncertain_lookup or job.status=='unknown' or job.attempts>1:
                # A temporary not-found/expired key cannot establish absence.
                raise TimeoutError('Unresolved mock provider lookup; no resend authorised')
            return None  # Fresh controlled mock identity; provider contract proves no prior effect.
        if self.delayed_reads>0:
            self.delayed_reads-=1;raise TimeoutError('Mock provider replica has no final observation yet')
        try:observed=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError) as exc:raise TimeoutError('Provider evidence is incomplete; absence is not established') from exc
        if observed!=self.intended(job):raise TimeoutError('Conflicting provider evidence; original effect remains unresolved')
        from apps.finance.invoice_delivery import record_accepted_mock
        try:return record_accepted_mock(job.pk,job.fence,observed)
        except (ValidationError,PermissionDenied) as exc:raise TimeoutError('Provider accepted; local reconciliation needs current controls') from exc

    def deliver(self,pk,fence):
        from apps.finance.models import InvoiceJob
        from apps.finance.invoice_delivery import deliver_local
        job=InvoiceJob.objects.select_related('invoice__case').get(pk=pk);path=self.path(job);value=self.intended(job)
        try:
            # Exclusive identity reservation prevents duplicate provider publication across workers.
            with path.open('x',encoding='utf-8') as output:
                json.dump(value,output,sort_keys=True);output.flush();os.fsync(output.fileno())
        except FileExistsError:
            if json.loads(path.read_text(encoding='utf-8'))!=value:raise ValidationError('IDEMPOTENCY_CONFLICT: changed mock request')
        if self.lose_response:
            self.lose_response=False;raise TimeoutError('Mock accepted publication; response lost before native receipt')
        try:return deliver_local(pk,fence)
        except (ValidationError,PermissionDenied) as exc:raise TimeoutError('Accepted external mock effect; local result unresolved') from exc
