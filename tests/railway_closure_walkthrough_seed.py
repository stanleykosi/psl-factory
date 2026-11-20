"""Guarded sample of the distinct quality, Head and PM closure stations."""

import json
import os
from functools import partial
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.role_assignments import COMPONENT, draft
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_closure
from apps.workflows.models import FactoryWork, HumanTask
from apps.workflows.services import run_once
from tests import test_delivery, test_factory_closure
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.signature_helpers import reaffirm_for


TENANT = 'design-distinct-closure-review-walkthrough'
TITLE = 'SAMPLE closure report with separate quality and Head decisions'
KEY = 'SAMPLE-DISTINCT-CLOSURE-REVIEW'
MARKER = 'sample.distinct_closure_prepared'
READ = ('case.read', 'delivery.read', 'factory.read')
HEAD_ACTIONS = (*READ, 'delivery.closure_decide')
QUALITY_ACTIONS = (*READ, 'document.review_controlled', 'evidence.add', 'factory.execute', 'factory.manage')
ADMITTED_GUARD = 'PSL_CLOSURE_ADMITTED_WALKTHROUGH_FIXTURE'
ADMITTED_IDENTITY = (7, 243)
ADMITTED_STAFF_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
ADMITTED_USERNAME = 'sample-correction-preparer-20261120'


def create_sample(case, quality, head, identity):
    sponsor = get_user_model().objects.create_user(
        username=f'sample-closure-report-builder-{case.pk.hex[:8]}', first_name='Sample closure report builder')
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action)
                               for user, actions in ((sponsor, dict.fromkeys(ACTIONS)),
                                                     (quality, QUALITY_ACTIONS), (head, HEAD_ACTIONS))
                               for action in actions])
    entry = test_delivery.DeliveryFixture()
    entry.setup_delivery(context=(sponsor, case))
    proof = entry.evidence('policy_decision', 'Fictional appointments for this isolated closure review sample.')
    roles = [row for row in reference_values(active_component(COMPONENT, case)) if row['role'] != 'Head of PMO']
    roles += [{'role': 'Head of PMO', 'user_id': head.pk}, {'role': 'PMO Lead', 'user_id': quality.pk}]
    assignments = draft(sponsor, case.pk, roles, proof.pk, timezone.now())
    transition(sponsor, assignments.pk, 'validated')
    transition(sponsor, assignments.pk, 'active')
    reaffirm_for(sponsor, case)
    artifact(sponsor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
             {'rules': [{'role': 'Head of PMO', 'actions': ['return']}]}, proof)

    # Reuse the native sample chain while keeping its Finance handoff claim on this case.
    with patch.object(test_delivery, 'run_once', partial(run_once, case_id=case.pk)):
        entry.closure_selected = entry.closing()
    entry = test_factory_closure.setup(base=entry, review=True, capture=False)
    correction = entry.evidence('closure_report', 'Revised fictional closure report with the corrected handover lesson.')
    # The seeded client report already has its exact receipt. The closure's pending
    # quality review belongs to the separately admitted operator.
    Grant.objects.filter(case=case, user=sponsor, action='document.review_controlled').update(active=False)
    work = factory_closure.start(sponsor, case.pk, KEY, entry.d.pk, entry.inputs, case.title, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    version = factory_closure.document(work)
    if (work.status != 'waiting' or not version or version.created_by_id != sponsor.pk or version.reviews.exists()
            or not HumanTask.objects.filter(case=case, version=version, status='open', required_role='PMO Lead').exists()
            or entry.d.records.filter(kind__in=('closure_decision', 'closure')).exists()):
        raise RuntimeError('The sample must stop at the first distinct controlled quality review.')
    return event(sponsor, case, MARKER, work=work.pk, dossier=entry.d.pk, report=version.pk,
                 quality=quality.pk, head=head.pk, inputs=entry.inputs, corrected_evidence=correction.pk,
                 decision_evidence=entry.e['requirements'].pk, **identity)


@transaction.atomic
def prepare(quality, head, *, admission=None):
    if len({quality.pk, head.pk}) != 2 or any(not user.is_active or user.is_staff or user.is_superuser
                                               for user in (quality, head)):
        raise RuntimeError('Current distinct ordinary sample operators are required.')
    partition = f'{TENANT}/{quality.pk}/{head.pk}'
    title, identity = TITLE, {}
    if admission is not None:
        if admission.user_id != quality.pk:
            raise RuntimeError('Match the quality reviewer to the accepted synthetic admission.')
        title = f'SAMPLE closure quality review for accepted invitation {admission.invitation_id}'
        partition += f'/admission/{admission.pk}'
        identity = {'invitation': admission.invitation_id, 'admission': admission.pk}
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, partition),
        defaults={'tenant': TENANT, 'kind': 'project', 'synthetic': True, 'title': title})
    if (case.tenant, case.kind, case.synthetic, case.title) != (TENANT, 'project', True, title):
        raise RuntimeError('The target is outside the guarded closure sample.')
    marker = create_sample(case, quality, head, identity) if created else Audit.objects.get(case=case, action=MARKER)
    if (marker.data['quality'], marker.data['head']) != (quality.pk, head.pk):
        raise RuntimeError('Use the original distinct closure sample operators.')
    if any(marker.data.get(key) != value for key, value in identity.items()):
        raise RuntimeError('Preserve the closure sample bound to its original admission.')
    work = FactoryWork.objects.get(case=case, actor=marker.actor, definition=factory_closure.DEFINITION, key=KEY,
                                   pk=marker.data['work'])
    return {**marker.data, 'case': str(case.pk), 'author': marker.actor_id, 'preserved': not created,
            'path': reverse('factory_detail', args=[work.pk]),
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk])}


@transaction.atomic
def run(invitation_id, user_id):
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_CLOSURE_WALKTHROUGH_FIXTURE')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and closure fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or (invitation_id, user_id) != (6, 123):
        raise RuntimeError('Use the explicitly admitted sample identity and isolated preview database.')
    head = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    _, quality = admitted_user(invitation_id, user_id, head)
    print('PSL_CLOSURE_WALKTHROUGH_FIXTURE=' + json.dumps(prepare(quality, head)), flush=True)


@transaction.atomic
def run_admitted():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(ADMITTED_GUARD)) != (
            'design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and admitted closure fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview database.')
    head = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    admission, quality = admitted_user(*ADMITTED_IDENTITY, head)
    if (admission.invitation.case_id, quality.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the exact synthetic invitation workspace and accepted account.')
    if not Grant.objects.select_for_update().filter(
            case_id=ADMITTED_STAFF_CASE, user=quality, action='case.read', active=True).first():
        raise RuntimeError('The admitted reviewer must retain current access to the invitation workspace.')
    print(ADMITTED_GUARD + '=' + json.dumps(prepare(quality, head, admission=admission)), flush=True)
