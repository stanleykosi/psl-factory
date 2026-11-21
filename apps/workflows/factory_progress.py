"""Bounded background progression through the existing factory coordinator."""
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, DateTimeField, Exists, F, OuterRef, Value, When
from django.utils import timezone

from apps.agents import factory_coordinator
from apps.core.services import event
from apps.documents.models import PublicationJob
from apps.finance.models import InvoiceIssue
from apps.pmo.approval_models import ApprovalRouteJob

from . import factory
from .factory_execution import require_control
from .models import FactoryAttempt, FactoryProgress, FactoryWork


ACTIVE = ('queued', 'running', 'waiting')
WAIT_INTERVAL = timedelta(seconds=45)
LEASE = timedelta(minutes=6)


def current_plan_started_at(work, observation_hash, options):
    """Read the start of a matching unsettled claim with one permitted step."""
    if (len(options) != 1 or work.cancel_requested or work.status in factory.TERMINAL or
            not work.lease_until or work.lease_until <= timezone.now()):
        return None
    settled = FactoryAttempt.objects.filter(activity_id=OuterRef('activity_id'), number=OuterRef('number'),
                                             phase__in=('observed', 'failed'))
    active = FactoryAttempt.objects.filter(activity__work=work, activity__kind='ACT03', phase='started',
                                            fence=work.fence, observation__hash=observation_hash).filter(~Exists(settled))
    return active.order_by('-pk').values_list('created_at', flat=True).first()


def current_plan_step(work, observation_hash, options):
    """Read the one permitted step of a matching unsettled planning claim."""
    return options[0] if current_plan_started_at(work, observation_hash, options) is not None else None


def wake_waiting(work_id):
    """A native decision or receipt can advance an existing authorised request."""
    now = timezone.now()
    FactoryProgress.objects.filter(work_id=work_id, status__in=['waiting', 'running']).update(
        available_at=Case(When(status='waiting', then=Value(now)), default=F('available_at'),
                          output_field=DateTimeField()),
        observation='', updated_at=now)


@transaction.atomic
def set_progress(actor, work_id, expected, enabled, *, initial=False):
    # Native intake can hold the case lock while an existing worker owns work.
    # Skip a busy row at intake so those transactions cannot wait on each other.
    work = FactoryWork.objects.select_for_update(of=('self',), skip_locked=initial).select_related(
        'case', 'actor',
    ).filter(pk=work_id).first()
    if work is None:
        raise ValidationError('The work item is busy or unavailable. Open it to request background work.')
    require_control(actor, work)
    if work.revision != expected:
        raise ValidationError('The work item changed. Open the current item and try again.')
    job = FactoryProgress.objects.select_for_update().filter(work=work).first()
    if initial and job:
        return job
    if enabled and (work.cancel_requested or work.status in factory.TERMINAL | {'waiting_effect'}):
        raise ValidationError('Use the work item’s follow-up or recovery action before asking it to continue.')
    if job and ((enabled and job.status in ACTIVE) or (not enabled and job.status == 'paused')):
        return job
    if not job and not enabled:
        raise ValidationError('There is no background request to pause.')
    if not job:
        job = FactoryProgress(work=work)
    job.requested_by = actor
    job.status = 'queued' if enabled else 'paused'
    job.available_at = timezone.now()
    job.token = None
    job.observation = ''
    job.save()
    event(actor, work.case, 'factory.background_enrolled' if enabled else 'factory.background_paused',
          work=work.pk, request=job.pk)
    return job


def invoice_release_ready(work):
    if (work.definition != 'pmo-finance/v1' or not work.invoice_id or work.status != 'ready'
            or work.cancel_requested or work.lease_until and work.lease_until > timezone.now()):
        return False
    _, profile = factory.profile(work)
    current = factory.snapshot(work, profile)
    jobs = current[-1]
    if jobs or InvoiceIssue.objects.filter(invoice_id=work.invoice_id).exists():
        return False
    actions, _ = factory.eligible(work, profile, *current)
    return actions == ['ACT11']


@transaction.atomic
def queue_invoice_release(actor, work_id, expected):
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'invoice').get(pk=work_id)
    require_control(actor, work)
    if work.revision != expected or not invoice_release_ready(work):
        raise ValidationError('The invoice is not ready to issue. Review the current sources and Finance approval.')
    job = set_progress(actor, work.pk, expected, True)
    wake_waiting(work.pk)
    return job


@transaction.atomic
def claim(work_id=None):
    now = timezone.now()
    due = FactoryProgress.objects.select_for_update(skip_locked=True).filter(
        status__in=ACTIVE, available_at__lte=now,
    )
    if work_id is not None:
        due = due.filter(work_id=work_id)
    job = due.order_by('available_at', 'pk').first()
    if job:
        job.status = 'running'
        job.token = uuid4()
        job.available_at = now + LEASE
        job.save(update_fields=['status', 'token', 'available_at', 'updated_at'])
    return job


def inspect(work):
    if work.status in {'verified', 'cancelled', 'followup_needed'}:
        return 'finished'
    if work.cancel_requested or work.status in factory.TERMINAL | {'waiting_effect'}:
        return 'held'
    if work.lease_until and work.lease_until > timezone.now():
        return 'busy'
    outstanding = factory_coordinator.pending(work)
    publications = PublicationJob.objects.filter(publication__factory_work=work)
    approval_routes = ApprovalRouteJob.objects.filter(request__case=work.case, intent__factory_execution__work=work.pk)
    if (outstanding and not factory_coordinator.has_receipt(outstanding)
            or any(factory.uncertain_job(job) for job in factory.invoice_jobs(work))
            or publications.filter(status='unknown').exists()
            or publications.filter(status='leased', lease_until__lte=timezone.now()).exists()
            or approval_routes.filter(status='unknown').exists()
            or approval_routes.filter(status='leased', lease_until__lte=timezone.now()).exists()):
        return 'held'
    return 'ready'


def run_job(job):
    work = FactoryWork.objects.select_related('case', 'actor').get(pk=job.work_id)
    require_control(job.requested_by, work)
    if work.definition == 'pmo-issues/v1':
        from .factory_issues import sync_owner
        if sync_owner(work.pk):
            work.refresh_from_db()
    state = inspect(work)
    if state != 'ready':
        return ('waiting', job.observation) if state == 'busy' else (state, '')
    if job.observation:
        _, profile = factory.profile(work)
        if factory.snapshot(work, profile)[0]['hash'] == job.observation:
            return 'waiting', job.observation
    if not FactoryProgress.objects.filter(pk=job.pk, token=job.token, status='running').exists():
        return 'paused', ''
    progressed = factory.run_once(work.pk)
    work = FactoryWork.objects.select_related('case', 'actor').get(pk=work.pk)
    state = inspect(work)
    if state != 'ready':
        return ('waiting', '') if state == 'busy' else (state, '')
    if progressed or work.status == 'ready':
        return 'queued', ''
    _, profile = factory.profile(work)
    return 'waiting', factory.snapshot(work, profile)[0]['hash']


def run_once(*, work_id=None):
    job = claim() if work_id is None else claim(work_id=work_id)
    if not job:
        return None
    try:
        status, observation = run_job(job)
    except (ValidationError, PermissionDenied):
        status, observation = 'held', ''
    now = timezone.now()
    completed = FactoryProgress.objects.filter(pk=job.pk, token=job.token, status='running',
        updated_at=job.updated_at).update(
        status=status, observation=observation, token=None,
        available_at=now + WAIT_INTERVAL if status == 'waiting' else now, updated_at=now,
    )
    if not completed:
        # A source wake during processing needs another observation. A pause or
        # replacement owns a different state/token and is preserved by this filter.
        FactoryProgress.objects.filter(pk=job.pk, token=job.token, status='running').update(
            status='queued', observation='', token=None, available_at=now, updated_at=now)
    return job.pk
