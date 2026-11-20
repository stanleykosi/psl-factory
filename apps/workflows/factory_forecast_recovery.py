"""Observe the original forecast delivery without authorising any new effect."""

import hashlib
import logging
from secrets import token_hex

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from adapters import case_uploads
from apps.agents.factory_coordinator import pending
from apps.core.models import Audit
from apps.core.services import event, lock_case
from apps.documents import delivery
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.identity.models import Grant
from apps.identity.services import require

from . import factory_forecast as forecast
from .factory_execution import require_control
from .models import FactoryWork


OBSERVED = 'factory.forecast_delivery_observed'
OUTCOMES = {'delivered': 'It arrived', 'not_delivered': 'It didn’t arrive', 'unknown': 'I can’t tell yet'}
UNSETTLED = ('pending', 'leased', 'unknown', 'held')
LOGGER = logging.getLogger(__name__)


def in_flight(work):
    return work.lease_until is not None and work.lease_until > timezone.now()


def lock_work(work_id):
    return FactoryWork.objects.select_for_update(of=('self',)).select_related('case').get(
        pk=work_id, definition=forecast.DEFINITION)


def lock_authority(actor, work, case_expected=None):
    require_control(actor, work)
    work.case = lock_case(actor, work.case_id, 'factory.execute', case_expected)
    list(Grant.objects.select_for_update().filter(case=work.case).order_by('pk'))
    require_control(actor, work)
    forecast.source(work, actor)


def original_job(work, jobs):
    # Earlier resume requests could leave a receipt-only job on work marked Ready.
    if work.status not in ('waiting_effect', 'ready') or pending(work) is not None:
        return None
    version = forecast.observed(work, 'document_version')
    return next((job for job in jobs if (job.publication.version_id, job.publication.factory_source_id,
                 job.publication.factory_policy_id) == (version, work.source_head_id, work.policy_id)), None)


def locked_jobs(work):
    return list(PublicationJob.objects.select_for_update(of=('self',)).filter(publication__factory_work=work)
                .select_related('publication').order_by('pk'))


def needs_lookup(job):
    return job.status == 'unknown' or (job.status == 'leased' and job.lease_until is not None
                                       and job.lease_until <= timezone.now())


def unsettled_delivery(work):
    return PublicationJob.objects.filter(publication__factory_work=work, publication__factory_source_id=work.source_head_id,
        publication__factory_policy_id=work.policy_id, publication__version_id=forecast.observed(work, 'document_version'),
        status__in=UNSETTLED).exists()


def recorded(work, job, jobs):
    return (work.status == 'waiting_effect' and job.status == 'confirmed'
            and not any(item.status in UNSETTLED for item in jobs))


def observations(work):
    return Audit.objects.filter(case_id=work.case_id, action=OBSERVED, data__work=work.pk)


def attachment(actor, work, observation_id):
    from types import SimpleNamespace

    require_control(actor, work)
    require(actor, work.case, 'evidence.add')
    proof = get_object_or_404(observations(work), pk=observation_id, actor=actor, data__outcome='delivered')
    recorded_job = PublicationJob.objects.filter(pk=proof.data['job'], publication__factory_work=work,
        publication_id=proof.data['publication'], publication__factory_source_id=proof.data['source']).exists()
    if not recorded_job or not proof.data.get('proof'):
        from django.http import Http404
        raise Http404
    return SimpleNamespace(**proof.data['proof'])


def finish_reconciliation(actor, work, job, jobs):
    from .factory import cancellation_status

    if not recorded(work, job, jobs):
        return work
    if work.cancel_requested:
        work.status = cancellation_status(work)
        work.finding = 'Stopping work cannot undo an already delivered forecast.'
    else:
        proof = forecast.verify(work, actor)
        if proof['publication'] != job.publication_id or not proof['receipt_ids']:
            raise ValidationError('Check the verified receipt for this exact forecast delivery.')
        receipts = PublicationReceipt.objects.filter(publication=job.publication, pk__in=proof['receipt_ids'])
        if any(key != f'{job.publication.operation_key}:user:{recipient}'
               for recipient, key in receipts.values_list('recipient_id', 'operation_key')):
            raise ValidationError('The receipt must identify the original forecast and recipient.')
        work.status = 'ready'
        work.finding = ''
        event(actor, work.case, 'factory.forecast_receipt_checked', work=work.pk, publication_job=job.pk,
              receipts=proof['receipt_ids'])
    work.observation_hash = ''
    work.revision += 1
    work.save(update_fields=['status', 'finding', 'observation_hash', 'revision', 'updated_at'])
    return work


def reconcile(actor, work_id, expected, adapter=None, job_id=None):
    with transaction.atomic():
        work = lock_work(work_id)
        require_control(actor, work)
        if type(expected) is not int or work.revision != expected or in_flight(work):
            raise ValidationError('Refresh the original forecast delivery before checking it.')
        lock_authority(actor, work)
        jobs = locked_jobs(work)
        job = original_job(work, jobs)
        if not job or job_id is not None and job.pk != job_id:
            raise ValidationError('Select the original forecast delivery.')
        if recorded(work, job, jobs):
            return finish_reconciliation(actor, work, job, jobs)
        if not needs_lookup(job):
            raise ValidationError('No original uncertain forecast delivery needs a receipt check.')
        event(actor, work.case, 'factory.reconciliation_requested', work=work.pk, publication_job=job.pk)
        pins = work.source_head_id, work.policy_id, work.execution_binding_id, work.cancel_requested

    delivery.run_publication_once(adapter, case_id=work.case_id, job_id=job.pk, lookup_only=True)

    with transaction.atomic():
        work = lock_work(work_id)
        if (work.revision != expected or in_flight(work) or
                pins != (work.source_head_id, work.policy_id, work.execution_binding_id, work.cancel_requested)):
            return work
        lock_authority(actor, work)
        jobs = locked_jobs(work)
        if original_job(work, jobs) != job:
            return work
        current = next(item for item in jobs if item.pk == job.pk)
        return finish_reconciliation(actor, work, current, jobs)


def proof_bytes(uploaded):
    if uploaded is None or not 0 < uploaded.size <= case_uploads.LIMIT:
        raise ValidationError('Choose one proof file up to 5 MiB.')
    name = uploaded.name.replace('\\', '/').rsplit('/', 1)[-1]
    if not name or len(name) > 160 or any(ord(character) < 32 for character in name):
        raise ValidationError('Choose a proof file with a valid name.')
    data = uploaded.read(case_uploads.LIMIT + 1)
    if len(data) != uploaded.size:
        raise ValidationError('The proof file is incomplete.')
    return name, data


def observe(actor, work_id, expected, case_expected, job_id, outcome, uploaded):
    if (any(type(number) is not int or number < 1 for number in (expected, case_expected, job_id))
            or outcome not in OUTCOMES):
        raise ValidationError('Choose what happened for the original forecast delivery.')
    if outcome != 'delivered' and uploaded is not None:
        raise ValidationError('Attach proof only when you observed that the forecast arrived.')

    key = None
    try:
        with transaction.atomic(durable=True):
            work = lock_work(work_id)
            lock_authority(actor, work, case_expected)
            if work.revision != expected or in_flight(work) or work.cancel_requested:
                raise ValidationError('Refresh the original forecast delivery before recording an observation.')
            job = original_job(work, locked_jobs(work))
            if not job or job.pk != job_id or not needs_lookup(job):
                raise ValidationError('Choose the original uncertain forecast delivery.')
            proof = None
            if outcome == 'delivered':
                require(actor, work.case, 'evidence.add')
                name, data = proof_bytes(uploaded)
                key = 'forecast-observation-' + token_hex(32)
                proof = {'name': name, 'key': key, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            event(actor, work.case, OBSERVED, work=work.pk, source=work.source_head_id, job=job.pk,
                  publication=job.publication_id, outcome=outcome, proof=proof)
            work.revision += 1
            work.save(update_fields=['revision', 'updated_at'])
            if proof:
                case_uploads.put(key, data)
    except Exception as exc:
        if key:
            try:
                if not Audit.objects.filter(action=OBSERVED, data__proof__key=key).exists():
                    case_uploads.discard_unbound(key)
            except (DatabaseError, OSError, ValidationError):
                LOGGER.warning('Forecast observation for work %s needs private storage reconciliation', work_id)
        if isinstance(exc, OSError):
            raise ValidationError('Private proof storage is unavailable. Try again later.') from exc
        raise
