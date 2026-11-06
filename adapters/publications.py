from typing import Protocol
from django.core.exceptions import ValidationError
from apps.documents.models import PublicationReceipt

class PublicationAdapter(Protocol):
    def lookup(self,publication): ...
    def deliver(self,job_id:int,fence:int): ...

class InternalPublicationAdapter:
    """Actual internal, permissioned recipient inbox. Does not send email or publish to a remote system."""
    def lookup(self,publication):
        receipts=list(PublicationReceipt.objects.filter(publication=publication))
        if not receipts:
            return None
        if sorted(r.recipient_id for r in receipts)!=publication.recipient_ids or any(
            r.payload_sha256!=publication.version.payload_sha256 or r.payload!=publication.version.payload for r in receipts):
            raise ValidationError('Incomplete or mismatched publication receipts; operator reconciliation required')
        return str(publication.pk)

    def deliver(self,job_id,fence):
        from apps.documents.delivery import deliver_internal
        return deliver_internal(job_id,fence)

class PublicationTimeoutAfterAccept(InternalPublicationAdapter):
    def deliver(self,job_id,fence):
        super().deliver(job_id,fence)
        raise TimeoutError('Synthetic transport loss after committed local delivery')
