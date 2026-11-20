"""Leave a separate fictional accepted go-live awaiting an optional milestone mapping."""
import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.models import PublicationReceipt
from apps.finance.models import Handoff
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.pmo.models import Milestone
from apps.policy import role_assignments
from apps.policy.go_live_milestone_validators import COMPONENT
from apps.policy.models import Configuration
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_go_live as go_live
from apps.workflows.models import FactoryProgress, FactoryWork, Outbox
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_closure_walkthrough_seed import ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME, PREVIEW_PROJECT
from tests.railway_go_live_signature_walkthrough_seed import PUBLISHER, REVIEWER, WITNESS
from tests.signature_helpers import reaffirm_for
from tests.test_delivery import DeliveryFixture
from tests.test_factory_go_live import configure


TENANT = 'design-go-live-milestone-walkthrough'
TITLE = 'SAMPLE verified go-live awaiting milestone completion'
KEY = 'SAMPLE-VERIFIED-GO-LIVE-MILESTONE'
GUARD = 'PSL_GO_LIVE_MILESTONE_WALKTHROUGH'
MARKER = 'sample.go_live_milestone_walkthrough_ready'
MILESTONE_NAME = 'SAMPLE rollout milestone complete'
MAPPING_OPERATOR = (*REVIEWER, 'policy.read', 'policy.configure', 'policy.activate')
PROJECT_MANAGER = (*WITNESS, 'milestone.complete')


def create_sample(case, pm, operator, identity):
    users = get_user_model().objects
    sponsor = users.create_user(username=f'sample-milestone-sponsor-{case.pk.hex[:8]}')
    publisher = users.create_user(username=f'sample-milestone-publisher-{case.pk.hex[:8]}')
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for user, actions in (
        (sponsor, dict.fromkeys(ACTIONS)), (pm, PROJECT_MANAGER), (operator, MAPPING_OPERATOR),
        (publisher, PUBLISHER),
    ) for action in actions])
    sample = DeliveryFixture()
    sample.setup_delivery(context=(sponsor, case))
    standing = reference_values(active_component(role_assignments.COMPONENT, case))
    appointments = sample.evidence('policy_decision', 'Fictional distinct PM and review appointments for this specimen.')
    assignment = role_assignments.draft(sponsor, case.pk, [
        *standing, {'role': 'PM', 'user_id': pm.pk}, {'role': 'PMO Lead', 'user_id': operator.pk},
    ], appointments.pk, timezone.now())
    transition(sponsor, assignment.pk, 'validated')
    transition(sponsor, assignment.pk, 'active')
    reaffirm_for(sponsor, case)
    release = sample.release()
    sample.publisher = publisher
    configure(sample)
    Grant.objects.filter(
        case=case, user=sponsor, action__in=('document.review_controlled', 'milestone.complete'),
    ).update(active=False)
    inputs = {'template_id': sample.t.pk, **{
        key: sample.evidence(kind, f'Fictional {kind} source for the separate milestone specimen.').pk
        for key, kind in go_live.KINDS.items()
    }}
    work = go_live.start(sponsor, case.pk, KEY, sample.d.pk, inputs, TITLE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    version = go_live.document(work)
    go_live.review(operator, work.pk, work.revision, rev(case), version.pk, 'approve',
                   'Independent review of this exact fictional client report.')
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    receipt = PublicationReceipt.objects.get(publication__version=version, recipient=sponsor)
    pm_proof = sample.evidence('signature', 'Fictional PM signature for this separate sample report.')
    client_proof = sample.evidence('signature', 'Fictional client signature for this separate sample report.')
    acceptance = go_live.accept(
        pm, work.pk, work.revision, rev(case), version.pk, receipt.pk, pm_proof.pk, client_proof.pk,
        'Verified fictional PM and client source copies for this exact delivered sample report.',
        attestation=sample.attestation(receipt, pm_proof, client_proof, actor=pm),
    )
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    owner_decision = sample.evidence(
        'policy_decision', f'Fictional owner decision for dossier {sample.d.pk} on its exact signed baseline: '
                           f'the PM may confirm the named milestone “{MILESTONE_NAME}” with separate completion proof.',
    )
    proof = go_live.verify(work)
    if (work.status != 'verified' or proof['acceptance'] != acceptance.pk
            or proof['receipt_ids'] != [receipt.pk] or proof['document_version'] != version.pk
            or FactoryProgress.objects.filter(work=work).exists()
            or Configuration.objects.filter(case=case, component=COMPONENT).exists()
            or Milestone.objects.filter(case=case).exists() or Outbox.objects.filter(case=case).exists()
            or Handoff.objects.filter(case=case).exists()):
        raise RuntimeError('Stop after exact fictional go-live verification with the optional milestone still untouched.')
    return event(
        sponsor, case, MARKER, work=work.pk, dossier=sample.d.pk, candidate=sample.candidate.pk,
        release=release.pk, report=version.pk, receipt=receipt.pk, acceptance=acceptance.pk,
        publisher=publisher.pk, pm=pm.pk, operator=operator.pk, owner_decision=owner_decision.pk, **identity,
    )


@transaction.atomic
def prepare(pm, operator, admission):
    if admission.user_id != pm.pk or pm.pk == operator.pk or any(
            not user.is_active or user.is_staff or user.is_superuser for user in (pm, operator)):
        raise RuntimeError('Match one admitted PM and a distinct ordinary settings operator.')
    identity = {'invitation': admission.invitation_id, 'admission': admission.pk}
    case, created = Case.objects.get_or_create(
        pk=uuid5(NAMESPACE_URL, f'{TENANT}/{admission.pk}/{pm.pk}/{operator.pk}'),
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True},
    )
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Use the distinct synthetic go-live milestone specimen.')
    marker = create_sample(case, pm, operator, identity) if created else Audit.objects.get(case=case, action=MARKER)
    if any(marker.data.get(key) != value for key, value in {**identity, 'pm': pm.pk, 'operator': operator.pk}.items()):
        raise RuntimeError('Preserve the original specimen and its exact admission and role bindings.')
    work = FactoryWork.objects.get(
        case=case, actor=marker.actor, definition=go_live.DEFINITION, key=KEY, pk=marker.data['work'],
    )
    dossier = delivery.dossier_for(case, marker.data['dossier'], current=False)
    if (dossier.candidate_id != marker.data['candidate']
            or delivery.latest(dossier, 'release_outcome').pk != marker.data['release']
            or not dossier.records.filter(pk=marker.data['acceptance'], kind='go_live', actor=pm).exists()
            or not PublicationReceipt.objects.filter(
                pk=marker.data['receipt'], publication__version_id=marker.data['report'],
                publication__factory_work=work, recipient=marker.actor,
            ).exists()):
        raise RuntimeError('The sample no longer matches the recorded fictional go-live lineage.')
    return {**marker.data, 'case': str(case.pk), 'sponsor': marker.actor_id, 'preserved': not created,
            'milestone_name': MILESTONE_NAME, 'work_path': reverse('factory_detail', args=[work.pk]),
            'policy_path': reverse('policy', args=[case.pk]),
            'evidence_path': reverse('case', args=[case.pk]) + '#add-document'}


@transaction.atomic
def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(GUARD)) != (
            'design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and go-live milestone fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    operator = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    admission, pm = admitted_user(*ADMITTED_IDENTITY, operator)
    if (admission.invitation.case_id, pm.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the current accepted synthetic invitation workspace and account.')
    if not Grant.objects.select_for_update().filter(
            case_id=ADMITTED_STAFF_CASE, user=pm, action='case.read', active=True).first():
        raise RuntimeError('The admitted PM must retain current access to the invitation workspace.')
    print(GUARD + '=' + json.dumps(prepare(pm, operator, admission)), flush=True)
