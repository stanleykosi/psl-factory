"""One isolated forecast receipt journey with no external recipients or sends."""

import os
from functools import partial
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from adapters.publications import InternalPublicationAdapter
from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents import delivery
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory, factory_forecast, factory_forecast_recovery, factory_progress
from apps.workflows.models import FactoryWork
from tests import test_factory_forecast
from tests.forecast_helpers import publication as sample_publication, review
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT, prepare_forecast


TENANT = 'forecast-delayed-receipt-walkthrough'
TITLE = 'SAMPLE cash forecast with delayed recipient receipt'
WITNESS = 'factory.synthetic_forecast_acceptance'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
RECIPIENT = 'forecast-delayed-receipt-sample-reader'


def operator():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_FORECAST_RECEIPT_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and forecast receipt fixture guard are required.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def exact_job(job_id):
    actor = operator()
    job = PublicationJob.objects.select_related('publication__factory_work__case', 'publication__version__document').get(pk=job_id)
    publication = job.publication
    work = publication.factory_work
    if (not work or work.case_id != CASE_ID or work.actor_id != actor.pk or work.definition != factory_forecast.DEFINITION
            or (work.case.tenant, work.case.title, work.case.synthetic) != (TENANT, TITLE, True)
            or publication.version.document.case_id != CASE_ID or publication.actor_id != actor.pk
            or publication.recipient_ids != [get_user_model().objects.get(username=RECIPIENT).pk]
            or publication.factory_source_id != work.source_head_id or publication.factory_policy_id != work.policy_id):
        raise RuntimeError('Use only this isolated forecast and its original synthetic publication.')
    return job, work, publication


def manifest(job, work, publication):
    return {'work': work.pk, 'case': str(work.case_id), 'job': job.pk, 'publication': publication.pk,
            'source': publication.factory_source_id, 'version': publication.version_id, 'recipients': publication.recipient_ids,
            'operation': publication.operation_key, 'sha256': publication.version.payload_sha256}


class FirstAcceptance(InternalPublicationAdapter):
    def deliver(self, job_id, fence):
        with transaction.atomic():
            job, work, publication = exact_job(job_id)
            job = PublicationJob.objects.select_for_update().get(pk=job.pk)
            delivery.check_fence(job, fence)
            if Audit.objects.filter(case_id=CASE_ID, action=WITNESS, data__effect__job=job_id).exists():
                raise AssertionError('Never accept the synthetic forecast twice.')
            event(publication.actor, work.case, WITNESS, effect=manifest(job, work, publication), fence=fence)
        raise TimeoutError('Synthetic acceptance occurred, but its original receipt is delayed.')


class DelayedLookup(InternalPublicationAdapter):
    @transaction.atomic
    def lookup(self, publication):
        job, work, publication = exact_job(publication.job.pk)
        FactoryWork.objects.select_for_update().get(pk=work.pk)
        Case.objects.select_for_update().get(pk=work.case_id)
        job = PublicationJob.objects.select_for_update().get(pk=job.pk)
        delivery.check_fence(job, job.fence)
        witness = Audit.objects.get(case_id=CASE_ID, actor=publication.actor, action=WITNESS, data__effect__job=job.pk)
        if witness.data['effect'] != manifest(job, work, publication) or not 0 < witness.data['fence'] < job.fence:
            raise RuntimeError('The synthetic recipient witness must match the original delivery reservation.')
        factory_forecast.publication_scope(publication.actor, work.case, publication.version, work.pk)
        for recipient in publication.recipient_ids:
            PublicationReceipt.objects.get_or_create(publication=publication, recipient_id=recipient, defaults={
                'operation_key': f'{publication.operation_key}:user:{recipient}',
                'payload': publication.version.payload, 'payload_sha256': publication.version.payload_sha256})
        return super().lookup(publication)

    def deliver(self, job_id, fence):
        raise AssertionError('Receipt lookup cannot send another forecast.')


@transaction.atomic
def prepare():
    actor = operator()
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The isolated synthetic forecast case identity must match.')
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        with patch.object(test_factory_forecast, 'publication', partial(sample_publication, reader_name=RECIPIENT)):
            work = prepare_forecast(actor, case)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        review(actor, case, factory_forecast.calculation(work, actor))
        factory_progress.set_progress(actor, work.pk, work.revision, True)
        factory_progress.set_progress(actor, work.pk, work.revision, False)
        factory.run_until_wait(work.pk, adapter=FirstAcceptance())
        work.refresh_from_db()
    else:
        work = FactoryWork.objects.get(case=case, actor=actor, definition=factory_forecast.DEFINITION)
    job, work, publication = exact_job(PublicationJob.objects.get(publication__factory_work=work).pk)
    if created and ((work.status, job.status) != ('waiting_effect', 'unknown')
                    or PublicationReceipt.objects.filter(publication=publication).exists()):
        raise RuntimeError('The seeded delivery must await the one original receipt.')
    return {**manifest(job, work, publication), 'preserved': not created,
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
            'work_path': reverse('factory_detail', args=[work.pk])}


def reveal(work_id):
    operator()
    job, work, publication = exact_job(PublicationJob.objects.get(publication__factory_work_id=work_id).pk)
    if not (factory_forecast_recovery.observations(work).filter(data__job=job.pk).exists()
            and Audit.objects.filter(case_id=CASE_ID, action='factory.reconciliation_requested',
                                     data__work=work.pk, data__publication_job=job.pk).exists()):
        raise RuntimeError('Record an operator observation and check the first receipt miss through the recovery view.')
    if job.status == 'unknown':
        delivery.run_publication_once(DelayedLookup(), case_id=CASE_ID, job_id=job.pk, lookup_only=True)
    job.refresh_from_db()
    if job.status != 'confirmed':
        raise RuntimeError('Wait for the exact original receipt lookup to settle.')
    return {**manifest(job, work, publication),
            'receipts': list(PublicationReceipt.objects.filter(publication=publication).values_list('pk', flat=True))}
