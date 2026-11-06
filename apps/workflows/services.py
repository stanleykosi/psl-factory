from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.services import event
from apps.identity.services import require
from .models import Outbox


@transaction.atomic
def claim(case_id=None):
    now = timezone.now()
    query = Outbox.objects.select_for_update(skip_locked=True).filter(
        Q(status__in=['pending', 'unknown']) | Q(status='leased', lease_until__lte=now))
    if case_id is not None:query=query.filter(case_id=case_id)
    job=query.order_by('pk').first()
    if not job:
        return None
    job.status = 'leased'
    job.fence += 1
    job.attempts += 1
    job.lease_until = now + timedelta(seconds=30)
    job.save()
    return job.pk, job.fence


@transaction.atomic
def finish(job_id, fence, status, receipt='', error=''):
    job = Outbox.objects.select_for_update().get(pk=job_id)
    if job.fence != fence or job.status != 'leased' or job.lease_until <= timezone.now():
        raise ValidationError('Expired worker fence')
    job.status, job.receipt, job.error = status, receipt, error
    job.save(update_fields=['status', 'receipt', 'error'])
    event(job.actor, job.case, 'handoff.' + status, operation_key=job.operation_key, fence=fence, receipt=receipt)


def run_once(adapter=None,case_id=None):
    from adapters.finance import InternalFinanceAdapter
    adapter = adapter or InternalFinanceAdapter()
    lease = claim(case_id)
    if not lease:
        return False
    job_id, fence = lease
    job = Outbox.objects.select_related('case', 'actor', 'milestone').get(pk=job_id)
    # Always reconcile before dispatch, including a crash with an expired lease.
    try:
        existing = adapter.lookup(job.operation_key, job.payload)
    except (ValueError,ValidationError,PermissionDenied) as exc:
        finish(job_id, fence, 'held', error=str(exc))
        return True
    except (TimeoutError, ConnectionError):
        finish(job_id, fence, 'unknown', error='Receipt lookup unavailable; no dispatch attempted')
        return True
    if existing:
        finish(job_id, fence, 'confirmed', existing)
        return True
    try:
        require(job.actor, job.case, 'milestone.complete')
    except PermissionDenied:
        finish(job_id, fence, 'held', error='Dispatch authority revoked; operator review required')
        return True
    if job.attempts > 5:
        finish(job_id, fence, 'held', error='Retry budget exhausted; reconcile with operator')
        return True
    try:
        receipt = adapter.deliver(job)
    except (TimeoutError, ConnectionError):
        finish(job_id, fence, 'unknown', error='Outcome unknown; lookup required before any retry')
    except (ValueError,ValidationError,PermissionDenied) as exc:
        finish(job_id, fence, 'held', error=str(exc))
    else:
        finish(job_id, fence, 'confirmed', receipt)
    return True
