"""A separate closure report poised for its first Head of PMO Return."""

import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.workflows import factory_closure
from apps.workflows.models import FactoryProgress, FactoryWork
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_closure_walkthrough_seed import (
    ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME, KEY, PREVIEW_PROJECT, create_sample,
)


TENANT = 'design-closure-return-and-correction-walkthrough'
TITLE = 'SAMPLE closure return for a corrected stability summary'
MARKER = 'sample.closure_return_walkthrough_prepared'
GUARD = 'PSL_RETURNED_CLOSURE_WALKTHROUGH'
RETURN_REASON = 'Add the sample client’s written sign-off on the release stability summary to this closure report.'


def create_return_sample(case, quality, head, identity):
    original = create_sample(case, quality, head, identity)
    work = FactoryWork.objects.get(case=case, pk=original.data['work'])
    report = factory_closure.document(work)
    dossier = delivery.dossier_for(case, original.data['dossier'])
    stability = delivery.latest(dossier, 'hypercare')
    signed_summary = add_evidence(
        original.actor, case.pk, 'project_artifact',
        f'The fictional client representative confirms the release stability summary for record {stability.pk}.',
        'synthetic:closure-return-stability-summary-signoff',
    )
    correction = add_evidence(
        original.actor, case.pk, 'closure_report',
        f'The fictional client’s written sign-off on the release stability summary for record {stability.pk} '
        f'is retained as evidence {signed_summary.pk}. The PM closure report includes that exact sign-off.',
        'synthetic:closure-return-report-successor',
    )
    setup_review = factory_closure.review(
        quality, work.pk, work.revision, rev(case), report.pk, 'approve',
        'Synthetic fixture setup. The original report passed document quality checks before the Head’s decision.',
    )
    if (setup_review.actor_id != quality.pk or FactoryProgress.objects.filter(work=work).exists()
            or dossier.records.filter(kind__in=('closure_decision', 'closure')).exists()):
        raise RuntimeError('Stop with the original Quality review recorded and no Head decision or closure.')
    return event(original.actor, case, MARKER, **(original.data | {
        'corrected_evidence': correction.pk, 'stability_record': stability.pk,
        'signed_summary_evidence': signed_summary.pk, 'setup_quality_review': setup_review.pk,
    }))


@transaction.atomic
def prepare(quality, head, admission):
    if (admission.user_id != quality.pk or quality.pk == head.pk or any(
            not user.is_active or user.is_staff or user.is_superuser for user in (quality, head))):
        raise RuntimeError('Match the current admitted Quality reviewer and distinct Head of PMO.')
    identity = {'invitation': admission.invitation_id, 'admission': admission.pk}
    case, created = Case.objects.get_or_create(
        pk=uuid5(NAMESPACE_URL, f'{TENANT}/{admission.pk}/{quality.pk}/{head.pk}'),
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True},
    )
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The work must belong to the separate fictional closure specimen.')
    marker = create_return_sample(case, quality, head, identity) if created else Audit.objects.get(case=case, action=MARKER)
    expected = {**identity, 'quality': quality.pk, 'head': head.pk}
    if any(marker.data.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Preserve the closure sample bound to its original admission and Head.')
    work = FactoryWork.objects.get(case=case, actor=marker.actor, definition=factory_closure.DEFINITION,
                                   key=KEY, pk=marker.data['work'])
    return {**marker.data, 'case': str(case.pk), 'author': marker.actor_id, 'preserved': not created,
            'return_reason': RETURN_REASON,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
            'checklist_path': reverse('closure_preparation', args=[case.pk, marker.data['dossier']])}


@transaction.atomic
def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(GUARD)) != (
            'design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and returned closure fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    head = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    admission, quality = admitted_user(*ADMITTED_IDENTITY, head)
    if (admission.invitation.case_id, quality.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the current accepted synthetic invitation workspace and account.')
    if not Grant.objects.select_for_update().filter(
            case_id=ADMITTED_STAFF_CASE, user=quality, action='case.read', active=True).first():
        raise RuntimeError('The admitted reviewer must retain current access to the invitation workspace.')
    print(GUARD + '=' + json.dumps(prepare(quality, head, admission)), flush=True)
