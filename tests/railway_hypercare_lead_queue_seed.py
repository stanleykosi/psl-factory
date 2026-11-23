"""An isolated below-target Hypercare result for the lead's next-action queue."""
import json
import os
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case, Evidence
from apps.core.services import event
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.policy.models import Configuration
from apps.policy.services import transition
from apps.workflows import factory, factory_hypercare as hypercare
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_hypercare_walkthrough_seed as base
from tests.helpers import rev


GUARD = 'PSL_HYPERCARE_LEAD_QUEUE_WALKTHROUGH'
TENANT = 'design-hypercare-lead-queue-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE lead queue stability observations'
KEY = 'SAMPLE-LEAD-QUEUE-STABILITY-OBSERVATIONS'
SUFFIX = '-lead-queue'
MARKER = 'sample.hypercare_lead_queue_prepared'
READ = ('case.read', 'factory.read', 'delivery.read')


def create(operator, case):
    work = base.create_sample(operator, case, KEY, SUFFIX)
    dossier = delivery.dossier_for(case, work.request['dossier'])
    release = delivery.latest(dossier, 'release_outcome')
    acceptance = delivery.latest(dossier, 'go_live')
    infrastructure, infrastructure_verification = delivery.verified_source(dossier, 'hypercare_infrastructure')
    original_proof = case.evidence.get(kind='test_results', source=base.ENGINEERING_PROOFS['not_met'])
    successor_proof = case.evidence.get(kind='test_results', source=base.ENGINEERING_PROOFS['qualified'])
    criteria = Configuration.objects.get(case=case, component=base.COMPONENT)
    for state in ('validated', 'active'):
        transition(dossier.actor, criteria.pk, state)

    # Reuse the source-owning Trial account only on this fictional project.
    Grant.objects.filter(case=case, user=operator, action__in=('policy.read', 'policy.configure', 'policy.activate')).update(active=False)
    reader = get_user_model().objects.create_user(f'sample-hypercare-reader-{case.pk.hex[:8]}')
    base.grant_case(reader, case, READ)

    values = {'owner': 'Engineering', 'configuration': criteria.pk, 'observed_at': timezone.now().isoformat(),
              'confirmed': 'yes', 'reference': original_proof.source, 'evidence': original_proof.pk,
              'verify_sample': 'on', 'metric_0': 2}
    work = factory.manage(operator, work.pk, work.revision, 'resume')
    original = hypercare.record_stability(operator, work.pk, work.revision, rev(case), values)
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    assessment = hypercare.assessed(work)
    if (work.status != 'waiting' or not assessment or assessment.snapshot['qualified'] is not False
            or assessment.snapshot['sources']['Engineering'][0] != original.pk
            or assessment.snapshot['sources']['Infrastructure'] != [infrastructure.pk, infrastructure_verification.pk]
            or FactoryProgress.objects.filter(work=work).exists()
            or dossier.sources.filter(kind='hypercare_engineering').count() != 1):
        raise RuntimeError('Stop with one exact below-target assessment and no successor or background request.')
    return event(
        dossier.actor, case, MARKER, work=work.pk, dossier=dossier.pk, candidate=dossier.candidate_id,
        release=release.pk, released_at=release.data['released_at'], acceptance=acceptance.pk,
        receipt=acceptance.data['receipt_id'],
        operator=operator.pk, reader=reader.pk, criteria=criteria.pk, original=original.pk,
        assessment=assessment.pk, successor_proof=successor_proof.pk, successor_reference=successor_proof.source,
        infrastructure=infrastructure.pk, infrastructure_verifier=infrastructure_verification.actor_id,
    )


@transaction.atomic
def prepare(operator):
    if not operator.is_active or operator.is_staff or operator.is_superuser:
        raise RuntimeError('Use the active ordinary acceptance lead account.')
    case, made = Case.objects.get_or_create(pk=CASE_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying this identifier.')
    marker = create(operator, case) if made else Audit.objects.get(case=case, action=MARKER)
    if marker.data['operator'] != operator.pk:
        raise RuntimeError('Preserve the originally appointed account for this specimen.')
    work = FactoryWork.objects.get(case=case, actor=operator, definition=hypercare.DEFINITION, key=KEY, pk=marker.data['work'])
    dossier = delivery.dossier_for(case, marker.data['dossier'], current=False)
    if (dossier.candidate_id != marker.data['candidate'] or work.request['dossier'] != dossier.pk
            or not dossier.sources.filter(pk=marker.data['original'], kind='hypercare_engineering', actor=operator).exists()
            or not dossier.records.filter(pk=marker.data['assessment'], kind='hypercare', snapshot__qualified=False).exists()
            or not Evidence.objects.filter(case=case, pk=marker.data['successor_proof'], source=marker.data['successor_reference']).exists()):
        raise RuntimeError('Preserve the exact original pending assessment and separate proof.')
    filters = {'q': TITLE, 'line': hypercare.DEFINITION}
    home = reverse('home')
    return {**marker.data, 'case': str(CASE_ID), 'preserved': not made,
            'path': reverse('factory_detail', args=[work.pk]),
            'needs_attention': home + '?' + urlencode({'queue': 'needs_me', **filters}),
            'waiting_on_others': home + '?' + urlencode({'queue': 'waiting', **filters}),
            'verified': home + '?' + urlencode({'queue': 'verified', **filters})}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            base.PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and Hypercare lead queue fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    operator = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print(GUARD + '=' + json.dumps(prepare(operator)), flush=True)
