"""A distinct go-live report waiting for its scoped reviewer and actual PM witness."""

import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.models import Publication
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.policy import role_assignments
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_go_live as go_live
from apps.workflows.factory_progress import set_progress
from apps.workflows.models import FactoryWork, HumanTask
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_closure_walkthrough_seed import ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME, PREVIEW_PROJECT
from tests.signature_helpers import reaffirm_for
from tests.test_delivery import DeliveryFixture
from tests.test_factory_go_live import configure


TENANT = 'design-go-live-independent-signatures-walkthrough'
TITLE = 'SAMPLE go-live report with distinct review and signature witness'
KEY = 'SAMPLE-INDEPENDENT-GO-LIVE-SIGNATURES'
MARKER = 'sample.go_live_independent_signature_walkthrough_ready'
GUARD = 'PSL_GO_LIVE_SIGNATURE_WALKTHROUGH'
READ = ('case.read', 'factory.read', 'delivery.read')
REVIEWER = (*READ, 'document.review_controlled')
WITNESS = (*READ, 'delivery.manage', 'evidence.add')
PUBLISHER = ('case.read', 'delivery.read', 'factory.execute', 'document.publish')


def create_sample(case, witness, reviewer, identity):
    users = get_user_model().objects
    sponsor = users.create_user(username=f'sample-go-live-preparer-{case.pk.hex[:8]}')
    publisher = users.create_user(username=f'sample-go-live-publisher-{case.pk.hex[:8]}')
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action)
        for user, actions in ((sponsor, dict.fromkeys(ACTIONS)), (witness, WITNESS), (reviewer, REVIEWER), (publisher, PUBLISHER))
        for action in actions])
    sample = DeliveryFixture()
    sample.setup_delivery(context=(sponsor, case))
    proof = sample.evidence('policy_decision', 'Fictional appointments for a distinct review and actual PM sign-off witness.')
    standing = reference_values(active_component(role_assignments.COMPONENT, case))
    assignments = [*standing, {'role': 'PM', 'user_id': witness.pk}, {'role': 'PMO Lead', 'user_id': reviewer.pk}]
    configuration = role_assignments.draft(sponsor, case.pk, assignments, proof.pk, timezone.now())
    transition(sponsor, configuration.pk, 'validated')
    transition(sponsor, configuration.pk, 'active')
    reaffirm_for(sponsor, case)
    # Native evidence of a fictional earlier release. No provider is asked to deploy.
    release = sample.release()
    sample.publisher = publisher
    sample.inputs = {'template_id': sample.t.pk, **{
        key: sample.evidence(kind, f'Fictional {kind.replace("_", " ")} for this review sample.').pk
        for key, kind in go_live.KINDS.items()
    }}
    configure(sample)
    Grant.objects.filter(case=case, user=sponsor, action='document.review_controlled').update(active=False)
    work = go_live.start(sponsor, case.pk, KEY, sample.d.pk, sample.inputs, TITLE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    version = go_live.document(work)
    if (work.status != 'waiting' or not version or version.created_by_id != sponsor.pk or version.reviews.exists()
            or not HumanTask.objects.filter(case=case, version=version, status='open', required_role='PMO Lead').exists()
            or Publication.objects.filter(factory_work=work).exists()
            or sample.d.records.filter(kind__in=('go_live', 'go_live_reaffirmation')).exists()):
        raise RuntimeError('Stop with the exact report waiting for human review and no recorded delivery or sign-off.')
    progress = set_progress(sponsor, work.pk, work.revision, True)
    return event(sponsor, case, MARKER, work=work.pk, dossier=sample.d.pk, candidate=sample.candidate.pk,
                 release=release.pk, report=version.pk, publisher=publisher.pk, background=progress.pk,
                 witness=witness.pk, reviewer=reviewer.pk, **identity)


@transaction.atomic
def prepare(witness, reviewer, admission):
    if (admission.user_id != witness.pk or witness.pk == reviewer.pk or any(
            not user.is_active or user.is_staff or user.is_superuser for user in (witness, reviewer))):
        raise RuntimeError('Match the current admitted PM witness and separate ordinary report reviewer.')
    identity = {'invitation': admission.invitation_id, 'admission': admission.pk}
    case, created = Case.objects.get_or_create(
        pk=uuid5(NAMESPACE_URL, f'{TENANT}/{admission.pk}/{witness.pk}/{reviewer.pk}'),
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True},
    )
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The work must belong to the separate fictional go-live specimen.')
    marker = create_sample(case, witness, reviewer, identity) if created else Audit.objects.get(case=case, action=MARKER)
    expected = {**identity, 'witness': witness.pk, 'reviewer': reviewer.pk}
    if any(marker.data.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Preserve the report bound to its original roles and admission.')
    work = FactoryWork.objects.get(case=case, actor=marker.actor, definition=go_live.DEFINITION,
                                   key=KEY, pk=marker.data['work'])
    release = delivery.latest(delivery.dossier_for(case, marker.data['dossier'], current=False), 'release_outcome')
    if release.pk != marker.data['release']:
        raise RuntimeError('The specimen no longer has its original fictional release source.')
    return {**marker.data, 'case': str(case.pk), 'author': marker.actor_id, 'preserved': not created,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'response_path': reverse('factory_work_response', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
            'evidence_path': reverse('case', args=[case.pk]) + '#add-document'}


@transaction.atomic
def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(GUARD)) != (
            'design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and go-live signature fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    reviewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    admission, witness = admitted_user(*ADMITTED_IDENTITY, reviewer)
    if (admission.invitation.case_id, witness.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the current accepted synthetic invitation workspace and account.')
    if not Grant.objects.select_for_update().filter(
            case_id=ADMITTED_STAFF_CASE, user=witness, action='case.read', active=True).first():
        raise RuntimeError('The admitted PM must retain current access to the invitation workspace.')
    print(GUARD + '=' + json.dumps(prepare(witness, reviewer, admission)), flush=True)
