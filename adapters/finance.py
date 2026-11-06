from typing import Protocol
from django.db import transaction
from apps.finance.models import Handoff


class HandoffAdapter(Protocol):
    def lookup(self, operation_key: str, payload: dict): ...
    def deliver(self, job): ...


class InternalFinanceAdapter:
    """Real internal inbox. Stable key and one milestone constrain duplicate effects."""
    def lookup(self, operation_key, payload):
        record = Handoff.objects.filter(operation_key=operation_key).first()
        if record and record.payload != payload:
            raise ValueError('Existing receipt payload differs from reserved intent')
        return str(record.pk) if record else None

    @transaction.atomic
    def deliver(self, job):
        from apps.core.models import Case
        from apps.identity.models import Grant
        from apps.workflows.readiness import gate
        case=Case.objects.select_for_update().get(pk=job.case_id)
        list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
        from apps.identity.services import require
        require(job.actor,case,'milestone.complete')
        gate(case,'handoff')
        record, _ = Handoff.objects.get_or_create(milestone=job.milestone,
            defaults={'case': job.case, 'operation_key': job.operation_key, 'payload': job.payload})
        if record.operation_key != job.operation_key or record.payload != job.payload:
            raise ValueError('Operation identity/payload mismatch')
        return str(record.pk)


class TimeoutAfterAccept(InternalFinanceAdapter):
    """Test fault adapter: persisted acceptance followed by transport uncertainty."""
    def deliver(self, job):
        super().deliver(job)
        raise TimeoutError('Synthetic timeout after acceptance')
