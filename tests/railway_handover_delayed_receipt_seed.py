"""Guarded late receipt for one original synthetic Support handover."""

import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from adapters.publications import InternalPublicationAdapter
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents import delivery
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.services import register_reference
from apps.workflows import factory, factory_handover
from apps.workflows.models import FactoryWork
from tests.helpers import activate, rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_delivery import DeliveryFixture
from tests.test_factory_handover import configure, ready
from tests.test_handover_replies import configure as configure_recorder


TENANT = 'design-delayed-handover-receipt'
TITLE = 'SAMPLE Support handover with delayed original receipt'
KEY = 'SAMPLE-HANDOVER-LATE-RECEIPT'
WITNESS = 'factory.sample_handover_original_accepted'
REPLY_SOURCE = 'synthetic:handover-original-delayed-reply'
DESTINATION = 'sample-delayed-handover-support'
PUBLISHER_ACTIONS = ('case.read', 'delivery.read', 'factory.execute', 'document.publish',
                     'document.receive:internal', 'delivery.support_receive')


def operator():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_HANDOVER_DELAYED_RECEIPT_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and delayed handover fixture guard are required.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def sample_scope(job):
    actor = operator()
    publication = job.publication
    work = publication.factory_work
    if (not work or work.definition != factory_handover.DEFINITION or work.key != KEY or work.actor_id != actor.pk
            or (work.case.tenant, work.case.title, work.case.synthetic) != (TENANT, TITLE, True)
            or publication.version.document.case_id != work.case_id or publication.actor.username != DESTINATION
            or publication.recipient_ids != [publication.actor_id]):
        raise RuntimeError('Use only this isolated synthetic publication and its exact Support destination.')
    return work, publication


def locked_original(job_id):
    work, publication = sample_scope(PublicationJob.objects.get(pk=job_id))
    FactoryWork.objects.select_for_update().get(pk=work.pk)
    Case.objects.select_for_update().get(pk=work.case_id)
    job = PublicationJob.objects.select_for_update().get(pk=job_id)
    return job, work, publication


def manifest(job, work, publication):
    return {'work': work.pk, 'case': str(work.case_id), 'job': job.pk, 'publication': publication.pk,
            'operation': publication.operation_key, 'version': publication.version_id, 'source': publication.factory_source_id,
            'policy': publication.factory_policy_id, 'review': publication.review_id, 'recipients': publication.recipient_ids,
            'payload_sha256': publication.version.payload_sha256}


class FirstAcceptance(InternalPublicationAdapter):
    @transaction.atomic
    def accept(self, job_id, fence):
        job, work, publication = locked_original(job_id)
        delivery.check_fence(job, fence)
        if Audit.objects.filter(case=work.case, action=WITNESS, data__effect__job=job.pk).exists():
            raise AssertionError('Never accept the original synthetic handover twice.')
        event(publication.actor, work.case, WITNESS, effect=manifest(job, work, publication), fence=fence)

    def deliver(self, job_id, fence):
        self.accept(job_id, fence)
        raise TimeoutError('The original synthetic handover was accepted. Its receipt is delayed.')


class DelayedLookup(InternalPublicationAdapter):
    @transaction.atomic
    def lookup(self, publication):
        job, work, publication = locked_original(publication.job.pk)
        delivery.check_fence(job, job.fence)
        witness = Audit.objects.get(case=work.case, action=WITNESS, actor=publication.actor, data__effect__job=job.pk)
        if (witness.data['effect'] != manifest(job, work, publication) or type(witness.data['fence']) is not int
                or not 0 < witness.data['fence'] < job.fence):
            raise RuntimeError('The delayed sample witness must match the original reserved effect.')
        recipient = publication.recipient_ids[0]
        PublicationReceipt.objects.get_or_create(publication=publication, recipient_id=recipient, defaults={
            'operation_key': f'{publication.operation_key}:user:{recipient}', 'payload': publication.version.payload,
            'payload_sha256': publication.version.payload_sha256})
        return super().lookup(publication)

    def deliver(self, job_id, fence):
        raise AssertionError('Receipt lookup never transmits the handover.')


def create_sample(actor, case):
    sample = DeliveryFixture()
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(ACTIONS)])
    sample.setup_delivery(context=(actor, case))
    sample.publisher = get_user_model().objects.create_user(username=DESTINATION, first_name='Sample Support recipient')
    Grant.objects.bulk_create([Grant(case=case, user=sample.publisher, action=action) for action in PUBLISHER_ACTIONS])
    recipient = register_reference(actor, case.pk, 'synthetic:delayed-handover-support', 'schema:psl/document-recipient/v1',
                                   {'audience': 'internal', 'user_id': sample.publisher.pk}, sample.e['policy_decision'].pk)
    activate(actor, case, 'D11.recipient_grant_refs', ['delivery-recipient:client', recipient.ref], sample.e['policy_decision'])
    sample.inputs = {'template_id': sample.t.pk,
                     'support_document': sample.evidence('support_document', 'Fictional Support restart and restore runbook.').pk,
                     'escalation_document': sample.evidence('escalation_document', 'Fictional Support escalation route.').pk}
    configure(sample)
    configure_recorder(sample)
    ready(sample)
    add_evidence(actor, case.pk, 'handover_receipt', 'Synthetic Support acknowledged the exact received runbook.', REPLY_SOURCE)
    work = factory_handover.start(actor, case.pk, KEY, sample.d.pk, sample.inputs, TITLE, rev(case))
    factory.run_until_wait(work.pk, adapter=FirstAcceptance())
    work.refresh_from_db()
    job = PublicationJob.objects.get(publication__factory_work=work)
    if ((work.status, job.status) != ('waiting_effect', 'unknown')
            or PublicationReceipt.objects.filter(publication=job.publication).exists()):
        raise RuntimeError('Retain exactly one original uncertain handover with no visible receipt.')
    return work


@transaction.atomic
def prepare():
    actor = operator()
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, TENANT),
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The isolated delayed handover case does not match.')
    work = create_sample(actor, case) if created else FactoryWork.objects.get(
        case=case, actor=actor, definition=factory_handover.DEFINITION, key=KEY)
    job = PublicationJob.objects.get(publication__factory_work=work)
    _, publication = sample_scope(job)
    proof = case.evidence.get(kind='handover_receipt', source=REPLY_SOURCE)
    return {**manifest(job, work, publication), 'preserved': not created, 'proof': proof.pk,
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
            'work_path': reverse('factory_detail', args=[work.pk])}


def reveal(work_id):
    actor = operator()
    job = PublicationJob.objects.get(publication__factory_work_id=work_id, publication__factory_work__case__tenant=TENANT)
    work, publication = sample_scope(job)
    if not Audit.objects.filter(case=work.case, actor=actor, action='factory.reconciliation_requested',
                                data={'work': work.pk, 'publication_job': job.pk}).exists():
        raise RuntimeError('Observe the first lookup miss in the handover recovery view.')
    if job.status == 'unknown':
        delivery.run_publication_once(DelayedLookup(), case_id=work.case_id, job_id=job.pk, lookup_only=True)
    job.refresh_from_db()
    if job.status != 'confirmed':
        raise RuntimeError('Wait for the exact original receipt lookup to settle.')
    receipts = list(PublicationReceipt.objects.filter(publication=publication).order_by('pk'))
    return {**manifest(job, work, publication), 'receipts': factory_handover.exact_receipts(publication, receipts)}


def run():
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The explicit preview sample database is required.')
    print('PSL_DELAYED_HANDOVER_FIXTURE=' + json.dumps(prepare()), flush=True)
