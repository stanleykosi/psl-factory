"""Prepare one fictional weekly report for two separate human browser stations."""
import json
import os
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence, event
from apps.documents.controlled import register_template
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo.meetings import record_meeting
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import register_reference, transition
from apps.workflows import factory, factory_reporting as weekly
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests.document_helpers import artifact
from tests.helpers import activate, rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_closure_walkthrough_seed import ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME, PREVIEW_PROJECT


GUARD = 'PSL_WEEKLY_RETURN_WALKTHROUGH'
TENANT = 'design-weekly-return-walkthrough'
TITLE = 'SAMPLE weekly report requiring a cited correction'
TEMPLATE = 'SAMPLE reviewed weekly client template'
KEY = 'SAMPLE-WEEKLY-REVIEW-RETURN-CORRECTION'
MARKER = 'sample.weekly_report_return_walkthrough_prepared'
RETURN_REASON = 'Use the later sample risk update and cite its meeting record.'
CORRECTION_REASON = 'Replaced only the risk wording and its source with the later reviewed meeting record.'
INITIAL = {
    'status': 'The fictional team completed its scheduled integration checks.',
    'risks': 'The fictional performance follow-up is waiting for an owner update.',
    'timeline': 'The sample review milestone remains in its recorded window.',
    'next_steps': 'The sample team will check recorded findings at its next review.',
}
REVISED_RISK = 'The fictional performance owner confirmed the follow-up is underway.'
READ = ('case.read', 'factory.read', 'report.read', 'meeting.read')
MAKER = (*READ, 'factory.start', 'factory.execute', 'factory.manage', 'evidence.add',
         'report.draft', 'document.draft', 'document.request_review')
REVIEWER = (*READ, 'document.read', 'document.review_controlled')
PUBLISHER = (*READ, 'factory.execute', 'document.publish')
SPONSOR = ('case.read', 'meeting.read', 'meeting.record', 'meeting.participate', 'evidence.add',
           'policy.configure', 'policy.activate', 'document.template')


def _meeting_source(sponsor, case, topic, text, happened_at):
    source = add_evidence(sponsor, case.pk, 'meeting_notes', text, f'synthetic:weekly-{topic}')
    record_meeting(sponsor, case.pk, f'SAMPLE-WEEKLY-{topic.upper()}', 'status', happened_at,
                   f'Review the fictional {topic.replace("_", " ")} update', text, [sponsor.pk], [], source.pk, rev(case))
    return source


def create_sample(case, maker, reviewer, identity):
    users = get_user_model().objects
    sponsor = users.create_user(f'sample-weekly-sponsor-{case.pk.hex[:8]}')
    publisher = users.create_user(f'sample-weekly-publisher-{case.pk.hex[:8]}')
    inbox = users.create_user(f'sample-weekly-inbox-{case.pk.hex[:8]}', first_name='Sample weekly inbox')
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for user, actions in (
        (sponsor, SPONSOR), (maker, MAKER), (reviewer, REVIEWER), (publisher, PUBLISHER),
        (inbox, ('document.receive:client',)),
    ) for action in actions])
    proof = add_evidence(sponsor, case.pk, 'policy_decision',
                         'Fictional local reviewer, report template and synthetic inbox only.', 'synthetic:weekly-governance')
    assignment = draft_roles(sponsor, case.pk, [{'role': 'PMO Lead', 'user_id': reviewer.pk}], proof.pk, timezone.now())
    transition(sponsor, assignment.pk, 'validated')
    transition(sponsor, assignment.pk, 'active')
    artifact(sponsor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
             {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, proof)
    fields = ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']
    template = register_template(sponsor, case.pk, TEMPLATE, {
        'document_type': 'status_report', 'required_fields': fields, 'audience_fields': {'client': fields},
    }, proof.pk, rev(case))
    artifact(sponsor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
             {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, proof)
    recipient = register_reference(sponsor, case.pk, 'sample:weekly-local-inbox', 'schema:psl/document-recipient/v1',
                                   {'audience': 'client', 'user_id': inbox.pk}, proof.pk)
    activate(sponsor, case, 'D11.recipient_grant_refs', [recipient.ref], proof)
    profile = json.loads((settings.BASE_DIR / 'fixtures/factory-reporting.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    profile.update(preparer_id=maker.pk, executor_id=publisher.pk)
    config = draft_operator_policy(sponsor, case.pk, 'OPS.factory_reporting_execution', profile, proof.pk, timezone.now())
    transition(sponsor, config.pk, 'validated')
    transition(sponsor, config.pk, 'active')

    end = timezone.now().replace(microsecond=0)
    start = end - timedelta(days=7)
    sections = {key: {'text': text, 'evidence_ids': [
        _meeting_source(sponsor, case, key, text, end - timedelta(hours=2)).pk,
    ]} for key, text in INITIAL.items()}
    revised = _meeting_source(sponsor, case, 'revised-risk', REVISED_RISK, end - timedelta(hours=1))
    content = add_evidence(maker, case.pk, 'agent_private_report_content', json.dumps({
        'protocol': 'pmo-weekly-client-content/v1', 'sections': sections,
    }, sort_keys=True), 'synthetic:weekly-original-narrative')
    inputs = {'start_at': start.isoformat(), 'end_at': end.isoformat(), 'template_id': template.pk, 'content_id': content.pk}
    work = weekly.start(maker, case.pk, KEY, inputs, TITLE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    report = weekly.document(work)
    if (work.status != 'waiting' or not report or report.created_by_id != maker.pk or report.reviews.exists()
            or Publication.objects.filter(factory_work=work).exists() or FactoryProgress.objects.filter(work=work).exists()):
        raise RuntimeError('Leave exactly the first unreviewed report for its independent human reviewer.')
    review = HumanTask.objects.get(case=case, version=report, status='open', required_role='PMO Lead', claimed_by=None)
    return event(
        sponsor, case, MARKER, **identity, maker=maker.pk, reviewer=reviewer.pk, publisher=publisher.pk, inbox=inbox.pk,
        work=work.pk, first_report=report.pk, first_task=review.pk, template=template.pk, content=content.pk,
        start=inputs['start_at'], end=inputs['end_at'], original_sections=sections,
        revised_risks={'text': REVISED_RISK, 'evidence_ids': [revised.pk]},
    )


@transaction.atomic
def prepare(maker, reviewer, admission):
    if admission.user_id != maker.pk or maker.pk == reviewer.pk or any(
            not user.is_active or user.is_superuser or user.is_staff for user in (maker, reviewer)):
        raise RuntimeError('Match an admitted maker and separate ordinary PMO Lead.')
    identity = {'invitation': admission.invitation_id, 'admission': admission.pk}
    case, created = Case.objects.get_or_create(
        pk=uuid5(NAMESPACE_URL, f'{TENANT}/{admission.pk}/{maker.pk}/{reviewer.pk}'),
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True},
    )
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Use the separate fictional weekly report specimen.')
    marker = create_sample(case, maker, reviewer, identity) if created else Audit.objects.get(case=case, action=MARKER)
    if any(marker.data.get(key) != value for key, value in {**identity, 'maker': maker.pk, 'reviewer': reviewer.pk}.items()):
        raise RuntimeError('Preserve the original weekly report and its admitted roles.')
    work = FactoryWork.objects.get(case=case, actor=maker, definition=weekly.DEFINITION, key=KEY, pk=marker.data['work'])
    if not HumanTask.objects.filter(
            pk=marker.data['first_task'], case=case, version_id=marker.data['first_report'],
            version__created_by=maker, required_role='PMO Lead',
    ).exists() or not Evidence.objects.filter(case=case, pk=marker.data['revised_risks']['evidence_ids'][0]).exists():
        raise RuntimeError('Preserve the original review and separately recorded risk source.')
    path = reverse('factory_detail', args=[work.pk])
    return {**marker.data, 'case': str(case.pk), 'preserved': not created, 'path': path,
            'edit_path': path + '?edit=1#report-correction', 'return_reason': RETURN_REASON,
            'correction_reason': CORRECTION_REASON,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk])}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and weekly return fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    with transaction.atomic():
        reviewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
        admission, maker = admitted_user(*ADMITTED_IDENTITY, reviewer)
        if (admission.invitation.case_id, maker.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
            raise RuntimeError('Match the exact accepted synthetic invitation workspace and account.')
        if not Grant.objects.select_for_update(no_key=True).filter(
                case_id=ADMITTED_STAFF_CASE, user=maker, action='case.read', active=True).exists():
            raise RuntimeError('The admitted maker must retain current access to the invitation workspace.')
        result = prepare(maker, reviewer, admission)
    print(GUARD + '=' + json.dumps(result), flush=True)
