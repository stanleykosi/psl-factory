"""Prepare one fictional returned Planning decision and its independently reviewed client proof."""

import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.upload_views import upload_file
from apps.core import client_contacts
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import client_uat, delivery, delivery_workarounds, issues
from apps.pmo.gates import register_candidate
from apps.policy import role_assignments
from apps.policy.client_uat_validators import COMPONENT, SCHEMA_REF
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory_delivery
from apps.workflows.models import FactoryProgress, FactoryWork
from tests.document_helpers import artifact
from tests.helpers import prepared, rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_closure_walkthrough_seed import ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME
from tests.test_delivery import DeliveryFixture


TENANT = 'design-planning-client-workaround-walkthrough'
TITLE = 'SAMPLE returned Planning decision with written client workaround'
KEY = 'SAMPLE-RETURNED-PLANNING-WORKAROUND'
MARKER = 'sample.returned_planning_workaround_prepared'
GUARD = 'PSL_PLANNING_WORKAROUND_WALKTHROUGH'
WITNESS = ('case.read', 'factory.read', 'delivery.read', 'delivery.manage', 'engagement.read', 'issue.read',
           'issue.own', 'client_uat.record', 'client_uat.inspect', 'client_uat.proof.read', 'evidence.add')
LEAD = ('case.read', 'factory.read', 'delivery.read', 'delivery.planning_decide', 'engagement.read', 'issue.read')
CANDIDATE = 'SAMPLE-WORKAROUND-BUILD'
CONTACT = 'SAMPLE Client Witness'


def activate(config, actor):
    transition(actor, config.pk, 'validated')
    transition(actor, config.pk, 'active')


def create_sample(case, pm, lead, identity):
    sponsor = get_user_model().objects.create_user(username=f'sample-planning-setup-{case.pk.hex[:8]}')
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action)
                                for user, actions in ((sponsor, dict.fromkeys(ACTIONS)), (pm, WITNESS), (lead, LEAD))
                                for action in actions])
    entry = DeliveryFixture()
    entry.actor, entry.case = sponsor, case
    entry.e = prepared(sponsor, case)
    entry.candidate = register_candidate(sponsor, case.pk, CANDIDATE, entry.e['requirements'].pk, rev(case))
    entry.d = delivery.open_dossier(sponsor, case.pk, entry.candidate.pk, entry.e['plan'].pk,
                                    'Fictional delivery scope for the exact returned Planning walkthrough.', rev(case))
    for kind in delivery.PLANNING:
        entry.source(kind, {'requires_ui': False, 'client_signoff_required': False} if kind == 'ui_applicability' else {})
    issue_ref = f'SAMPLE-LOGIN-ISSUE-{case.pk.hex[:8].upper()}'
    issue = issues.log_issue(sponsor, case.pk, issue_ref, 'Login retry needs a workaround', 'Defect', pm.pk,
                             'Review the exact written client workaround for the retry.', entry.e['requirements'].pk,
                             'Fictional accepted walkthrough issue.', rev(case), severity='Medium')
    proof = add_evidence(sponsor, case.pk, 'policy_decision',
                         'Fictional appointments and rules for this isolated Planning workaround specimen.',
                         'synthetic:planning-workaround-owner-evidence')
    standing = reference_values(active_component(role_assignments.COMPONENT, case))
    assignments = [item for item in standing if item['role'] not in ('PM', 'PMO Lead')]
    assignments += [{'role': 'PM', 'user_id': pm.pk}, {'role': 'PMO Lead', 'user_id': lead.pk},
                    {'role': 'QA', 'user_id': sponsor.pk}]
    activate(role_assignments.draft(sponsor, case.pk, assignments, proof.pk, timezone.now()), sponsor)
    artifact(sponsor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
             {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, proof)
    artifact(sponsor, case, COMPONENT, SCHEMA_REF, {
        'format': 'psl.client-uat-rules/v1', 'human_only': True,
        'qualification_mode': 'reviewed_human_attestation_v1', 'reviewer_ids': [sponsor.pk],
        'reviewer_role': 'QA', 'independent_review': True, 'agent_review_required': False,
        'exact_mentions_required': True, 'proof_formats': ['txt'],
        'workaround_mode': 'explicit_client_approved_scope_v1',
        'assurance': 'human_witnessed_not_external_authentication', 'financial_controls': 'independent',
    }, proof)
    contact = client_contacts.save(sponsor, case, 'project', {
        'customer': '', 'client_name': 'SAMPLE Client', 'name': CONTACT, 'email': 'sample-client@example.invalid',
        'role': 'Fictional client reviewer', 'evidence': proof, 'revision': rev(case),
    })
    returned = delivery.decide_planning(lead, case.pk, entry.d.pk, 'return', entry.e['plan'].pk,
        'The login issue needs a fix or the client’s written acceptance of the exact workaround.', rev(case), issue_id=issue.issue_id)
    target = client_uat.record_target(pm, case.pk, entry.d.pk, contact.pk, timezone.now() - timedelta(minutes=1),
                                     None, None, False, uuid4(), rev(case))
    wording = f'For {issue_ref}, use the sample retry prompt until the login fix is verified.'
    text = f'{CONTACT} approved {CANDIDATE} with this exact workaround. {wording} Fictional preview evidence.'
    upload = upload_file(pm, case, SimpleUploadedFile('SAMPLE-client-planning-workaround.txt', text.encode()))
    response = client_uat.record_response(pm, case.pk, target.pk, timezone.now(), 'approved_with_workaround',
        True, 'Recorded this fictional written client response.', wording, None, [upload.pk], None, uuid4(), rev(case))
    inspection = client_uat.inspect_proof(pm, case.pk, response.pk, rev(case))
    review = client_uat.review_proof(sponsor, case.pk, response.pk, inspection.pk, 'confirm', True,
        'Independently checked the exact fictional client, candidate and written workaround.', uuid4(), rev(case))

    profile = json.loads(Path('fixtures/factory-delivery.json').read_text())
    profile.pop('classification')
    activate(draft_operator_policy(sponsor, case.pk, 'OPS.factory_delivery_execution', profile, proof.pk, timezone.now()), sponsor)
    work = factory_delivery.start(sponsor, case.pk, KEY, entry.d.pk, TITLE, rev(case))
    if (FactoryProgress.objects.filter(work=work).exists() or entry.candidate.gates.exists()
            or entry.d.sources.filter(kind=delivery_workarounds.KIND).exists()
            or entry.d.records.exclude(pk=returned.pk).exists()):
        raise RuntimeError('Stop at the verified client proof and its unlinked Planning return.')
    return event(sponsor, case, MARKER, work=work.pk, dossier=entry.d.pk, candidate=entry.candidate.pk,
                 issue=issue.issue_id, issue_state=issue.pk, issue_ref=issue_ref, returned=returned.pk,
                 target=target.pk, response=response.pk, review=review.pk, upload=upload.pk,
                 planning_evidence=entry.e['plan'].pk, **identity)


@transaction.atomic
def prepare(pm, lead, admission):
    if (admission.user_id != pm.pk or pm.pk == lead.pk or any(
            not user.is_active or user.is_staff or user.is_superuser for user in (pm, lead))):
        raise RuntimeError('Match the current distinct admitted PM and independent Planning reviewer.')
    identity = {'invitation': admission.invitation_id, 'admission': admission.pk, 'pm': pm.pk, 'lead': lead.pk}
    case, created = Case.objects.get_or_create(
        pk=uuid5(NAMESPACE_URL, f'{TENANT}/{admission.pk}/{pm.pk}/{lead.pk}'),
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True},
    )
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The work must belong to the separate fictional Planning specimen.')
    marker = create_sample(case, pm, lead, identity) if created else Audit.objects.get(case=case, action=MARKER)
    if any(marker.data.get(key) != value for key, value in identity.items()):
        raise RuntimeError('Preserve the specimen bound to the original separate participants.')
    work = FactoryWork.objects.get(pk=marker.data['work'], case=case, actor=marker.actor,
                                   key=KEY, definition=factory_delivery.DEFINITION)
    return {**marker.data, 'case': str(case.pk), 'preserved': not created,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'client_path': reverse('client_uat', args=[case.pk, marker.data['dossier']]),
            'issue_path': reverse('issues', args=[case.pk]) + f'#issue-{marker.data["issue"]}'}


@transaction.atomic
def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv(GUARD)) != (
            'design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('The exact Railway preview and Planning workaround fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    lead = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    admission, pm = admitted_user(*ADMITTED_IDENTITY, lead)
    if (admission.invitation.case_id, pm.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the current accepted synthetic invitation workspace and account.')
    if not Grant.objects.select_for_update().filter(
            case_id=ADMITTED_STAFF_CASE, user=pm, action='case.read', active=True).first():
        raise RuntimeError('The admitted PM must retain current access to the invitation workspace.')
    print(GUARD + '=' + json.dumps(prepare(pm, lead, admission)), flush=True)
