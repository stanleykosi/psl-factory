"""Prepare separate synthetic release facts and an unsubmitted escalation draft."""

import json
import os
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.controlled import register_template
from apps.documents.models import Publication
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery, escalations
from apps.pmo.issues import log_issue
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import register_reference, transition
from apps.workflows import factory, factory_escalation, factory_hypercare
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests.document_helpers import DEFINITION, artifact
from tests.helpers import activate, rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_closure_walkthrough_seed import ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME
from tests.test_delivery import DeliveryFixture


GUARD = 'PSL_RELEASE_ESCALATION_WALKTHROUGH'
TENANT = 'design-release-escalation-walkthrough'
TITLES = {
    'release': 'SAMPLE observed release with deployment environment',
    'release_file': 'SAMPLE observed release with private PDF deployment log',
    'escalation': 'SAMPLE escalation draft awaiting submission',
}
CASE_IDS = {name: uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}/{name}') for name in TITLES}
MARKER = 'sample.release_escalation_walkthrough_prepared'
RELEASE_REFERENCE = 'SAMPLE-PREVIEW-RELEASE-LOG-01'
ENVIRONMENT = 'Preview · Sample delivery workspace'
FILE_NAME = 'SAMPLE-PREVIEW-RELEASE-LOG-01.pdf'
START = ('case.read', 'factory.read', 'factory.start', 'evidence.add')


def grant(case, actor, actions):
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(actions)])


def prepare_release(case, operator, *, private_file=False):
    maker = get_user_model().objects.create_user(f'sample-release-environment-source-{case.pk.hex[:8]}')
    grant(case, maker, ACTIONS)
    grant(case, operator, (*START, 'delivery.read', 'delivery.release_record'))
    sample = DeliveryFixture()
    sample.setup_delivery(context=(maker, case))
    readiness = sample.ready()
    occurred = timezone.now().isoformat()
    proof = add_evidence(maker, case.pk, 'release_log',
        f'Fictional release of {sample.candidate.reference} in {ENVIRONMENT} at {occurred}. Reference {RELEASE_REFERENCE}.',
        'synthetic:release-environment-walkthrough-log')
    upload = None
    if private_file:
        from pypdf import PdfWriter
        from apps.agents.upload_views import upload_file
        buffer = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_metadata({'/Title': f'{RELEASE_REFERENCE} · {sample.candidate.reference} · {occurred}'})
        writer.write(buffer)
        upload = upload_file(operator, case, SimpleUploadedFile(FILE_NAME, buffer.getvalue(), content_type='application/pdf'))
    work = factory_hypercare.start(operator, case.pk, 'SAMPLE-RELEASE-ENVIRONMENT', sample.d.pk, case.title, rev(case))
    panel = factory_hypercare.projection(operator, work)
    if (not panel['can_record_release'] or proof.pk not in {row.pk for row in panel['decision_evidence']}
            or readiness.pk not in {row.pk for row in panel['readiness_records']}
            or sample.d.records.filter(kind='release_outcome').exists()):
        raise RuntimeError('Stop at the first release observation with its exact sample log and readiness.')
    return event(maker, case, MARKER, operator=operator.pk, work=work.pk, dossier=sample.d.pk,
        candidate=sample.candidate.pk, version=sample.candidate.reference, readiness=readiness.pk, evidence=proof.pk,
        evidence_version=proof.version, released_at=occurred, environment=ENVIRONMENT, reference=RELEASE_REFERENCE,
        note='Observed sample release as recorded in the selected release log.',
        **({'private_log': upload.pk, 'file_name': upload.name, 'file_sha256': upload.sha256} if upload else {})).data


def prepare_escalation(case, operator, reviewer, admission):
    users = get_user_model().objects
    head = users.create_user(f'sample-escalation-head-{case.pk.hex[:8]}')
    recipient = users.create_user(f'sample-escalation-inbox-{case.pk.hex[:8]}')
    grant(case, head, ACTIONS)
    grant(case, operator, (*START, 'issue.read', 'issue.escalate', 'agent.issues', 'factory.execute',
                           'document.draft', 'document.request_review'))
    grant(case, reviewer, ('case.read', 'factory.read', 'issue.read', 'document.review_controlled'))
    grant(case, recipient, ('document.receive:client',))
    owner = add_evidence(head, case.pk, 'policy_decision', 'Fictional roles and controls for this sample draft.',
                         'synthetic:escalation-draft-walkthrough-controls')
    source = add_evidence(head, case.pk, 'completion',
        'Fictional customer test data is late. The release depends on a confirmed delivery date.',
        'synthetic:escalation-draft-walkthrough-source')
    assignments = draft_roles(head, case.pk, [
        {'role': 'PM', 'user_id': head.pk}, {'role': 'Head of PMO', 'user_id': head.pk},
        {'role': 'PMO Lead', 'user_id': reviewer.pk},
    ], owner.pk, timezone.now())
    transition(head, assignments.pk, 'validated')
    transition(head, assignments.pk, 'active')
    template = register_template(head, case.pk, 'SAMPLE escalation communication', DEFINITION, owner.pk, rev(case))
    mailbox = register_reference(head, case.pk, 'client:sample-escalation-inbox', 'schema:psl/document-recipient/v1',
                                 {'audience': 'client', 'user_id': recipient.pk}, owner.pk)
    activate(head, case, 'D11.recipient_grant_refs', [mailbox.ref], owner)
    artifact(head, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
             {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, owner)
    settings = json.loads(Path('fixtures/factory-escalation.json').read_text())
    settings.pop('classification')
    settings.update(preparer_id=operator.pk, executor_id=head.pk)
    configuration = draft_operator_policy(head, case.pk, 'OPS.factory_escalation_execution', settings, owner.pk, timezone.now())
    transition(head, configuration.pk, 'validated')
    transition(head, configuration.pk, 'active')

    issue = log_issue(head, case.pk, 'SAMPLE-LATE-TEST-DATA', 'Customer test data is delayed', 'Delivery',
                      head.pk, 'Confirm the expected date.', source.pk, 'Fictional source for review.', rev(case), 'High')
    profile = escalations.capture_profile(head, case.pk, issue.issue_id, issue.pk, 'client_dependent', True,
                                          None, source.pk, 'Recorded impact of the sample delay.', rev(case))
    request = escalations.request_escalation(head, case.pk, profile.pk, 'escalate', 'Client', source.pk,
                                            'Ask the sample sponsor for a date.', rev(case))
    work = factory_escalation.start(operator, case.pk, 'SAMPLE-ESCALATION-SEND-FOR-REVIEW', request.pk,
                                    template.pk, case.title, rev(case))
    decision = factory_escalation.decide(head, work.pk, work.revision, rev(case), request.pk, 'Head of PMO',
                                         'approve', 'Synthetic decision to draft this exact message.')
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    version = factory_escalation.document(work)
    if (work.status != 'waiting' or not version or version.created_by_id != operator.pk
            or HumanTask.objects.filter(version=version).exists() or Publication.objects.filter(factory_work=work).exists()
            or not factory_escalation.projection(operator, work)['can_request_review']):
        raise RuntimeError('Stop with the exact draft waiting for a human to send it for review.')
    return event(head, case, MARKER, operator=operator.pk, reviewer=reviewer.pk, admission=admission.pk,
        invitation=admission.invitation_id, head=head.pk, work=work.pk, issue=issue.issue_id,
        profile=profile.pk, request=request.pk, decision=decision.pk, version=version.pk, template=template.pk,
        recipient=recipient.pk).data


@transaction.atomic
def prepare_case(operator, scenario, *, reviewer=None, admission=None):
    title = TITLES[scenario]
    case, created = Case.objects.get_or_create(pk=CASE_IDS[scenario], defaults={
        'tenant': TENANT, 'title': title, 'kind': 'project', 'synthetic': True,
    })
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, title, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying this sample identifier.')
    if not created:
        data = Audit.objects.get(case=case, action=MARKER).data
    elif scenario in ('release', 'release_file'):
        data = prepare_release(case, operator, private_file=scenario == 'release_file')
    else:
        data = prepare_escalation(case, operator, reviewer, admission)
    if data['operator'] != operator.pk:
        raise RuntimeError('Preserve the original sample operator.')
    definition = factory_escalation.DEFINITION if scenario == 'escalation' else factory_hypercare.DEFINITION
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=operator, definition=definition)
    if created and FactoryProgress.objects.filter(work=work).exists():
        raise RuntimeError('The sample must leave later progression to the browser.')
    if scenario != 'escalation':
        dossier = delivery.dossier_for(case, work.request['dossier'], current=False)
        if (dossier.pk, dossier.candidate_id) != (data['dossier'], data['candidate']):
            raise RuntimeError('Preserve the original release candidate and proof.')
    elif (data['reviewer'], data['admission'], data['invitation']) != (reviewer.pk, admission.pk, admission.invitation_id):
        raise RuntimeError('Preserve the escalation bound to its original reviewer and admission.')
    return {**data, 'case': str(case.pk), 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created}


@transaction.atomic
def prepare_admitted_escalation(operator):
    admission, reviewer = admitted_user(*ADMITTED_IDENTITY, operator)
    if (admission.invitation.case_id, reviewer.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the exact accepted synthetic invitation and reviewer.')
    if not Grant.objects.filter(case_id=ADMITTED_STAFF_CASE, user=reviewer, action='case.read', active=True).exists():
        raise RuntimeError('The admitted reviewer needs current access to the invitation workspace.')
    return prepare_case(operator, 'escalation', reviewer=reviewer, admission=admission)


def run(scenario='both'):
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and release/escalation sample guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    if scenario not in ('both', *TITLES):
        raise RuntimeError('Select one registered synthetic scenario or both.')
    operator = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    result = {}
    if scenario in ('both', 'release'):
        result['release'] = prepare_case(operator, 'release')
    if scenario == 'release_file':
        result['release_file'] = prepare_case(operator, 'release_file')
    if scenario in ('both', 'escalation'):
        result['escalation'] = prepare_admitted_escalation(operator)
    print(GUARD + '=' + json.dumps(result), flush=True)
