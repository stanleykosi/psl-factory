from typing import Protocol
from django.core.exceptions import ValidationError
from .finance_inputs import preview_csv

class FinanceSourceAdapter(Protocol):
    def read(self,source): ...

class LocalFinanceSourceAdapter:
    """Read actual immutable supplied CSV. No QuickBooks extraction/posting or HR authenticity claim."""
    def read(self,source):
        rows,findings=preview_csv(source.batch.evidence.body)
        if rows!=source.batch.rows or findings!=source.batch.findings or source.batch.evidence.sha256!=source.batch.source_sha256:
            raise ValidationError('Stored import disagrees with immutable source evidence')
        return {'rows':rows,'findings':findings,'source_evidence':source.batch.evidence_id,'sha256':source.batch.source_sha256,'external_authenticity_verified':False}
