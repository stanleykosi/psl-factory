"""One guarded bid pack awaiting its first native maker edit."""

import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import commercial, rfp
from apps.pmo.models import RFPDocumentBinding, RFPResponse, RFPSubmission, RFPSubmissionPack
from apps.policy import role_assignments
from apps.policy.factory_rfp_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, decision_authority, reference_values, transition
from apps.workflows import factory, factory_rfp
from apps.workflows.models import FactoryWork
from tests.factory_rfp_helpers import costing_review
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_independent_commercial_seed import PROJECT
from tests.railway_rfp_admitted_return_seed import PREPARER_ACTIONS, TRIAL
from tests.test_rfp import fixture as rfp_sources


TENANT = 'design-admitted-bid-submission-pack'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE bid pack with independent final review'
REFERENCE = 'SAMPLE-ADMITTED-BID-SUBMISSION-PACK'
MARKER = 'sample.admitted_bid_submission_pack_ready'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_MAKER = 'sample-correction-preparer-20261120'
ROLE = 'PMO Lead'
MAKER_ACTIONS = PREPARER_ACTIONS | {
    'rfp.review', 'rfp.submit', 'commercial.decide', 'document.draft', 'document.request_review',
}
REVIEW_ACTIONS = {'case.read', 'factory.read', 'rfp.read', 'rfp.review', 'document.read', 'document.review_controlled'}
FILE_REQUIREMENT = 'SAMPLE client requests one PDF file, under 20,000,000 bytes. No submission deadline is stated.'
COVER_NOTE = 'Thank you for considering our fictional reconciliation proposal.'
RETURN_REASON = 'Name the exact reconciliation proposal and the separate exception summary in the cover note.'
REVISED_NOTE = 'Thank you for considering our fictional reconciliation proposal and separate exception summary.'
APPROVE_REASON = 'Reviewed the exact revised cover note, approved costing and stated PDF requirement.'


def prepared_bid(maker, reviewer, case):
    Grant.objects.bulk_create([
        *[Grant(case=case, user=maker, action=action) for action in sorted(MAKER_ACTIONS)],
        *[Grant(case=case, user=reviewer, action=action) for action in sorted(REVIEW_ACTIONS)],
    ])
    _, _, sources, template, route = rfp_sources(reference=REFERENCE, portal=True, record_intake=False,
                                                 context=(maker, case))
    proof = add_evidence(maker, case.pk, 'policy_decision',
        'SAMPLE decision retains the admitted user as the response preparer and appoints the separate trial '
        'user to the PMO Lead response and final document reviews for this fictional bid.',
        'synthetic:admitted-bid-pack-roles')
    current_roles = reference_values(active_component(role_assignments.COMPONENT, case))
    roles = [row for row in current_roles if row['role'] != ROLE] + [{'role': ROLE, 'user_id': reviewer.pk}]
    profile = role_assignments.draft(maker, case.pk, roles, proof.pk, timezone.now())
    transition(maker, profile.pk, 'validated')
    transition(maker, profile.pk, 'active')

    received = add_evidence(maker, case.pk, 'rfp_intake', FILE_REQUIREMENT, 'synthetic:admitted-bid-pack-received')
    intake = rfp.intake(maker, case.pk, REFERENCE, received.pk, timezone.now()-timedelta(hours=1),
                        'not_stated', None, None, 'The sample explicitly has no submission deadline.', rev(case))
    rfp.assign(maker, case.pk, maker, 'CEO', proof.pk, 'SAMPLE exact preparer assignment.', rev(case))
    for team, kind in rfp.TEAMS.items():
        rfp.contribute(maker, case.pk, team, sources[kind].pk, rev(case))

    execution = json.loads(Path('fixtures/factory-rfp.json').read_text())
    execution.pop('classification')
    execution.update(template_id=template.pk, route_key=route['key'])
    settings = draft_operator_policy(maker, case.pk, COMPONENT, execution, proof.pk, timezone.now())
    transition(maker, settings.pk, 'validated')
    transition(maker, settings.pk, 'active')
    payload = {'response_evidence': sources['rfp_response'].pk, 'public_terms': sources['rfp_commercial_terms'].pk,
               'sources': {key: sources[key].pk for key in ('requirements', 'plan', 'costing')},
               'matrix': [{'key': 'R1', 'evidence_id': sources['requirements'].pk, 'response': 'Cited coverage',
                           'disposition': 'addressed'}], 'lessons': sources['rfp_lessons'].pk}
    work = factory_rfp.start(maker, case.pk, REFERENCE, payload, REFERENCE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    response = factory_rfp.response_for(work)
    if response is None or response.actor_id != maker.pk:
        raise RuntimeError('The exact admitted actor must prepare the fictional source response.')
    rfp.review(maker, case.pk, response.pk, 'Engineering Lead', 'approve', proof.pk,
               'SAMPLE Engineering review of the cited response.', rev(case))
    rfp.review(reviewer, case.pk, response.pk, ROLE, 'approve', proof.pk,
               'SAMPLE PMO review of the same response. Final document review remains separate.', rev(case))
    costing_review({'actor': maker, 'case': case}, response)
    if (RFPSubmissionPack.objects.filter(response=response).exists()
            or RFPDocumentBinding.objects.filter(response=response).exists()):
        raise RuntimeError('Leave the cover note and controlled document to the native browser workflow.')
    return work, response, intake, proof, template


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    reviewer = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or maker.username != HOSTED_MAKER):
        raise RuntimeError('Use the exact previously accepted hosted preparer invitation and account.')
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'kind': 'project', 'title': TITLE, 'synthetic': True})
    if (case.tenant, case.kind, case.title, case.synthetic) != (TENANT, 'project', TITLE, True):
        raise RuntimeError('Preserve all other workspaces and cases.')
    identities = {'admission': admission.pk, 'invitation': invitation_id, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if created:
        work, response, intake, proof, template = prepared_bid(maker, reviewer, case)
        marker = event(maker, case, MARKER, **identities, work=work.pk, response=response.pk,
                       costing=response.commercial_id, intake=intake.pk, received=intake.evidence_id,
                       decision_proof=proof.pk, template=template.pk)
    else:
        marker = Audit.objects.get(case=case, action=MARKER, actor=maker)
        if any(marker.data.get(key) != val for key, val in identities.items()):
            raise RuntimeError('Preserve the original sample and its two exact actors.')
        work = FactoryWork.objects.get(pk=marker.data['work'], case=case, definition=factory_rfp.DEFINITION,
                                       key=REFERENCE, actor=maker)
        response = RFPResponse.objects.get(pk=marker.data['response'], rfp__case=case, actor=maker)
    for actor, actions in ((maker, MAKER_ACTIONS), (reviewer, REVIEW_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve the exact original case-local preparer and reviewer permissions.')
    decision_authority(reviewer, case, ROLE, 'return')
    rfp.reviewed(response)
    commercial.valid_approvals(response.commercial, ['PM', 'Head of PMO', 'CEO'])
    if RFPSubmission.objects.filter(response__rfp__case=case).exists() or Publication.objects.filter(
            version__document__case=case).exists():
        raise RuntimeError('No submission or publication is part of this draft and review sample.')
    document = factory_rfp.review_document(work)
    return {'case': str(case.pk), 'reference': REFERENCE, **marker.data, 'role': ROLE,
            'overview': reverse('factory_detail', args=[work.pk]),
            'decision': reverse('factory_invoice_decision', args=[work.pk]) + '#client-submission-pack',
            'cover_note': COVER_NOTE, 'return_reason': RETURN_REASON, 'revised_note': REVISED_NOTE,
            'approve_reason': APPROVE_REASON, 'file_extension': 'PDF', 'file_count': 1,
            'file_size_rule': 'less_than', 'file_size_bytes': 20_000_000,
            'current_controlled_version': document.pk if document else None, 'preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_RFP_SUBMISSION_PACK_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The explicit Railway design-acceptance bid pack fixture guard is required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_RFP_SUBMISSION_PACK_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
