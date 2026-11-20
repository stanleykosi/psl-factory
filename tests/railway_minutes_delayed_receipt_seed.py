"""Guarded sample of a one-time accepted publication with a delayed receipt."""

import json
import os
from hashlib import sha256
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from adapters.publications import InternalPublicationAdapter
from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence, event
from apps.documents import delivery
from apps.documents.contracts import digest
from apps.documents.controlled import review_version
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory, factory_minutes, factory_progress
from apps.workflows.models import FactoryWork
from tests import document_helpers
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_factory_minutes import FactoryMinutesTests


TENANT = 'design-minutes-delayed-receipt'
TITLE = 'SAMPLE delayed original minutes receipt'
WITNESS = 'agent_private_sample_minutes_acceptance'


def trial_user():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_MINUTES_DELAYED_RECEIPT_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('Use only the guarded Railway sample environment.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def scope(job):
    publication = job.publication
    work = publication.factory_work
    if (not work or work.definition != factory_minutes.DEFINITION or not work.case.synthetic
            or (work.case.tenant, work.case.title) != (TENANT, TITLE) or publication.actor_id != trial_user().pk
            or publication.version.document.case_id != work.case_id):
        raise RuntimeError('Exact isolated sample publication required.')
    return work, publication


def fingerprint(job):
    work, publication = scope(job)
    return {'classification': 'synthetic-delayed-acceptance', 'work': work.pk, 'case': str(work.case_id),
            'job': job.pk, 'publication': publication.pk, 'version': publication.version_id,
            'source': publication.factory_source_id, 'review': publication.review_id,
            'operation': publication.operation_key, 'recipients': publication.recipient_ids,
            'payload_sha256': publication.version.payload_sha256}


def locked_sample_job(job_id):
    original = PublicationJob.objects.get(pk=job_id)
    work, publication = scope(original)
    FactoryWork.objects.select_for_update().get(pk=work.pk)
    Case.objects.select_for_update().get(pk=work.case_id)
    return PublicationJob.objects.select_for_update().get(pk=job_id), work, publication


class FirstAttempt(InternalPublicationAdapter):
    @transaction.atomic
    def accept(self, job_id, fence):
        job, work, publication = locked_sample_job(job_id)
        delivery.check_fence(job, fence)
        if Evidence.objects.filter(case=work.case, kind=WITNESS, source=publication.operation_key).exists():
            raise AssertionError('The original publication has already been dispatched.')
        add_evidence(publication.actor, work.case_id, WITNESS,
                     json.dumps({'effect': fingerprint(job), 'original_fence': fence}, sort_keys=True),
                     publication.operation_key)

    def deliver(self, job_id, fence):
        self.accept(job_id, fence)
        raise TimeoutError('Synthetic acceptance recorded once. The receipt is not yet visible.')


class DelayedLookup(InternalPublicationAdapter):
    @transaction.atomic
    def lookup(self, publication):
        job, work, publication = locked_sample_job(publication.job.pk)
        delivery.check_fence(job, job.fence)
        witness = Evidence.objects.get(case=work.case, kind=WITNESS, source=publication.operation_key,
                                       created_by_id=publication.actor_id)
        proof = json.loads(witness.body)
        if (witness.sha256 != sha256(witness.body.encode()).hexdigest() or proof['effect'] != fingerprint(job)
                or type(proof['original_fence']) is not int or not 0 < proof['original_fence'] < job.fence):
            raise RuntimeError('The original synthetic witness does not match this reserved effect.')
        for recipient in publication.recipient_ids:
            PublicationReceipt.objects.get_or_create(publication=publication, recipient_id=recipient, defaults={
                'operation_key': f'{publication.operation_key}:user:{recipient}',
                'payload': publication.version.payload, 'payload_sha256': publication.version.payload_sha256})
        event(publication.actor, work.case, 'factory.sample_minutes_acceptance_observed', work=work.pk,
              job=job.pk, witness_sha256=witness.sha256, effect_sha256=digest(proof['effect']))
        return super().lookup(publication)

    def deliver(self, job_id, fence):
        raise AssertionError('A receipt lookup cannot dispatch the original publication again.')


@transaction.atomic
def prepare():
    operator = trial_user()
    case, created = Case.objects.get_or_create(tenant=TENANT, title=TITLE, kind='project', synthetic=True)
    if created:
        Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
        users = get_user_model().objects
        create_user = users.create_user
        with (patch.object(document_helpers, 'setup_case', return_value=(operator, case)),
              patch.object(users, 'create_user', side_effect=lambda username: create_user(f'sample-late-minutes-{username}'))):
            sample = FactoryMinutesTests()
            sample.setUp()
        work = sample.start(outward=True)
        sample.advance()
        sample.confirm()
        sample.advance()
        draft = factory_minutes.document(work)
        sample.request_outward_review()
        review_version(operator, case.pk, draft.version_id, 'approve', 'Reviewed exact synthetic minutes for the delayed receipt fixture.', rev(case))
        factory_progress.set_progress(operator, work.pk, work.revision, True)
        factory_progress.set_progress(operator, work.pk, work.revision, False)
        factory.run_until_wait(work.pk, adapter=FirstAttempt())
        work.refresh_from_db()
    else:
        work = FactoryWork.objects.get(case=case, actor=operator, definition=factory_minutes.DEFINITION)
    job = PublicationJob.objects.get(publication__factory_work=work)
    if created and (job.status != 'unknown' or work.status != 'waiting_effect'
                    or PublicationReceipt.objects.filter(publication=job.publication).exists()):
        raise RuntimeError('The sample must retain one unknown accepted effect with no visible receipt.')
    return {'work': work.pk, 'case': str(case.pk), 'job': job.pk, 'publication': job.publication_id,
            'version': job.publication.version_id, 'operation': job.publication.operation_key,
            'path': reverse('factory_invoice_recovery', args=[work.pk]), 'preserved': not created}


def reveal(work_id):
    operator = trial_user()
    job = PublicationJob.objects.get(publication__factory_work_id=work_id, publication__actor=operator,
        publication__version__document__case__tenant=TENANT, publication__version__document__case__title=TITLE)
    work, publication = scope(job)
    if not Audit.objects.filter(case=work.case, actor=operator, action='factory.reconciliation_requested',
                                data={'work': work.pk, 'publication_job': job.pk}).exists():
        raise RuntimeError('Observe the initial receipt lookup miss before revealing the synthetic receipt.')
    if job.status != 'confirmed':
        if job.status != 'unknown':
            raise RuntimeError('Wait for any active lookup before revealing the original witness.')
        delivery.run_publication_once(DelayedLookup(), case_id=work.case_id, job_id=job.pk, lookup_only=True)
    job.refresh_from_db()
    if job.status != 'confirmed':
        raise RuntimeError('The original receipt lookup is still in progress.')
    receipts = list(PublicationReceipt.objects.filter(publication=publication).order_by('pk').values_list('pk', flat=True))
    return {'work': work.pk, 'job': job.pk, 'publication': publication.pk, 'version': publication.version_id,
            'receipt_ids': receipts, 'operation': publication.operation_key}


def run():
    print('PSL_DELAYED_MINUTES_FIXTURE=' + json.dumps(prepare()), flush=True)
