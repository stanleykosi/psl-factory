"""Prepare one independently reviewed synthetic client escalation for Return."""

import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.workflows import factory_escalation
from apps.workflows.models import FactoryWork, HumanTask
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_release_escalation_walkthrough_seed import PREVIEW_PROJECT, prepare_escalation
from tests.railway_rfp_submission_pack_seed import HOSTED_ADMISSION, HOSTED_ADMISSION_CASE, HOSTED_MAKER, TRIAL


GUARD = 'PSL_ESCALATION_REVIEW_RETURN_FIXTURE'
TENANT = 'design-escalation-review-return'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}/client-message')
TITLE = 'SAMPLE North Clinic escalation message review'
MARKER = 'sample.escalation_message_return_ready'
NOTE = 'Cite the original test-data request date and ask the sponsor to confirm a date.'


def populate(case, maker, trial, admission):
    prepared = prepare_escalation(case, maker, trial, admission)
    head = get_user_model().objects.get(pk=prepared['head'])
    proof = add_evidence(head, case.pk, 'policy_decision',
        'Fictional PMO Lead may return the exact client escalation draft for correction.',
        'synthetic:north-clinic-escalation-review-options')
    matrix = artifact(head, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                      {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, proof)
    Grant.objects.bulk_create(Grant(case=case, user=user, action='document.read') for user in (maker, trial))
    work = FactoryWork.objects.get(pk=prepared['work'], case=case, actor=maker, definition=factory_escalation.DEFINITION)
    version = factory_escalation.document(work)
    task = factory_escalation.request_communication_review(maker, work.pk, work.revision, rev(case), version.pk)
    work.refresh_from_db()
    if (task.created_by_id != maker.pk or task.required_role != 'PMO Lead' or version.created_by_id != maker.pk
            or version.pk != prepared['version'] or version.reviews.exists()
            or factory_escalation.projection(trial, work)['review_verdicts'] != ['approve', 'return']
            or factory_escalation.projection(maker, work)['review_verdicts']):
        raise RuntimeError('The exact client message must wait for the independent Trial reviewer.')
    return event(head, case, MARKER, maker=maker.pk, reviewer=trial.pk, invitation=admission.invitation_id,
        admission=admission.pk, work=work.pk, issue=prepared['issue'], request=prepared['request'],
        escalation_decision=prepared['decision'], version=version.pk, version_number=version.number,
        version_sha256=version.payload_sha256, task=task.pk, rules=matrix.pk).data


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, maker = admitted_user(invitation_id, user_id, trial)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or maker.username != HOSTED_MAKER):
        raise RuntimeError('Use the exact original accepted synthetic maker account.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Only the exact synthetic North Clinic sample may be prepared.')
    data = populate(case, maker, trial, admission) if created else Audit.objects.get(case=case, action=MARKER).data
    if (data['maker'], data['reviewer'], data['admission']) != (maker.pk, trial.pk, admission.pk):
        raise RuntimeError('Preserve the original admitted maker and separate Trial reviewer.')
    work = FactoryWork.objects.get(pk=data['work'], actor=maker, case=case, definition=factory_escalation.DEFINITION)
    task = HumanTask.objects.get(pk=data['task'], version_id=data['version'], case=case, created_by=maker)
    version = factory_escalation.document(work)
    if (not version or version.pk != data['version'] or version.payload_sha256 != data['version_sha256']
            or task.status not in ('open', 'returned') or Publication.objects.filter(version=version).exists()):
        raise RuntimeError('Preserve the current controlled review or its recorded Return.')
    return {**data, 'case': str(case.pk), 'work_path': reverse('factory_detail', args=[work.pk]),
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'readback_path': reverse('design_document_review', args=[case.pk, version.pk]),
            'note': NOTE, 'preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(GUARD)) != (
            'design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and escalation return guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicitly configured preview sample database.')
    print(GUARD + '=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
